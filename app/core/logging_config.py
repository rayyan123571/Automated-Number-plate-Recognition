# =============================================================================
# app/core/logging_config.py — Structured Logging Setup
# =============================================================================
# PURPOSE:
#   Configures Python's standard `logging` module with:
#     • Structured, human-readable format for development.
#     • JSON-style structured format for production log aggregation.
#     • Rotating file handler so logs don't eat disk space.
#     • Console (stdout) handler for Docker / cloud-native deploys.
#
# WHY NOT LOGURU / STRUCTLOG?
#   The stdlib `logging` module is dependency-free, universally supported,
#   and fully compatible with Uvicorn's internal loggers.  We keep the
#   dependency footprint minimal; Loguru can be swapped in later without
#   changing any call-site (`logger.info(...)` is the same API).
#
# ARCHITECTURE DECISION:
#   Logging config is in `core/` so it's initialized once at startup
#   (in `main.py`) before any other module emits a log.
# =============================================================================

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)       # Create logs/ dir if missing

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """
    Initialize the root logger with console + rotating file handlers.

    Call this **once** at application startup inside the lifespan context
    before any route or service is loaded.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # ── Root logger ──────────────────────────────────────────────────────
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Prevent duplicate handlers on hot-reload
    if root_logger.handlers:
        root_logger.handlers.clear()

    # ── Formatter ────────────────────────────────────────────────────────
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Console handler (stdout) ─────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ── Rotating file handler ────────────────────────────────────────────
    file_handler = RotatingFileHandler(
        filename=LOG_DIR / "anpr.log",
        maxBytes=10 * 1024 * 1024,   # 10 MB per file
        backupCount=5,                # Keep last 5 rotated files
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # ── Silence noisy third-party loggers ────────────────────────────────
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    root_logger.info(
        "Logging initialized  |  level=%s  |  log_file=%s",
        settings.LOG_LEVEL,
        LOG_DIR / "anpr.log",
    )
