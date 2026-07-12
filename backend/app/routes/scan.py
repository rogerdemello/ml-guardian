from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..db import get_session
from ..schemas import ScanResult
from ..serializers import to_summary
from ..services.datahub import get_datahub_client
from ..services.risk_detector import run_scan

router = APIRouter(tags=["scan"])


@router.post("/scan", response_model=ScanResult)
def scan(session: Session = Depends(get_session)) -> ScanResult:
    client = get_datahub_client()
    scanned = len(client.search("*"))
    created = run_scan(session, client)
    return ScanResult(
        scanned_assets=scanned,
        incidents_created=len(created),
        incidents=[to_summary(i) for i in created],
    )
