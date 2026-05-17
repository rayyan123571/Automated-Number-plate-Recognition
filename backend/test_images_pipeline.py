import sys
import os
import cv2
import glob

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services import anpr_service
from app.services import ocr_service
from app.services import detector
import logging

# Set logging to warning to reduce noise
logging.getLogger("app.services").setLevel(logging.WARNING)

def test_images():
    from app.core.config import settings
    settings.YOLO_CONFIDENCE_THRESHOLD = 0.15
    
    image_paths = glob.glob("../images/**/*.jpg", recursive=True) + \
                  glob.glob("../images/**/*.jpeg", recursive=True)
                  
    if not image_paths:
        print("No images found to test.")
        return

    print("Loading YOLOv8 Model...")
    detector.load_model()
    print("Loading EasyOCR...")
    ocr_service.load_ocr_reader()
    print("Models loaded successfully.")

    for path in image_paths:
        print(f"\n[{os.path.basename(path)}]")
        image = cv2.imread(path)
        if image is None:
            print("  Error: Could not read image.")
            continue
            
        try:
            result = anpr_service.recognize(image, is_live=False)
            plates = result.get("plates", [])
            
            if not plates:
                print("  Result: No plates detected.")
            else:
                for i, p in enumerate(plates):
                    print(f"  Plate {i+1}: {p.get('plate_text')} "
                          f"(Conf: {p.get('combined_confidence', 0):.2f}) "
                          f"Valid: {p.get('is_valid_format')} "
                          f"[{p.get('province')}, {p.get('city')}]")
        except Exception as e:
            print(f"  Error processing image: {e}")

if __name__ == "__main__":
    test_images()