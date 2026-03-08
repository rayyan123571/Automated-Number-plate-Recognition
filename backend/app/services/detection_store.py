# =============================================================================
# app/services/detection_store.py — Detection Persistence Service
# =============================================================================
# PURPOSE:
#   Handles saving ANPR pipeline results to the SQLite database.
#   Keeps database logic out of the ANPR pipeline (separation of concerns).
#
# USAGE:
#   Called by the detection route AFTER the ANPR pipeline completes:
#       result = anpr_service.recognize(image)
#       saved = detection_store.save_detections(db, result)
#
# DESIGN:
#   • One row per detected plate (not per image).
#   • Proper rollback on any failure — never leaves the DB in a bad state.
#   • Returns the list of saved Detection ORM objects for response building.
# =============================================================================

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.detection import Detection
from app.models.authorized_vehicle import AuthorizedVehicle
from app.models.unauthorized_log import UnauthorizedLog
from app.schemas.detection_schema import DetectionCreate

logger = logging.getLogger(__name__)


def save_detections(
    db: Session,
    pipeline_result: dict,
    image_path: Optional[str] = None,
    location: str = "Main Gate",
) -> list[Detection]:
    """
    Persist all plate detections from a single ANPR pipeline run.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session (injected via Depends(get_db)).
    pipeline_result : dict
        Raw dict returned by ``anpr_service.recognize()``.
    image_path : str, optional
        File path if the uploaded image was saved to disk.

    Returns
    -------
    list[Detection]
        List of saved ORM objects (with IDs and timestamps populated).
    """
    plates = pipeline_result.get("plates", [])
    timing = pipeline_result.get("timing", {})
    img_w = pipeline_result.get("image_width", 0)
    img_h = pipeline_result.get("image_height", 0)
    total_ms = timing.get("total_ms", 0.0)

    if not plates:
        logger.debug("No plates to save — skipping database insert.")
        return []

    saved: list[Detection] = []

    try:
        for plate in plates:
            plate_text = plate.get("plate_text", "")

            # ── Access control check ─────────────────────────────────
            access_status = None
            alert = None
            if plate_text:
                normalized = plate_text.upper().strip()
                authorized = (
                    db.query(AuthorizedVehicle)
                    .filter(AuthorizedVehicle.plate_number == normalized)
                    .first()
                )
                if authorized:
                    access_status = "AUTHORIZED"
                    alert = "Access Granted — Vehicle Passed"
                else:
                    access_status = "UNAUTHORIZED"
                    alert = "Unauthorized Vehicle Detected"
                    db.add(UnauthorizedLog(
                        plate_number=normalized,
                        location=location,
                    ))

            plate["access_status"] = access_status
            plate["alert"] = alert

            detection = Detection(
                plate_text=plate_text,
                confidence=plate.get("combined_confidence", 0.0),
                detection_confidence=plate.get("detection_confidence", 0.0),
                ocr_confidence=plate.get("ocr_confidence", 0.0),
                image_path=image_path,
                bbox=plate.get("bbox", {}),
                image_width=img_w,
                image_height=img_h,
                camera_location=location,
                processing_time=total_ms,
            )
            db.add(detection)
            saved.append(detection)

        db.commit()

        # Refresh to load DB-generated defaults (id, detected_at)
        for det in saved:
            db.refresh(det)

        plate_texts = [d.plate_text for d in saved if d.plate_text]
        logger.info(
            "Saved %d detection(s) to database: %s",
            len(saved),
            ", ".join(plate_texts) if plate_texts else "(no text recognized)",
        )

        return saved

    except Exception as exc:
        db.rollback()
        logger.error("Failed to save detections to database: %s", exc)
        # Don't re-raise — detection should still return results even if
        # the DB write fails.  Log the error and return an empty list.
        return []


def get_detection_count(db: Session) -> int:
    """Return total number of detection records."""
    from sqlalchemy import func
    return db.query(func.count(Detection.id)).scalar() or 0
