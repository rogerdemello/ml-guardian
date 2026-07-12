"""SQLModel tables for ML Guardian's application state.

DataHub remains the source of truth for assets and lineage (referenced by URN);
these tables hold only ML-Guardian-specific incident/risk/action records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskScore(SQLModel, table=True):
    __tablename__ = "risk_scores"

    id: Optional[int] = Field(default=None, primary_key=True)
    datahub_urn: str = Field(index=True)
    asset_type: str
    score: int
    severity: str
    reason: str = ""
    last_evaluated_at: datetime = Field(default_factory=_utcnow)


class MLIncident(SQLModel, table=True):
    __tablename__ = "ml_incidents"

    id: Optional[int] = Field(default=None, primary_key=True)
    datahub_urn: str = Field(index=True)
    dataset_key: str = Field(index=True)  # e.g. "nyc-taxi"
    incident_type: str  # "freshness" | "quality" | "schema"
    severity: str  # "low" | "medium" | "high" | "critical"
    score: int
    description: str = ""
    impact_radius: str = ""  # JSON-encoded list of downstream URNs
    remediation_artifact: str = ""  # path under examples/generated/ once applied
    status: str = Field(default="open", index=True)  # "open" | "resolved"
    created_by_agent: bool = True
    detected_at: datetime = Field(default_factory=_utcnow)
    resolved_at: Optional[datetime] = None


class AgentAction(SQLModel, table=True):
    __tablename__ = "agent_actions"

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: int = Field(index=True, foreign_key="ml_incidents.id")
    action_type: str  # "detect" | "write_back" | "generate_code" | "resolve"
    detail: str = ""
    artifact_link: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class DataHubWriteback(SQLModel, table=True):
    """A record of metadata written back to DataHub (tags / glossary terms).

    In fixture mode these are recorded here (and appended to writeback_log.json)
    as visible proof; in mcp mode they mirror real add_tags / add_terms calls.
    """

    __tablename__ = "datahub_writebacks"

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: int = Field(index=True, foreign_key="ml_incidents.id")
    datahub_urn: str = Field(index=True)
    write_type: str  # "tag" | "glossary_term"
    value: str  # e.g. "ml_incident:critical" or "Data Freshness Incident"
    mode: str  # "fixture" | "mcp"
    created_at: datetime = Field(default_factory=_utcnow)
