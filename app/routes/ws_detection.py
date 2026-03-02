# =============================================================================
# app/routes/ws_detection.py — WebSocket Real-time ANPR Detection
# =============================================================================
# PURPOSE:
#   Provides a /ws/detect WebSocket endpoint for real-time video frame
#   detection.  Clients send base64-encoded image frames and receive
#   JSON detection results for every frame.
#
# WHY WEBSOCKETS OVER HTTP POLLING?
#   ┌────────────────────────┬──────────────────────────────────────────┐
#   │ HTTP Polling           │ WebSockets                              │
#   ├────────────────────────┼──────────────────────────────────────────┤
#   │ New TCP conn per frame │ Single persistent connection            │
#   │ HTTP headers overhead  │ Only 2-byte frame header                │
#   │ Client must ask "any?" │ Server pushes result instantly          │
#   │ Latency ≥ poll interval│ Latency = processing time only         │
#   │ Wastes bandwidth idle  │ Zero traffic when idle                  │
#   └────────────────────────┴──────────────────────────────────────────┘
#   For 1-5 FPS video streams, polling wastes 30-50× more bandwidth
#   and adds 100-500 ms extra latency per frame.
#
# FRAME RATE & ACCURACY:
#   • 1 FPS  — suitable for parking lots, toll booths (low speed).
#   • 3–5 FPS — balanced for urban roads, moderate vehicle speed.
#   • 10+ FPS — highway capture (needs GPU for real-time processing).
#   On CPU, each frame takes ~200-800 ms (YOLO + OCR), so 1-2 FPS
#   is the practical maximum without a GPU.
#
# DATABASE LOGGING:
#   Every detection (including live ones) is persisted to SQLite.
#   This means the analytics dashboard, history table, and charts
#   update in real-time.  Historical data supports:
#     • Peak-hour traffic analysis
#     • Repeat-vehicle detection
#     • Long-term accuracy metrics
#
# PROTOCOL:
#   Client → Server:  base64 encoded JPEG/PNG frame  (text message)
#   Server → Client:  JSON detection result           (text message)
#
#   Control messages:
#     Client sends "ping"  → Server replies "pong"     (keepalive)
#     Client sends "close" → Server closes connection  (graceful)
# =============================================================================

import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import SessionLocal
from app.services import anpr_service
from app.services.detection_store import save_detections

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# ---------------------------------------------------------------------------
# Connection manager — handles multiple concurrent WebSocket clients
# ---------------------------------------------------------------------------

class ConnectionManager:
    """
    Manages active WebSocket connections.

    Thread-safe set tracks all live connections so we can:
      • Log active connection count.
      • Broadcast alerts (future enhancement).
      • Gracefully disconnect all on shutdown.
    """

    def __init__(self) -> None:
        self._active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.add(ws)
        logger.info(
            "WebSocket connected  |  client=%s  |  active=%d",
            ws.client, len(self._active),
        )

    def disconnect(self, ws: WebSocket) -> None:
        self._active.discard(ws)
        logger.info(
            "WebSocket disconnected  |  client=%s  |  active=%d",
            ws.client, len(self._active),
        )

    @property
    def active_count(self) -> int:
        return len(self._active)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Frame decoder — base64 → OpenCV BGR numpy array
# ---------------------------------------------------------------------------

def decode_frame(data: str) -> np.ndarray:
    """
    Decode a base64-encoded image frame to a BGR numpy array.

    Accepts both raw base64 and data-URI format:
        data:image/jpeg;base64,/9j/4AAQ...

    Raises
    ------
    ValueError
        If the data is not valid base64 or not a decodable image.
    """
    # Strip data-URI prefix if present
    if "," in data[:100]:
        data = data.split(",", 1)[1]

    try:
        raw_bytes = base64.b64decode(data)
    except Exception as exc:
        raise ValueError(f"Invalid base64 data: {exc}") from exc

    buf = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(buf, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image from base64 data.")

    return image


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/detect")
async def ws_detect(websocket: WebSocket):
    """
    Real-time ANPR detection over WebSocket.

    Protocol
    --------
    1. Client connects → server accepts.
    2. Client sends a text message containing a base64-encoded image frame.
    3. Server runs YOLO + OCR pipeline on the frame.
    4. Server sends JSON result back to client.
    5. Repeat from step 2 until client disconnects.

    Special messages:
      • "ping" → server replies "pong" (keepalive)
      • "close" → server closes connection gracefully.
    """
    await manager.connect(websocket)

    try:
        while True:
            # ── Receive frame ────────────────────────────────────────
            raw = await websocket.receive_text()

            # ── Control messages ─────────────────────────────────────
            if raw.strip().lower() == "ping":
                await websocket.send_text("pong")
                continue

            if raw.strip().lower() == "close":
                logger.info("Client requested close.")
                break

            # ── Decode image ─────────────────────────────────────────
            frame_start = time.perf_counter()
            try:
                image = decode_frame(raw)
            except ValueError as exc:
                await websocket.send_text(json.dumps({
                    "success": False,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
                continue

            # ── Run ANPR pipeline (in thread pool to avoid blocking) ─
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, anpr_service.recognize, image
                )
            except Exception as exc:
                logger.error("ANPR pipeline error on WS frame: %s", exc)
                await websocket.send_text(json.dumps({
                    "success": False,
                    "error": f"Pipeline error: {exc}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
                continue

            # ── Persist to database (non-blocking) ───────────────────
            plates = result.get("plates", [])
            if plates:
                try:
                    db = SessionLocal()
                    try:
                        save_detections(db, result, image_path=None)
                    finally:
                        db.close()
                except Exception as db_exc:
                    logger.warning("WS: DB save failed — %s", db_exc)

            # ── Build response ───────────────────────────────────────
            frame_ms = (time.perf_counter() - frame_start) * 1000
            timestamp = datetime.now(timezone.utc).isoformat()

            response = {
                "success": result.get("success", False),
                "num_plates": result.get("num_plates", 0),
                "plates": [
                    {
                        "plate_text": p.get("plate_text", ""),
                        "confidence": round(p.get("combined_confidence", 0.0), 4),
                        "detection_confidence": round(p.get("detection_confidence", 0.0), 4),
                        "ocr_confidence": round(p.get("ocr_confidence", 0.0), 4),
                        "bbox": p.get("bbox", {}),
                    }
                    for p in plates
                ],
                "timing": result.get("timing", {}),
                "frame_time_ms": round(frame_ms, 1),
                "image_width": result.get("image_width", 0),
                "image_height": result.get("image_height", 0),
                "timestamp": timestamp,
            }

            await websocket.send_text(json.dumps(response))

            logger.debug(
                "WS frame  |  plates=%d  |  frame=%.1f ms",
                len(plates), frame_ms,
            )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally.")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc, exc_info=True)
    finally:
        manager.disconnect(websocket)
        try:
            await websocket.close()
        except Exception:
            pass  # Connection already closed
