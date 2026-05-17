import os
import re

def update_config():
    f = "backend/app/core/config.py"
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()
    content = content.replace("YOLO_CONFIDENCE_THRESHOLD: float = 0.10", "YOLO_CONFIDENCE_THRESHOLD: float = 0.40")
    if "OCR_CONFIDENCE_FALLBACK_THRESHOLD" not in content:
        content = content.replace("YOLO_IMAGE_SIZE: int = 1280", "YOLO_IMAGE_SIZE: int = 1280\n    OCR_CONFIDENCE_FALLBACK_THRESHOLD: float = 0.50\n    TEMPORAL_SMOOTHING_FRAMES: int = 7")
    with open(f, "w", encoding="utf-8") as file:
        file.write(content)

def update_vehicle_tracker():
    f = "backend/app/services/vehicle_tracker.py"
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()
    
    content = content.replace("from threading import Lock", "from threading import Lock\n\nfrom app.core.config import settings")
    content = content.replace("metadata: dict = field(default_factory=dict)", "metadata: dict = field(default_factory=dict)\n    ocr_history: deque = field(default_factory=lambda: deque(maxlen=settings.TEMPORAL_SMOOTHING_FRAMES))")
    content = content.replace("sharpness: float = 100.0,\n    ) -> dict:", "sharpness: float = 100.0,\n        ocr_confidence: float = 0.0,\n    ) -> dict:")
    content = content.replace("sharpness: float = 100.0,\r\n    ) -> dict:", "sharpness: float = 100.0,\r\n        ocr_confidence: float = 0.0,\r\n    ) -> dict:")
    
    content = content.replace('track.plate_history.append(plate_text or "")\n            track.bbox_history.append(bbox)\n            track.last_seen = now', 'track.plate_history.append(plate_text or "")\n            track.bbox_history.append(bbox)\n            track.ocr_history.append((plate_text or "", ocr_confidence))\n            track.last_seen = now')
    content = content.replace('track.plate_history.append(plate_text or "")\r\n            track.bbox_history.append(bbox)\r\n            track.last_seen = now', 'track.plate_history.append(plate_text or "")\r\n            track.bbox_history.append(bbox)\r\n            track.ocr_history.append((plate_text or "", ocr_confidence))\r\n            track.last_seen = now')

    new_method = '''
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
'''
    if "get_best_plate_text" not in content:
        content = content.replace("    def active_tracks(self) -> list[dict]:", new_method + "\n    def active_tracks(self) -> list[dict]:")
    
    with open(f, "w", encoding="utf-8") as file:
        file.write(content)

def update_ocr_service():
    f = "backend/app/services/ocr_service.py"
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()

    paddle_method = '''
def _run_paddleocr(image: np.ndarray) -> tuple[str, float]:
    """
    Run PaddleOCR on the provided image as a fallback engine.
    
    Args:
        image (np.ndarray): The plate image array.
        
    Returns:
        tuple[str, float]: The recognized text and its confidence score.
        
    Raises:
        RuntimeError: If the paddleocr package is not installed.
    """
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("PaddleOCR is not installed. Cannot use it as a fallback engine.") from exc

    ocr = PaddleOCR(use_angle_cls=False, lang='en', show_log=False)
    results = ocr.ocr(image, cls=False)
    
    if not results or not results[0]:
        return "", 0.0

    best_text = ""
    best_conf = 0.0
    for line in results[0]:
        _, (text, conf) = line
        if conf > best_conf:
            best_conf = conf
            best_text = text

    return best_text, best_conf
'''
    if "_run_paddleocr" not in content:
        content = content.replace("logger = logging.getLogger(__name__)", "logger = logging.getLogger(__name__)\n" + paddle_method)

    replace_ocr = '''    cleaned_text = clean_plate_text(raw_text)

    from app.core.config import settings
    if avg_confidence < settings.OCR_CONFIDENCE_FALLBACK_THRESHOLD:
        p_text, p_conf = _run_paddleocr(plate_image)
        engine = "PaddleOCR"
        raw_text = p_text
        avg_confidence = p_conf
        cleaned_text = clean_plate_text(raw_text)
    else:
        engine = "EasyOCR"
        
    logger.debug("OCR engine: %s | confidence: %.2f", engine, avg_confidence)'''

    if "OCR engine:" not in content:
        content = content.replace("    cleaned_text = clean_plate_text(raw_text)", replace_ocr)
    
    with open(f, "w", encoding="utf-8") as file:
        file.write(content)

def update_pakistan_plate_format():
    f = "backend/app/services/pakistan_plate_format.py"
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()

    new_patterns = r'''    ("COMMERCIAL_REV", re.compile(r"^(\d{3,4})[-\s]?([A-Z]{1,3})$")),
    ("PUNJAB_SMART", re.compile(r"^[A-Z]{3}-\d{3}$")),
    ("SINDH_SMART", re.compile(r"^[A-Z]{2}-\d{3}-\d{3}$")),
    ("ISLAMABAD_SERIES", re.compile(r"^[A-Z]{3}-\d{4}$")),
]

PLATE_PATTERNS = [pat for _, pat in PATTERNS]

def is_valid_pakistan_plate(text: str) -> bool:
    """Return True if text matches any registered plate pattern."""
    return any(p.match(text.strip().upper()) for p in PLATE_PATTERNS)'''

    if "PUNJAB_SMART" not in content:
        content = re.sub(
            r'    \("COMMERCIAL_REV", re\.compile\(r"\^\(\\d\{3,4\}\)\[-\\s\]\?\(\[A-Z\]\{1,3\}\)\$"\)\),\s*\]',
            new_patterns,
            content
        )
    with open(f, "w", encoding="utf-8") as file:
        file.write(content)

update_config()
update_vehicle_tracker()
update_ocr_service()
update_pakistan_plate_format()
print("All files updated successfully.")