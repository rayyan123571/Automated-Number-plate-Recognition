# =============================================================================
# app/utils/plate_preprocessor.py — License Plate Image Preprocessing
# =============================================================================
# Converts a raw cropped plate image into multiple clean, high-contrast
# variants optimized for OCR accuracy.
# =============================================================================

import logging
import os
import time
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARGET_PLATE_HEIGHT: int = 100  # Taller = more detail for OCR
MIN_CROP_WIDTH: int = 20
MIN_CROP_HEIGHT: int = 10

# Debug output directory (created lazily)
DEBUG_DIR: Path = Path(__file__).resolve().parents[2] / "debug_plates"


def _ensure_debug_dir() -> Path:
    """Create debug output directory if it doesn't exist."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    return DEBUG_DIR


def preprocess_plate(
    plate_crop: np.ndarray,
    target_height: int = TARGET_PLATE_HEIGHT,
    debug: bool = True,
    plate_index: int = 0,
) -> dict:
    """
    Full preprocessing pipeline producing multiple OCR-ready variants.

    Pipeline:
        1. Resize to standard height (preserve aspect ratio)
        2. Convert to grayscale
        3. Gaussian blur to reduce noise
        4. CLAHE for contrast enhancement
        5. Sharpening via unsharp mask
        6. Bilateral filter for edge-preserving denoising
        7. Adaptive threshold (Gaussian) → binary
        8. Otsu threshold → binary_otsu
        9. Inverted binary for light-on-dark plates
       10. Morphological cleanup

    Returns dict with variants: binary, binary_otsu, binary_inv,
    enhanced, sharp, gray.
    """
    h, w = plate_crop.shape[:2]

    if w < MIN_CROP_WIDTH or h < MIN_CROP_HEIGHT:
        raise ValueError(
            f"Plate crop too small ({w}×{h}). "
            f"Minimum: {MIN_CROP_WIDTH}×{MIN_CROP_HEIGHT} pixels."
        )

    logger.info("Preprocessing plate crop: %d×%d (index=%d)", w, h, plate_index)

    # ── Step 1: Resize ───────────────────────────────────────────────────
    aspect_ratio = w / h
    new_width = max(int(target_height * aspect_ratio), 100)
    resized = cv2.resize(
        plate_crop,
        (new_width, target_height),
        interpolation=cv2.INTER_CUBIC,
    )

    # ── Step 2: Grayscale ────────────────────────────────────────────────
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # ── Step 3: Gaussian blur (light — just reduce sensor noise) ─────────
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # ── Step 4: CLAHE contrast enhancement ───────────────────────────────
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(blurred)

    # ── Step 5: Sharpening via unsharp mask ──────────────────────────────
    gaussian = cv2.GaussianBlur(enhanced, (0, 0), 3)
    sharp = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)

    # ── Step 6: Bilateral filter (edge-preserving denoise) ───────────────
    denoised = cv2.bilateralFilter(sharp, d=9, sigmaColor=75, sigmaSpace=75)

    # ── Step 7: Adaptive threshold (Gaussian) ────────────────────────────
    binary_adaptive = cv2.adaptiveThreshold(
        denoised,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=15,
        C=5,
    )

    # ── Step 8: Otsu threshold ───────────────────────────────────────────
    _, binary_otsu = cv2.threshold(
        denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # ── Step 9: Inverted binary (for light text on dark plates) ──────────
    binary_inv = cv2.bitwise_not(binary_adaptive)

    # ── Step 10: Morphological cleanup on each binary variant ────────────
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))

    cleaned_adaptive = cv2.morphologyEx(binary_adaptive, cv2.MORPH_CLOSE, kernel, iterations=1)
    cleaned_otsu = cv2.morphologyEx(binary_otsu, cv2.MORPH_CLOSE, kernel, iterations=1)
    cleaned_inv = cv2.morphologyEx(binary_inv, cv2.MORPH_CLOSE, kernel, iterations=1)

    # ── Debug: save all stages ───────────────────────────────────────────
    if debug:
        _save_debug_images(plate_index, {
            "1_crop_original": plate_crop,
            "2_resized": resized,
            "3_gray": gray,
            "4_blurred": blurred,
            "5_clahe": enhanced,
            "6_sharp": sharp,
            "7_denoised": denoised,
            "8_binary_adaptive": cleaned_adaptive,
            "9_binary_otsu": cleaned_otsu,
            "10_binary_inv": cleaned_inv,
        })

    return {
        "binary": cleaned_adaptive,
        "binary_otsu": cleaned_otsu,
        "binary_inv": cleaned_inv,
        "enhanced": denoised,
        "sharp": sharp,
        "gray": gray,
    }


def _save_debug_images(plate_index: int, images: dict) -> None:
    """Save intermediate preprocessing images for debugging."""
    try:
        out_dir = _ensure_debug_dir()
        ts = int(time.time())
        for name, img in images.items():
            filename = f"plate{plate_index}_{ts}_{name}.png"
            cv2.imwrite(str(out_dir / filename), img)
        logger.info(
            "Debug images saved to %s (plate %d, %d images)",
            out_dir, plate_index, len(images),
        )
    except Exception as exc:
        logger.warning("Failed to save debug images: %s", exc)


def crop_plate_from_image(
    image: np.ndarray,
    bbox: dict,
    padding_pct: float = 0.12,
) -> np.ndarray:
    """
    Crop a license plate region with generous padding.

    Uses 12% padding (up from 5%) to avoid clipping characters at
    plate edges, which is the #1 cause of OCR misreads on real images.
    """
    img_h, img_w = image.shape[:2]

    x_min = bbox["x_min"]
    y_min = bbox["y_min"]
    x_max = bbox["x_max"]
    y_max = bbox["y_max"]

    box_w = x_max - x_min
    box_h = y_max - y_min
    pad_x = int(box_w * padding_pct)
    pad_y = int(box_h * padding_pct)

    x1 = max(0, int(x_min) - pad_x)
    y1 = max(0, int(y_min) - pad_y)
    x2 = min(img_w, int(x_max) + pad_x)
    y2 = min(img_h, int(y_max) + pad_y)

    crop = image[y1:y2, x1:x2]

    logger.info(
        "Cropped plate: bbox=[%d,%d,%d,%d] pad=%d%%→ crop=%d×%d",
        x1, y1, x2, y2, int(padding_pct * 100), crop.shape[1], crop.shape[0],
    )

    return crop
