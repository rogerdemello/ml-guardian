from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import AgentAction, MLIncident
from ..schemas import IncidentDetail, IncidentSummary, RemediationResult
from ..serializers import to_detail, to_summary
from ..services.datahub import get_datahub_client
from ..services.remediation import generate_remediation

router = APIRouter(tags=["incidents"])


@router.get("/incidents", response_model=list[IncidentSummary])
def list_incidents(
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[IncidentSummary]:
    stmt = select(MLIncident)
    if severity:
        stmt = stmt.where(MLIncident.severity == severity)
    if status:
        stmt = stmt.where(MLIncident.status == status)
    stmt = stmt.order_by(MLIncident.score.desc(), MLIncident.detected_at.desc())
    return [to_summary(i) for i in session.exec(stmt).all()]


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, session: Session = Depends(get_session)) -> IncidentDetail:
    incident = session.get(MLIncident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return to_detail(session, incident)


@router.post("/incidents/{incident_id}/apply-remediation", response_model=RemediationResult)
def apply_remediation(incident_id: int, session: Session = Depends(get_session)) -> RemediationResult:
    incident = session.get(MLIncident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    client = get_datahub_client()
    artifact_path, code, explanation = generate_remediation(incident, client)

    incident.remediation_artifact = artifact_path
    incident.status = "resolved"
    incident.resolved_at = datetime.now(timezone.utc)
    session.add(incident)
    session.add(
        AgentAction(
            incident_id=incident.id,
            action_type="generate_code",
            detail=explanation,
            artifact_link=artifact_path,
        )
    )
    session.add(
        AgentAction(
            incident_id=incident.id,
            action_type="resolve",
            detail="Incident marked resolved after remediation artifact generated.",
        )
    )
    session.commit()

    return RemediationResult(
        incident_id=incident.id,
        status=incident.status,
        artifact_path=artifact_path,
        code=code,
        explanation=explanation,
    )
