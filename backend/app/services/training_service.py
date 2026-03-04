# =============================================================================
# app/services/training_service.py — YOLOv8 Training Pipeline
# =============================================================================
# PURPOSE:
#   Production-grade training service that handles the entire lifecycle:
#     1. Environment detection (GPU vs CPU).
#     2. Dataset validation (calls dataset_validator).
#     3. Model initialization (YOLOv8n pretrained on COCO).
#     4. Training with configurable hyperparameters.
#     5. Checkpoint management (best.pt & last.pt).
#     6. Post-training evaluation on the test set.
#     7. Metrics export to JSON.
#     8. Model export to ONNX for deployment.
#
# WHY YOLOv8n (Nano)?
#   ┌──────────┬──────────┬─────────┬─────────────────────────────────────┐
#   │ Variant  │  Params  │  Speed  │  When to use                        │
#   ├──────────┼──────────┼─────────┼─────────────────────────────────────┤
#   │ YOLOv8n  │  3.2 M   │  ~2 ms  │  Edge/mobile, real-time, MVP ✓     │
#   │ YOLOv8s  │  11.2 M  │  ~4 ms  │  Balanced speed + accuracy          │
#   │ YOLOv8m  │  25.9 M  │  ~8 ms  │  When accuracy matters more         │
#   │ YOLOv8l  │  43.7 M  │  ~12 ms │  High-accuracy server-side          │
#   │ YOLOv8x  │  68.2 M  │  ~18 ms │  Maximum accuracy, unlimited GPU    │
#   └──────────┴──────────┴─────────┴─────────────────────────────────────┘
#   For ANPR (1 class, clear object), YOLOv8n gives excellent mAP with
#   real-time inference.  If accuracy is low, upgrade to YOLOv8s/m.
#
# SPEED vs ACCURACY TRADEOFF:
#   • More parameters → higher mAP but slower inference & more VRAM.
#   • For number plates (typically 1–5 plates per image, clear shapes),
#     Nano is usually sufficient.  Medium/Large help when plates are tiny,
#     occluded, or the camera angle is extreme.
#
# ARCHITECTURE DECISION:
#   This is a service, not a route.  It can be invoked from:
#     • A CLI script (train.py)
#     • A background task (Celery/ARQ)
#     • An admin API endpoint (future /admin/train)
#   The service returns structured results, never prints to stdout.
# =============================================================================

import json
import logging
import platform
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import torch
from ultralytics import YOLO

from app.services.dataset_validator import validate_dataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"
RUNS_DIR = PROJECT_ROOT / "runs"
METRICS_DIR = PROJECT_ROOT / "metrics"


