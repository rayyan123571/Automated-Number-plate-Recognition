# =============================================================================
# app/utils/plate_preprocessor.py — License Plate Image Preprocessing
# =============================================================================
# PURPOSE:
#   Converts a raw cropped plate image into a clean, high-contrast image
#   optimized for OCR accuracy.  This is the MOST critical step for good
#   plate reading — even a perfect OCR engine fails on a blurry, noisy,
#   low-contrast plate crop.
#
# WHY PREPROCESSING IMPROVES OCR:
# ─────────────────────────────────────────────────────────────────────────
#   1. GRAYSCALE CONVERSION
#      OCR engines work on character shapes, not color.  Converting to
#      grayscale removes color noise (shadows, reflections, colored
#      backgrounds) and reduces input dimensions from 3-channel to 1.
#
#   2. CONTRAST ENHANCEMENT (CLAHE)
#      CLAHE (Contrast Limited Adaptive Histogram Equalization) enhances
#      local contrast without over-amplifying noise.  This makes faded
#      or unevenly lit characters stand out from the plate background.
#      Critical for night-time / shadow images.
#
#   3. NOISE REMOVAL (BILATERAL FILTER)
#      Bilateral filtering smooths out sensor noise and JPEG artifacts
#      while preserving the sharp edges of characters.  Unlike Gaussian
#      blur, it doesn't make text blurry — only backgrounds get smoothed.
#
#   4. ADAPTIVE THRESHOLDING
#      Converts the image to pure black-and-white (binary).  Adaptive
#      thresholding handles uneven lighting across the plate — the left
#      side can be brighter than the right, and it still works.
#      OCR engines perform best on clean binary images.
#
#   5. MORPHOLOGICAL OPERATIONS
#      Opening (erosion → dilation) removes small noise specks.
#      Closing (dilation → erosion) fills small gaps in characters.
#      This produces cleaner character contours for OCR.
#
#   6. RESIZING
#      EasyOCR works best on images where characters are 20–50 pixels
#      tall.  We resize the crop to a standard height while maintaining
#      aspect ratio, ensuring consistent OCR performance regardless of
#      the original plate size in the image.
#
# ARCHITECTURE DECISION:
#   Pure utility — no dependencies on services, routes, or config.
#   Takes a NumPy array in, returns a NumPy array out.  100% testable.
# =============================================================================

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Target height for resized plate crop (pixels).
# Characters should be roughly 20–50 px tall for optimal EasyOCR performance.
TARGET_PLATE_HEIGHT: int = 80

# Minimum crop dimensions to consider valid (avoids OCR on noise)
MIN_CROP_WIDTH: int = 20
MIN_CROP_HEIGHT: int = 10


