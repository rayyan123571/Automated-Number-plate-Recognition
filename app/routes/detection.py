# =============================================================================
# app/routes/detection.py — Number Plate Detection + Recognition Endpoint
# =============================================================================
# PURPOSE:
#   Exposes POST /detect — the core ANPR inference endpoint.
#   Accepts an image upload, delegates to the ANPR pipeline service, and
#   returns structured JSON with plate text, bounding boxes, confidences,
#   and per-stage timing information.
#
# DESIGN PRINCIPLES:
#   • Thin controller — all AI logic lives in `services/anpr_service.py`.
#   • Explicit error handling — each failure mode returns a clear message.
#   • Async file I/O — uses `await file.read()` to avoid blocking the
#     event loop under high concurrency.
#
# ARCHITECTURE DECISION:
#   The route knows nothing about YOLOv8 or EasyOCR internals.  It:
#     1. Reads bytes from the upload.
#     2. Calls image_helpers to decode.
#     3. Calls anpr_service.recognize() for the full pipeline.
#     4. Maps the raw dict output through Pydantic schemas.
#   If we swap the AI models, this file stays unchanged.
# =============================================================================

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.schemas import ANPRResponse, ErrorResponse
from app.services import anpr_service
from app.services.detection_store import save_detections
from app.utils.image_helpers import read_image_from_upload

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router instance — mounted in main.py
# ---------------------------------------------------------------------------
router = APIRouter(tags=["Detection"])


@router.post(
    "/detect",
    response_model=ANPRResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid image upload."},
        500: {"model": ErrorResponse, "description": "Internal server error."},
    },
    summary="Detect and recognize number plates",
    description=(
        "Upload an image and receive recognized license plate numbers, "
        "bounding boxes, confidence scores (detection + OCR), and "
        "per-stage timing information."
    ),
)
async def detect_plates(
    file: UploadFile = File(
        ...,
        description="Image file (JPEG, PNG, BMP, or WebP — max 10 MB).",
    ),
    db: Session = Depends(get_db),
) -> ANPRResponse:
    """
    Full ANPR pipeline endpoint.

    Flow:
        1. Read and validate uploaded image bytes.
        2. Decode to NumPy array (BGR).
        3. Run full ANPR pipeline: Detection → Crop → Preprocess → OCR → Clean.
        4. Return structured recognition results.
    """

    # ── Step 1: Read uploaded file ───────────────────────────────────────
    try:
        file_bytes = await file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded file: {exc}",
        ) from exc

    # ── Step 2: Decode image ─────────────────────────────────────────────
    try:
        image = await read_image_from_upload(
            file_bytes=file_bytes,
            content_type=file.content_type,
        )
    except ValueError as exc:
        logger.warning("Image validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # ── Step 3: Run full ANPR pipeline ───────────────────────────────────
    try:
        result = anpr_service.recognize(image)
    except RuntimeError as exc:
        logger.error("ANPR pipeline failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ANPR pipeline error: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during ANPR processing.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during plate recognition.",
        ) from exc

    # ── Step 4: Build response ───────────────────────────────────────────
    if not result.get("success", False):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Unknown pipeline error."),
        )

    num = result["num_plates"]
    total_ms = result["timing"]["total_ms"]
    recognized = sum(1 for p in result["plates"] if p["plate_text"])

    logger.info(
        "POST /detect  |  detected=%d  |  recognized=%d  |  "
        "image=%dx%d  |  total=%.1f ms",
        num,
        recognized,
        result["image_width"],
        result["image_height"],
        total_ms,
    )

    # Build human-readable message
    if num == 0:
        message = "No number plates detected in the image."
    elif recognized == 0:
        message = (
            f"Detected {num} plate(s) but could not read text. "
            f"Total time: {total_ms:.1f} ms."
        )
    else:
        plate_texts = [p["plate_text"] for p in result["plates"] if p["plate_text"]]
        message = (
            f"Recognized {recognized} plate(s): {', '.join(plate_texts)}. "
            f"Total time: {total_ms:.1f} ms."
        )

    # ── Step 5: Persist to database ───────────────────────────────────────────
    # Save detection results to SQLite. This is non-blocking — if the DB
    # write fails, the API still returns the detection results.
    saved = save_detections(db, result, image_path=None)
    if saved:
        logger.info("Persisted %d detection(s) to database.", len(saved))

    return ANPRResponse(
        success=True,
        message=message,
        num_plates=num,
        plates=result["plates"],
        timing=result["timing"],
        image_width=result["image_width"],
        image_height=result["image_height"],
    )
