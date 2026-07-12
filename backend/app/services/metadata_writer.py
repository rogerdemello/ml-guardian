"""Write incident context back into DataHub - the judged differentiator.

For each incident ML Guardian attaches:
  - a tag  `ml_incident:<severity>`
  - a glossary term describing the incident category

In `fixture` mode these are recorded to the `datahub_writebacks` table and
appended to `writeback_log.json` at the repo root as visible, inspectable proof.
In `mcp` mode the same calls hit the real DataHub via `add_tags` / `add_terms`.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from ..config import REPO_ROOT, settings
from ..models import AgentAction, DataHubWriteback, MLIncident
from .datahub.base import DataHubClient

WRITEBACK_LOG = REPO_ROOT / "writeback_log.json"

_GLOSSARY_TERM = {
    "freshness": "Data Freshness Incident",
    "quality": "Data Quality Incident",
    "schema": "Schema Drift Incident",
}


def _append_log(entry: dict) -> None:
    log: list[dict] = []
    if WRITEBACK_LOG.exists():
        try:
            log = json.loads(WRITEBACK_LOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log = []
    log.append(entry)
    WRITEBACK_LOG.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")


def write_incident_metadata(
    session: Session, client: DataHubClient, incident: MLIncident
) -> list[DataHubWriteback]:
    tag = f"ml_incident:{incident.severity}"
    term = _GLOSSARY_TERM.get(incident.incident_type, "Data Incident")

    # Perform the write (no-op in fixture mode, real API call in mcp mode).
    client.add_tags(incident.datahub_urn, [tag])
    client.add_terms(incident.datahub_urn, [term])

    writes = [
        DataHubWriteback(
            incident_id=incident.id,
            datahub_urn=incident.datahub_urn,
            write_type="tag",
            value=tag,
            mode=settings.datahub_mode,
        ),
        DataHubWriteback(
            incident_id=incident.id,
            datahub_urn=incident.datahub_urn,
            write_type="glossary_term",
            value=term,
            mode=settings.datahub_mode,
        ),
    ]
    for w in writes:
        session.add(w)
        _append_log(
            {
                "incident_id": incident.id,
                "urn": w.datahub_urn,
                "write_type": w.write_type,
                "value": w.value,
                "mode": w.mode,
            }
        )

    session.add(
        AgentAction(
            incident_id=incident.id,
            action_type="write_back",
            detail=f"Wrote tag '{tag}' and glossary term '{term}' to DataHub ({settings.datahub_mode} mode).",
        )
    )
    session.commit()
    return writes
