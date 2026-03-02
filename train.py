# =============================================================================
# train.py — CLI Entry Point for Training Pipeline
# =============================================================================
# PURPOSE:
#   Single command to run the entire ML pipeline:
#     python train.py
#
#   This script:
#     1. Sets up logging.
#     2. Optionally runs dataset validation only (--validate-only).
#     3. Runs training with configurable parameters.
#     4. Runs post-training evaluation on the test set.
#     5. Prints a final summary.
#
# USAGE:
#   python train.py                          # Full pipeline (train + eval)
#   python train.py --validate-only          # Only validate dataset
#   python train.py --epochs 100 --batch 8   # Custom hyperparameters
#   python train.py --model yolov8s.pt       # Use larger model variant
#   python train.py --no-export              # Skip ONNX export
#
# WHY A SEPARATE SCRIPT?
#   Training is a long-running batch job, NOT an API operation.
#   It should run in a terminal, not behind an HTTP endpoint.
#   The service layer does the work; this script is just a CLI wrapper.
# =============================================================================

import argparse
import logging
import sys
from pathlib import Path

# ── Ensure project root is on the Python path ───────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.logging_config import setup_logging
from app.services.dataset_validator import validate_dataset
from app.services.training_service import TrainingConfig, train
from app.services.evaluation_service import evaluate


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments with sensible defaults."""
    parser = argparse.ArgumentParser(
        description="ANPR System — YOLOv8 Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train.py                          Full pipeline (train + evaluate)
  python train.py --validate-only          Validate dataset only
  python train.py --epochs 100 --batch 8   Custom hyperparameters
  python train.py --model yolov8s.pt       Use Small variant for better accuracy
  python train.py --no-export              Skip ONNX export
        """,
    )

    # Mode
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the dataset, do not train.",
    )

    # Model
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n.pt",
        help="YOLOv8 variant: yolov8n.pt (nano), yolov8s.pt (small), yolov8m.pt (medium).",
    )

    # Dataset
    parser.add_argument(
        "--data",
        type=str,
        default=str(PROJECT_ROOT / "dataset" / "data.yaml"),
        help="Path to data.yaml.",
    )

    # Hyperparameters
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs (default: 50).")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (default: 16).")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size (default: 640).")
    parser.add_argument("--patience", type=int, default=15, help="Early stopping patience (default: 15).")
    parser.add_argument("--lr0", type=float, default=0.01, help="Initial learning rate (default: 0.01).")

    # Device
    parser.add_argument(
        "--device",
        type=str,
        default="",
        help="Device: '' (auto), '0' (GPU 0), 'cpu'. Default: auto-detect.",
    )

    # Export
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip ONNX export after training.",
    )

    # Evaluation
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Skip post-training evaluation on the test set.",
    )

    return parser.parse_args()


def main():
    """Main entry point for the training pipeline."""

    # ── Setup ────────────────────────────────────────────────────────────
    setup_logging()
    logger = logging.getLogger("train")
    args = parse_args()

    logger.info("=" * 70)
    logger.info("  🚀  ANPR SYSTEM — TRAINING PIPELINE")
    logger.info("=" * 70)

    # ── Resolve dataset path ─────────────────────────────────────────────
    data_yaml = Path(args.data)
    if not data_yaml.exists():
        logger.error("data.yaml not found at: %s", data_yaml)
        sys.exit(1)

    # Resolve dataset root from data.yaml
    import yaml
    with open(data_yaml, "r") as f:
        data_cfg = yaml.safe_load(f)

    yaml_dir = data_yaml.resolve().parent
    dataset_path = (yaml_dir / data_cfg.get("path", ".")).resolve()

    # ── Validate-only mode ───────────────────────────────────────────────
    if args.validate_only:
        logger.info("Running dataset validation ONLY (--validate-only)")
        report = validate_dataset(
            dataset_dir=dataset_path,
            num_classes=data_cfg.get("nc", 1),
            class_names=list(data_cfg.get("names", {}).values()) if isinstance(data_cfg.get("names"), dict) else data_cfg.get("names", []),
            check_images=True,  # Full check including corrupt image detection
        )
        if report.is_healthy:
            logger.info("✅ Dataset passed all checks!")
            sys.exit(0)
        else:
            logger.error("❌ Dataset has issues. See report above.")
            sys.exit(1)

    # ── Build training config ────────────────────────────────────────────
    config = TrainingConfig(
        model_variant=args.model,
        data_yaml=str(data_yaml),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        patience=args.patience,
        lr0=args.lr0,
        device=args.device,
        export_onnx=not args.no_export,
    )

    logger.info("Training Configuration:")
    logger.info("  Model:     %s", config.model_variant)
    logger.info("  Data:      %s", config.data_yaml)
    logger.info("  Epochs:    %d", config.epochs)
    logger.info("  Batch:     %d", config.batch)
    logger.info("  ImgSz:     %d", config.imgsz)
    logger.info("  Patience:  %d", config.patience)
    logger.info("  LR0:       %f", config.lr0)
    logger.info("  Device:    %s", config.device or "auto")
    logger.info("  ONNX:      %s", "yes" if config.export_onnx else "no")

    # ── Run training ─────────────────────────────────────────────────────
    logger.info("")
    logger.info("Starting training pipeline...")
    result = train(config)

    if not result.success:
        logger.error("❌ Training FAILED: %s", result.message)
        sys.exit(1)

    logger.info("")
    logger.info("✅ Training completed successfully!")
    logger.info("   %s", result.message)

    # ── Post-training evaluation on test set ─────────────────────────────
    if not args.skip_eval and result.best_model_path:
        logger.info("")
        logger.info("=" * 70)
        logger.info("  RUNNING POST-TRAINING EVALUATION ON TEST SET")
        logger.info("=" * 70)

        eval_result = evaluate(
            model_path=result.best_model_path,
            data_yaml=str(data_yaml),
            split="test",
            imgsz=config.imgsz,
            device=config.device,
        )

        if eval_result.success:
            logger.info("✅ Test evaluation complete!")
        else:
            logger.warning("⚠️  Test evaluation failed: %s", eval_result.message)

    # ── Final Summary ────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 70)
    logger.info("  📊  FINAL SUMMARY")
    logger.info("=" * 70)
    logger.info("  Training Time:  %.2f minutes", result.training_time_minutes)
    logger.info("  Epochs Run:     %d / %d", result.total_epochs_run, config.epochs)
    logger.info("  Device:         %s", result.device_used)
    logger.info("")
    logger.info("  ┌─────────────────────────────────────────┐")
    logger.info("  │  METRIC          │  VALUE               │")
    logger.info("  ├─────────────────────────────────────────┤")
    logger.info("  │  Precision       │  %.4f               │", result.precision)
    logger.info("  │  Recall          │  %.4f               │", result.recall)
    logger.info("  │  mAP@50          │  %.4f               │", result.mAP50)
    logger.info("  │  mAP@50-95       │  %.4f               │", result.mAP50_95)
    logger.info("  └─────────────────────────────────────────┘")
    logger.info("")
    logger.info("  Output Files:")
    logger.info("    best.pt (deploy):  %s", result.best_model_path)
    logger.info("    last.pt (resume):  %s", result.last_model_path)
    if result.onnx_model_path:
        logger.info("    ONNX:              %s", result.onnx_model_path)
    logger.info("    Metrics JSON:      %s", result.metrics_path)
    logger.info("")
    logger.info("  Next Steps:")
    logger.info("    1. Restart the backend: uvicorn app.main:app --reload")
    logger.info("    2. The backend will auto-load models/best.pt")
    logger.info("    3. Test: POST /detect with an image")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
