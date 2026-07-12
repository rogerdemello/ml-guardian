"""ML Guardian FastAPI application.

Serves the JSON API under /api and the static dashboard at /.
Runs fully offline in the default `fixture` mode.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT, settings
from .db import init_db
from .errors import ConfigurationError
from .routes import incidents, risk_scores, scan, simulate

logger = logging.getLogger("ml_guardian")

FRONTEND_DIR = REPO_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ML Guardian",
    description="Metadata-driven ML risk sentinel built on DataHub.",
    version="0.1.0",
    lifespan=lifespan,
)

# API routes under /api.
for module in (scan, incidents, risk_scores, simulate):
    app.include_router(module.router, prefix="/api")


@app.exception_handler(ConfigurationError)
async def _config_error_handler(request: Request, exc: ConfigurationError) -> JSONResponse:
    # Turn setup failures (e.g. live mode without a DataHub) into an actionable
    # 503. Only the curated `detail` is returned — never raw exception internals.
    logger.warning("configuration error: %s", exc.detail)
    return JSONResponse(status_code=503, content={"detail": exc.detail})


@app.get("/api/health")
def health() -> dict:
    from .services.datahub import get_datahub_client

    status, assets, error = "ok", 0, None
    try:
        assets = len(get_datahub_client().search("*"))
    except ConfigurationError as exc:
        status, error = "degraded", exc.detail  # curated, user-safe
    except Exception:
        logger.exception("health check failed")
        status, error = "degraded", "DataHub is unreachable or misconfigured."
    return {
        "status": status,
        "datahub_mode": settings.datahub_mode,
        "llm_enabled": settings.llm_enabled,
        "assets_monitored": assets,
        "error": error,
    }


# Serve the dashboard.
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(FRONTEND_DIR / "index.html"))
