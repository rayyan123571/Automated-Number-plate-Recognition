# =============================================================================
# app/routes/health.py — Health Check Endpoint
# =============================================================================
# PURPOSE:
#   Provides a lightweight GET /health endpoint used by:
#     • Load balancers (AWS ALB, Nginx) for liveness / readiness probes.
#     • Monitoring dashboards (Grafana, Datadog) for uptime tracking.
#     • Developers to quickly verify the API and model are running.
#
# WHY A SEPARATE ROUTER?
#   Each domain gets its own APIRouter.  This keeps files small,
#   enables independent versioning (e.g., `/v2/health`), and makes
#   it trivial to add middleware or dependencies per-router.
#
# ARCHITECTURE DECISION:
#   Routes are the outermost ring — they depend on services and schemas
#   but contain zero business logic themselves.  A route should be
#   3–10 lines: validate → delegate → respond.
# =============================================================================

import logging

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HealthResponse
from app.services import detector  # import MODULE, not the variable
from app.services import ocr_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router instance — mounted in main.py
# ---------------------------------------------------------------------------
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns API status, version, and model readiness.",
)
async def health_check() -> HealthResponse:
    """
    Lightweight health check.

    Returns 200 with model status — downstream services can decide
    whether a non-loaded model is acceptable (degraded) or critical.
    """
    logger.debug("Health check requested.")

    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        model_loaded=detector._model is not None,
        ocr_loaded=ocr_service._reader is not None,
    )


@router.get("/debug/routes", include_in_schema=False)
async def debug_routes():
    """List all registered routes (temporary debug endpoint)."""
    from app.main import app as _app
    routes = []
    for route in _app.routes:
        path = getattr(route, "path", "?")
        name = getattr(route, "name", "?")
        rtype = type(route).__name__
        routes.append({"path": path, "name": name, "type": rtype})
    return {"routes": routes}
