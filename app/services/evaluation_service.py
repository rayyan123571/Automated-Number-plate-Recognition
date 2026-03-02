# =============================================================================
# app/services/evaluation_service.py — Post-Training Model Evaluation
# =============================================================================
# PURPOSE:
#   Standalone evaluation service that can:
#     1. Evaluate a trained model on ANY split (train/val/test).
#     2. Extract per-class and aggregate metrics.
#     3. Generate a structured JSON evaluation report.
#     4. Run independently of training (e.g., evaluate a downloaded model).
#
# WHEN TO USE:
#   • After training → evaluate on the held-out TEST set.
#   • When comparing two models → evaluate both on the same test set.
#   • In CI/CD → gate deployment on minimum mAP threshold.
#
# METRICS EXPLAINED:
# ─────────────────────────────────────────────────────────────────────────
#   Precision  : Of all detections, what % were correct?
#                High precision = few false positives.
#
#   Recall     : Of all actual plates, what % did we find?
#                High recall = few missed plates.
#
#   mAP@50     : Mean Average Precision at IoU threshold 0.50.
#                The most common detection metric.
#                "Does the box overlap ≥50% with ground truth?"
#
#   mAP@50-95  : Average of mAP at IoU thresholds 0.50, 0.55, ..., 0.95.
#                A stricter metric — rewards tight, precise boxes.
#                This is the COCO standard and the gold metric.
#
#   F1 Score   : Harmonic mean of Precision and Recall.
#                Best single number for overall detection quality.
# =============================================================================

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ultralytics import YOLO

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRICS_DIR = PROJECT_ROOT / "metrics"


@dataclass
class EvaluationResult:
    """Structured evaluation output."""

    success: bool
    message: str
    model_path: str = ""
    data_yaml: str = ""
    split: str = ""
    # Aggregate metrics
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    mAP50: float = 0.0
    mAP50_95: float = 0.0
    # Per-class metrics (for multi-class models)
    per_class_metrics: dict = None
    # Metadata
    num_images: int = 0
    inference_speed_ms: float = 0.0


def evaluate(
    model_path: str | Path,
    data_yaml: str | Path,
    split: str = "test",
    imgsz: int = 640,
    conf: float = 0.25,
    device: str = "",
    save_report: bool = True,
) -> EvaluationResult:
    """
    Evaluate a YOLOv8 model on a specific dataset split.

    Parameters
    ----------
    model_path : str | Path
        Path to the .pt weights file.
    data_yaml : str | Path
        Path to the data.yaml config file.
    split : str
        Dataset split to evaluate on: 'train', 'val', or 'test'.
    imgsz : int
        Image size for evaluation.
    conf : float
        Confidence threshold for detections.
    device : str
        '' = auto, '0' = GPU, 'cpu' = CPU.
    save_report : bool
        Save evaluation report to metrics/ directory.

    Returns
    -------
    EvaluationResult
        Structured evaluation results.
    """
    model_path = Path(model_path)
    data_yaml = Path(data_yaml)

    logger.info("=" * 60)
    logger.info("  MODEL EVALUATION")
    logger.info("=" * 60)
    logger.info("Model:   %s", model_path)
    logger.info("Data:    %s", data_yaml)
    logger.info("Split:   %s", split)
    logger.info("ImgSz:   %d", imgsz)
    logger.info("Conf:    %.2f", conf)
    logger.info("=" * 60)

    # ── Validate inputs ──────────────────────────────────────────────────
    if not model_path.exists():
        return EvaluationResult(
            success=False,
            message=f"Model not found: {model_path}",
        )

    if not data_yaml.exists():
        return EvaluationResult(
            success=False,
            message=f"data.yaml not found: {data_yaml}",
        )

    # ── Load model ───────────────────────────────────────────────────────
    try:
        model = YOLO(str(model_path))
    except Exception as exc:
        return EvaluationResult(
            success=False,
            message=f"Failed to load model: {exc}",
        )

    # ── Run validation ───────────────────────────────────────────────────
    try:
        metrics = model.val(
            data=str(data_yaml),
            split=split,
            imgsz=imgsz,
            conf=conf,
            device=device or ("0" if __import__("torch").cuda.is_available() else "cpu"),
            verbose=True,
            plots=True,  # Generate PR curves, confusion matrix
        )
    except Exception as exc:
        logger.exception("Evaluation failed.")
        return EvaluationResult(
            success=False,
            message=f"Evaluation error: {exc}",
        )

    # ── Extract metrics ──────────────────────────────────────────────────
    try:
        precision = round(float(metrics.box.mp), 4)    # Mean precision
        recall = round(float(metrics.box.mr), 4)       # Mean recall
        mAP50 = round(float(metrics.box.map50), 4)     # mAP at IoU=0.50
        mAP50_95 = round(float(metrics.box.map), 4)    # mAP at IoU=0.50-0.95

        # F1 Score = 2 × (P × R) / (P + R)
        f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

        # Per-class metrics
        per_class = {}
        if hasattr(metrics.box, "maps") and hasattr(model, "names"):
            for cls_id, cls_name in model.names.items():
                if cls_id < len(metrics.box.maps):
                    per_class[cls_name] = {
                        "mAP50_95": round(float(metrics.box.maps[cls_id]), 4),
                    }

        # Speed metrics
        speed = getattr(metrics, "speed", {})
        inference_ms = speed.get("inference", 0) if isinstance(speed, dict) else 0

    except Exception as exc:
        logger.warning("Failed to extract some metrics: %s", exc)
        precision = recall = f1 = mAP50 = mAP50_95 = 0.0
        per_class = {}
        inference_ms = 0

    # ── Log results ──────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  EVALUATION RESULTS (%s set)", split.upper())
    logger.info("=" * 60)
    logger.info("  Precision:      %.4f", precision)
    logger.info("  Recall:         %.4f", recall)
    logger.info("  F1 Score:       %.4f", f1)
    logger.info("  mAP@50:         %.4f", mAP50)
    logger.info("  mAP@50-95:      %.4f", mAP50_95)
    if inference_ms:
        logger.info("  Inference:      %.1f ms/image", inference_ms)
    logger.info("=" * 60)

    # ── Interpret results ────────────────────────────────────────────────
    if mAP50 >= 0.9:
        logger.info("🏆 EXCELLENT — Model is production-ready!")
    elif mAP50 >= 0.8:
        logger.info("✅ GOOD — Model is usable. Consider more data or yolov8s for improvement.")
    elif mAP50 >= 0.6:
        logger.info("⚠️  MODERATE — May need more data, augmentation, or a larger model variant.")
    else:
        logger.info("❌ LOW — Check dataset quality, try yolov8m, or increase epochs.")

    result = EvaluationResult(
        success=True,
        message=f"Evaluation on {split} set: mAP@50={mAP50:.4f}, F1={f1:.4f}",
        model_path=str(model_path),
        data_yaml=str(data_yaml),
        split=split,
        precision=precision,
        recall=recall,
        f1_score=f1,
        mAP50=mAP50,
        mAP50_95=mAP50_95,
        per_class_metrics=per_class,
        inference_speed_ms=inference_ms,
    )

    # ── Save report ──────────────────────────────────────────────────────
    if save_report:
        METRICS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = METRICS_DIR / f"eval_{split}_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(asdict(result), f, indent=2, default=str)
        logger.info("Evaluation report saved to: %s", report_file)

    return result