# ═══════════════════════════════════════════════════════════════════════════
# Data class for training configuration
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class TrainingConfig:
    """
    All hyperparameters in one place.

    WHY A DATACLASS?
    • Type-safe, IDE-friendly.
    • Easy to serialize to JSON for experiment tracking.
    • Can be loaded from a YAML/JSON config file in the future.
    """

    # ── Model ────────────────────────────────────────────────────────────
    model_variant: str = "yolov8n.pt"
    """
    Pretrained checkpoint to initialize from.
    'yolov8n.pt' = COCO-pretrained Nano (downloaded automatically).
    Use 'yolov8s.pt', 'yolov8m.pt' for larger variants.
    """

    # ── Dataset ──────────────────────────────────────────────────────────
    data_yaml: str = str(PROJECT_ROOT / "dataset" / "data.yaml")
    """Path to the data.yaml config file."""

    # ── Training hyperparameters ─────────────────────────────────────────
    epochs: int = 50
    """Total training epochs. 50 is a good starting point for fine-tuning."""

    imgsz: int = 640
    """
    Input image size (pixels).  640 is the YOLOv8 default.
    Higher (1280) improves small-object detection but uses 4× VRAM.
    """

    batch: int = 16
    """
    Batch size.  16 is safe for 6–8 GB VRAM.
    Reduce to 8 if you get CUDA OOM.  Increase to 32 on 24 GB+ GPUs.
    """

    # ── Optimizer & Scheduling ───────────────────────────────────────────
    optimizer: str = "auto"
    """'auto' lets YOLOv8 choose (SGD for training, AdamW for fine-tune)."""

    lr0: float = 0.01
    """Initial learning rate."""

    lrf: float = 0.01
    """Final learning rate (fraction of lr0) — cosine annealing target."""

    # ── Augmentation ─────────────────────────────────────────────────────
    augment: bool = True
    """Enable YOLOv8's built-in augmentation pipeline (mosaic, mixup, etc.)."""

    # ── Regularization ───────────────────────────────────────────────────
    patience: int = 15
    """
    Early stopping patience (epochs).
    If val mAP doesn't improve for this many epochs, stop early.
    Prevents overfitting and saves GPU time.
    """

    # ── Output ───────────────────────────────────────────────────────────
    project: str = str(RUNS_DIR)
    """Parent directory for training run outputs."""

    name: str = "anpr_train"
    """Subdirectory name for this training run."""

    exist_ok: bool = True
    """If True, overwrite existing run directory instead of creating v2/v3."""

    # ── System ───────────────────────────────────────────────────────────
    workers: int = 4
    """DataLoader worker threads for CPU data loading."""

    device: str = ""
    """
    '' = auto-detect (GPU if available, else CPU).
    '0' = first GPU.  'cpu' = force CPU.
    """

    # ── Checkpointing ────────────────────────────────────────────────────
    save: bool = True
    """Save checkpoints."""

    save_period: int = -1
    """Save checkpoint every N epochs. -1 = only best & last."""

    # ── Export ────────────────────────────────────────────────────────────
    export_onnx: bool = True
    """Export best model to ONNX after training."""


# ═══════════════════════════════════════════════════════════════════════════
# Data class for training results
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class TrainingResult:
    """Structured output of a training run."""

    success: bool
    message: str
    # Paths
    best_model_path: str = ""
    last_model_path: str = ""
    onnx_model_path: str = ""
    metrics_path: str = ""
    # Performance
    training_time_minutes: float = 0.0
    # Metrics
    precision: float = 0.0
    recall: float = 0.0
    mAP50: float = 0.0
    mAP50_95: float = 0.0
    # System
    device_used: str = ""
    total_epochs_run: int = 0


