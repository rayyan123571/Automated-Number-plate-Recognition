# =============================================================================
# app/services/anpr_service.py — Full ANPR Pipeline Orchestrator
# =============================================================================
# PURPOSE:
#   Orchestrates the complete Automatic Number Plate Recognition pipeline:
#     1. YOLOv8 DETECTION  → finds bounding boxes for all plates in image.
#     2. PLATE CROPPING     → extracts each plate region from the image.
#     3. PREPROCESSING      → enhances the crop for optimal OCR accuracy.
#     4. OCR (EasyOCR)      → reads the text from the plate image.
#     5. TEXT CLEANING       → normalizes OCR output (uppercase, A-Z0-9 only).
#     6. RESPONSE ASSEMBLY  → bundles everything into a structured result.
#
# WHY AN ORCHESTRATOR SERVICE?
# ─────────────────────────────────────────────────────────────────────────
#   Each component (detector, preprocessor, OCR) is a standalone unit that
#   can be tested and swapped independently.  The orchestrator:
#     • Sequences the components in the correct order.
#     • Tracks timing for each stage (detection_ms, ocr_ms, total_ms).
#     • Handles per-plate failures gracefully (if OCR fails on one plate,
#       the other plates still return results).
#     • Provides a single function for the route to call — the route
#       never needs to know about internal AI pipeline details.
#
# DATA FLOW:
#   ┌─────────┐    ┌───────────┐    ┌──────────────┐    ┌─────────┐
#   │  Image  │ →  │ Detector  │ →  │ Preprocessor │ →  │   OCR   │
#   │ (BGR)   │    │ (YOLOv8)  │    │ (OpenCV)     │    │(EasyOCR)│
#   └─────────┘    └───────────┘    └──────────────┘    └─────────┘
#        ↓               ↓                ↓                  ↓
#    raw image       bboxes +         clean binary       plate text
#                   confidence         plate image       + confidence
#                                                             ↓
#                                                      ┌───────────┐
#                                                      │  Cleaned  │
#                                                      │ Plate No. │
#                                                      └───────────┘
#
# ARCHITECTURE DECISION:
#   This service sits one level above detector.py and ocr_service.py.
#   It composes them — it does NOT duplicate their logic.
#   Routes call anpr_service.recognize() and get a complete result.
# =============================================================================

import logging
import time

import numpy as np

from app.services import detector
from app.services import ocr_service
from app.utils.plate_preprocessor import crop_plate_from_image, preprocess_plate

logger = logging.getLogger(__name__)


