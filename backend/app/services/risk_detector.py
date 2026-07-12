"""Deterministic ML risk detection over DataHub metadata.

`detect()` is pure (no DB, no wall clock) so it is trivially unit-testable.
`run_scan()` wraps it with persistence, agent explanation, and metadata
write-back.
"""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field

from sqlmodel import Session, select

from ..config import Settings, settings as default_settings
from ..models import AgentAction, MLIncident, RiskScore
from .datahub.base import Asset, DataHubClient


@dataclass
class Finding:
    urn: str
    dataset_key: str
    asset_name: str
    asset_type: str
    incident_type: str  # "freshness" | "quality" | "schema"
    score: int
    severity: str
    reason: str
    impact_radius: list[str] = field(default_factory=list)


def severity_for(score: int) -> str:
    if score < 30:
        return "low"
    if score < 60:
        return "medium"
    if score < 85:
        return "high"
    return "critical"


def _downstream_closure(client: DataHubClient, urn: str) -> list[str]:
    """All downstream URNs reachable from `urn` (BFS, dedup, excludes self)."""
    seen: list[str] = []
    queue: deque[str] = deque(client.list_lineage(urn, "downstream"))
    visited = set()
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        seen.append(node)
        queue.extend(client.list_lineage(node, "downstream"))
    return seen


def _check_freshness(asset: Asset, s: Settings) -> Finding | None:
    if not asset.freshness:
        return None
    sla = asset.freshness.expected_sla_hours or 1.0
    ratio = asset.freshness.hours_since_update / sla
    if ratio <= s.freshness_warn_ratio:
        return None
    score = min(100, int(round(30 * ratio)))
    reason = (
        f"Data is {asset.freshness.hours_since_update:.0f}h old vs a "
        f"{sla:.0f}h SLA ({ratio:.1f}x over). Downstream ML features/models may "
        f"train or score on stale data."
    )
    if asset.freshness.notes:
        reason += f" {asset.freshness.notes}"
    return Finding(
        urn=asset.urn,
        dataset_key=asset.dataset_key,
        asset_name=asset.name,
        asset_type=asset.asset_type,
        incident_type="freshness",
        score=score,
        severity=severity_for(score),
        reason=reason,
    )


def _check_quality(asset: Asset, s: Settings) -> Finding | None:
    if not asset.quality:
        return None
    q = asset.quality
    breaches_null = q.null_rate > s.quality_null_rate_max
    breaches_invalid = q.invalid_rate > s.quality_null_rate_max
    if not breaches_null and not breaches_invalid and q.anomaly_count == 0:
        return None
    ceiling = s.quality_null_rate_max or 1.0
    worst_rate = max(q.null_rate, q.invalid_rate)
    ratio = worst_rate / ceiling
    score = min(100, int(round(30 * ratio)) + q.anomaly_count * 10)
    parts = []
    if q.null_rate:
        parts.append(f"null rate {q.null_rate:.0%}")
    if q.invalid_rate:
        parts.append(f"invalid-value rate {q.invalid_rate:.0%}")
    detail = " and ".join(parts) if parts else "quality anomalies"
    reason = (
        f"Data quality degraded ({detail}"
        + (f", {q.anomaly_count} validity rule(s) failing" if q.anomaly_count else "")
        + "). This can silently bias model outputs."
    )
    if q.notes:
        reason += f" {q.notes}"
    return Finding(
        urn=asset.urn,
        dataset_key=asset.dataset_key,
        asset_name=asset.name,
        asset_type=asset.asset_type,
        incident_type="quality",
        score=score,
        severity=severity_for(score),
        reason=reason,
    )


def _check_schema(asset: Asset, s: Settings) -> Finding | None:
    if not asset.baseline_fields:
        return None
    current = {f.name for f in asset.schema_fields}
    dropped = [f for f in asset.baseline_fields if f not in current]
    if not dropped:
        return None
    score = min(100, 20 + len(dropped) * 40)
    reason = (
        f"Schema drift: expected column(s) {', '.join(dropped)} missing. "
        f"Feature extraction downstream will break."
    )
    return Finding(
        urn=asset.urn,
        dataset_key=asset.dataset_key,
        asset_name=asset.name,
        asset_type=asset.asset_type,
        incident_type="schema",
        score=score,
        severity=severity_for(score),
        reason=reason,
    )


def _apply_downstream_weight(finding: Finding, s: Settings) -> None:
    """Raise score/severity when downstream ML models or dashboards are at risk.

    A stale/degraded table that feeds a live model is more dangerous than one
    feeding nothing — this is the core of the "name the models at risk" pitch.
    """
    models = sum(1 for u in finding.impact_radius if ":mlModel:" in u)
    dashboards = sum(1 for u in finding.impact_radius if ":dashboard:" in u)
    if not models and not dashboards:
        return
    boosted = min(
        100,
        finding.score + models * s.downstream_model_boost + dashboards * s.downstream_dashboard_boost,
    )
    if boosted <= finding.score:
        return
    finding.score = boosted
    finding.severity = severity_for(boosted)
    consumers = []
    if models:
        consumers.append(f"{models} ML model{'s' if models > 1 else ''}")
    if dashboards:
        consumers.append(f"{dashboards} dashboard{'s' if dashboards > 1 else ''}")
    finding.reason += f" Downstream {' and '.join(consumers)} at risk — severity raised."


def detect(client: DataHubClient, s: Settings | None = None) -> list[Finding]:
    """Pure detection: return one finding per (asset, issue) that breaches a rule."""
    s = s or default_settings
    findings: list[Finding] = []
    for asset in client.search("*"):
        for check in (_check_freshness, _check_quality, _check_schema):
            finding = check(asset, s)
            if finding:
                finding.impact_radius = _downstream_closure(client, asset.urn)
                _apply_downstream_weight(finding, s)
                findings.append(finding)
    return findings


def run_scan(session: Session, client: DataHubClient, s: Settings | None = None) -> list[MLIncident]:
    """Detect, persist incidents + risk scores, explain, and write metadata back."""
    from .metadata_writer import write_incident_metadata
    from .orchestrator import explain_risk

    s = s or default_settings
    findings = detect(client, s)
    created: list[MLIncident] = []

    for f in findings:
        # Skip if an open incident of the same type already exists for this asset.
        existing = session.exec(
            select(MLIncident).where(
                MLIncident.datahub_urn == f.urn,
                MLIncident.incident_type == f.incident_type,
                MLIncident.status == "open",
            )
        ).first()
        if existing:
            continue

        description = explain_risk(f, client)
        incident = MLIncident(
            datahub_urn=f.urn,
            dataset_key=f.dataset_key,
            incident_type=f.incident_type,
            severity=f.severity,
            score=f.score,
            description=description,
            impact_radius=json.dumps(f.impact_radius),
        )
        session.add(incident)
        session.add(
            RiskScore(
                datahub_urn=f.urn,
                asset_type=f.asset_type,
                score=f.score,
                severity=f.severity,
                reason=f.reason,
            )
        )
        session.commit()
        session.refresh(incident)

        session.add(
            AgentAction(
                incident_id=incident.id,
                action_type="detect",
                detail=f"Detected {f.incident_type} risk (score {f.score}, {f.severity}).",
            )
        )
        session.commit()

        write_incident_metadata(session, client, incident)
        created.append(incident)

    return created
