# =============================================================================
# app/main.py — FastAPI Application Entry Point
# =============================================================================
# PURPOSE:
#   This is the single file that Uvicorn loads:
#       uvicorn app.main:app --reload
#
#   Responsibilities:
#     1. Initialize logging (before anything else logs).
#     2. Load the YOLOv8 model during startup (lifespan context).
#     3. Create the FastAPI app instance with metadata for Swagger UI.
#     4. Enable CORS middleware.
#     5. Mount all routers.
#
# WHY LIFESPAN (not @app.on_event)?
#   `@app.on_event("startup")` is deprecated since FastAPI 0.109.
#   The `lifespan` async context manager is the modern replacement:
#     • Startup code runs before `yield`.
#     • Shutdown / cleanup code runs after `yield`.
#     • Fully typed, testable, and compatible with ASGI servers.
#
# ARCHITECTURE DECISION:
#   `main.py` is a **composition root** — it wires together all layers
#   (core, services, routes) but contains zero business logic itself.
#   If you need to add a new feature, you:
#     1. Create a service in `services/`.
#     2. Create a router in `routes/`.
#     3. Mount the router here.
#   That's it. main.py barely changes.
# =============================================================================

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.database import Base, engine
from app.routes import detection, detections, health, ws_detection
from app.services.detector import load_model
from app.services.ocr_service import load_ocr_reader

# Import ORM models so Base.metadata knows about all tables
import app.models.detection  # noqa: F401

# ---------------------------------------------------------------------------
# Initialize logging FIRST — before any module emits a log message.
# ---------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown logic
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    • **Startup** (before yield):  Load the YOLOv8 model into memory.
    • **Shutdown** (after yield):  Release resources / log shutdown.
    """
    logger.info("=" * 60)
    logger.info("  %s v%s  —  Starting up …", settings.APP_NAME, settings.APP_VERSION)
    logger.info("=" * 60)

    # ── Create database tables ───────────────────────────────────────────
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified / created (SQLite).")
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)

    # ── Load AI model ────────────────────────────────────────────────────
    try:
        load_model()
        logger.info("YOLOv8 model is ready for inference.")
    except FileNotFoundError:
        logger.warning(
            "YOLOv8 model weights not found. "
            "The server will start, but /detect will return 500 "
            "until a valid model is provided."
        )
    except Exception as exc:
        logger.error("Model loading error (non-fatal): %s", exc)

    # ── Load EasyOCR reader ──────────────────────────────────────────────
    try:
        load_ocr_reader(languages=["en"], gpu=False)
        logger.info("EasyOCR reader is ready for text recognition.")
    except Exception as exc:
        logger.error("EasyOCR loading error (non-fatal): %s", exc)

    logger.info("=" * 60)
    logger.info("  Application startup complete!")
    logger.info("=" * 60)

    yield  # ← Application is running and serving requests here

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("Shutting down %s …", settings.APP_NAME)


# ---------------------------------------------------------------------------
# FastAPI Application Instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",        # Swagger UI
    redoc_url="/redoc",      # ReDoc alternative
    openapi_url="/openapi.json",
)


# ---------------------------------------------------------------------------
# Middleware: CORS
# ---------------------------------------------------------------------------
# WHY CORS?
#   In production the frontend (React, Next.js, etc.) will be served
#   from a different origin.  Without CORS the browser blocks requests.
#   We default to `*` (all origins) for development and tighten it via
#   the CORS_ORIGINS env var in production.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Mount Routers
# ---------------------------------------------------------------------------
# Each router is a self-contained module.  Adding a new feature = adding
# one line here.  Prefix can version the API (e.g., prefix="/v1").
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="", tags=["Health"])
app.include_router(detection.router, prefix="", tags=["Detection"])
app.include_router(detections.router, prefix="", tags=["Detection History"])
app.include_router(ws_detection.router, prefix="", tags=["WebSocket"])


# ---------------------------------------------------------------------------
# Root redirect (optional convenience)
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to interactive API docs."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
