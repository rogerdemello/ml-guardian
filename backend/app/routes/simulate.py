from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..config import settings
from ..db import get_session
from ..schemas import ScanResult, SimulateRequest
from ..serializers import to_summary
from ..services.datahub import get_datahub_client
from ..services.risk_detector import run_scan

router = APIRouter(tags=["simulate"])


@router.post("/simulate-issue", response_model=ScanResult)
def simulate_issue(req: SimulateRequest, session: Session = Depends(get_session)) -> ScanResult:
    """Worsen a signal on a sample dataset, then re-scan (fixture mode only)."""
    if settings.datahub_mode != "fixture":
        raise HTTPException(
            status_code=400,
            detail="simulate-issue is only available in fixture mode.",
        )
    from ..services.datahub.fixture_client import apply_override

    client = get_datahub_client()
    candidates = [
        a
        for a in client.search("*")
        if a.dataset_key == req.dataset and a.asset_type == "dataset"
    ]
    if not candidates:
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{req.dataset}'")

    if req.issue_type == "freshness":
        target = next((a for a in candidates if a.freshness), candidates[0])
        sla = target.freshness.expected_sla_hours if target.freshness else 24.0
        apply_override(target.urn, hours_since_update=sla * 6)
    elif req.issue_type == "quality":
        target = next((a for a in candidates if a.quality), candidates[0])
        apply_override(target.urn, null_rate=0.25)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown issue_type '{req.issue_type}'")

    # Rebuild the client so overrides are re-applied on load, then scan.
    client = get_datahub_client()
    scanned = len(client.search("*"))
    created = run_scan(session, client)
    return ScanResult(
        scanned_assets=scanned,
        incidents_created=len(created),
        incidents=[to_summary(i) for i in created],
    )
