from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..db import get_session
from ..models import RiskScore
from ..schemas import RiskScoreOut

router = APIRouter(tags=["risk-scores"])


@router.get("/risk-scores", response_model=list[RiskScoreOut])
def list_risk_scores(session: Session = Depends(get_session)) -> list[RiskScoreOut]:
    stmt = select(RiskScore).order_by(RiskScore.score.desc(), RiskScore.last_evaluated_at.desc())
    return [
        RiskScoreOut(
            datahub_urn=r.datahub_urn,
            asset_type=r.asset_type,
            score=r.score,
            severity=r.severity,
            reason=r.reason,
            last_evaluated_at=r.last_evaluated_at,
        )
        for r in session.exec(stmt).all()
    ]
