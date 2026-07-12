"""Pydantic response/request models for the API layer."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WritebackOut(BaseModel):
    datahub_urn: str
    write_type: str
    value: str
    mode: str


class IncidentSummary(BaseModel):
    id: int
    datahub_urn: str
    dataset_key: str
    incident_type: str
    severity: str
    score: int
    status: str
    detected_at: datetime
    datahub_link: str


class IncidentDetail(IncidentSummary):
    description: str
    impact_radius: list[str]
    remediation_artifact: str
    resolved_at: Optional[datetime]
    writebacks: list[WritebackOut]


class RiskScoreOut(BaseModel):
    datahub_urn: str
    asset_type: str
    score: int
    severity: str
    reason: str
    last_evaluated_at: datetime


class ScanResult(BaseModel):
    scanned_assets: int
    incidents_created: int
    incidents: list[IncidentSummary]


class SimulateRequest(BaseModel):
    dataset: str  # "nyc-taxi" | "healthcare" | "fiction-retail"
    issue_type: str = "freshness"  # "freshness" | "quality"


class RemediationResult(BaseModel):
    incident_id: int
    status: str
    artifact_path: str
    code: str
    explanation: str
