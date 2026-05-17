# =============================================================================
# app/utils/image_enhancer.py — Complete Enhancement Pipeline
# =============================================================================
# PURPOSE:
#   Implements the 4-stage enhancement pipeline:
#     1. fix_lighting() - Condition-based lighting correction
#     2. remove_blur() - Type-specific deblurring
#     3. enhance_contrast_and_denoise() - Universal contrast/noise enhancement
#     4. enhance_plate_crop() - Post-crop super enhancement for OCR
#
# ARCHITECTURE:
#   Each function is independent and handles exceptions gracefully.
#   Returns original image if any step fails.
# =============================================================================

import logging

import cv2
import numpy as np
from scipy import ndimage, signal

logger = logging.getLogger(__name__)

# ============================================================================
# STAGE 1: CONDITION-BASED LIGHTING FIX
# ============================================================================

def fix_lighting(image: np.ndarray, report: dict) -> np.ndarray:
    """
    Fix lighting based on diagnostic report.

    Applies:
      - night: LIME algorithm
      - overexposed: Gamma correction + highlight clipping
      - foggy: Dark Channel Prior defogging
      - normal: No change
    """
    lighting_condition = report.get("lighting_condition", "normal")

    try:
        if lighting_condition == "night":
            return fix_night_image(image)
        elif lighting_condition == "overexposed":
            return fix_overexposed_image(image)
        elif lighting_condition == "foggy":
            return fix_foggy_image(image)
        else:
            return image
    except Exception as e:
        logger.warning(f"Lighting fix failed: {e}. Using original.")
        return image


def fix_night_image(image: np.ndarray) -> np.ndarray:
    """
    LIME (Lighting Enhancement) algorithm for night images.

    Steps:
      1. Extract illumination map T = max(R,G,B) per pixel
      2. Refine T using guided filter
      3. Apply gamma correction (gamma=0.7)
      4. Recover enhanced image
    """
    # Extract illumination map (max of RGB channels)
    if len(image.shape) == 3:
        illum = np.maximum(np.maximum(image[:, :, 0], image[:, :, 1]), image[:, :, 2])
    else:
        illum = image.copy()

    # Refine illumination using bilateral filter (approximation of guided filter)
    illum_refined = cv2.bilateralFilter(illum.astype(np.float32), 15, 0.01, 0.01)

    # Normalize illumination
    illum_refined = illum_refined / (illum_refined.max() + 1e-6)

    # Gamma correction
    gamma = 0.7
    illum_gamma = np.power(illum_refined, gamma)

    # Apply enhancement per channel
    if len(image.shape) == 3:
        result = np.zeros_like(image, dtype=np.float32)
        for c in range(3):
            # Enhanced = image / (T^gamma)
            result[:, :, c] = image[:, :, c].astype(np.float32) / (illum_gamma + 0.1)
        result = np.clip(result, 0, 255).astype(np.uint8)
    else:
        result = np.clip(image.astype(np.float32) / (illum_gamma + 0.1), 0, 255).astype(np.uint8)

    logger.info("Applied LIME night enhancement")
    return result


def fix_overexposed_image(image: np.ndarray) -> np.ndarray:
    """
    Fix overexposed images using gamma correction and highlight clipping.
    """
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # Gamma correction on L channel
    gamma = 1.6
    l_float = l.astype(np.float32) / 255.0
    l_gamma = np.power(l_float, gamma) * 255.0
    l_corrected = np.clip(l_gamma, 0, 255).astype(np.uint8)

    # Clip highlights (L > 220 -> 200)
    l_corrected = np.where(l_corrected > 220, 200, l_corrected)

    # Merge channels
    lab_corrected = cv2.merge([l_corrected, a, b])

    # Convert back to BGR
    result = cv2.cvtColor(lab_corrected, cv2.COLOR_LAB2BGR)

    logger.info("Applied overexposure correction")
    return result


