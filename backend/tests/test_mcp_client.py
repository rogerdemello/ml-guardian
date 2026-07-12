"""Guard tests for the live client — no live DataHub calls."""
import pytest

from backend.app.services.datahub.mcp_client import McpDataHubClient


def test_constructor_requires_token():
    # conftest leaves DATAHUB_TOKEN unset, so live mode must refuse to start
    # rather than silently misbehave.
    with pytest.raises(RuntimeError, match="DATAHUB_TOKEN"):
        McpDataHubClient()
