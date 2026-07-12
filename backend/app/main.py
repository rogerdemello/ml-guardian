"""ML Guardian FastAPI application.

Serves the JSON API under /api and the static dashboard at /.
Runs fully offline in the default `fixture` mode.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
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


@app.get("/api/health")
def health() -> dict:
    from .services.datahub import get_datahub_client

    try:
        assets = len(get_datahub_client().search("*"))
    except Exception:
        assets = 0
    return {
        "status": "ok",
        "datahub_mode": settings.datahub_mode,
        "llm_enabled": settings.llm_enabled,
        "assets_monitored": assets,
    }


# Serve the dashboard.
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(FRONTEND_DIR / "index.html"))
