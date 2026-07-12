"""DataHub client interface and shared data shapes.

The rest of the app depends only on this interface, so swapping fixtures for a
live DataHub (via MCP) is a one-line change in `get_datahub_client`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SchemaField:
    name: str
    type: str


@dataclass
class FreshnessSignal:
    hours_since_update: float
    expected_sla_hours: float
    notes: str = ""


@dataclass
class QualitySignal:
    row_count: int
    null_rate: float
    anomaly_count: int = 0
    invalid_rate: float = 0.0  # share of rows failing validity rules
    notes: str = ""  # human-readable description of the planted/observed issues


@dataclass
class Asset:
    urn: str
    name: str
    asset_type: str  # "dataset" | "mlModel" | "dashboard"
    platform: str
    dataset_key: str  # logical group, e.g. "nyc-taxi"
    schema_fields: list[SchemaField] = field(default_factory=list)
    freshness: Optional[FreshnessSignal] = None
    quality: Optional[QualitySignal] = None
    baseline_fields: list[str] = field(default_factory=list)  # for schema-drift checks


class DataHubClient(ABC):
    """Read + write access to DataHub metadata used by ML Guardian."""

    @abstractmethod
    def search(self, query: str = "*") -> list[Asset]:
        """Return assets matching a query (all assets for '*')."""

    @abstractmethod
    def get_entities(self, urns: list[str]) -> list[Asset]:
        """Fetch full details for the given URNs."""

    @abstractmethod
    def list_lineage(self, urn: str, direction: str = "downstream") -> list[str]:
        """Return upstream or downstream neighbour URNs (one hop)."""

    @abstractmethod
    def add_tags(self, urn: str, tags: list[str]) -> None:
        """Attach tags to an entity (write-back)."""

    @abstractmethod
    def add_terms(self, urn: str, terms: list[str]) -> None:
        """Attach glossary terms to an entity (write-back)."""

    def ui_link(self, urn: str) -> str:
        """Build a clickable DataHub UI link for an entity URN."""
        from ...config import settings

        return f"{settings.datahub_ui_url}/dataset/{urn}"
