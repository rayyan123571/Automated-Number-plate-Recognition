# =============================================================================
# app/services/fake_plate_detector.py — Heuristic fake/tampered plate detector
# =============================================================================
# UNIQUE FEATURE — Pakistan's roads have many tampered/fake plates:
#   * Hand-painted plates with irregular fonts & spacing
#   * Plates with stickers covering characters
#   * Color category mismatch (commercial yellow used on private cars, etc.)
#   * Wrong background color for province
#   * Tinted/blurred protective covers (illegal under Pakistan MV ordinance)
#
# This module runs SHALLOW computer-vision heuristics on the plate crop
# AFTER OCR. It is NOT a deep model — it's a rule-based screening layer
# that flags plates worth manual review. CPU-friendly.
#
# Inputs : plate_crop (BGR), plate_text (cleaned), plate_info (PlateInfo)
# Outputs: dict with `is_suspicious`, `tamper_score`, `reasons`, `color_class`.
# =============================================================================

from __future__ import annotations

import logging

import cv2
import numpy as np

from app.services.pakistan_plate_format import PlateInfo

logger = logging.getLogger(__name__)


# --- color HSV ranges (rough, OpenCV H is 0..179) ---------------------------
COLOR_RANGES = {
    "white":  ((0, 0, 180),     (180, 50,  255)),
    "yellow": ((15, 80, 120),   (40,  255, 255)),
    "green":  ((40, 60, 60),    (85,  255, 255)),
    "blue":   ((95, 80, 60),    (130, 255, 255)),
    "red1":   ((0, 100, 80),    (10,  255, 255)),
    "red2":   ((165, 100, 80),  (180, 255, 255)),
}


def _dominant_background_color(plate_crop: np.ndarray) -> tuple[str, float]:
    """
    Return the dominant background color of a plate crop and its purity 0..1.
    Background is approximated as the border pixels (top + bottom rows).
    """
    h, w = plate_crop.shape[:2]
    if h < 6 or w < 6:
        return ("unknown", 0.0)

    # Top + bottom 15% rows are usually background
    border_rows = max(2, h // 7)
    sample = np.vstack([plate_crop[:border_rows], plate_crop[-border_rows:]])
    hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)

    best_color, best_ratio = "unknown", 0.0
    total = sample.shape[0] * sample.shape[1]
    color_hits = {}
    for color, (lo, hi) in COLOR_RANGES.items():
        mask = cv2.inRange(hsv, np.array(lo), np.array(hi))
        ratio = float(mask.sum()) / 255.0 / total
        color_hits[color] = ratio
    # red wraps; combine
    color_hits["red"] = color_hits.pop("red1") + color_hits.pop("red2")

    for color, ratio in color_hits.items():
        if ratio > best_ratio:
            best_color, best_ratio = color, ratio
    return (best_color, best_ratio)


def _character_spacing_variance(gray_plate: np.ndarray) -> float:
    """
    Standard deviation of horizontal gaps between connected components.
    Genuine Pakistani plates have very uniform spacing; tampered/hand-painted
    plates have high variance.
    Returns the std/mean ratio (coefficient of variation). 0 = perfect.
    """
    if gray_plate.size == 0:
        return 0.0
    _, binary = cv2.threshold(
        gray_plate, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    n, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n < 4:
        return 0.0
    h = gray_plate.shape[0]
    # filter character-sized components
    char_boxes = [
        s for s in stats[1:]
        if s[3] > h * 0.3 and s[2] < gray_plate.shape[1] * 0.4
    ]
    if len(char_boxes) < 3:
        return 0.0
    char_boxes.sort(key=lambda s: s[0])
    gaps = [
        char_boxes[i + 1][0] - (char_boxes[i][0] + char_boxes[i][2])
        for i in range(len(char_boxes) - 1)
    ]
    gaps = [g for g in gaps if g >= 0]
    if not gaps:
        return 0.0
    mean = float(np.mean(gaps))
    std = float(np.std(gaps))
    return std / mean if mean > 0 else 0.0


def _blur_variance(gray_plate: np.ndarray) -> float:
    """Higher = sharper. Used to flag overly blurred / obscured plates."""
    if gray_plate.size == 0:
        return 0.0
    return float(cv2.Laplacian(gray_plate, cv2.CV_64F).var())


def check_plate(
    plate_crop: np.ndarray,
    plate_text: str,
    plate_info: PlateInfo | None,
) -> dict:
    """
    Run all heuristic checks. Returns:
      {
        "is_suspicious": bool,
        "tamper_score": float [0..1],
        "reasons": [str, ...],
        "color_class": str,
        "background_color_ratio": float,
        "spacing_cv": float,
        "sharpness": float,
      }
    """
    reasons: list[str] = []
    score = 0.0

    if plate_crop is None or plate_crop.size == 0:
        return {
            "is_suspicious": False,
            "tamper_score": 0.0,
            "reasons": ["empty crop"],
            "color_class": "unknown",
            "background_color_ratio": 0.0,
            "spacing_cv": 0.0,
            "sharpness": 0.0,
        }

    gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY) if plate_crop.ndim == 3 else plate_crop

    # --- Heuristic 1: dominant color vs declared category --------------
    color, ratio = _dominant_background_color(plate_crop)
    expected_color = None
    if plate_info and plate_info.category != "unknown":
        expected_color = {
            "private": "white",
            "commercial": "yellow",
            "government": "green",
            "diplomatic": "blue",
            "army": "red",
        }.get(plate_info.category)

    if expected_color and color != "unknown" and color != expected_color and ratio > 0.25:
        reasons.append(
            f"color mismatch: detected '{color}' but category '{plate_info.category}' expects '{expected_color}'"
        )
        score += 0.35

    # --- Heuristic 2: format invalidity ------------------------------
    if plate_info and not plate_info.is_valid_format and len(plate_text) >= 4:
        reasons.append("text does not match any Pakistan plate format")
        score += 0.25

    # --- Heuristic 3: character spacing variance --------------------
    spacing_cv = _character_spacing_variance(gray)
    if spacing_cv > 1.2:
        reasons.append(f"irregular character spacing (cv={spacing_cv:.2f})")
        score += 0.25

    # --- Heuristic 4: extreme blur (could be covered) ---------------
    sharpness = _blur_variance(gray)
    if sharpness < 30.0:
        reasons.append(f"very low sharpness ({sharpness:.1f}) — possibly covered/obscured")
        score += 0.15

    # --- Heuristic 5: extreme aspect ratio -------------------------
    h, w = plate_crop.shape[:2]
    if h > 0:
        ar = w / float(h)
        if not (1.5 <= ar <= 6.0):
            reasons.append(f"unusual aspect ratio {ar:.2f}")
            score += 0.1

    score = min(1.0, score)
    return {
        "is_suspicious": score >= 0.4,
        "tamper_score": round(score, 3),
        "reasons": reasons,
        "color_class": color,
        "background_color_ratio": round(ratio, 3),
        "spacing_cv": round(spacing_cv, 3),
        "sharpness": round(sharpness, 1),
    }