def recognize(image: np.ndarray) -> dict:
    """
    Run the full ANPR pipeline on a single image.

    Parameters
    ----------
    image : np.ndarray
        BGR image as a NumPy array (from OpenCV / image upload).

    Returns
    -------
    dict
        {
            "success": bool,
            "plates": [
                {
                    "plate_text": str,         # Final cleaned plate number
                    "ocr_raw_text": str,       # Raw OCR output before cleaning
                    "detection_confidence": float,  # YOLO bbox confidence
                    "ocr_confidence": float,   # EasyOCR average confidence
                    "combined_confidence": float,   # detection × OCR confidence
                    "bbox": {x_min, y_min, x_max, y_max},
                    "class_name": str,
                    "class_id": int,
                },
                ...
            ],
            "num_plates": int,
            "timing": {
                "detection_ms": float,
                "ocr_ms": float,         # Total OCR time for all plates
                "total_ms": float,
            },
            "image_width": int,
            "image_height": int,
        }
    """
    total_start = time.perf_counter()
    img_h, img_w = image.shape[:2]

    # ─────────────────────────────────────────────────────────────────────
    # Stage 1: DETECTION — find all plates in the image
    # ─────────────────────────────────────────────────────────────────────
    detection_start = time.perf_counter()
    try:
        raw_detections = detector.detect(image)
    except RuntimeError as exc:
        logger.error("Detection stage failed: %s", exc)
        return _build_error_result(str(exc), img_w, img_h, total_start)

    detection_ms = (time.perf_counter() - detection_start) * 1000

    if not raw_detections:
        logger.info("No plates detected in image (%d×%d).", img_w, img_h)
        elapsed = (time.perf_counter() - total_start) * 1000
        return {
            "success": True,
            "plates": [],
            "num_plates": 0,
            "timing": {
                "detection_ms": round(detection_ms, 1),
                "ocr_ms": 0.0,
                "total_ms": round(elapsed, 1),
            },
            "image_width": img_w,
            "image_height": img_h,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Stage 2–4: CROP → PREPROCESS → OCR  (per plate)
    # ─────────────────────────────────────────────────────────────────────
    ocr_start = time.perf_counter()
    plates = []

    for i, det in enumerate(raw_detections):
        plate_result = _process_single_plate(image, det, plate_index=i)
        plates.append(plate_result)

    ocr_ms = (time.perf_counter() - ocr_start) * 1000
    total_ms = (time.perf_counter() - total_start) * 1000

    # ── Log summary ──────────────────────────────────────────────────────
    recognized_count = sum(1 for p in plates if p["plate_text"])
    logger.info(
        "ANPR complete  |  detected=%d  |  recognized=%d  |  "
        "detection=%.1f ms  |  ocr=%.1f ms  |  total=%.1f ms",
        len(plates),
        recognized_count,
        detection_ms,
        ocr_ms,
        total_ms,
    )

    return {
        "success": True,
        "plates": plates,
        "num_plates": len(plates),
        "timing": {
            "detection_ms": round(detection_ms, 1),
            "ocr_ms": round(ocr_ms, 1),
            "total_ms": round(total_ms, 1),
        },
        "image_width": img_w,
        "image_height": img_h,
    }


def _process_single_plate(
    image: np.ndarray,
    detection: dict,
    plate_index: int,
) -> dict:
    """
    Process a single detected plate: crop → preprocess → OCR → clean.

    Tries 6 preprocessed variants (binary, binary_otsu, binary_inv,
    enhanced, sharp, gray) and picks the result with the longest
    cleaned text, breaking ties by highest confidence.
    """
    bbox = detection["bbox"]
    det_confidence = detection["confidence"]
    class_id = detection["class_id"]
    class_name = detection["class_name"]

    # ── Stage 2: Crop plate from image ───────────────────────────────────
    try:
        plate_crop = crop_plate_from_image(image, bbox, padding_pct=0.12)
    except Exception as exc:
        logger.warning("Plate %d: crop failed — %s", plate_index, exc)
        return _build_plate_result(
            bbox=bbox,
            det_confidence=det_confidence,
            class_id=class_id,
            class_name=class_name,
        )

    # ── Stage 3: Preprocess plate for OCR ────────────────────────────────
    try:
        preprocessed = preprocess_plate(plate_crop, debug=True, plate_index=plate_index)
    except ValueError as exc:
        logger.warning("Plate %d: preprocessing failed — %s", plate_index, exc)
        return _build_plate_result(
            bbox=bbox,
            det_confidence=det_confidence,
            class_id=class_id,
            class_name=class_name,
        )

    # ── Stage 4: OCR with fallback strategy ─────────────────────────────
    # Try all preprocessed variants and pick the best result.
    # Order: enhanced first (best for real photos), then binary variants,
    # then sharp, then gray as fallback.
    variant_order = ("enhanced", "sharp", "binary", "binary_otsu", "binary_inv", "gray")
    best_ocr = None
    best_variant = None

    for variant_name in variant_order:
        variant_img = preprocessed.get(variant_name)
        if variant_img is None:
            continue

        ocr_result = ocr_service.read_plate_text(variant_img)

        logger.info(
            "Plate %d | variant='%s' | raw='%s' | cleaned='%s' | conf=%.3f",
            plate_index, variant_name,
            ocr_result["raw_text"], ocr_result["cleaned_text"],
            ocr_result["confidence"],
        )

        if ocr_result["cleaned_text"]:
            if best_ocr is None:
                best_ocr = ocr_result
                best_variant = variant_name
            elif (
                len(ocr_result["cleaned_text"]) > len(best_ocr["cleaned_text"])
                or (
                    len(ocr_result["cleaned_text"]) == len(best_ocr["cleaned_text"])
                    and ocr_result["confidence"] > best_ocr["confidence"]
                )
            ):
                best_ocr = ocr_result
                best_variant = variant_name

        # If we got a good result (4+ chars), stop trying other variants.
        if best_ocr and len(best_ocr["cleaned_text"]) >= 4:
            break

    # Use best result or empty fallback
    if best_ocr is None:
        best_ocr = {
            "raw_text": "",
            "cleaned_text": "",
            "confidence": 0.0,
            "ocr_time_ms": 0.0,
        }

    plate_text = best_ocr["cleaned_text"]
    ocr_confidence = best_ocr["confidence"]
    combined = round(det_confidence * ocr_confidence, 4) if plate_text else 0.0

    logger.info(
        "=== PLATE %d RESULT ===  text='%s'  |  best_variant='%s'  |  "
        "raw='%s'  |  det_conf=%.3f  |  ocr_conf=%.3f  |  combined=%.3f",
        plate_index, plate_text, best_variant,
        best_ocr["raw_text"], det_confidence, ocr_confidence, combined,
    )

    return _build_plate_result(
        bbox=bbox,
        det_confidence=det_confidence,
        class_id=class_id,
        class_name=class_name,
        plate_text=plate_text,
        ocr_raw_text=best_ocr["raw_text"],
        ocr_confidence=ocr_confidence,
        combined_confidence=combined,
    )


def _build_plate_result(
    bbox: dict,
    det_confidence: float,
    class_id: int,
    class_name: str,
    plate_text: str = "",
    ocr_raw_text: str = "",
    ocr_confidence: float = 0.0,
    combined_confidence: float = 0.0,
) -> dict:
    """Build a standardized plate result dict."""
    return {
        "plate_text": plate_text,
        "ocr_raw_text": ocr_raw_text,
        "detection_confidence": det_confidence,
        "ocr_confidence": ocr_confidence,
        "combined_confidence": combined_confidence,
        "bbox": bbox,
        "class_id": class_id,
        "class_name": class_name,
    }


def _build_error_result(
    error_msg: str,
    img_w: int,
    img_h: int,
    total_start: float,
) -> dict:
    """Build an error result dict when the pipeline fails."""
    elapsed = (time.perf_counter() - total_start) * 1000
    return {
        "success": False,
        "error": error_msg,
        "plates": [],
        "num_plates": 0,
        "timing": {
            "detection_ms": 0.0,
            "ocr_ms": 0.0,
            "total_ms": round(elapsed, 1),
        },
        "image_width": img_w,
        "image_height": img_h,
    }
