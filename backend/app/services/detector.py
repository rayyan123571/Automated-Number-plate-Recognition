# =============================================================================
# app/services/detector.py — YOLOv8 Number Plate Detection Service
# =============================================================================
# PURPOSE:
#   Encapsulates ALL interaction with the Ultralytics YOLOv8 model:
#     1. Model loading (once at startup — heavy operation).
#     2. Inference on a single image.
#     3. Post-processing: extract bounding boxes, confidence, class names.
#
# WHY A DEDICATED SERVICE?
#   • **Single Responsibility** — this file does detection, nothing else.
#   • **Testability** — you can unit-test `detect()` by passing a numpy
#     array without needing FastAPI or HTTP.
#   • **Swap-ability** — want to switch from YOLOv8 to YOLOv9 / RT-DETR?
#     Change only this file; routes stay untouched.
#   • **Lazy Singleton** — the model is loaded once into GPU/CPU memory
#     via `load_model()` and cached for the lifetime of the process.
#
# ARCHITECTURE DECISION:
#   Services sit between routes (transport) and models (data contracts).
#   Routes call services; services return Pydantic-friendly dicts.
# =============================================================================

import logging
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

_model: Any = None
# YOLOv8 model.predict is NOT thread-safe across simultaneous calls — it
# mutates internal state. Serialize calls with a lock to avoid corruption
# when multiple WebSocket frames hit the executor pool concurrently.
_predict_lock = Lock()


def load_model() -> Any:
    """
    Load the YOLOv8 model from disk and cache it in module scope.

    Called once during the FastAPI lifespan startup event.
    Subsequent calls return the cached instance instantly.

    Raises:
        FileNotFoundError: If the weights file does not exist.
        RuntimeError: If Ultralytics cannot load the model.
    """
    global _model

    if _model is not None:
        logger.debug("YOLOv8 model already loaded — returning cached instance.")
        return _model

    model_path = Path(settings.YOLO_MODEL_PATH)
    logger.info("Loading YOLOv8 model from: %s", model_path)

    # ── Validate model file exists ───────────────────────────────────────
    if not model_path.exists():
        error_msg = (
            f"YOLOv8 weights not found at '{model_path}'. "
            f"Place your trained 'best.pt' inside the 'models/' directory, "
            f"or set the YOLO_MODEL_PATH environment variable."
        )
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # ── Load model ───────────────────────────────────────────────────────
    try:
        from ultralytics import YOLO

        _model = YOLO(str(model_path))
        logger.info(
            "YOLOv8 model loaded successfully  |  classes=%s",
            _model.names,
        )
        return _model
    except Exception as exc:
        logger.exception("Failed to load YOLOv8 model.")
        raise RuntimeError(f"YOLOv8 model loading failed: {exc}") from exc


def is_model_loaded() -> bool:
    """Check if the YOLOv8 model is currently loaded in memory."""
    return _model is not None


def get_model() -> Any:
    """
    Return the cached model instance.

    Raises RuntimeError if `load_model()` was never called (i.e. the
    application lifespan did not start properly).
    """
    if _model is None:
        raise RuntimeError(
            "YOLOv8 model is not loaded. "
            "Ensure the application startup (lifespan) ran successfully."
        )
    return _model


def detect(image: np.ndarray) -> list[dict]:
    """
    Run YOLOv8 inference on a single image.

    Parameters
    ----------
    image : np.ndarray
        BGR image as a NumPy array (OpenCV format).

    Returns
    -------
    list[dict]
        Each dict contains:
        - ``bbox``  : [x_min, y_min, x_max, y_max]  (pixel coords, float)
        - ``confidence`` : detection confidence (0–1, float)
        - ``class_id``   : integer class index
        - ``class_name`` : human-readable class label (e.g. "plate-number")

    Raises
    ------
    RuntimeError
        If the model was not loaded prior to calling this function.
    """
    model = get_model()

    logger.debug(
        "Running inference  |  image_shape=%s  |  conf_threshold=%.2f",
        image.shape,
        settings.YOLO_CONFIDENCE_THRESHOLD,
    )

    # ── Run inference (locked: predict is not thread-safe) ──────────────
    # Auto-pick larger imgsz for high-res input (helps small/distant plates).
    h, w = image.shape[:2]
    imgsz = settings.YOLO_IMAGE_SIZE
    if max(h, w) > 1280:
        imgsz = 1280  # larger inference resolution recovers tiny plates

    with _predict_lock:
        results = model.predict(
            source=image,
            conf=settings.YOLO_CONFIDENCE_THRESHOLD,
            imgsz=imgsz,
            iou=0.45,             # NMS IoU threshold (tighter = fewer dupes)
            agnostic_nms=True,    # treat all classes same in NMS
            max_det=20,
            verbose=False,
        )

    # ── Parse results ────────────────────────────────────────────────────
    detections: list[dict] = []

    for result in results:
        boxes = result.boxes  # ultralytics.engine.results.Boxes

        if boxes is None or len(boxes) == 0:
            continue

        for box in boxes:
            # box.xyxy → tensor of shape (1, 4): [x1, y1, x2, y2]
            coords = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = model.names.get(cls_id, "unknown")

            # Filter out character-level detections (e.g. individual 'A' or '7')
            # We only want to pass the full plate crop to the OCR pipeline.
            if cls_name.lower() not in ("plate", "plate-number", "license_plate"):
                continue

            detections.append(
                {
                    "bbox": {
                        "x_min": round(coords[0], 2),
                        "y_min": round(coords[1], 2),
                        "x_max": round(coords[2], 2),
                        "y_max": round(coords[3], 2),
                    },
                    "confidence": round(conf, 4),
                    "class_id": cls_id,
                    "class_name": cls_name,
                }
            )

    logger.info("Detection complete  |  plates_found=%d", len(detections))
    return detections
