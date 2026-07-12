"""Environment-driven settings for ML Guardian.

All configuration is read once at import time. The app is designed to run with
zero configuration: defaults put it in offline `fixture` mode with a local
SQLite DB and no LLM key required.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = two levels up from this file (backend/app/config.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # DataHub integration
    datahub_mode: str = "fixture"  # "fixture" | "mcp"
    datahub_gms_url: str = "http://localhost:8080"
    datahub_token: str = ""
    datahub_ui_url: str = "http://localhost:9002"

    # LLM (optional) — Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Storage
    database_url: str = "sqlite:///./ml_guardian.db"

    # Risk thresholds
    freshness_warn_ratio: float = 1.0
    quality_null_rate_max: float = 0.05

    # Downstream-impact severity weighting: an incident feeding a live ML model
    # or dashboard is more dangerous than one feeding nothing.
    downstream_model_boost: int = 15
    downstream_dashboard_boost: int = 5

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
