"""Live DataHub client that maps ML Guardian's interface onto the real
`mcp-server-datahub` tools.

This is a thin adapter kept behind `DATAHUB_MODE=mcp`. The default offline path
(FixtureDataHubClient) needs none of this. Wiring the actual MCP transport is
intentionally left as the single integration point to complete when a live
DataHub instance is available; the tool names and payload shapes below match the
published `mcp-server-datahub` surface (v0.5.0+):

    read:   search, get_entities, list_lineage, list_schema_fields, get_queries
    write:  add_tags, remove_tags, add_terms, remove_terms

See: https://pypi.org/project/mcp-server-datahub/
"""
from __future__ import annotations

from .base import Asset, DataHubClient


class McpDataHubClient(DataHubClient):
    def __init__(self) -> None:
        from ...config import settings

        if not settings.datahub_token:
            raise RuntimeError(
                "DATAHUB_MODE=mcp requires DATAHUB_TOKEN (and DATAHUB_GMS_URL). "
                "Set them in .env or use DATAHUB_MODE=fixture for offline mode."
            )
        self._settings = settings
        # A real implementation opens an MCP session here, e.g. via the
        # `mcp` python client pointed at `mcp-server-datahub` (stdio/http).
        self._session = None

    def _require_session(self):  # pragma: no cover - integration point
        raise NotImplementedError(
            "Live MCP session not wired in this build. Run in fixture mode "
            "(DATAHUB_MODE=fixture) or complete the MCP transport here by "
            "connecting to mcp-server-datahub and mapping the calls below."
        )

    def search(self, query: str = "*") -> list[Asset]:  # pragma: no cover
        # -> MCP tool: search(query=...)
        self._require_session()
        return []

    def get_entities(self, urns: list[str]) -> list[Asset]:  # pragma: no cover
        # -> MCP tool: get_entities(urns=...)
        self._require_session()
        return []

    def list_lineage(self, urn: str, direction: str = "downstream") -> list[str]:  # pragma: no cover
        # -> MCP tool: list_lineage(urn=..., direction=...)
        self._require_session()
        return []

    def add_tags(self, urn: str, tags: list[str]) -> None:  # pragma: no cover
        # -> MCP tool: add_tags(urn=..., tags=...)
        self._require_session()

    def add_terms(self, urn: str, terms: list[str]) -> None:  # pragma: no cover
        # -> MCP tool: add_terms(urn=..., terms=...)
        self._require_session()
