# =============================================================================
# app/services/vehicle_tracker.py — Lightweight in-memory vehicle tracker
# =============================================================================
# UNIQUE FEATURE — Single-camera vehicle tracking with auto-challan logic.
#
# Production ANPR systems use DeepSORT/ByteTrack with re-id features; that
# requires extra ML weights and GPU. For a CPU semester project this module
# uses a simple but effective approach:
#
#   * Each tracked vehicle is keyed by its (normalized) plate text.
#   * IoU between successive bounding boxes is used to associate detections
#     with existing tracks when plate text is ambiguous.
#   * Temporal voting (mode of last N OCR reads per track) raises accuracy
#     and protects against transient OCR misreads on video streams.
#   * Auto-challan rules are triggered when policy is violated:
#       - fake/tampered plate (from fake_plate_detector)
#       - repeated UNAUTHORIZED appearance at same gate
#       - tinted/obscured plate (low sharpness over multiple frames)
#       - speed (placeholder — needs calibrated camera, exposed in API)
#
# State is in-memory only — for production, persist tracks to a database
# or Redis. For a single-station demo it is sufficient.
# =============================================================================

from __future__ import annotations

import logging
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from threading import Lock

from app.core.config import settings

logger = logging.getLogger(__name__)


TRACK_TTL_SECONDS = 60.0       # tracks idle longer than this are dropped
VOTING_WINDOW = 7              # last N reads used for plate-text voting
IOU_THRESHOLD = 0.3            # association threshold when text is ambiguous
REPEAT_UNAUTH_THRESHOLD = 3    # # times unauthorized triggers challan


@dataclass
class Track:
    track_id: str
    plate_history: deque
    bbox_history: deque
    first_seen: float
    last_seen: float
    location: str
    unauthorized_count: int = 0
    challan_issued: bool = False
    metadata: dict = field(default_factory=dict)
    ocr_history: deque = field(default_factory=lambda: deque(maxlen=settings.TEMPORAL_SMOOTHING_FRAMES))

    def stable_plate(self) -> str:
        """Return the most common plate text in the voting window."""
        valid = [p for p in self.plate_history if p]
        if not valid:
            return ""
        return Counter(valid).most_common(1)[0][0]


def _iou(b1: dict, b2: dict) -> float:
    """Standard IoU between two bbox dicts."""
    x1 = max(b1["x_min"], b2["x_min"])
    y1 = max(b1["y_min"], b2["y_min"])
    x2 = min(b1["x_max"], b2["x_max"])
    y2 = min(b1["y_max"], b2["y_max"])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    a1 = (b1["x_max"] - b1["x_min"]) * (b1["y_max"] - b1["y_min"])
    a2 = (b2["x_max"] - b2["x_min"]) * (b2["y_max"] - b2["y_min"])
    union = a1 + a2 - inter
    return inter / union if union > 0 else 0.0


