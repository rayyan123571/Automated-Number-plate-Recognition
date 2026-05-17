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

from app.core.config import settings
from app.services import detector
from app.services import ocr_service
from app.services import fake_plate_detector
from app.services.pakistan_plate_format import parse_plate
from app.utils.plate_preprocessor import crop_plate_from_image, preprocess_plate
from app.utils.image_diagnostics import diagnose_image
from app.utils.image_enhancer import (
    fix_lighting,
    remove_blur,
    enhance_contrast_and_denoise,
    enhance_plate_crop
)

logger = logging.getLogger(__name__)


def recognize(image: np.ndarray, is_live: bool = False) -> dict:
    """
    Run the full ANPR pipeline on a single image.

    Parameters
    ----------
    image : np.ndarray
        BGR image as a NumPy array (from OpenCV / image upload).
    is_live : bool
        If True, restricts the number of OCR variants to prevent latency in video streams.

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

    # Initialize timing dictionary
    timings = {}
    enhancement_report = {}

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 0: SMART IMAGE DIAGNOSIS
    # ─────────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    diagnosis_report = diagnose_image(image)
    timings["diagnosis_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    # Store diagnosis info for later use
    blur_score = diagnosis_report.get("blur_score", 0.0)
    blur_type = diagnosis_report.get("blur_type", "none")
    enhancement_report["blur_score"] = blur_score
    enhancement_report["blur_type"] = blur_type
    enhancement_report["lighting_condition"] = diagnosis_report.get("lighting_condition", "normal")

    logger.info(
        f"Image diagnosis: blur_score={blur_score:.1f}, type={blur_type}, "
        f"lighting={diagnosis_report.get('lighting_condition', 'normal')}, "
        f"is_blurry={diagnosis_report.get('is_blurry', False)}"
    )

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 1: CONDITION-BASED LIGHTING FIX
    # ─────────────────────────────────────────────────────────────────────
    t1 = time.perf_counter()
    image = fix_lighting(image, diagnosis_report)
    timings["lighting_ms"] = round((time.perf_counter() - t1) * 1000, 2)

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 2: BLUR REMOVAL ENGINE
    # ─────────────────────────────────────────────────────────────────────
    t2 = time.perf_counter()
    image = remove_blur(image, diagnosis_report)
    timings["deblur_ms"] = round((time.perf_counter() - t2) * 1000, 2)

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 3: UNIVERSAL CONTRAST AND NOISE ENHANCEMENT
    # ─────────────────────────────────────────────────────────────────────
    t3 = time.perf_counter()
    image = enhance_contrast_and_denoise(image)
    timings["enhance_ms"] = round((time.perf_counter() - t3) * 1000, 2)

    # Total enhancement time before detection
    total_pre_detection_ms = sum([
        timings.get("diagnosis_ms", 0),
        timings.get("lighting_ms", 0),
        timings.get("deblur_ms", 0),
        timings.get("enhance_ms", 0)
    ])

    logger.info(
        f"Pre-detection enhancement pipeline complete | total_time={total_pre_detection_ms:.1f}ms"
    )

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
                "diagnosis_ms": timings.get("diagnosis_ms", 0),
                "lighting_ms": timings.get("lighting_ms", 0),
                "deblur_ms": timings.get("deblur_ms", 0),
                "enhance_ms": timings.get("enhance_ms", 0),
                "detection_ms": round(detection_ms, 1),
                "ocr_ms": 0.0,
                "total_ms": round(elapsed, 1),
            },
            "enhancement_report": {
                "blur_score": blur_score,
                "blur_type": blur_type,
                "lighting": diagnosis_report.get("lighting_condition", "normal"),
                "is_blurry": diagnosis_report.get("is_blurry", False),
                "timings_ms": timings,
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
        plate_result = _process_single_plate(image, det, plate_index=i, is_live=is_live)
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
            "diagnosis_ms": timings.get("diagnosis_ms", 0),
            "lighting_ms": timings.get("lighting_ms", 0),
            "deblur_ms": timings.get("deblur_ms", 0),
            "enhance_ms": timings.get("enhance_ms", 0),
            "detection_ms": round(detection_ms, 1),
            "ocr_ms": round(ocr_ms, 1),
            "total_ms": round(total_ms, 1),
        },
        "enhancement_report": {
            "blur_score": blur_score,
            "blur_type": blur_type,
            "lighting": diagnosis_report.get("lighting_condition", "normal"),
            "is_blurry": diagnosis_report.get("is_blurry", False),
            "timings_ms": timings,
        },
        "image_width": img_w,
        "image_height": img_h,
    }


def _process_single_plate(
    image: np.ndarray,
    detection: dict,
    plate_index: int,
    is_live: bool = False,
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

    # ── Stage 4: Post-Crop Plate Super Enhancement (before OCR) ─────────
    # Apply super enhancement for better OCR accuracy
    try:
        plate_crop = enhance_plate_crop(plate_crop)
    except Exception as exc:
        logger.warning("Plate %d: plate crop enhancement failed — %s", plate_index, exc)

    # ── Stage 3: Preprocess plate for OCR ────────────────────────────────
    try:
        preprocessed = preprocess_plate(plate_crop, plate_index=plate_index, is_live=is_live)
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
    # Order: enhanced first, then aggressive sharpening variants, 
    # then binary variants, then gray as fallback.
    
    # Check if GPU is available to determine how many variants we can afford to run
    import torch
    is_gpu = torch.cuda.is_available()
    
    if is_gpu or not is_live:
        # If GPU is available OR it is a static image upload (not live), run all variants.
        variant_order = ("enhanced", "ultra_sharp", "laplacian", "sharp", "binary", "binary_otsu", "binary_inv", "gray")
    else:
        # On CPU + Live Video, OCR is extremely slow. Using just one highly-effective variant 
        # (binary_otsu) to prevent massive trailing/desync of the bounding box.
        variant_order = ("binary_otsu",)

    best_ocr = None
    best_variant = None
    best_score = -1.0

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

        cleaned = ocr_result["cleaned_text"]
        if cleaned:
            text_len = len(cleaned)
            in_range = settings.ANPR_MIN_PLATE_CHARS <= text_len <= settings.ANPR_MAX_PLATE_CHARS
            length_score = 1.0 if in_range else 0.0
            score = (ocr_result["confidence"] * 0.8) + (length_score * 0.2)

            if score > best_score:
                best_score = score
                best_ocr = ocr_result
                best_variant = variant_name

        # If we already have a strong read, avoid extra OCR calls.
        if (
            best_ocr
            and best_ocr["confidence"] >= 0.60
            and settings.ANPR_MIN_PLATE_CHARS <= len(best_ocr["cleaned_text"]) <= settings.ANPR_MAX_PLATE_CHARS
        ):
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

    if plate_text and _is_low_quality_plate(plate_text, ocr_confidence, combined):
        logger.info(
            "Plate %d rejected by quality gate  |  text='%s'  |  len=%d  |  ocr_conf=%.3f  |  combined=%.3f",
            plate_index,
            plate_text,
            len(plate_text),
            ocr_confidence,
            combined,
        )
        plate_text = ""
        combined = 0.0

    logger.info(
        "=== PLATE %d RESULT ===  text='%s'  |  best_variant='%s'  |  "
        "raw='%s'  |  det_conf=%.3f  |  ocr_conf=%.3f  |  combined=%.3f",
        plate_index, plate_text, best_variant,
        best_ocr["raw_text"], det_confidence, ocr_confidence, combined,
    )

    # ── Stage 5: Pakistan plate format parsing ───────────────────────
    plate_info = parse_plate(plate_text) if plate_text else None

    # ── Stage 6: Fake / tampered plate screening ─────────────────────
    fake_info = {}
    if settings.ANPR_FAKE_PLATE_CHECK and plate_text:
        try:
            fake_info = fake_plate_detector.check_plate(plate_crop, plate_text, plate_info)
        except Exception as exc:
            logger.warning("Fake-plate check failed for plate %d: %s", plate_index, exc)
            fake_info = {}

    return _build_plate_result(
        bbox=bbox,
        det_confidence=det_confidence,
        class_id=class_id,
        class_name=class_name,
        plate_text=plate_text,
        ocr_raw_text=best_ocr["raw_text"],
        ocr_confidence=ocr_confidence,
        combined_confidence=combined,
        plate_info=plate_info,
        fake_info=fake_info,
        plate_crop=plate_crop,
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
    plate_info=None,
    fake_info: dict | None = None,
    plate_crop: np.ndarray | None = None,
) -> dict:
    """Build a standardized plate result dict."""
    result = {
        "plate_text": plate_text,
        "ocr_raw_text": ocr_raw_text,
        "detection_confidence": det_confidence,
        "ocr_confidence": ocr_confidence,
        "combined_confidence": combined_confidence,
        "bbox": bbox,
        "class_id": class_id,
        "class_name": class_name,
        "plate_crop": plate_crop,
        # New Pakistan-specific fields (always present, may be null)
        "province": None,
        "city": None,
        "category": None,
        "is_valid_format": False,
        "is_suspicious": False,
        "tamper_score": 0.0,
        "tamper_reasons": [],
        "color_class": None,
        "track_id": None,
        "challan": None,
    }
    if plate_info is not None:
        result["province"] = plate_info.province
        result["city"] = plate_info.city
        result["category"] = plate_info.category
        result["is_valid_format"] = plate_info.is_valid_format
    if fake_info:
        result["is_suspicious"] = fake_info.get("is_suspicious", False)
        result["tamper_score"] = fake_info.get("tamper_score", 0.0)
        result["tamper_reasons"] = fake_info.get("reasons", [])
        result["color_class"] = fake_info.get("color_class")
    return result


def _is_low_quality_plate(plate_text: str, ocr_confidence: float, combined_confidence: float) -> bool:
    """Return True if recognized text is too weak/unreliable to expose as a plate."""
    length = len(plate_text)

    if length < settings.ANPR_MIN_PLATE_CHARS or length > settings.ANPR_MAX_PLATE_CHARS:
        return True

    if ocr_confidence < settings.ANPR_MIN_OCR_CONFIDENCE:
        return True

    if combined_confidence < settings.ANPR_MIN_COMBINED_CONFIDENCE:
        return True

    return False


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
            "diagnosis_ms": 0.0,
            "lighting_ms": 0.0,
            "deblur_ms": 0.0,
            "enhance_ms": 0.0,
            "detection_ms": 0.0,
            "ocr_ms": 0.0,
            "total_ms": round(elapsed, 1),
        },
        "enhancement_report": {
            "blur_score": 0.0,
            "blur_type": "none",
            "lighting": "normal",
            "is_blurry": False,
            "timings_ms": {},
        },
        "image_width": img_w,
        "image_height": img_h,
    }
