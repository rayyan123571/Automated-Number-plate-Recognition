import sys
import os
import cv2
import glob

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services import ocr_service

def test_ocr_direct():
    image_paths = glob.glob("../images/**/*.jpg", recursive=True) + \
                  glob.glob("../images/**/*.jpeg", recursive=True)
                  
    if not image_paths:
        print("No images found.")
        return

    ocr_service.load_ocr_reader()

    for path in image_paths:
        print(f"\n[{os.path.basename(path)}]")
        image = cv2.imread(path)
        if image is None:
            continue
            
        result = ocr_service.read_plate_text(image)
        raw = result.get('raw_text', '')
        clean = result.get('cleaned_text', '')
        conf = result.get('confidence', 0)
        
        print(f"  Raw: '{raw}'")
        print(f"  Cleaned: '{clean}' (Conf: {conf:.2f})")

if __name__ == "__main__":
    test_ocr_direct()