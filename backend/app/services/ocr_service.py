# =============================================================================
# app/services/ocr_service.py — EasyOCR Text Recognition Service
# =============================================================================

import logging
import re
import time

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level OCR reader cache (Singleton — loaded once)
# ---------------------------------------------------------------------------
_reader = None


def load_ocr_reader(languages: list[str] | None = None, gpu: bool = False):
    """Initialize the EasyOCR reader and cache it globally."""
    global _reader

    if _reader is not None:
        logger.debug("EasyOCR reader already loaded — returning cached instance.")
        return _reader

    if languages is None:
        languages = ["en"]

    logger.info("Loading EasyOCR reader  |  languages=%s  |  gpu=%s", languages, gpu)

    try:
        import easyocr
        _reader = easyocr.Reader(
            languages,
            gpu=gpu,
            verbose=False,
        )
        logger.info("EasyOCR reader loaded successfully.")
        return _reader
    except Exception as exc:
        logger.exception("Failed to load EasyOCR reader.")
        raise RuntimeError(f"EasyOCR initialization failed: {exc}") from exc


def get_ocr_reader():
    """Return the cached EasyOCR reader. Raises if not loaded."""
    if _reader is None:
        raise RuntimeError(
            "EasyOCR reader is not loaded. "
            "Ensure load_ocr_reader() was called during application startup."
        )
    return _reader


def read_plate_text(
    plate_image: np.ndarray,
    allowlist: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
) -> dict:
    """
    Extract text from a preprocessed license plate image using EasyOCR.

    Uses optimized parameters for short text (license plates):
    - text_threshold=0.5: lower threshold to catch faint characters
    - low_text=0.3: detect characters with lower confidence
    - width_ths=0.9: merge nearby text boxes more aggressively
    - contrast_ths=0.1: handle low contrast plates
    - adjust_contrast=0.7: auto-adjust contrast
    """
    reader = get_ocr_reader()

    start = time.perf_counter()

    try:
        results = reader.readtext(
            plate_image,
            detail=1,
            paragraph=False,
            allowlist=allowlist,
            text_threshold=0.5,
            low_text=0.3,
            width_ths=0.9,
            contrast_ths=0.1,
            adjust_contrast=0.7,
            mag_ratio=1.5,
        )
    except Exception as exc:
        logger.error("EasyOCR failed: %s", exc)
        return {
            "raw_text": "",
            "cleaned_text": "",
            "confidence": 0.0,
            "ocr_time_ms": (time.perf_counter() - start) * 1000,
            "all_detections": [],
        }

    elapsed_ms = (time.perf_counter() - start) * 1000

    if not results:
        logger.info("EasyOCR returned no text detections.")
        return {
            "raw_text": "",
            "cleaned_text": "",
            "confidence": 0.0,
            "ocr_time_ms": elapsed_ms,
            "all_detections": [],
        }

    # Concatenate all detected text fragments
    raw_texts = []
    confidences = []
    for bbox, text, conf in results:
        raw_texts.append(text)
        confidences.append(conf)

    raw_text = " ".join(raw_texts)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # Clean the text
    cleaned_text = clean_plate_text(raw_text)

    logger.info(
        "OCR  |  raw='%s'  |  cleaned='%s'  |  conf=%.3f  |  "
        "detections=%d  |  time=%.1f ms",
        raw_text, cleaned_text, avg_confidence, len(results), elapsed_ms,
    )

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "confidence": round(avg_confidence, 4),
        "ocr_time_ms": round(elapsed_ms, 1),
        "all_detections": [
            {"text": t, "confidence": round(c, 4)}
            for _, t, c in results
        ],
    }


def clean_plate_text(raw_text: str) -> str:
    """
    Clean and normalize raw OCR output into a valid plate number.

    Steps:
    1. Uppercase everything
    2. Strip ALL non-alphanumeric characters (spaces, dashes, dots, etc.)
    3. Apply context-aware misread corrections (O↔0, I↔1, etc.)
    4. Reject if <2 characters
    """
    if not raw_text:
        return ""

    # Step 1: Uppercase
    text = raw_text.upper().strip()

    # Step 2: Keep only A-Z, 0-9
    text = re.sub(r"[^A-Z0-9]", "", text)

    # Step 3: Context-aware misread fixes
    text = _fix_common_misreads(text)

    # Step 4: Minimum length filter
    if len(text) < 2:
        return ""

    return text


def _fix_common_misreads(text: str) -> str:
    """
    Apply context-aware corrections for common OCR misreads.

    If a character is surrounded by digits → assume ambiguous letters
    should be digits. If surrounded by letters → digits become letters.
    """
    if len(text) <= 1:
        return text

    letter_to_digit = {"O": "0", "I": "1", "S": "5", "B": "8", "G": "6", "Z": "2"}
    digit_to_letter = {"0": "O", "1": "I", "5": "S", "8": "B", "6": "G", "2": "Z"}

    result = list(text)

    for i, char in enumerate(result):
        prev_is_digit = result[i - 1].isdigit() if i > 0 else None
        next_is_digit = result[i + 1].isdigit() if i < len(result) - 1 else None

        if prev_is_digit is True and next_is_digit is True:
            if char in letter_to_digit:
                result[i] = letter_to_digit[char]

        elif prev_is_digit is False and next_is_digit is False:
            if char in digit_to_letter:
                result[i] = digit_to_letter[char]

    return "".join(result)
