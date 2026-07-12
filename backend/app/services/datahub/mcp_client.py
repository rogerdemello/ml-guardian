"""Live DataHub client backed by the DataHub Python SDK (`acryl-datahub`).

Active only when `DATAHUB_MODE=mcp`. The default offline path
(`FixtureDataHubClient`) needs none of this, and `acryl-datahub` is a lazy import
so offline/CI installs stay lean.

Reads use `DataHubGraph` (schema, lineage, freshness signal). Writes do a real
read-modify-write of the `globalTags` / `glossaryTerms` aspects and emit an MCP —
the same tag + glossary-term write-back the fixture mode simulates offline.

NOTE: this path requires a running DataHub and is exercised live, not by the
offline test suite (which stays the verified path). See docs/live-datahub.md.
Freshness is derived best-effort from the `operation` aspect; quality signals
require DataHub Assertions and are left to a follow-up (returns None here).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from .base import Asset, DataHubClient, FreshnessSignal, SchemaField

logger = logging.getLogger("ml_guardian.datahub.mcp")

DEFAULT_SLA_HOURS = 24.0  # DataHub has no SLA field; use a sane default.


def _platform_from_urn(urn: str) -> str:
    m = re.search(r"dataPlatform:([^,]+),", urn)
    return m.group(1) if m else "unknown"


def _name_from_urn(urn: str) -> str:
    m = re.search(r"dataPlatform:[^,]+,([^,]+),", urn)
    if m:
        return m.group(1)
    m = re.search(r"\(([^)]+)\)\s*$", urn)
    return m.group(1).split(",")[-1] if m else urn


def _entity_type(urn: str) -> str:
    if ":mlModel:" in urn:
        return "mlModel"
    if ":dashboard:" in urn:
        return "dashboard"
    return "dataset"


class McpDataHubClient(DataHubClient):
    def __init__(self) -> None:
        from ...config import settings

        if not settings.datahub_token:
            raise RuntimeError(
                "DATAHUB_MODE=mcp requires DATAHUB_TOKEN (and DATAHUB_GMS_URL). "
                "Set them in .env or use DATAHUB_MODE=fixture for offline mode."
            )
        self._settings = settings
        try:
            from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
        except ImportError as exc:  # pragma: no cover - needs the optional dep
            raise RuntimeError(
                "Live mode requires the DataHub SDK. Install it with "
                "`pip install acryl-datahub`."
            ) from exc
        self._graph = DataHubGraph(
            DatahubClientConfig(server=settings.datahub_gms_url, token=settings.datahub_token)
        )

    # ---------------- reads ----------------
    def search(self, query: str = "*") -> list[Asset]:  # pragma: no cover - live only
        urns = list(
            self._graph.get_urns_by_filter(
                entity_types=["dataset"],
                query=None if query == "*" else query,
            )
        )
        return self.get_entities(urns)

    def get_entities(self, urns: list[str]) -> list[Asset]:  # pragma: no cover - live only
        from datahub.metadata.schema_classes import SchemaMetadataClass

        assets: list[Asset] = []
        for urn in urns:
            fields: list[SchemaField] = []
            try:
                sm = self._graph.get_aspect(urn, SchemaMetadataClass)
                if sm and sm.fields:
                    fields = [
                        SchemaField(name=f.fieldPath, type=getattr(f.type, "type", "unknown").__class__.__name__)
                        for f in sm.fields
                    ]
            except Exception:
                logger.exception("schema fetch failed for %s", urn)
            assets.append(
                Asset(
                    urn=urn,
                    name=_name_from_urn(urn),
                    asset_type=_entity_type(urn),
                    platform=_platform_from_urn(urn),
                    dataset_key=_platform_from_urn(urn),
                    schema_fields=fields,
                    freshness=self._derive_freshness(urn),
                    quality=None,  # requires DataHub Assertions; follow-up.
                )
            )
        return assets

    def _derive_freshness(self, urn: str) -> FreshnessSignal | None:  # pragma: no cover - live only
        from datahub.metadata.schema_classes import OperationClass

        try:
            op = self._graph.get_aspect(urn, OperationClass)
        except Exception:
            logger.exception("operation aspect fetch failed for %s", urn)
            return None
        ts = getattr(op, "lastUpdatedTimestamp", None) if op else None
        if not ts:
            return None
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        hours = max(0.0, (now_ms - ts) / 3_600_000)
        return FreshnessSignal(hours_since_update=hours, expected_sla_hours=DEFAULT_SLA_HOURS)

    def list_lineage(self, urn: str, direction: str = "downstream") -> list[str]:  # pragma: no cover
        query = """
        query($urn: String!, $dir: LineageDirection!) {
          searchAcrossLineage(input: {urn: $urn, direction: $dir, query: "*", start: 0, count: 100}) {
            searchResults { entity { urn } }
          }
        }"""
        try:
            res = self._graph.execute_graphql(
                query, variables={"urn": urn, "dir": direction.upper()}
            )
            return [
                r["entity"]["urn"]
                for r in res["searchAcrossLineage"]["searchResults"]
            ]
        except Exception:
            logger.exception("lineage fetch failed for %s", urn)
            return []

    # ---------------- writes (real tag / glossary-term write-back) ----------------
    def add_tags(self, urn: str, tags: list[str]) -> None:  # pragma: no cover - live only
        from datahub.emitter.mce_builder import make_tag_urn
        from datahub.metadata.schema_classes import GlobalTagsClass, TagAssociationClass

        current = self._graph.get_aspect(urn, GlobalTagsClass) or GlobalTagsClass(tags=[])
        existing = {t.tag for t in current.tags}
        for tag in tags:
            tag_urn = make_tag_urn(tag)
            if tag_urn not in existing:
                current.tags.append(TagAssociationClass(tag=tag_urn))
        self._emit(urn, current)

    def add_terms(self, urn: str, terms: list[str]) -> None:  # pragma: no cover - live only
        from datahub.emitter.mce_builder import make_term_urn
        from datahub.metadata.schema_classes import (
            AuditStampClass,
            GlossaryTermAssociationClass,
            GlossaryTermsClass,
        )

        current = self._graph.get_aspect(urn, GlossaryTermsClass)
        if current is None:
            current = GlossaryTermsClass(
                terms=[],
                auditStamp=AuditStampClass(time=0, actor="urn:li:corpuser:ml-guardian"),
            )
        existing = {t.urn for t in current.terms}
        for term in terms:
            term_urn = make_term_urn(term)
            if term_urn not in existing:
                current.terms.append(GlossaryTermAssociationClass(urn=term_urn))
        self._emit(urn, current)

    def _emit(self, urn: str, aspect) -> None:  # pragma: no cover - live only
        from datahub.emitter.mcp import MetadataChangeProposalWrapper

        self._graph.emit_mcp(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
