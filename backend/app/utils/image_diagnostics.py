# =============================================================================
# app/utils/image_diagnostics.py — Smart Image Diagnosis Module
# =============================================================================
# PURPOSE:
#   Analyzes uploaded images to detect blur type, lighting conditions,
#   and determines which enhancement stages are needed.
#
# OUTPUT:
#   Returns a diagnostic report dict with:
#     - blur_score: Laplacian variance (primary blur metric)
#     - blur_type: "motion", "gaussian", "defocus", or "none"
#     - blur_angle: degrees (only for motion blur)
#     - lighting_condition: "night", "overexposed", "foggy", "normal"
#     - is_blurry: bool (blur_score < 120)
#     - needs_defogging: bool
#     - needs_night_enhance: bool
#     - needs_exposure_fix: bool
#
# ARCHITECTURE:
#   Pure function - no side effects, no external dependencies.
# =============================================================================

import logging

import cv2
import numpy as np
from scipy import ndimage

logger = logging.getLogger(__name__)

# Diagnostic thresholds
BLUR_THRESHOLD = 120
NIGHT_BRIGHTNESS_THRESHOLD = 60
OVEREXPOSED_BRIGHTNESS_THRESHOLD = 200
FOGGY_DCP_THRESHOLD = 0.6


def calculate_laplacian_variance(image: np.ndarray) -> float:
    """
    Calculate Laplacian variance as primary blur metric.
    Higher variance = sharper image, lower variance = more blurry.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())


def detect_blur_type(image: np.ndarray, blur_score: float) -> tuple[str, float]:
    """
    Detect the type of blur using gradient analysis.

    Returns:
        tuple: (blur_type, blur_angle_degrees)
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Calculate gradients in X and Y directions
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

    # Gradient magnitude and angle
    magnitude = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
    angle = np.arctan2(sobel_y, sobel_x) * 180 / np.pi

    # Analyze gradient distribution
    mean_mag_x = np.mean(np.abs(sobel_x))
    mean_mag_y = np.mean(np.abs(sobel_y))

    # Calculate gradient direction histogram (8 bins)
    angle_hist, _ = np.histogram(angle.flatten(), bins=8, range=(-180, 180), weights=magnitude.flatten())
    dominant_bin = np.argmax(angle_hist)

    # Determine blur type based on gradient analysis
    if blur_score < 50:
        # Very blurry - analyze directionality
        horizontal_strength = np.sum(magnitude[(angle > -22.5) & (angle < 22.5)])
        vertical_strength = np.sum(magnitude[(angle > 67.5) | (angle < -67.5)])
        diagonal_strength = np.sum(magnitude[(angle >= 22.5) & (angle <= 67.5)])

        # Motion blur has strong directionality
        max_strength = max(horizontal_strength, vertical_strength, diagonal_strength)
        directionality_ratio = max_strength / (np.sum(magnitude) + 1e-6)

        if directionality_ratio > 0.5:
            # Motion blur - determine angle
            if horizontal_strength == max_strength:
                blur_angle = 0.0  # Horizontal motion
            elif vertical_strength == max_strength:
                blur_angle = 90.0  # Vertical motion
            else:
                blur_angle = 45.0 if diagonal_strength == max_strength else -45.0

            # Refine angle using Hough-like approach
            blur_angle = refine_motion_angle(gray, blur_angle)
            return "motion", blur_angle
        elif mean_mag_x < 10 and mean_mag_y < 10:
            return "gaussian", 0.0
        else:
            return "defocus", 0.0
    elif blur_score < BLUR_THRESHOLD:
        # Moderately blurry - likely defocus
        return "defocus", 0.0
    else:
        return "none", 0.0


