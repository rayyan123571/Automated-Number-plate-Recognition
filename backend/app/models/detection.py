# =============================================================================
# app/models/detection.py — Detection ORM Model (SQLAlchemy)
# =============================================================================
# PURPOSE:
#   Defines the `detections` table in SQLite.  Every ANPR pipeline result
#   is persisted here so the frontend can query detection history.
#
# WHY UUID PRIMARY KEY?
#   • Globally unique — safe for distributed systems, merges, or future
#     multi-instance deployments.
#   • Non-sequential — doesn't leak information about record count or order.
#   • Generated client-side — no need to query DB for the next ID.
#
# WHY INDEX ON detected_at?
#   History queries always ORDER BY detected_at DESC with LIMIT/OFFSET.
#   Without an index, SQLite must scan the entire table and sort in memory.
#   With a B-tree index, the DB walks the index in order — O(log n) seek.
# =============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.types import JSON

from app.core.database import Base


class Detection(Base):
    """
    ORM model for the ``detections`` table.

    Each row represents one recognized license plate from a single
    detection run.  Multiple plates from the same image produce
    multiple rows.
    """

    __tablename__ = "detections"

    # ── Primary key ──────────────────────────────────────────────────────
    id: str = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID v4 primary key",
    )

    # ── Plate recognition data ───────────────────────────────────────────
    plate_text: str = Column(
        String(20),
        nullable=False,
        default="",
        index=True,
        comment="Cleaned plate number (e.g., ABC1234)",
    )
    confidence: float = Column(
        Float,
        nullable=False,
        default=0.0,
        comment="Combined confidence (detection × OCR), 0.0–1.0",
    )
    detection_confidence: float = Column(
        Float,
        nullable=False,
        default=0.0,
        comment="YOLOv8 bounding-box confidence, 0.0–1.0",
    )
    ocr_confidence: float = Column(
        Float,
        nullable=False,
        default=0.0,
        comment="EasyOCR text confidence, 0.0–1.0",
    )

    # ── Image / spatial data ─────────────────────────────────────────────
    image_path: str = Column(
        String(500),
        nullable=True,
        default=None,
        comment="Path to the source image (if saved to disk)",
    )
    bbox: dict = Column(
        JSON,
        nullable=False,
        comment="Bounding box {x_min, y_min, x_max, y_max} in pixels",
    )
    image_width: int = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Source image width in pixels",
    )
    image_height: int = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Source image height in pixels",
    )
    # ── Location ─────────────────────────────────────────────────────
    camera_location: str = Column(
        String(200),
        nullable=True,
        default="Gate 1",
        comment="Camera / gate location identifier",
    )
    # ── Timing ───────────────────────────────────────────────────────────
    processing_time: float = Column(
        Float,
        nullable=False,
        default=0.0,
        comment="Total pipeline processing time in milliseconds",
    )

    # ── Timestamp ────────────────────────────────────────────────────────
    detected_at: datetime = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="UTC timestamp of detection",
    )

    # ── Table-level indexes ──────────────────────────────────────────────
    __table_args__ = (
        Index("ix_detections_detected_at_desc", detected_at.desc()),
        Index("ix_detections_plate_text_lower", "plate_text"),
    )

    def __repr__(self) -> str:
        return (
            f"<Detection(id={self.id!r}, plate={self.plate_text!r}, "
            f"conf={self.confidence:.3f}, at={self.detected_at})>"
        )
