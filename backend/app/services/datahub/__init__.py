"""DataHub client factory: selects fixture (offline) or MCP (live) backend."""
from __future__ import annotations

from ...config import settings
from .base import DataHubClient


def get_datahub_client() -> DataHubClient:
    if settings.datahub_mode == "mcp":
        from .mcp_client import McpDataHubClient

        return McpDataHubClient()
    from .fixture_client import FixtureDataHubClient

    return FixtureDataHubClient()
