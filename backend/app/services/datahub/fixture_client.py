"""Offline DataHub client backed by JSON fixtures.

Loads bundled sample datasets (nyc-taxi, healthcare, fiction-retail) that mirror
DataHub's official showcase datasets, complete with lineage and planted
freshness/quality issues. Fully deterministic and infra-free.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import (
    Asset,
    DataHubClient,
    FreshnessSignal,
    QualitySignal,
    SchemaField,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"

# In-process simulation overrides applied on load: {urn: {"hours_since_update": x,
# "null_rate": y}}. Lets POST /simulate-issue worsen a signal without editing disk.
_OVERRIDES: dict[str, dict[str, float]] = {}


def apply_override(urn: str, **kwargs: float) -> None:
    _OVERRIDES.setdefault(urn, {}).update(kwargs)


def clear_overrides() -> None:
    _OVERRIDES.clear()


def _asset_from_dict(d: dict, dataset_key: str) -> Asset:
    fresh = None
    if "freshness" in d.get("signals", {}):
        f = d["signals"]["freshness"]
        fresh = FreshnessSignal(
            hours_since_update=float(f["hours_since_update"]),
            expected_sla_hours=float(f["expected_sla_hours"]),
            notes=f.get("notes", ""),
        )
    qual = None
    if "quality" in d.get("signals", {}):
        q = d["signals"]["quality"]
        qual = QualitySignal(
            row_count=int(q.get("row_count", 0)),
            null_rate=float(q.get("null_rate", 0.0)),
            anomaly_count=int(q.get("anomaly_count", 0)),
            invalid_rate=float(q.get("invalid_rate", 0.0)),
            notes=q.get("notes", ""),
        )
    asset = Asset(
        urn=d["urn"],
        name=d["name"],
        asset_type=d.get("asset_type", "dataset"),
        platform=d.get("platform", "unknown"),
        dataset_key=dataset_key,
        schema_fields=[SchemaField(**s) for s in d.get("schema_fields", [])],
        freshness=fresh,
        quality=qual,
        baseline_fields=d.get("baseline_fields", []),
    )
    # Apply any simulation overrides.
    ov = _OVERRIDES.get(asset.urn)
    if ov:
        if "hours_since_update" in ov and asset.freshness:
            asset.freshness.hours_since_update = ov["hours_since_update"]
        if "null_rate" in ov and asset.quality:
            asset.quality.null_rate = ov["null_rate"]
    return asset


class FixtureDataHubClient(DataHubClient):
    def __init__(self) -> None:
        self._assets: dict[str, Asset] = {}
        self._lineage: dict[str, dict[str, list[str]]] = {}
        self._load()

    def _load(self) -> None:
        for path in sorted(FIXTURE_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            key = data["dataset_key"]
            for ent in data.get("entities", []):
                asset = _asset_from_dict(ent, key)
                self._assets[asset.urn] = asset
            for edge in data.get("lineage", []):
                up, down = edge["upstream"], edge["downstream"]
                self._lineage.setdefault(up, {"downstream": [], "upstream": []})
                self._lineage.setdefault(down, {"downstream": [], "upstream": []})
                self._lineage[up]["downstream"].append(down)
                self._lineage[down]["upstream"].append(up)

    def search(self, query: str = "*") -> list[Asset]:
        assets = list(self._assets.values())
        if query and query != "*":
            q = query.lower()
            assets = [a for a in assets if q in a.name.lower() or q in a.dataset_key.lower()]
        return assets

    def get_entities(self, urns: list[str]) -> list[Asset]:
        return [self._assets[u] for u in urns if u in self._assets]

    def list_lineage(self, urn: str, direction: str = "downstream") -> list[str]:
        return list(self._lineage.get(urn, {}).get(direction, []))

    def add_tags(self, urn: str, tags: list[str]) -> None:
        # Fixture mode: no live graph to mutate. metadata_writer records the
        # intent to the DB + writeback_log.json for visible proof.
        return None

    def add_terms(self, urn: str, terms: list[str]) -> None:
        return None
