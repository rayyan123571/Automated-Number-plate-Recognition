# =============================================================================
# app/core/config.py — Centralized Application Configuration
# =============================================================================
# PURPOSE:
#   Single source of truth for ALL application settings.  Uses Pydantic
#   Settings so that every value can be overridden via environment
#   variables or a `.env` file — zero hard-coded secrets.
#
# WHY PYDANTIC SETTINGS?
#   • Automatic type validation & casting (str → int, str → bool).
#   • IDE auto-complete on `settings.<field>`.
#   • Immutable after load — prevents accidental mutation at runtime.
#   • `.env` support via `model_config` — no extra library needed.
#
# ARCHITECTURE DECISION:
#   Config lives in `core/` because every other layer (routes, services,
#   utils) may depend on it, but it depends on nothing inside `app/`.
#   This is the innermost dependency ring in Clean Architecture.
# =============================================================================

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment variables / .env file.

    Each field maps 1-to-1 to an env var (case-insensitive).
    Example:  `APP_NAME` env var  →  `settings.APP_NAME`
    """

    # ── General ──────────────────────────────────────────────────────────
    APP_NAME: str = "ANPR System"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Automated Number Plate Recognition API"
    DEBUG: bool = False

    # ── Server ───────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── CORS ─────────────────────────────────────────────────────────────
    # Comma-separated origins — parsed into a list below.
    CORS_ORIGINS: str = "*"

    # ── AI / YOLOv8 ─────────────────────────────────────────────────────
    # Path to the trained YOLOv8 weights file (.pt).
    # Default points to the project-level `models/` directory.
    YOLO_MODEL_PATH: str = str(
        Path(__file__).resolve().parents[2] / "models" / "best.pt"
    )
    # Confidence threshold for detections (0.0 – 1.0).
    YOLO_CONFIDENCE_THRESHOLD: float = 0.40
    # Max image dimension (pixels) — larger images are resized automatically.
    # Increased to 1280 to catch tiny plates in uploaded 720p/1080p videos
    YOLO_IMAGE_SIZE: int = 1280
    OCR_CONFIDENCE_FALLBACK_THRESHOLD: float = 0.50
    TEMPORAL_SMOOTHING_FRAMES: int = 7

    # ── ANPR post-processing quality gates ─────────────────────────────
    # Reject OCR reads that are too weak/noisy to trust.
    ANPR_MIN_PLATE_CHARS: int = 2
    ANPR_MAX_PLATE_CHARS: int = 15
    ANPR_MIN_OCR_CONFIDENCE: float = 0.05
    ANPR_MIN_COMBINED_CONFIDENCE: float = 0.01

    # ── Accuracy / new features toggles ─────────────────────────────────
    ANPR_ENABLE_DESKEW: bool = False             # Hough-line based rotation correction (Slow on CPU)
    ANPR_ENABLE_SUPER_RES: bool = False          # Up-scale small plates 2x before OCR (Very slow on CPU)
    ANPR_ENABLE_DEDUPLICATION: bool = True      # Suppress repeat unauthorized logs
    ANPR_DEDUP_WINDOW_SECONDS: int = 30
    ANPR_FAKE_PLATE_CHECK: bool = True
    ANPR_DEBUG_SAVE_PLATES: bool = False        # Was always-on; now opt-in via env
    EVIDENCE_STORAGE_PATH: str = "uploads/evidence"

    # ── Pakistan plate fuzzy match (Levenshtein distance) ───────────────
    ANPR_AUTHORIZED_FUZZY_MAX_DISTANCE: int = 1  # 0 = exact; 1 tolerates O/0, I/1

    # ── Training ─────────────────────────────────────────────────────
    TRAINING_DATA_YAML: str = str(
        Path(__file__).resolve().parents[2] / "dataset" / "data.yaml"
    )
    TRAINING_EPOCHS: int = 50
    TRAINING_BATCH_SIZE: int = 16
    TRAINING_PATIENCE: int = 15
    # ── Logging ──────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Database (SQLite) ────────────────────────────────────────────────
    # File-based SQLite — no external server required.
    # Override via DATABASE_URL env var for PostgreSQL in production.
    DATABASE_URL: str = "sqlite:///./anpr.db"

    # ── Pydantic v2 model config ─────────────────────────────────────────
    model_config = {
        "env_file": ".env",          # Load from .env at project root
        "env_file_encoding": "utf-8",
        "case_sensitive": False,      # APP_NAME == app_name in env
        "extra": "ignore",            # Silently ignore unknown env vars
    }

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS into a Python list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# ---------------------------------------------------------------------------
# Singleton instance — import this everywhere:
#     from app.core.config import settings
# ---------------------------------------------------------------------------
settings = Settings()
