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


def is_ocr_loaded() -> bool:
    """Check if the EasyOCR reader is currently loaded in memory."""
    return _reader is not None


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

    # Sort detected fragments by y-center (top-to-bottom) then x-center (left-to-right)
    # so multi-line Pakistani plates (Punjab/Sindh) keep correct character order.
    def _box_center(bbox):
        ys = [pt[1] for pt in bbox]
        xs = [pt[0] for pt in bbox]
        return (sum(ys) / 4.0, sum(xs) / 4.0)

    # Group into lines by y-coordinate (within plate-row tolerance)
    sorted_results = sorted(results, key=lambda r: _box_center(r[0])[0])
    if sorted_results:
        first_y = _box_center(sorted_results[0][0])[0]
        line_tol = max(15, plate_image.shape[0] // 4)
        lines: list[list] = [[]]
        cur_y = first_y
        for r in sorted_results:
            cy = _box_center(r[0])[0]
            if abs(cy - cur_y) > line_tol:
                lines.append([])
                cur_y = cy
            lines[-1].append(r)
        # within each line, sort left-to-right
        ordered = []
        for line in lines:
            line.sort(key=lambda r: _box_center(r[0])[1])
            ordered.extend(line)
    else:
        ordered = sorted_results

    raw_texts = [t for _, t, _ in ordered]
    confidences = [c for _, _, c in ordered]

    raw_text = " ".join(raw_texts)
    # Weight confidence by character count so a stray "PUNJAB" word doesn't
    # boost the score when the actual plate digits are weak.
    if confidences:
        weights = [max(1, len(t)) for _, t, _ in ordered]
        total_w = sum(weights)
        avg_confidence = sum(c * w for c, w in zip(confidences, weights)) / total_w
    else:
        avg_confidence = 0.0

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
    Pakistan-plate-aware OCR correction.

    Pakistani plates broadly follow: <LETTERS><DIGITS> where the letter
    prefix is 1-3 characters identifying province/city (e.g., LEA, ICT,
    BJN, KHI, RIN) and the suffix is 1-4 digits.

    Strategy:
      - Split text into a leading alphabetic block and trailing numeric block.
      - In the LETTER zone, digits commonly misread should become letters
        (0->O, 1->I, 5->S, 8->B).
      - In the DIGIT zone, letters commonly misread should become digits
        (O->0, I->1, S->5, B->8, G->6, Z->2, Q->0, D->0).
      - Only flip when the change makes the resulting block match the
        expected character class — never blindly transform.
    """
    if len(text) <= 1:
        return text

    digit_to_letter = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
    letter_to_digit = {
        "O": "0", "Q": "0", "D": "0",
        "I": "1", "L": "1",
        "S": "5",
        "B": "8",
        "G": "6",
        "Z": "2",
    }

    # Find the split point: end of leading letter block.
    # Allow at most 4 chars in the prefix (Pakistan max is ~3, +1 tolerance).
    split = 0
    for i, ch in enumerate(text[:5]):
        if ch.isalpha():
            split = i + 1
        elif ch.isdigit() and split == 0:
            # plate starts with digit (e.g., commercial Karachi "7777-A")
            break
        else:
            break

    # Heuristic: if no clear letter prefix, leave text alone (could be
    # an Urdu plate or an unusual format — better to not corrupt).
    if split == 0 or split >= len(text):
        return text

    prefix = text[:split]
    suffix = text[split:]

    # Fix prefix: digits that should be letters
    prefix_fixed = "".join(digit_to_letter.get(ch, ch) if ch.isdigit() else ch for ch in prefix)

    # Fix suffix: letters that should be digits
    suffix_fixed = "".join(letter_to_digit.get(ch, ch) if ch.isalpha() else ch for ch in suffix)

    return prefix_fixed + suffix_fixed
