# =============================================================================
# app/utils/image_helpers.py — Image Processing Utilities
# =============================================================================
# PURPOSE:
#   Pure helper functions for image I/O that have no dependency on the
#   web framework or AI model.  Currently provides:
#     • `read_image_from_upload()` — decode a FastAPI UploadFile into a
#       NumPy array suitable for OpenCV / YOLOv8.
#
# WHY A SEPARATE UTILS MODULE?
#   • **Reusability** — the same decoder can be used in CLI scripts,
#     batch jobs, or tests without importing FastAPI.
#   • **Testability** — feed raw bytes, assert output shape & dtype.
#   • **Extensibility** — future helpers (resize, draw boxes, etc.)
#     live here without cluttering the service layer.
#
# ARCHITECTURE DECISION:
#   Utils are leaf-level: they import only stdlib / third-party code,
#   never other `app.*` modules.  This keeps them side-effect-free.
# =============================================================================

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed MIME types for uploaded images
# ---------------------------------------------------------------------------
ALLOWED_CONTENT_TYPES: set[str] = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/bmp",
    "image/webp",
}

# Maximum upload size in bytes (10 MB)
MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024


async def read_image_from_upload(
    file_bytes: bytes,
    content_type: str | None = None,
) -> np.ndarray:
    """
    Decode raw image bytes into a BGR NumPy array (OpenCV format).

    Parameters
    ----------
    file_bytes : bytes
        Raw bytes read from ``UploadFile.read()``.
    content_type : str | None
        MIME type of the uploaded file (used for validation).

    Returns
    -------
    np.ndarray
        Decoded image in BGR format, shape (H, W, 3), dtype uint8.

    Raises
    ------
    ValueError
        If the content type is not allowed, the file is too large,
        or OpenCV cannot decode the bytes.
    """
    # ── Validate content type ────────────────────────────────────────────
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(
            f"Unsupported image type '{content_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        )

    # ── Validate file size ───────────────────────────────────────────────
    if len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise ValueError(
            f"Image too large ({size_mb:.1f} MB). "
            f"Maximum allowed: {MAX_IMAGE_SIZE_BYTES / (1024 * 1024):.0f} MB."
        )

    if len(file_bytes) == 0:
        raise ValueError("Uploaded file is empty (0 bytes).")

    # ── Decode image ─────────────────────────────────────────────────────
    np_array = np.frombuffer(file_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError(
            "Failed to decode image. The file may be corrupted or "
            "in an unsupported format."
        )

    logger.debug(
        "Image decoded  |  shape=%s  |  dtype=%s  |  size=%.1f KB",
        image.shape,
        image.dtype,
        len(file_bytes) / 1024,
    )
    return image
