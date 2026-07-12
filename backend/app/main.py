"""ML Guardian FastAPI application.

Serves the JSON API under /api and the static dashboard at /.
Runs fully offline in the default `fixture` mode.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT, settings
from .db import init_db
from .routes import incidents, risk_scores, scan, simulate

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


@app.exception_handler(RuntimeError)
async def _runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    # Turn configuration/setup failures (e.g. live mode without a DataHub) into an
    # actionable 503 instead of a cryptic 500.
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict:
    from .services.datahub import get_datahub_client

    status, assets, error = "ok", 0, None
    try:
        assets = len(get_datahub_client().search("*"))
    except Exception as exc:  # DataHub unreachable / misconfigured in live mode
        status, error = "degraded", str(exc)
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
