# =============================================================================
# app/services/dataset_validator.py — Dataset Integrity Validator
# =============================================================================
# PURPOSE:
#   Before wasting hours on training, this script does a full health-check
#   of the dataset.  It catches the mistakes that would silently produce
#   a garbage model:
#
#     1. Image-label pairing — every image has a label and vice-versa.
#     2. Corrupt images       — files that OpenCV can't decode.
#     3. Label format         — YOLO format: <class_id> <cx> <cy> <w> <h>
#     4. Class consistency    — no class IDs outside the range in data.yaml.
#     5. Annotation stats     — min/max boxes per image, total counts.
#
# WHY VALIDATE BEFORE TRAINING?
#   • A single corrupt image crashes training at epoch 30 (wasted GPU).
#   • An orphan label (no image) silently reduces mAP by shifting splits.
#   • A wrong class ID (e.g., 1 in a 1-class dataset) trains a phantom
#     class and makes the real class underperform.
#
# ARCHITECTURE DECISION:
#   Lives in `services/` because it's domain logic (ML data engineering),
#   not HTTP transport.  Can be called from CLI scripts or the API.
# =============================================================================

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported image extensions (YOLOv8-compatible)
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}


@dataclass
class ValidationReport:
    """
    Structured report returned by `validate_dataset()`.
    Every issue is stored here so callers can decide severity.
    """

    # ── Counts ───────────────────────────────────────────────────────────
    total_images: int = 0
    total_labels: int = 0
    total_annotations: int = 0

    # ── Per-split counts ─────────────────────────────────────────────────
    split_counts: dict = field(default_factory=dict)

    # ── Issues ───────────────────────────────────────────────────────────
    missing_labels: list[str] = field(default_factory=list)
    orphan_labels: list[str] = field(default_factory=list)
    corrupt_images: list[str] = field(default_factory=list)
    invalid_labels: list[str] = field(default_factory=list)
    out_of_range_classes: list[str] = field(default_factory=list)

    # ── Stats ────────────────────────────────────────────────────────────
    class_distribution: dict = field(default_factory=dict)
    min_boxes_per_image: int = 0
    max_boxes_per_image: int = 0
    avg_boxes_per_image: float = 0.0

    @property
    def is_healthy(self) -> bool:
        """True if no critical issues found."""
        return (
            len(self.missing_labels) == 0
            and len(self.orphan_labels) == 0
            and len(self.corrupt_images) == 0
            and len(self.invalid_labels) == 0
            and len(self.out_of_range_classes) == 0
        )


