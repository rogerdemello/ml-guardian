"""DataHub client factory: selects fixture (offline) or MCP (live) backend."""
from __future__ import annotations

from functools import lru_cache

from ...config import settings
from .base import DataHubClient


@lru_cache(maxsize=1)
def get_datahub_client() -> DataHubClient:
    """Return a cached client. Fixture mode applies simulation overrides at
    read-time, so a cached singleton stays correct; MCP mode reuses one session."""
    if settings.datahub_mode == "mcp":
        from .mcp_client import McpDataHubClient

        return McpDataHubClient()
    from .fixture_client import FixtureDataHubClient

    return FixtureDataHubClient()
