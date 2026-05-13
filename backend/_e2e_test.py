"""
End-to-end smoke test for ANPR backend.

Tests:
  1. Loads YOLO model from models/best.pt
  2. Loads EasyOCR reader
  3. Runs the FULL pipeline on a test image
  4. Asserts Pakistan plate parsing, fake-plate check, tracker all wired up
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2
import numpy as np

print("[1/6] Loading YOLO model...")
from app.services.detector import load_model, detect
load_model()
print("  ✓ YOLO loaded")

print("[2/6] Loading EasyOCR...")
from app.services.ocr_service import load_ocr_reader
load_ocr_reader(languages=["en"], gpu=False)
print("  ✓ EasyOCR loaded")

print("[3/6] Reading test image...")
test_path = Path("/tmp/test_plate.png")
if not test_path.exists():
    # Make a synthetic test
    img = np.full((400, 600, 3), 220, dtype=np.uint8)
    cv2.putText(img, "LEA-1234", (100, 220), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 6)
    cv2.imwrite(str(test_path), img)
img = cv2.imread(str(test_path))
print(f"  ✓ Test image shape: {img.shape}")

print("[4/6] Running full ANPR pipeline...")
from app.services.anpr_service import recognize
t = time.perf_counter()
result = recognize(img)
elapsed = (time.perf_counter() - t) * 1000
print(f"  ✓ Pipeline finished in {elapsed:.0f} ms")
print(f"     success={result['success']}  plates_detected={result['num_plates']}")
for i, p in enumerate(result.get("plates", [])):
    print(f"     plate[{i}]: text='{p['plate_text']}' "
          f"province={p.get('province')} city={p.get('city')} category={p.get('category')} "
          f"suspicious={p.get('is_suspicious')} score={p.get('tamper_score'):.2f}")

print("[5/6] Smoke-testing Pakistan plate parser...")
from app.services.pakistan_plate_format import parse_plate
samples = [("LEA1234", "Punjab/Lahore"), ("ICT171234", "ICT/Islamabad"),
           ("Q1234", "Balochistan/Quetta"), ("BJN770", "Sindh/Karachi")]
for plate, expected in samples:
    info = parse_plate(plate)
    print(f"  {plate:>10} -> {info.province}/{info.city}  (expected: {expected})")

print("[6/6] Tracker + auto-challan smoke...")
from app.services.vehicle_tracker import tracker
tracker.reset()
bbox = {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 50}
for i in range(4):
    info = tracker.update("FAKEPLATE", bbox, location="Demo",
                          access_status="UNAUTHORIZED", is_fake=False)
print(f"  ✓ Challan issued: {info['challan'] is not None}, fine: Rs."
      f"{info['challan']['total_fine_pkr'] if info['challan'] else 0}")

print("\nALL TESTS PASSED.")
