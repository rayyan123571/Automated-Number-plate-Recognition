"""
Dataset augmentation for the YOLO training set.

Adds blur, low-light, glare, and partial-occlusion variants so the
detector learns to localise plates in difficult Pakistani road scenes.

Run from repo root:
    python backend/augment_dataset_blur.py
or pass a custom dataset path:
    python backend/augment_dataset_blur.py --dataset path/to/yolo_dataset/train
"""

import argparse
import math
import random
import shutil
from pathlib import Path

import cv2
import numpy as np


def _motion_blur_kernel(ksize: int, angle_deg: float) -> np.ndarray:
    """
    Build a real directional motion-blur kernel (line at given angle).
    The previous implementation used a Gaussian kernel — which produces
    isotropic blur, NOT motion blur.
    """
    kernel = np.zeros((ksize, ksize), dtype=np.float32)
    center = ksize // 2
    angle_rad = math.radians(angle_deg)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)
    for i in range(ksize):
        offset = i - center
        x = int(round(center + offset * dx))
        y = int(round(center + offset * dy))
        if 0 <= x < ksize and 0 <= y < ksize:
            kernel[y, x] = 1.0
    kernel /= kernel.sum() if kernel.sum() > 0 else 1.0
    return kernel


def apply_motion_blur(img: np.ndarray) -> np.ndarray:
    ksize = random.choice([9, 11, 13, 15])
    angle = random.uniform(-30, 30)  # mostly horizontal motion
    return cv2.filter2D(img, -1, _motion_blur_kernel(ksize, angle))


def apply_gaussian_blur(img: np.ndarray) -> np.ndarray:
    ksize = random.choice([5, 7, 9])
    return cv2.GaussianBlur(img, (ksize, ksize), 0)


def apply_low_light(img: np.ndarray) -> np.ndarray:
    factor = random.uniform(0.35, 0.65)
    dim = (img.astype(np.float32) * factor).clip(0, 255).astype(np.uint8)
    # Sodium-vapor street tint common in Pakistani roads
    if random.random() < 0.5:
        b, g, r = cv2.split(dim)
        r = cv2.add(r, 20)
        g = cv2.add(g, 8)
        dim = cv2.merge([b, g, r])
    return dim


def apply_glare(img: np.ndarray) -> np.ndarray:
    overlay = img.copy()
    h, w = img.shape[:2]
    cx = random.randint(0, w)
    cy = random.randint(0, h)
    radius = random.randint(w // 4, w // 2)
    cv2.circle(overlay, (cx, cy), radius, (255, 255, 255), -1)
    return cv2.addWeighted(overlay, 0.25, img, 0.75, 0)


AUGMENTATIONS = {
    "motion": apply_motion_blur,
    "gauss":  apply_gaussian_blur,
    "lowlight": apply_low_light,
    "glare": apply_glare,
}


def augment(dataset_dir: Path, fraction: float = 0.5) -> None:
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"

    if not images_dir.exists() or not labels_dir.exists():
        print(f"[!] Dataset directories not found: {images_dir} or {labels_dir}")
        return

    images = (
        list(images_dir.glob("*.jpg"))
        + list(images_dir.glob("*.png"))
        + list(images_dir.glob("*.jpeg"))
    )
    print(f"[i] Found {len(images)} source images in {images_dir}")
    print(f"[i] Augmenting ~{int(fraction*100)}% with: {', '.join(AUGMENTATIONS)}")

    count = 0
    for img_path in images:
        if any(tag in img_path.stem for tag in AUGMENTATIONS):
            continue  # already augmented
        if random.random() > fraction:
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue

        aug_name = random.choice(list(AUGMENTATIONS))
        aug_img = AUGMENTATIONS[aug_name](img)

        new_stem = f"{img_path.stem}_{aug_name}"
        out_img = images_dir / f"{new_stem}{img_path.suffix}"
        cv2.imwrite(str(out_img), aug_img)

        label_path = labels_dir / f"{img_path.stem}.txt"
        if label_path.exists():
            shutil.copy2(label_path, labels_dir / f"{new_stem}.txt")
            count += 1

    print(f"[ok] Generated {count} new augmented image/label pairs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("backend/Automatic Plate Number Recognition.v4i.yolov8/train"),
        help="Path to YOLO train split (must contain images/ and labels/).",
    )
    parser.add_argument("--fraction", type=float, default=0.5)
    args = parser.parse_args()
    augment(args.dataset, fraction=args.fraction)
