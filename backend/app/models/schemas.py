# =============================================================================
# app/models/schemas.py — Pydantic Request / Response Schemas
# =============================================================================
# PURPOSE:
#   Define strict data contracts for every API endpoint.  FastAPI uses
#   these schemas for:
#     • Automatic request validation (reject malformed payloads).
#     • Response serialization (guarantee JSON shape for clients).
#     • OpenAPI / Swagger documentation (auto-generated from schemas).
#
# WHY PYDANTIC V2?
#   • 5–50× faster validation than v1 (Rust core).
#   • `model_config` replaces the old inner `class Config`.
#   • Native support for JSON Schema generation.
#
# ARCHITECTURE DECISION:
#   Schemas live in `models/` — the innermost ring that has zero imports
#   from routes or services.  They are pure data definitions.
# =============================================================================

from pydantic import BaseModel, Field


# ─── Health Check ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response schema for GET /health."""

    status: str = Field(
        ...,
        examples=["healthy"],
        description="Current health status of the API.",
    )
    app_name: str = Field(
        ...,
        examples=["ANPR System"],
        description="Application name from environment config.",
    )
    version: str = Field(
        ...,
        examples=["1.0.0"],
        description="Application version.",
    )
    model_loaded: bool = Field(
        ...,
        description="Whether the YOLOv8 model is loaded and ready.",
    )
    ocr_loaded: bool = Field(
        ...,
        description="Whether the EasyOCR reader is loaded and ready.",
    )


# ─── Detection ───────────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    """Pixel-coordinate bounding box for a single detection."""

    x_min: float = Field(..., description="Left edge (pixels).")
    y_min: float = Field(..., description="Top edge (pixels).")
    x_max: float = Field(..., description="Right edge (pixels).")
    y_max: float = Field(..., description="Bottom edge (pixels).")


class Detection(BaseModel):
    """A single number-plate detection result."""

    bbox: BoundingBox = Field(
        ..., description="Bounding box coordinates in pixels."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score (0–1).",
    )
    class_id: int = Field(
        ..., description="Integer class index from the model."
    )
    class_name: str = Field(
        ...,
        examples=["plate-number"],
        description="Human-readable class label.",
    )


class DetectionResponse(BaseModel):
    """Response schema for POST /detect."""

    success: bool = Field(
        ..., description="Whether inference completed without errors."
    )
    message: str = Field(
        ..., description="Human-readable summary of the result."
    )
    num_detections: int = Field(
        ..., ge=0, description="Total number of plates detected."
    )
    detections: list[Detection] = Field(
        default_factory=list,
        description="List of individual detection results.",
    )
    image_width: int = Field(
        ..., ge=1, description="Width of the uploaded image (pixels)."
    )
    image_height: int = Field(
        ..., ge=1, description="Height of the uploaded image (pixels)."
    )


# ─── ANPR (Full Pipeline) ────────────────────────────────────────────────────

class AccessCheckResult(BaseModel):
    """Access-control result for a single plate."""

    plate: str = Field(..., description="Normalized plate number.")
    access: str = Field(
        ...,
        examples=["AUTHORIZED", "UNAUTHORIZED"],
        description="AUTHORIZED if the plate is in the allow-list, else UNAUTHORIZED.",
    )
    alert: str | None = Field(
        default=None,
        description="Alert message when the vehicle is unauthorized.",
    )


class PlateResult(BaseModel):
    """A single recognized license plate with text + detection metadata."""

    plate_text: str = Field(
        ...,
        examples=["ABC1234"],
        description=(
            "Final cleaned plate number (uppercase, A-Z and 0-9 only). "
            "Empty string if OCR failed or returned no text."
        ),
    )
    access_status: str | None = Field(
        default=None,
        examples=["AUTHORIZED", "UNAUTHORIZED"],
        description="Access control status. None if no text was recognized.",
    )
    alert: str | None = Field(
        default=None,
        description="Alert message when the vehicle is unauthorized.",
    )
    ocr_raw_text: str = Field(
        default="",
        description="Raw OCR output before cleaning (for debugging).",
    )
    detection_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="YOLOv8 bounding-box detection confidence (0–1).",
    )
    ocr_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="EasyOCR average character confidence (0–1).",
    )
    combined_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "End-to-end confidence = detection_confidence × ocr_confidence. "
            "Single metric representing overall reliability."
        ),
    )
    bbox: BoundingBox = Field(
        ..., description="Bounding box of the plate in the original image."
    )
    class_id: int = Field(
        ..., description="Integer class index from the YOLO model."
    )
    class_name: str = Field(
        ...,
        examples=["plate-number"],
        description="Human-readable class label.",
    )


class TimingInfo(BaseModel):
    """Processing time breakdown for the ANPR pipeline."""

    detection_ms: float = Field(
        ..., ge=0.0, description="YOLOv8 detection stage time (ms)."
    )
    ocr_ms: float = Field(
        ..., ge=0.0, description="Total OCR time for all plates (ms)."
    )
    total_ms: float = Field(
        ..., ge=0.0, description="End-to-end pipeline time (ms)."
    )


class ANPRResponse(BaseModel):
    """
    Response schema for POST /detect — the full ANPR pipeline result.

    Contains recognized plate numbers, confidences, bounding boxes,
    and per-stage timing information.
    """

    success: bool = Field(
        ..., description="Whether the pipeline completed without errors."
    )
    message: str = Field(
        ..., description="Human-readable summary of the result."
    )
    num_plates: int = Field(
        ..., ge=0, description="Total number of plates detected."
    )
    plates: list[PlateResult] = Field(
        default_factory=list,
        description="List of recognized plate results.",
    )
    timing: TimingInfo = Field(
        ..., description="Per-stage processing time breakdown."
    )
    image_width: int = Field(
        ..., ge=1, description="Width of the uploaded image (pixels)."
    )
    image_height: int = Field(
        ..., ge=1, description="Height of the uploaded image (pixels)."
    )


# ─── Generic Error ───────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response body."""

    success: bool = Field(default=False)
    error: str = Field(..., description="Error type / category.")
    detail: str = Field(..., description="Human-readable error message.")