def validate_dataset(
    dataset_dir: str | Path,
    num_classes: int = 1,
    class_names: list[str] | None = None,
    check_images: bool = True,
) -> ValidationReport:
    """
    Run a comprehensive health check on a YOLO-format dataset.

    Parameters
    ----------
    dataset_dir : str | Path
        Root directory containing train/, valid/, test/ subdirectories.
    num_classes : int
        Expected number of classes (from data.yaml `nc` field).
    class_names : list[str] | None
        Class name list (for logging only).
    check_images : bool
        If True, attempt to decode every image with OpenCV.
        Set to False for a quick structural check.

    Returns
    -------
    ValidationReport
        A structured report with all findings.
    """
    dataset_dir = Path(dataset_dir)
    report = ValidationReport()
    class_names = class_names or [str(i) for i in range(num_classes)]

    logger.info("=" * 60)
    logger.info("  DATASET VALIDATION — %s", dataset_dir.name)
    logger.info("=" * 60)
    logger.info("Expected classes: %d → %s", num_classes, class_names)

    all_box_counts: list[int] = []

    # ── Iterate over each split ──────────────────────────────────────────
    for split in ["train", "valid", "test"]:
        img_dir = dataset_dir / split / "images"
        lbl_dir = dataset_dir / split / "labels"

        if not img_dir.exists():
            logger.warning("Split '%s' missing images/ directory.", split)
            continue

        # Collect stems (filename without extension)
        img_files = {f.stem: f for f in img_dir.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS}
        lbl_files = {f.stem: f for f in lbl_dir.iterdir() if f.suffix == ".txt"} if lbl_dir.exists() else {}

        split_images = len(img_files)
        split_labels = len(lbl_files)
        report.total_images += split_images
        report.total_labels += split_labels
        report.split_counts[split] = {"images": split_images, "labels": split_labels}

        logger.info("[%s]  images=%d  labels=%d", split.upper(), split_images, split_labels)

        # ── Check image↔label pairing ────────────────────────────────────
        for stem in img_files:
            if stem not in lbl_files:
                report.missing_labels.append(f"{split}/images/{img_files[stem].name}")

        for stem in lbl_files:
            if stem not in img_files:
                report.orphan_labels.append(f"{split}/labels/{lbl_files[stem].name}")

        # ── Check image integrity (optional, slow) ───────────────────────
        if check_images:
            for stem, img_path in img_files.items():
                img = cv2.imread(str(img_path))
                if img is None:
                    report.corrupt_images.append(f"{split}/images/{img_path.name}")

        # ── Validate labels ──────────────────────────────────────────────
        for stem, lbl_path in lbl_files.items():
            try:
                with open(lbl_path, "r") as f:
                    lines = f.readlines()
            except Exception as exc:
                report.invalid_labels.append(f"{split}/labels/{lbl_path.name}: {exc}")
                continue

            box_count = 0
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue  # Skip blank lines

                parts = line.split()

                # YOLO format: <class_id> <cx> <cy> <w> <h>  (5 values)
                if len(parts) != 5:
                    report.invalid_labels.append(
                        f"{split}/labels/{lbl_path.name}:L{line_num} "
                        f"expected 5 values, got {len(parts)}"
                    )
                    continue

                try:
                    cls_id = int(parts[0])
                    cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                except ValueError:
                    report.invalid_labels.append(
                        f"{split}/labels/{lbl_path.name}:L{line_num} "
                        f"non-numeric values: {line}"
                    )
                    continue

                # Class ID range check
                if cls_id < 0 or cls_id >= num_classes:
                    report.out_of_range_classes.append(
                        f"{split}/labels/{lbl_path.name}:L{line_num} "
                        f"class_id={cls_id} (expected 0..{num_classes - 1})"
                    )

                # Coordinate range check (YOLO normalized: 0–1)
                for val_name, val in [("cx", cx), ("cy", cy), ("w", w), ("h", h)]:
                    if val < 0.0 or val > 1.0:
                        report.invalid_labels.append(
                            f"{split}/labels/{lbl_path.name}:L{line_num} "
                            f"{val_name}={val} outside [0, 1]"
                        )

                # Track class distribution
                cls_name = class_names[cls_id] if cls_id < len(class_names) else f"unknown-{cls_id}"
                report.class_distribution[cls_name] = report.class_distribution.get(cls_name, 0) + 1
                report.total_annotations += 1
                box_count += 1

            all_box_counts.append(box_count)

    # ── Aggregate stats ──────────────────────────────────────────────────
    if all_box_counts:
        report.min_boxes_per_image = min(all_box_counts)
        report.max_boxes_per_image = max(all_box_counts)
        report.avg_boxes_per_image = round(sum(all_box_counts) / len(all_box_counts), 2)

    # ── Log summary ──────────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("-" * 60)
    logger.info("Total images:       %d", report.total_images)
    logger.info("Total labels:       %d", report.total_labels)
    logger.info("Total annotations:  %d", report.total_annotations)
    logger.info("Class distribution: %s", report.class_distribution)
    logger.info("Boxes/image:        min=%d  max=%d  avg=%.2f",
                report.min_boxes_per_image, report.max_boxes_per_image, report.avg_boxes_per_image)
    logger.info("Missing labels:     %d", len(report.missing_labels))
    logger.info("Orphan labels:      %d", len(report.orphan_labels))
    logger.info("Corrupt images:     %d", len(report.corrupt_images))
    logger.info("Invalid labels:     %d", len(report.invalid_labels))
    logger.info("Out-of-range classes: %d", len(report.out_of_range_classes))
    logger.info("-" * 60)

    if report.is_healthy:
        logger.info("✅ Dataset is HEALTHY — ready for training.")
    else:
        logger.warning("⚠️  Dataset has issues — review the report before training.")

    return report