class VehicleTracker:
    """Thread-safe singleton tracker."""

    def __init__(self):
        self._tracks: dict[str, Track] = {}
        self._lock = Lock()

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #
    def update(
        self,
        plate_text: str,
        bbox: dict,
        location: str = "unknown",
        access_status: str | None = None,
        is_fake: bool = False,
        sharpness: float = 100.0,
        ocr_confidence: float = 0.0,
    ) -> dict:
        """
        Associate a single detection with an existing or new track.
        Returns the track summary including any triggered auto-challan.
        """
        now = time.time()
        with self._lock:
            self._evict_stale(now)

            track = self._match_track(plate_text, bbox)
            if track is None:
                track = Track(
                    track_id=str(uuid.uuid4())[:8],
                    plate_history=deque(maxlen=VOTING_WINDOW),
                    bbox_history=deque(maxlen=VOTING_WINDOW),
                    first_seen=now, last_seen=now,
                    location=location,
                )
                self._tracks[track.track_id] = track

            track.plate_history.append(plate_text or "")
            track.bbox_history.append(bbox)
            track.ocr_history.append((plate_text or "", ocr_confidence))
            track.last_seen = now

            if access_status == "UNAUTHORIZED":
                track.unauthorized_count += 1

            track.metadata["last_is_fake"] = is_fake
            track.metadata["last_sharpness"] = sharpness

            # ── Auto-challan decision ────────────────────────────────
            challan = self._evaluate_challan(track, is_fake=is_fake, sharpness=sharpness)

            return {
                "track_id": track.track_id,
                "stable_plate": track.stable_plate(),
                "is_first_seen": (now - track.first_seen) < 0.1,
                "seconds_since_first_seen": round(now - track.first_seen, 2),
                "frame_count": len(track.plate_history),
                "unauthorized_count": track.unauthorized_count,
                "challan": challan,
            }


    def get_best_plate_text(self, track_id: str) -> str | None:
        """
        Get the most frequently recognized plate text for a given track ID over the temporal smoothing window.
        
        Args:
            track_id (str): The unique identifier for the track.
            
        Returns:
            str | None: The majority-voted plate text, or None if the history is empty. Ties are broken by highest OCR confidence.
        """
        with self._lock:
            track = self._tracks.get(track_id)
            if not track or not track.ocr_history:
                return None
                
            valid_reads = [(text, conf) for text, conf in track.ocr_history if text]
            if not valid_reads:
                return None
                
            counts = Counter(text for text, conf in valid_reads)
            max_count = max(counts.values())
            candidates = [text for text, count in counts.items() if count == max_count]
            
            if len(candidates) == 1:
                return candidates[0]
                
            best_text = candidates[0]
            best_conf = -1.0
            for text, conf in valid_reads:
                if text in candidates and conf > best_conf:
                    best_conf = conf
                    best_text = text
                    
            return best_text

    def active_tracks(self) -> list[dict]:
        """Inspect current tracker state (for /tracks endpoint)."""
        now = time.time()
        with self._lock:
            self._evict_stale(now)
            return [
                {
                    "track_id": t.track_id,
                    "stable_plate": t.stable_plate(),
                    "first_seen": t.first_seen,
                    "last_seen": t.last_seen,
                    "frame_count": len(t.plate_history),
                    "unauthorized_count": t.unauthorized_count,
                    "challan_issued": t.challan_issued,
                    "location": t.location,
                }
                for t in self._tracks.values()
            ]

    def reset(self) -> None:
        with self._lock:
            self._tracks.clear()

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #
    def _evict_stale(self, now: float) -> None:
        stale = [tid for tid, t in self._tracks.items() if now - t.last_seen > TRACK_TTL_SECONDS]
        for tid in stale:
            del self._tracks[tid]

    def _match_track(self, plate_text: str, bbox: dict) -> Track | None:
        # First try exact plate match (most reliable)
        if plate_text:
            for t in self._tracks.values():
                if plate_text in t.plate_history:
                    return t
        # Fall back to IoU on most recent bbox
        best, best_iou = None, 0.0
        for t in self._tracks.values():
            if not t.bbox_history:
                continue
            iou = _iou(t.bbox_history[-1], bbox)
            if iou > best_iou:
                best_iou, best = iou, t
        if best_iou >= IOU_THRESHOLD:
            return best
        return None

    def _evaluate_challan(
        self,
        track: Track,
        is_fake: bool,
        sharpness: float,
    ) -> dict | None:
        if track.challan_issued:
            return None

        violations = []
        if is_fake:
            violations.append({
                "code": "FAKE_PLATE",
                "description": "Suspected fake / tampered number plate (MV Ordinance 1965, Sec 92).",
                "fine_pkr": 5000,
            })
        if track.unauthorized_count >= REPEAT_UNAUTH_THRESHOLD:
            violations.append({
                "code": "REPEAT_UNAUTHORIZED",
                "description": (
                    f"Vehicle appeared as UNAUTHORIZED {track.unauthorized_count} times "
                    "at access-controlled location."
                ),
                "fine_pkr": 2000,
            })
        avg_sharp = float(track.metadata.get("last_sharpness", 100.0))
        if avg_sharp < 25.0 and len(track.plate_history) >= 3:
            violations.append({
                "code": "OBSCURED_PLATE",
                "description": "Plate obscured / tinted / dirty — illegal under MV rules.",
                "fine_pkr": 1500,
            })

        if not violations:
            return None

        track.challan_issued = True
        challan = {
            "challan_id": str(uuid.uuid4())[:8].upper(),
            "issued_at": time.time(),
            "track_id": track.track_id,
            "plate_text": track.stable_plate(),
            "location": track.location,
            "violations": violations,
            "total_fine_pkr": sum(v["fine_pkr"] for v in violations),
        }
        logger.warning(
            "AUTO-CHALLAN %s issued for plate '%s' total fine=Rs.%d violations=%s",
            challan["challan_id"], challan["plate_text"],
            challan["total_fine_pkr"],
            [v["code"] for v in violations],
        )
        return challan


# Singleton
tracker = VehicleTracker()
