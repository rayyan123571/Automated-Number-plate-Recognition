"""Resume YOLOv8 training from the last checkpoint."""
from ultralytics import YOLO
import time

print("=" * 70)
print("  RESUMING ANPR TRAINING FROM LAST CHECKPOINT")
print("  Previous: 15/50 epochs completed")
print("  Remaining: 35 epochs (with early stopping patience=15)")
print("=" * 70)

start = time.time()

model = YOLO("runs/anpr_train/weights/last.pt")
results = model.train(resume=True)

elapsed = (time.time() - start) / 60
print(f"\nTraining completed in {elapsed:.2f} minutes.")
print("Best weights: runs/anpr_train/weights/best.pt")
print("Last weights: runs/anpr_train/weights/last.pt")
