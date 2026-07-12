"""Convert ORM models to API response schemas."""
from __future__ import annotations

import json

from sqlmodel import Session, select

from .models import DataHubWriteback, MLIncident
from .schemas import IncidentDetail, IncidentSummary, WritebackOut
from .services.datahub import get_datahub_client


def _link(urn: str) -> str:
    return get_datahub_client().ui_link(urn)


def to_summary(incident: MLIncident) -> IncidentSummary:
    return IncidentSummary(
        id=incident.id,
        datahub_urn=incident.datahub_urn,
        dataset_key=incident.dataset_key,
        incident_type=incident.incident_type,
        severity=incident.severity,
        score=incident.score,
        status=incident.status,
        detected_at=incident.detected_at,
        datahub_link=_link(incident.datahub_urn),
    )


def to_detail(session: Session, incident: MLIncident) -> IncidentDetail:
    writebacks = session.exec(
        select(DataHubWriteback).where(DataHubWriteback.incident_id == incident.id)
    ).all()
    try:
        impact = json.loads(incident.impact_radius) if incident.impact_radius else []
    except json.JSONDecodeError:
        impact = []
    return IncidentDetail(
        **to_summary(incident).model_dump(),
        description=incident.description,
        impact_radius=impact,
        remediation_artifact=incident.remediation_artifact,
        resolved_at=incident.resolved_at,
        writebacks=[
            WritebackOut(
                datahub_urn=w.datahub_urn,
                write_type=w.write_type,
                value=w.value,
                mode=w.mode,
            )
            for w in writebacks
        ],
    )