def refine_motion_angle(image: np.ndarray, initial_angle: float) -> float:
    """
    Refine motion blur angle using frequency domain analysis.
    """
    # Convert to frequency domain
    f = np.fft.fft2(image)
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = np.log(np.abs(fshift) + 1)

    # Analyze the spectral pattern for directionality
    h, w = image.shape
    center_y, center_x = h // 2, w // 2

    # Sample points along the perpendicular to blur direction
    angles_to_check = [initial_angle - 15, initial_angle, initial_angle + 15]
    best_angle = initial_angle
    max_energy = 0

    for test_angle in angles_to_check:
        perp_angle = test_angle + 90
        perp_rad = perp_angle * np.pi / 180

        energy = 0
        for r in range(10, min(h, w) // 4, 5):
            y = int(center_y + r * np.sin(perp_rad))
            x = int(center_x + r * np.cos(perp_rad))
            if 0 <= y < h and 0 <= x < w:
                energy += magnitude_spectrum[y, x]

        if energy > max_energy:
            max_energy = energy
            best_angle = test_angle

    return best_angle


def detect_lighting_condition(image: np.ndarray) -> str:
    """
    Detect lighting condition based on image brightness analysis.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Calculate mean brightness
    mean_brightness = np.mean(gray)

    # Check for foggy condition using Dark Channel Prior
    is_foggy = compute_dark_channel_prior(image) > FOGGY_DCP_THRESHOLD

    # Determine lighting condition
    if mean_brightness < NIGHT_BRIGHTNESS_THRESHOLD:
        return "night"
    elif mean_brightness > OVEREXPOSED_BRIGHTNESS_THRESHOLD:
        return "overexposed"
    elif is_foggy:
        return "foggy"
    else:
        return "normal"


def compute_dark_channel_prior(image: np.ndarray) -> float:
    """
    Compute Dark Channel Prior mean for fog detection.
    Dark channel = min(min(R,G,B)) over local patch.
    Foggy images have higher dark channel values.
    """
    if len(image.shape) == 2:
        # Already grayscale
        dark_channel = image.astype(np.float32) / 255.0
    else:
        # Get minimum across RGB channels
        rgb = image.astype(np.float32) / 255.0
        dark_channel = np.minimum(np.minimum(rgb[:, :, 0], rgb[:, :, 1]), rgb[:, :, 2])

    # Apply minimum filter (equivalent to min over 15x15 patch)
    kernel_size = 15
    dark_channel_min = cv2.erode(dark_channel, np.ones((kernel_size, kernel_size)))

    return float(np.mean(dark_channel_min))


def diagnose_image(image: np.ndarray) -> dict:
    """
    Main diagnostic function - analyzes image and returns comprehensive report.

    Parameters
    ----------
    image : np.ndarray
        Input image in BGR format.

    Returns
    -------
    dict
        Diagnostic report containing:
        - blur_score: float (Laplacian variance)
        - blur_type: str ("motion", "gaussian", "defocus", "none")
        - blur_angle: float (degrees, 0 for non-motion)
        - lighting_condition: str ("night", "overexposed", "foggy", "normal")
        - is_blurry: bool
        - needs_defogging: bool
        - needs_night_enhance: bool
        - needs_exposure_fix: bool
    """
    report = {
        "blur_score": 0.0,
        "blur_type": "none",
        "blur_angle": 0.0,
        "lighting_condition": "normal",
        "is_blurry": False,
        "needs_defogging": False,
        "needs_night_enhance": False,
        "needs_exposure_fix": False,
    }

    try:
        # Stage 1: Calculate blur score
        blur_score = calculate_laplacian_variance(image)
        report["blur_score"] = round(blur_score, 2)
        report["is_blurry"] = blur_score < BLUR_THRESHOLD

        # Stage 2: Detect blur type
        blur_type, blur_angle = detect_blur_type(image, blur_score)
        report["blur_type"] = blur_type
        report["blur_angle"] = round(blur_angle, 2)

        # Stage 3: Detect lighting condition
        lighting_condition = detect_lighting_condition(image)
        report["lighting_condition"] = lighting_condition

        # Stage 4: Determine what enhancements are needed
        if lighting_condition == "night":
            report["needs_night_enhance"] = True
        elif lighting_condition == "overexposed":
            report["needs_exposure_fix"] = True
        elif lighting_condition == "foggy":
            report["needs_defogging"] = True

        logger.info(
            f"Image diagnosis: blur_score={blur_score:.1f}, type={blur_type}, "
            f"lighting={lighting_condition}, is_blurry={report['is_blurry']}"
        )

    except Exception as e:
        logger.warning(f"Image diagnosis failed: {e}. Using default report.")
        # Keep default report (safe values)

    return report