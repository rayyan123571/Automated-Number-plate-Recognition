# =============================================================================
# app/services/detection_store.py — Detection Persistence Service
# =============================================================================
# Saves ANPR pipeline results to DB and runs:
#   * Fuzzy access-control match (Levenshtein) to tolerate O/0, I/1 misreads
#   * 30-second de-duplication window for UnauthorizedLog
#   * Vehicle-tracker update (auto-challan when violations triggered)
# =============================================================================

from __future__ import annotations

import logging
import time
import os
import cv2
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.detection import Detection
from app.models.authorized_vehicle import AuthorizedVehicle
from app.models.unauthorized_log import UnauthorizedLog
from app.services.vehicle_tracker import tracker

logger = logging.getLogger(__name__)

# Ensure evidence directory exists
EVIDENCE_DIR = Path(settings.EVIDENCE_STORAGE_PATH)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _levenshtein(a: str, b: str) -> int:
    """Minimal Levenshtein distance — adequate for short plate strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def _normalize_plate(text: str) -> str:
    """Strip whitespace/hyphens/dots, uppercase."""
    return "".join(ch for ch in text.upper() if ch.isalnum())


def _find_authorized(db: Session, plate_text: str) -> AuthorizedVehicle | None:
    """Match against authorized list with fuzzy tolerance for OCR errors."""
    normalized = _normalize_plate(plate_text)
    if not normalized:
        return None

    # Try exact match on normalized text first
    exact = (
        db.query(AuthorizedVehicle)
        .filter(AuthorizedVehicle.plate_number == normalized)
        .first()
    )
    if exact:
        return exact

    # Fuzzy match within configured distance
    max_dist = settings.ANPR_AUTHORIZED_FUZZY_MAX_DISTANCE
    if max_dist <= 0:
        return None

    candidates = db.query(AuthorizedVehicle).all()
    best, best_d = None, max_dist + 1
    for vehicle in candidates:
        d = _levenshtein(normalized, _normalize_plate(vehicle.plate_number))
        if d < best_d:
            best, best_d = vehicle, d
    if best and best_d <= max_dist:
        logger.info(
            "Fuzzy auth match: '%s' -> '%s' (distance=%d)",
            normalized, best.plate_number, best_d,
        )
        return best
    return None


def _recent_unauthorized_exists(
    db: Session,
    plate_number: str,
    location: str,
    window_seconds: int,
) -> bool:
    """Return True if same plate was logged at same location within window."""
    if window_seconds <= 0:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    recent = (
        db.query(UnauthorizedLog)
        .filter(
            UnauthorizedLog.plate_number == plate_number,
            UnauthorizedLog.location == location,
            UnauthorizedLog.detected_at >= cutoff,
        )
        .first()
    )
    return recent is not None


def save_detections(
    db: Session,
    pipeline_result: dict,
    image_path: Optional[str] = None,
    location: str = "Main Gate",
) -> list[Detection]:
    """Persist all plate detections from a single ANPR pipeline run."""
    plates = pipeline_result.get("plates", [])
    timing = pipeline_result.get("timing", {})
    img_w = pipeline_result.get("image_width", 0)
    img_h = pipeline_result.get("image_height", 0)
    total_ms = timing.get("total_ms", 0.0)

    if not plates:
        return []

    saved: list[Detection] = []
    dedup_window = (
        settings.ANPR_DEDUP_WINDOW_SECONDS
        if settings.ANPR_ENABLE_DEDUPLICATION
        else 0
    )

    try:
        for plate in plates:
            plate_text = plate.get("plate_text", "")

            # ── Access control (fuzzy) ──────────────────────────────
            access_status = None
            alert = None
            if plate_text:
                normalized = _normalize_plate(plate_text)
                authorized = _find_authorized(db, plate_text)
                if authorized:
                    access_status = "AUTHORIZED"
                    alert = "Access Granted — Vehicle Passed"
                else:
                    access_status = "UNAUTHORIZED"
                    alert = "Unauthorized Vehicle Detected"
                    if not _recent_unauthorized_exists(db, normalized, location, dedup_window):
                        db.add(UnauthorizedLog(
                            plate_number=normalized,
                            location=location,
                        ))

            plate["access_status"] = access_status
            plate["alert"] = alert

            # ── Tracker + auto-challan ──────────────────────────────
            try:
                bbox = plate.get("bbox", {})
                track_info = tracker.update(
                    plate_text=plate_text,
                    bbox=bbox,
                    location=location,
                    access_status=access_status,
                    is_fake=plate.get("is_suspicious", False),
                    sharpness=100.0,  # populated from fake_info upstream if available
                )
                plate["track_id"] = track_info.get("track_id")
                plate["challan"] = track_info.get("challan")

                # STABILITY FIX: Use majority-voted "stable_plate" for the live UI
                if track_info.get("stable_plate"):
                    plate["plate_text"] = track_info["stable_plate"]
                    plate_text = track_info["stable_plate"]
            except Exception as exc:
                logger.warning("Tracker update failed: %s", exc)

            # ── Evidence Storage ────────────────────────────────────
            crop_path = None
            plate_crop = plate.pop("plate_crop", None)
            if plate_crop is not None and plate_text:
                try:
                    filename = f"crop_{int(time.time())}_{plate.get('track_id', 'new')}_{_normalize_plate(plate_text)}.jpg"
                    save_path = EVIDENCE_DIR / filename
                    cv2.imwrite(str(save_path), plate_crop)
                    crop_path = str(save_path)
                except Exception as save_exc:
                    logger.warning("Failed to save plate evidence: %s", save_exc)

            detection = Detection(
                plate_text=plate_text,
                confidence=plate.get("combined_confidence", 0.0),
                detection_confidence=plate.get("detection_confidence", 0.0),
                ocr_confidence=plate.get("ocr_confidence", 0.0),
                image_path=image_path,
                crop_path=crop_path,
                bbox=plate.get("bbox", {}),
                image_width=img_w,
                image_height=img_h,
                camera_location=location,
                processing_time=total_ms,
            )
            db.add(detection)
            saved.append(detection)

        db.commit()
        for det in saved:
            db.refresh(det)

        return saved

    except Exception as exc:
        db.rollback()
        logger.error("Failed to save detections: %s", exc)
        return []


def get_detection_count(db: Session) -> int:
    from sqlalchemy import func
    return db.query(func.count(Detection.id)).scalar() or 0
