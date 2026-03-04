# =============================================================================
# app/routes/detections.py — Detection History API Endpoints
# =============================================================================
# PURPOSE:
#   Exposes GET /detections and GET /detections/search for querying
#   stored detection history from the SQLite database.
#
# ENDPOINTS:
#   GET /detections             → Paginated list (limit/offset)
#   GET /detections/search      → Case-insensitive partial plate search
#   GET /detections/{id}        → Single detection by UUID
#   DELETE /detections/{id}     → Delete a detection record
#   DELETE /detections          → Clear all detection history
#
# WHY PAGINATION?
#   Without pagination, a table with 10,000 rows would dump all records
#   into a single JSON response — slow for the server, slow for the client,
#   and wasteful on network bandwidth.  Pagination lets the frontend
#   fetch small pages (e.g., 20 records) and request more on scroll.
#
# WHY SORT NEWEST FIRST?
#   Users almost always care about the most recent detections.  Sorting
#   by detected_at DESC puts the latest results at the top, matching
#   the natural "news feed" UX pattern.
# =============================================================================

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.detection import Detection
from app.schemas.detection_schema import (
    DetectionListResponse,
    DetectionResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/detections", tags=["Detection History"])


# ---------------------------------------------------------------------------
# GET /detections — Paginated history
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=DetectionListResponse,
    summary="List detection history",
    description=(
        "Retrieve paginated detection history, ordered newest first. "
        "Use `limit` and `offset` query parameters for pagination."
    ),
)
def list_detections(
    limit: int = Query(
        default=20, ge=1, le=500, description="Number of records per page."
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of records to skip."
    ),
    db: Session = Depends(get_db),
) -> DetectionListResponse:
    """Return paginated detection records, newest first."""
    try:
        total = db.query(func.count(Detection.id)).scalar() or 0

        detections = (
            db.query(Detection)
            .order_by(Detection.detected_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        logger.info(
            "GET /detections  |  total=%d  |  returned=%d  |  "
            "limit=%d  offset=%d",
            total,
            len(detections),
            limit,
            offset,
        )

        return DetectionListResponse(
            total=total,
            limit=limit,
            offset=offset,
            results=[
                DetectionResponse.model_validate(d) for d in detections
            ],
        )
    except Exception as exc:
        logger.error("Failed to retrieve detections: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve detection history.",
        ) from exc


# ---------------------------------------------------------------------------
# GET /detections/search — Case-insensitive partial plate search
# ---------------------------------------------------------------------------
# WHY SEARCH?
#   Users may want to find a specific plate or plates matching a pattern
#   (e.g., all plates starting with "AB").  Full-text search would be
#   overkill for plate numbers — SQL LIKE is perfectly adequate.
# ---------------------------------------------------------------------------
@router.get(
    "/search",
    response_model=DetectionListResponse,
    summary="Search detections by plate text",
    description=(
        "Case-insensitive partial match on plate_text. "
        "Example: `/detections/search?plate=ABC` matches 'ABC1234', 'XABC99'."
    ),
)
def search_detections(
    plate: str = Query(
        ..., min_length=1, max_length=20, description="Plate text to search."
    ),
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> DetectionListResponse:
    """Search detection records by partial plate text match."""
    try:
        # SQLite LIKE is case-insensitive for ASCII by default
        pattern = f"%{plate}%"

        base_query = db.query(Detection).filter(
            Detection.plate_text.ilike(pattern)
        )

        total = base_query.count()

        detections = (
            base_query
            .order_by(Detection.detected_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        logger.info(
            "GET /detections/search  |  plate='%s'  |  matches=%d  |  "
            "returned=%d",
            plate,
            total,
            len(detections),
        )

        return DetectionListResponse(
            total=total,
            limit=limit,
            offset=offset,
            results=[
                DetectionResponse.model_validate(d) for d in detections
            ],
        )
    except Exception as exc:
        logger.error("Failed to search detections: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search detection history.",
        ) from exc


# ---------------------------------------------------------------------------
# GET /detections/{detection_id} — Single detection by UUID
# ---------------------------------------------------------------------------
@router.get(
    "/{detection_id}",
    response_model=DetectionResponse,
    summary="Get a single detection",
    description="Retrieve a single detection record by its UUID.",
)
def get_detection(
    detection_id: str,
    db: Session = Depends(get_db),
) -> DetectionResponse:
    """Return a single detection by ID."""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()

    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {detection_id} not found.",
        )

    return DetectionResponse.model_validate(detection)


# ---------------------------------------------------------------------------
# DELETE /detections/{detection_id} — Delete a single detection
# ---------------------------------------------------------------------------
@router.delete(
    "/{detection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a detection",
    description="Remove a single detection record from the database.",
)
def delete_detection(
    detection_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete a detection by ID."""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()

    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {detection_id} not found.",
        )

    db.delete(detection)
    db.commit()
    logger.info("Deleted detection %s", detection_id)


# ---------------------------------------------------------------------------
# DELETE /detections — Clear all history
# ---------------------------------------------------------------------------
@router.delete(
    "",
    status_code=status.HTTP_200_OK,
    summary="Clear all detection history",
    description="Remove all detection records from the database.",
)
def clear_detections(
    db: Session = Depends(get_db),
) -> dict:
    """Delete all detection records."""
    try:
        count = db.query(Detection).delete()
        db.commit()
        logger.info("Cleared %d detection records.", count)
        return {"message": f"Deleted {count} detection(s).", "deleted": count}
    except Exception as exc:
        db.rollback()
        logger.error("Failed to clear detections: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear detection history.",
        ) from exc