def preprocess_plate(
    plate_crop: np.ndarray,
    target_height: int = TARGET_PLATE_HEIGHT,
    debug: bool = False,
) -> dict:
    """
    Full preprocessing pipeline for a cropped license plate image.

    Pipeline:
        1. Resize to standard height (preserve aspect ratio).
        2. Convert to grayscale.
        3. Apply CLAHE for contrast enhancement.
        4. Bilateral filter for noise reduction.
        5. Adaptive thresholding to create binary image.
        6. Morphological cleanup (open + close).

    Returns a dict with multiple preprocessed variants so the caller
    can try OCR on each and pick the best result.

    Parameters
    ----------
    plate_crop : np.ndarray
        Cropped plate region in BGR format, shape (H, W, 3).
    target_height : int
        Target height for the resized plate crop.
    debug : bool
        If True, log intermediate step details.

    Returns
    -------
    dict
        {
            "binary": np.ndarray,    # Binary (black/white) — best for clean plates
            "enhanced": np.ndarray,  # CLAHE + bilateral — best for noisy plates
            "gray": np.ndarray,      # Simple grayscale — fallback
        }

    Raises
    ------
    ValueError
        If the input crop is too small to process.
    """
    h, w = plate_crop.shape[:2]

    # ── Validate minimum size ────────────────────────────────────────────
    if w < MIN_CROP_WIDTH or h < MIN_CROP_HEIGHT:
        raise ValueError(
            f"Plate crop too small ({w}×{h}). "
            f"Minimum: {MIN_CROP_WIDTH}×{MIN_CROP_HEIGHT} pixels."
        )

    if debug:
        logger.debug("Preprocessing plate crop: %d×%d", w, h)

    # ── Step 1: Resize to standard height ────────────────────────────────
    # WHY: Ensures consistent character size for OCR regardless of how
    # far the camera was from the plate.
    aspect_ratio = w / h
    new_width = int(target_height * aspect_ratio)
    resized = cv2.resize(
        plate_crop,
        (new_width, target_height),
        interpolation=cv2.INTER_CUBIC,  # Cubic = best for upscaling
    )

    # ── Step 2: Convert to grayscale ─────────────────────────────────────
    # WHY: OCR works on shape, not color. Removes color noise.
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # ── Step 3: CLAHE contrast enhancement ───────────────────────────────
    # WHY: Enhances local contrast without amplifying noise globally.
    # clipLimit=2.0 prevents over-enhancement in already high-contrast areas.
    # tileGridSize=(8,8) divides image into 8×8 blocks for local adaptation.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # ── Step 4: Bilateral filter for noise removal ───────────────────────
    # WHY: Smooths noise while preserving character edges.
    # d=11: neighborhood diameter.  sigmaColor=17: color similarity range.
    # sigmaSpace=17: spatial proximity range.
    denoised = cv2.bilateralFilter(enhanced, d=11, sigmaColor=17, sigmaSpace=17)

    # ── Step 5: Adaptive thresholding ────────────────────────────────────
    # WHY: Creates binary (black/white) image. Adaptive handles uneven
    # lighting across the plate (e.g., shadow on one side).
    # GAUSSIAN method uses weighted sum of neighborhood pixels.
    # blockSize=19: size of neighborhood area.
    # C=7: constant subtracted from mean (fine-tunes threshold).
    binary = cv2.adaptiveThreshold(
        denoised,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=19,
        C=7,
    )

    # ── Step 6: Morphological cleanup ────────────────────────────────────
    # WHY: Opening removes small noise specks. Closing fills gaps in chars.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    # Opening: erosion → dilation (removes tiny white noise)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    # Closing: dilation → erosion (fills small gaps in characters)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)

    if debug:
        logger.debug(
            "Preprocessing complete: %d×%d → %d×%d (binary)",
            w, h, cleaned.shape[1], cleaned.shape[0],
        )

    return {
        "binary": cleaned,
        "enhanced": denoised,
        "gray": gray,
    }


def crop_plate_from_image(
    image: np.ndarray,
    bbox: dict,
    padding_pct: float = 0.05,
) -> np.ndarray:
    """
    Crop a license plate region from the full image using bbox coordinates.

    Adds a small padding around the bounding box to ensure characters at
    the edges of the plate are not clipped.

    Parameters
    ----------
    image : np.ndarray
        Full image in BGR format.
    bbox : dict
        Bounding box with keys: x_min, y_min, x_max, y_max (pixel coords).
    padding_pct : float
        Padding as a fraction of the bbox dimensions (e.g., 0.05 = 5%).

    Returns
    -------
    np.ndarray
        Cropped plate region in BGR format.
    """
    img_h, img_w = image.shape[:2]

    x_min = bbox["x_min"]
    y_min = bbox["y_min"]
    x_max = bbox["x_max"]
    y_max = bbox["y_max"]

    # Calculate padding in pixels
    box_w = x_max - x_min
    box_h = y_max - y_min
    pad_x = int(box_w * padding_pct)
    pad_y = int(box_h * padding_pct)

    # Apply padding and clamp to image boundaries
    x1 = max(0, int(x_min) - pad_x)
    y1 = max(0, int(y_min) - pad_y)
    x2 = min(img_w, int(x_max) + pad_x)
    y2 = min(img_h, int(y_max) + pad_y)

    crop = image[y1:y2, x1:x2]

    logger.debug(
        "Cropped plate: bbox=[%d,%d,%d,%d] → crop=%d×%d",
        x1, y1, x2, y2, crop.shape[1], crop.shape[0],
    )

    return crop
