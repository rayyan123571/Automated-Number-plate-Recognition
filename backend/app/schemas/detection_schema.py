# =============================================================================
# app/schemas/detection_schema.py — Pydantic Schemas for Detection History
# =============================================================================
# PURPOSE:
#   Data Transfer Objects (DTOs) for the /detections endpoints.
#   These schemas define what the API accepts and returns — separate
#   from the SQLAlchemy ORM model.
#
# ORM MODEL vs PYDANTIC SCHEMA:
#   ┌──────────────────────┬────────────────────────────────────────────┐
#   │ ORM Model            │ Pydantic Schema                           │
#   │ (detection.py)       │ (detection_schema.py)                     │
#   ├──────────────────────┼────────────────────────────────────────────┤
#   │ Maps to a DB table   │ Maps to JSON request/response             │
#   │ Has DB-specific cols │ Has validation rules for API consumers    │
#   │ Used inside services │ Used at the API boundary (routes)         │
#   │ Mutable, has state   │ Immutable, stateless data containers      │
#   └──────────────────────┴────────────────────────────────────────────┘
#
# WHY from_attributes=True?
#   Pydantic v2 renamed `orm_mode` to `from_attributes`.  When enabled,
#   Pydantic reads data from ORM model attributes (obj.plate_text) instead
#   of dict keys (obj["plate_text"]).  This allows:
#       DetectionResponse.model_validate(db_detection_object)
#   without manually converting to a dict first.
# =============================================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── Create Schema (input for manual insertion, if needed) ────────────────────

class DetectionCreate(BaseModel):
    """
    Schema for creating a detection record.

    Used internally by the ANPR service — not exposed as a public API
    request body.  All fields match the ORM model columns.
    """

    plate_text: str = Field(
        default="",
        max_length=20,
        description="Cleaned plate number (e.g., ABC1234).",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Combined confidence (detection × OCR).",
    )
    detection_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="YOLOv8 bounding-box confidence.",
    )
    ocr_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="EasyOCR text confidence.",
    )
    image_path: Optional[str] = Field(
        default=None,
        description="Path to the source image (if saved).",
    )
    bbox: dict = Field(
        ...,
        description="Bounding box {x_min, y_min, x_max, y_max}.",
    )
    image_width: int = Field(
        default=0,
        ge=0,
        description="Source image width (px).",
    )
    image_height: int = Field(
        default=0,
        ge=0,
        description="Source image height (px).",
    )
    processing_time: float = Field(
        default=0.0,
        ge=0.0,
        description="Total pipeline time in milliseconds.",
    )


# ─── Response Schema ─────────────────────────────────────────────────────────

class DetectionResponse(BaseModel):
    """
    Schema for returning a detection record to API consumers.

    Maps 1-to-1 with the Detection ORM model via `from_attributes=True`.
    """

    id: str = Field(..., description="UUID of the detection record.")
    plate_text: str = Field(..., description="Cleaned plate number.")
    confidence: float = Field(
        ..., description="Combined confidence (detection × OCR)."
    )
    detection_confidence: float = Field(
        ..., description="YOLOv8 detection confidence."
    )
    ocr_confidence: float = Field(
        ..., description="EasyOCR OCR confidence."
    )
    image_path: Optional[str] = Field(
        default=None, description="Path to source image."
    )
    bbox: dict = Field(
        ..., description="Bounding box coordinates."
    )
    image_width: int = Field(
        ..., description="Source image width (px)."
    )
    image_height: int = Field(
        ..., description="Source image height (px)."
    )
    processing_time: float = Field(
        ..., description="Pipeline processing time (ms)."
    )
    detected_at: datetime = Field(
        ..., description="UTC timestamp of detection."
    )

    # Enable reading from ORM model attributes (not just dicts).
    model_config = ConfigDict(from_attributes=True)


# ─── Paginated Response ──────────────────────────────────────────────────────

class DetectionListResponse(BaseModel):
    """Paginated list of detection records."""

    total: int = Field(..., ge=0, description="Total records in database.")
    limit: int = Field(..., ge=1, description="Page size.")
    offset: int = Field(..., ge=0, description="Number of records skipped.")
    results: list[DetectionResponse] = Field(
        default_factory=list,
        description="Detection records for this page.",
    )