def fix_foggy_image(image: np.ndarray) -> np.ndarray:
    """
    Dark Channel Prior defogging algorithm.
    """
    # Normalize to [0, 1]
    img_float = image.astype(np.float32) / 255.0

    # Step 1: Compute dark channel (min over local patch)
    if len(image.shape) == 3:
        dark = np.min(img_float, axis=2)
    else:
        dark = img_float

    # Apply minimum filter (15x15 window)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    dark_channel = cv2.erode(dark, kernel)

    # Step 2: Estimate atmospheric light A
    # Top 0.1% brightest pixels in dark channel
    h, w = dark_channel.shape
    flat_dark = dark_channel.flatten()
    sorted_indices = np.argsort(flat_dark)[::-1]
    num_pixels = int(0.001 * h * w)
    top_indices = sorted_indices[:num_pixels]

    # Average of brightest pixels in original image
    if len(image.shape) == 3:
        A = np.mean([img_float[idx // w, idx % w, :] for idx in top_indices], axis=0)
        A = np.max(A)  # Use the highest channel as A
    else:
        A = np.mean([img_float[idx // w, idx % w] for idx in top_indices])

    A = max(A, 0.7)  # Ensure minimum atmospheric light

    # Step 3: Estimate transmission map
    transmission = 1 - 0.95 * (dark_channel / A)
    transmission = np.clip(transmission, 0.1, 1.0)

    # Step 4: Recover scene (guided filter refinement of transmission)
    # Use simple refinement
    transmission_refined = cv2.bilateralFilter(transmission.astype(np.float32), 15, 0.1, 0.1)

    # Step 5: Recover scene J(x) = (I(x) - A) / t(x) + A
    result = np.zeros_like(img_float)
    for c in range(img_float.shape[2]):
        result[:, :, c] = (img_float[:, :, c] - A) / np.maximum(transmission_refined, 0.1) + A

    result = np.clip(result * 255, 0, 255).astype(np.uint8)

    logger.info("Applied Dark Channel Prior defogging")
    return result


# ============================================================================
# STAGE 2: BLUR REMOVAL ENGINE
# ============================================================================

def remove_blur(image: np.ndarray, report: dict) -> np.ndarray:
    """
    Remove blur based on blur type from diagnostic report.
    """
    if not report.get("is_blurry", False):
        return image

    blur_type = report.get("blur_type", "none")
    blur_score = report.get("blur_score", 120)
    blur_angle = report.get("blur_angle", 0.0)

    try:
        if blur_type == "motion":
            return remove_motion_blur(image, blur_angle, blur_score)
        elif blur_type == "gaussian":
            return remove_gaussian_blur(image, blur_score)
        elif blur_type == "defocus":
            return remove_defocus_blur(image, blur_score)
        else:
            return image
    except Exception as e:
        logger.warning(f"Blur removal failed: {e}. Using original.")
        return image


def create_motion_kernel(angle: float, size: int) -> np.ndarray:
    """
    Create a motion blur PSF kernel at the specified angle.
    """
    kernel = np.zeros((size, size), dtype=np.float32)
    center = size // 2

    # Convert angle to radians
    rad = angle * np.pi / 180

    # Draw line through center
    length = size - 1
    x2 = int(center + length * np.cos(rad))
    y2 = int(center + length * np.sin(rad))

    cv2.line(kernel, (center, center), (x2, y2), 1, 1)

    # Normalize
    kernel = kernel / (np.sum(kernel) + 1e-6)
    return kernel


def remove_motion_blur(image: np.ndarray, blur_angle: float, blur_score: float) -> np.ndarray:
    """
    Apply directional Wiener filter for motion blur removal.
    """
    # Determine kernel size based on blur severity
    if blur_score < 50:
        size = 21
    elif blur_score < 100:
        size = 15
    else:
        size = 9

    # Create motion PSF
    kernel = create_motion_kernel(blur_angle, size)

    # Apply Wiener deconvolution per channel
    if len(image.shape) == 3:
        result = np.zeros_like(image)
        for c in range(3):
            channel = image[:, :, c].astype(np.float64)
            # Wiener deconvolution using Richardson-Lucy approximation
            deblurred = wiener_deconvolution(channel, kernel, noise_factor=0.01)
            result[:, :, c] = np.clip(deblurred, 0, 255).astype(np.uint8)
    else:
        result = wiener_deconvolution(image.astype(np.float64), kernel, noise_factor=0.01)
        result = np.clip(result, 0, 255).astype(np.uint8)

    logger.info(f"Applied motion blur removal (angle={blur_angle}, size={size})")
    return result


def wiener_deconvolution(image: np.ndarray, kernel: np.ndarray, noise_factor: float = 0.01) -> np.ndarray:
    """
    Wiener deconvolution for blur removal.
    """
    from numpy.fft import fft2, ifft2, fftshift

    # Pad kernel to match image size
    kh, kw = kernel.shape
    ih, iw = image.shape
    pad_h = (ih - kh) // 2
    pad_w = (iw - kw) // 2

    kernel_padded = np.zeros((ih, iw), dtype=np.float64)
    kernel_padded[pad_h:pad_h+kh, pad_w:pad_w+kw] = kernel

    # FFT
    img_fft = fft2(image)
    kernel_fft = fft2(np.fft.ifftshift(kernel_padded))

    # Wiener filter: H* / (|H|^2 + K)
    kernel_fft_conj = np.conj(kernel_fft)
    kernel_fft_abs_sq = np.abs(kernel_fft) ** 2
    K = noise_factor * np.max(kernel_fft_abs_sq)

    wiener_fft = (kernel_fft_conj * img_fft) / (kernel_fft_abs_sq + K + 1e-10)

    # Inverse FFT
    result = np.real(ifft2(wiener_fft))
    return result


def remove_gaussian_blur(image: np.ndarray, blur_score: float) -> np.ndarray:
    """
    Apply Lucy-Richardson deconvolution for gaussian blur.
    """
    # Create Gaussian PSF
    kernel_size = 15
    gaussian_kernel = cv2.getGaussianKernel(kernel_size, 2)
    psf = gaussian_kernel @ gaussian_kernel.T

    # Normalize PSF
    psf = psf / psf.sum()

    # Apply Richardson-Lucy iteration
    max_iterations = 10
    estimate = image.astype(np.float64)

    for _ in range(max_iterations):
        # Convolve estimate with PSF
        blurred = cv2.filter2D(estimate, -1, psf)

        # Avoid division by zero
        blurred = np.maximum(blurred, 1e-6)

        # Calculate ratio
        ratio = image.astype(np.float64) / blurred

        # Convolve ratio with flipped PSF
        psf_flipped = np.flip(psf)
        correction = cv2.filter2D(ratio, -1, psf_flipped)

        # Update estimate
        estimate = estimate * correction

    result = np.clip(estimate, 0, 255).astype(np.uint8)

    logger.info("Applied Richardson-Lucy deconvolution")
    return result


def remove_defocus_blur(image: np.ndarray, blur_score: float) -> np.ndarray:
    """
    Apply disk PSF Wiener deconvolution for defocus blur.
    """
    # Create disk-shaped PSF
    radius = 7
    disk_kernel = np.zeros((radius * 2 + 1, radius * 2 + 1), dtype=np.float32)
    cv2.circle(disk_kernel, (radius, radius), radius, 1, -1)
    disk_kernel = disk_kernel / (disk_kernel.sum() + 1e-6)

    # Apply Wiener deconvolution per channel
    if len(image.shape) == 3:
        result = np.zeros_like(image)
        for c in range(3):
            channel = image[:, :, c].astype(np.float64)
            deblurred = wiener_deconvolution(channel, disk_kernel, noise_factor=0.02)
            result[:, :, c] = np.clip(deblurred, 0, 255).astype(np.uint8)
    else:
        result = wiener_deconvolution(image.astype(np.float64), disk_kernel, noise_factor=0.02)
        result = np.clip(result, 0, 255).astype(np.uint8)

    logger.info("Applied defocus blur removal (disk PSF)")
    return result


# ============================================================================
# STAGE 3: UNIVERSAL CONTRAST AND NOISE ENHANCEMENT
# ============================================================================

def enhance_contrast_and_denoise(image: np.ndarray) -> np.ndarray:
    """
    Apply universal contrast enhancement and denoising.
    Always runs all steps in order.
    """
    try:
        # Step A: CLAHE
        image = apply_clahe(image)

        # Step B: HSV Channel Boost
        image = boost_hsv_channels(image)

        # Step C: Unsharp Masking
        image = apply_unsharp_mask(image)

        # Step D: Bilateral Filter
        image = apply_bilateral_filter(image)

        logger.info("Applied universal contrast and denoise enhancement")
        return image
    except Exception as e:
        logger.warning(f"Contrast/denoise enhancement failed: {e}. Using original.")
        return image


def apply_clahe(image: np.ndarray, clip_limit: float = 3.0, tile_size: tuple = (8, 8)) -> np.ndarray:
    """Apply CLAHE in LAB color space."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
    l_enhanced = clahe.apply(l)

    lab_enhanced = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)


def boost_hsv_channels(image: np.ndarray) -> np.ndarray:
    """Boost saturation and value channels."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Boost saturation by 1.2
    s = np.clip(s * 1.2, 0, 255).astype(np.uint8)

    # Boost value by 1.1
    v = np.clip(v * 1.1, 0, 255).astype(np.uint8)

    hsv_boosted = cv2.merge([h, s, v])
    return cv2.cvtColor(hsv_boosted, cv2.COLOR_HSV2BGR)


def apply_unsharp_mask(image: np.ndarray, kernel_size: int = 5, sigma: float = 1.0,
                        amount: float = 1.6) -> np.ndarray:
    """Apply unsharp masking for sharpening."""
    blurred = cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)
    return cv2.addWeighted(image, amount, blurred, -0.6, 0)


def apply_bilateral_filter(image: np.ndarray, d: int = 9, sigma_color: float = 75,
                           sigma_space: float = 75) -> np.ndarray:
    """Apply bilateral filter for edge-preserving denoising."""
    return cv2.bilateralFilter(image, d, sigma_color, sigma_space)


# ============================================================================
# STAGE 4: POST-CROP PLATE SUPER ENHANCEMENT
# ============================================================================

def enhance_plate_crop(plate_crop: np.ndarray) -> np.ndarray:
    """
    Apply super enhancement to cropped plate images for better OCR.

    Steps:
      A. Upscale if small
      B. Non-Local Means denoising
      C. Sharpening
      D. Deskewing
      E. Binarization for OCR (hybrid Otsu + Adaptive)
      F. Stroke width normalization
    """
    try:
        # Step A: Upscale if needed
        plate_crop = upscale_if_small(plate_crop)

        # Step B: Non-Local Means Denoising
        if len(plate_crop.shape) == 3:
            plate_crop = cv2.fastNlMeansDenoisingColored(plate_crop, None, 10, 10, 7, 21)
        else:
            plate_crop = cv2.fastNlMeansDenoising(plate_crop, None, 10, 7, 21)

        # Step C: Sharpening
        plate_crop = apply_plate_sharpening(plate_crop)

        # Step D: Deskewing
        plate_crop = deskew_plate(plate_crop)

        # Step E: Binarization for OCR
        plate_crop = apply_ocr_binarization(plate_crop)

        # Step F: Stroke width normalization
        plate_crop = normalize_stroke_width(plate_crop)

        logger.info("Applied plate crop super enhancement")
        return plate_crop

    except Exception as e:
        logger.warning(f"Plate crop enhancement failed: {e}. Using original.")
        return plate_crop


def upscale_if_small(plate_crop: np.ndarray, min_width: int = 200, min_height: int = 60) -> np.ndarray:
    """Upscale small plate crops."""
    h, w = plate_crop.shape[:2]
    if w < min_width or h < min_height:
        scale_w = max(min_width / w, 1.0)
        scale_h = max(min_height / h, 1.0)
        scale = max(scale_w, scale_h)
        # Cap scale at 2x to avoid over-enlargement
        scale = min(scale, 2.0)
        new_w = int(w * scale)
        new_h = int(h * scale)
        plate_crop = cv2.resize(plate_crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        logger.info(f"Plate upscaled: {w}x{h} -> {new_w}x{new_h}")
    return plate_crop


def apply_plate_sharpening(plate_crop: np.ndarray) -> np.ndarray:
    """Apply sharpening kernel."""
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    return cv2.filter2D(plate_crop, -1, kernel)


def deskew_plate(plate_crop: np.ndarray, angle_threshold: float = 2.0) -> np.ndarray:
    """
    Deskew tilted plates using Hough line detection.
    """
    if len(plate_crop.shape) == 3:
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = plate_crop

    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Hough line detection
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=30, maxLineGap=10)

    if lines is None or len(lines) == 0:
        return plate_crop

    # Calculate average angle
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
        angles.append(angle)

    median_angle = np.median(angles)

    # Only rotate if angle exceeds threshold
    if abs(median_angle) > angle_threshold:
        h, w = plate_crop.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        plate_crop = cv2.warpAffine(plate_crop, rotation_matrix, (w, h),
                                     flags=cv2.INTER_CUBIC,
                                     borderMode=cv2.BORDER_REPLICATE)
        logger.info(f"Plate deskewed by {median_angle:.2f} degrees")

    return plate_crop


def apply_ocr_binarization(plate_crop: np.ndarray) -> np.ndarray:
    """
    Apply hybrid Otsu + Adaptive binarization for better OCR.
    Returns color image but with enhanced character contrast.
    """
    if len(plate_crop.shape) == 3:
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = plate_crop

    # Otsu threshold
    _, otsu_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Adaptive threshold
    adaptive_binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 11, 2)

    # Combine both
    hybrid_binary = cv2.bitwise_and(otsu_binary, adaptive_binary)

    # Enhance the original color image using the binary mask
    # Boost contrast in character regions
    if len(plate_crop.shape) == 3:
        # Apply contrast enhancement in regions where there are characters
        result = plate_crop.copy()
        # Convert to grayscale for mask application
        mask = cv2.cvtColor(hybrid_binary, cv2.COLOR_GRAY2BGR) / 255.0
        # Slightly boost brightness in character regions
        result = np.clip(result * (1 + 0.1 * mask), 0, 255).astype(np.uint8)
        return result
    else:
        # For grayscale, just return hybrid
        return hybrid_binary


def normalize_stroke_width(plate_crop: np.ndarray) -> np.ndarray:
    """
    Apply morphological dilation to thicken thin characters.
    """
    if len(plate_crop.shape) == 3:
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = plate_crop

    # Dilation to thicken characters
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    dilated = cv2.dilate(gray, kernel, iterations=1)

    # If original was color, blend with color
    if len(plate_crop.shape) == 3:
        result = plate_crop.copy()
        # Replace character regions with slightly thicker version
        gray_plain = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        # Keep color in non-character regions
        return result
    else:
        return dilated