# ═══════════════════════════════════════════════════════════════════════════
# Environment detection
# ═══════════════════════════════════════════════════════════════════════════
def detect_environment() -> dict:
    """
    Detect and log the training environment.

    Returns a dict with system info so it can be stored with metrics
    for reproducibility.
    """
    env = {
        "os": platform.system(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "cpu": platform.processor(),
    }

    logger.info("=" * 60)
    logger.info("  TRAINING ENVIRONMENT")
    logger.info("=" * 60)
    logger.info("OS:           %s", env["os"])
    logger.info("Python:       %s", env["python"])
    logger.info("PyTorch:      %s", env["torch"])

    if env["cuda_available"]:
        logger.info("CUDA:         %s", env["cuda_version"])
        logger.info("GPU:          %s", env["gpu_name"])
        logger.info("GPU Count:    %d", env["gpu_count"])
        logger.info("🚀 Training will use GPU — expect fast training!")
    else:
        logger.info("GPU:          Not available")
        logger.info("⚠️  Training will use CPU — this will be slow.")
        logger.info("    For faster training, install CUDA toolkit + torch-cu*")

    logger.info("=" * 60)
    return env


# ═══════════════════════════════════════════════════════════════════════════
# Main training function
# ═══════════════════════════════════════════════════════════════════════════
def train(config: TrainingConfig | None = None) -> TrainingResult:
    """
    Execute the complete YOLOv8 training pipeline.

    Steps:
        1. Detect environment (GPU / CPU).
        2. Validate dataset integrity.
        3. Initialize YOLOv8 model (pretrained on COCO).
        4. Train on the ANPR dataset.
        5. Extract and save metrics.
        6. Copy best weights to models/ for backend use.
        7. Export to ONNX (optional).

    Parameters
    ----------
    config : TrainingConfig | None
        Training configuration. Uses defaults if None.

    Returns
    -------
    TrainingResult
        Structured result with paths, metrics, and status.
    """
    if config is None:
        config = TrainingConfig()

    start_time = time.time()

    # ── Step 1: Environment detection ────────────────────────────────────
    env_info = detect_environment()

    # Resolve device
    if not config.device:
        config.device = "0" if torch.cuda.is_available() else "cpu"
    logger.info("Using device: %s", config.device)

    # ── Step 2: Validate dataset ─────────────────────────────────────────
    logger.info("Validating dataset before training...")
    dataset_dir = Path(config.data_yaml).parent / ".." / "Automatic Plate Number Recognition.v4i.yolov8"

    # Resolve the actual dataset directory from data.yaml
    # The data.yaml `path` field points to the dataset root
    import yaml
    with open(config.data_yaml, "r") as f:
        data_cfg = yaml.safe_load(f)

    # Resolve dataset path relative to data.yaml location
    yaml_dir = Path(config.data_yaml).resolve().parent
    dataset_path = (yaml_dir / data_cfg.get("path", ".")).resolve()

    report = validate_dataset(
        dataset_dir=dataset_path,
        num_classes=data_cfg.get("nc", 1),
        class_names=list(data_cfg.get("names", {}).values()) if isinstance(data_cfg.get("names"), dict) else data_cfg.get("names", []),
        check_images=False,  # Skip image decoding for speed; set True for first-time validation
    )

    if not report.is_healthy:
        logger.error("Dataset validation FAILED. Fix issues before training.")
        return TrainingResult(
            success=False,
            message=f"Dataset has {len(report.missing_labels)} missing labels, "
                    f"{len(report.corrupt_images)} corrupt images, "
                    f"{len(report.invalid_labels)} invalid labels.",
            device_used=config.device,
        )

    logger.info("Dataset validated: %d images, %d annotations", report.total_images, report.total_annotations)

    # ── Step 3: Initialize model ─────────────────────────────────────────
    logger.info("Initializing YOLOv8 model: %s", config.model_variant)
    logger.info(
        "WHY %s?  Small model (3.2M params), fast inference (~2ms/image), "
        "excellent for single-class detection like ANPR. "
        "Upgrade to yolov8s.pt or yolov8m.pt if mAP < 0.85.",
        config.model_variant,
    )

    model = YOLO(config.model_variant)

    # ── Step 4: Train ────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  STARTING TRAINING")
    logger.info("=" * 60)
    logger.info("  Epochs:     %d", config.epochs)
    logger.info("  Image Size: %d", config.imgsz)
    logger.info("  Batch Size: %d", config.batch)
    logger.info("  Patience:   %d (early stopping)", config.patience)
    logger.info("  Data:       %s", config.data_yaml)
    logger.info("  Output:     %s/%s", config.project, config.name)
    logger.info("=" * 60)

    try:
        results = model.train(
            data=config.data_yaml,
            epochs=config.epochs,
            imgsz=config.imgsz,
            batch=config.batch,
            device=config.device,
            optimizer=config.optimizer,
            lr0=config.lr0,
            lrf=config.lrf,
            patience=config.patience,
            project=config.project,
            name=config.name,
            exist_ok=config.exist_ok,
            save=config.save,
            save_period=config.save_period,
            workers=config.workers,
            verbose=True,
            pretrained=True,   # Use COCO pretrained weights for transfer learning
            plots=True,        # Generate confusion matrix, PR curve, etc.
        )
    except Exception as exc:
        logger.exception("Training FAILED with error.")
        elapsed = (time.time() - start_time) / 60
        return TrainingResult(
            success=False,
            message=f"Training crashed: {exc}",
            device_used=config.device,
            training_time_minutes=round(elapsed, 2),
        )

    elapsed = (time.time() - start_time) / 60
    logger.info("Training completed in %.2f minutes.", elapsed)

    # ── Step 5: Extract metrics ──────────────────────────────────────────
    train_dir = Path(config.project) / config.name
    metrics = _extract_metrics(results, train_dir)

    logger.info("=" * 60)
    logger.info("  TRAINING METRICS")
    logger.info("=" * 60)
    logger.info("  Precision:    %.4f", metrics["precision"])
    logger.info("  Recall:       %.4f", metrics["recall"])
    logger.info("  mAP@50:       %.4f", metrics["mAP50"])
    logger.info("  mAP@50-95:    %.4f", metrics["mAP50_95"])
    logger.info("  Total Epochs: %d", metrics.get("epochs_completed", config.epochs))
    logger.info("=" * 60)

    # ── Step 6: Save metrics to JSON ─────────────────────────────────────
    METRICS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    metrics_file = METRICS_DIR / f"metrics_{timestamp}.json"

    metrics_export = {
        "timestamp": timestamp,
        "config": {
            "model_variant": config.model_variant,
            "epochs": config.epochs,
            "imgsz": config.imgsz,
            "batch": config.batch,
            "patience": config.patience,
            "lr0": config.lr0,
            "lrf": config.lrf,
        },
        "metrics": metrics,
        "dataset": {
            "total_images": report.total_images,
            "total_annotations": report.total_annotations,
            "class_distribution": report.class_distribution,
            "splits": report.split_counts,
        },
        "environment": env_info,
        "training_time_minutes": round(elapsed, 2),
    }

    with open(metrics_file, "w") as f:
        json.dump(metrics_export, f, indent=2, default=str)
    logger.info("Metrics saved to: %s", metrics_file)

    # ── Step 7: Copy best.pt to models/ for backend ──────────────────────
    best_pt = train_dir / "weights" / "best.pt"
    last_pt = train_dir / "weights" / "last.pt"

    MODELS_DIR.mkdir(exist_ok=True)
    production_best = MODELS_DIR / "best.pt"
    production_last = MODELS_DIR / "last.pt"

    if best_pt.exists():
        shutil.copy2(best_pt, production_best)
        logger.info("✅ best.pt copied to %s", production_best)
        logger.info(
            "   WHAT IS best.pt?  The checkpoint with the highest validation "
            "mAP@50 across all epochs.  This is what you deploy."
        )
    else:
        logger.warning("best.pt not found at %s", best_pt)

    if last_pt.exists():
        shutil.copy2(last_pt, production_last)
        logger.info("✅ last.pt copied to %s", production_last)
        logger.info(
            "   WHAT IS last.pt?  The checkpoint from the final epoch. "
            "Useful for resuming training, but NOT recommended for deployment "
            "because it may be overfit if early stopping didn't trigger."
        )
    else:
        logger.warning("last.pt not found at %s", last_pt)

    # ── Step 8: Export to ONNX ───────────────────────────────────────────
    onnx_path = ""
    if config.export_onnx and best_pt.exists():
        onnx_path = _export_to_onnx(best_pt, config.imgsz)

    # ── Build result ─────────────────────────────────────────────────────
    return TrainingResult(
        success=True,
        message=f"Training completed in {elapsed:.2f} minutes. "
                f"mAP@50={metrics['mAP50']:.4f}, mAP@50-95={metrics['mAP50_95']:.4f}",
        best_model_path=str(production_best),
        last_model_path=str(production_last),
        onnx_model_path=onnx_path,
        metrics_path=str(metrics_file),
        training_time_minutes=round(elapsed, 2),
        precision=metrics["precision"],
        recall=metrics["recall"],
        mAP50=metrics["mAP50"],
        mAP50_95=metrics["mAP50_95"],
        device_used=config.device,
        total_epochs_run=metrics.get("epochs_completed", config.epochs),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Private helpers
# ═══════════════════════════════════════════════════════════════════════════

def _extract_metrics(results, train_dir: Path) -> dict:
    """
    Extract key metrics from Ultralytics training results.

    Tries multiple approaches because the Ultralytics API varies
    slightly between versions.
    """
    metrics = {
        "precision": 0.0,
        "recall": 0.0,
        "mAP50": 0.0,
        "mAP50_95": 0.0,
        "epochs_completed": 0,
    }

    try:
        # Approach 1: Direct from results object
        if hasattr(results, "results_dict"):
            rd = results.results_dict
            metrics["precision"] = round(float(rd.get("metrics/precision(B)", 0)), 4)
            metrics["recall"] = round(float(rd.get("metrics/recall(B)", 0)), 4)
            metrics["mAP50"] = round(float(rd.get("metrics/mAP50(B)", 0)), 4)
            metrics["mAP50_95"] = round(float(rd.get("metrics/mAP50-95(B)", 0)), 4)
            logger.info("Metrics extracted from results.results_dict")
        else:
            logger.warning("results_dict not available, trying CSV fallback.")
    except Exception as exc:
        logger.warning("Failed to extract metrics from results object: %s", exc)

    # Approach 2: Parse results.csv if metrics are still zero
    csv_path = train_dir / "results.csv"
    if metrics["mAP50"] == 0.0 and csv_path.exists():
        try:
            import csv
            with open(csv_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if rows:
                last_row = rows[-1]
                # Column names have leading spaces in Ultralytics CSV
                metrics["precision"] = round(float(last_row.get("metrics/precision(B)", "").strip() or 0), 4)
                metrics["recall"] = round(float(last_row.get("metrics/recall(B)", "").strip() or 0), 4)
                metrics["mAP50"] = round(float(last_row.get("metrics/mAP50(B)", "").strip() or 0), 4)
                metrics["mAP50_95"] = round(float(last_row.get("metrics/mAP50-95(B)", "").strip() or 0), 4)
                metrics["epochs_completed"] = len(rows)
                logger.info("Metrics extracted from results.csv (epoch %d)", len(rows))
        except Exception as exc:
            logger.warning("Failed to parse results.csv: %s", exc)

    return metrics


def _export_to_onnx(model_path: Path, imgsz: int = 640) -> str:
    """
    Export a YOLOv8 model to ONNX format.

    WHY ONNX?
    ─────────
    • **Portable** — runs on any platform (Linux, Windows, ARM, edge).
    • **Fast inference** — ONNX Runtime is 2–3× faster than PyTorch for
      inference on CPU (and competitive on GPU).
    • **Framework-agnostic** — deploy with ONNX Runtime, TensorRT,
      OpenVINO, CoreML, or any ONNX-compatible runtime.
    • **No Python needed** — ONNX models can run in C++, C#, Java, Rust.
    • **Smaller footprint** — no PyTorch dependency in production.

    Parameters
    ----------
    model_path : Path
        Path to the .pt weights file.
    imgsz : int
        Image size the model was trained with.

    Returns
    -------
    str
        Path to the exported ONNX file, or empty string on failure.
    """
    logger.info("Exporting model to ONNX format...")
    logger.info(
        "WHY ONNX?  Portable, 2-3× faster inference on CPU via ONNX Runtime, "
        "no PyTorch dependency in production, works in C++/Java/Rust."
    )

    try:
        model = YOLO(str(model_path))
        export_path = model.export(
            format="onnx",
            imgsz=imgsz,
            simplify=True,   # Optimize graph with onnx-simplifier
            dynamic=False,   # Fixed input shape for max speed
            opset=12,        # ONNX opset 12 has wide runtime support
        )

        # Copy ONNX to models/ directory
        onnx_source = Path(export_path)
        onnx_dest = MODELS_DIR / "best.onnx"
        if onnx_source.exists():
            shutil.copy2(onnx_source, onnx_dest)
            logger.info("✅ ONNX model exported to: %s", onnx_dest)
            logger.info("   File size: %.2f MB", onnx_dest.stat().st_size / (1024 * 1024))
            return str(onnx_dest)

    except Exception as exc:
        logger.error("ONNX export failed: %s", exc)
        logger.info("   This is non-critical — .pt model still works for inference.")

    return ""
