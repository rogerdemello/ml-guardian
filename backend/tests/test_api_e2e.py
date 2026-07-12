"""End-to-end API tests in fixture mode (no external infra, no LLM)."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import REPO_ROOT
from backend.app.main import app

client = TestClient(app)


def test_health_reports_fixture_mode():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["datahub_mode"] == "fixture"
    assert body["llm_enabled"] is False


def test_full_flow_scan_detail_writeback_remediation():
    # Scan detects exactly the two planted incidents.
    r = client.post("/api/scan")
    assert r.status_code == 200
    scan = r.json()
    assert scan["scanned_assets"] == 17
    assert scan["incidents_created"] == 2

    # Re-scan is idempotent (open incidents are not duplicated).
    assert client.post("/api/scan").json()["incidents_created"] == 0

    # Listing returns both, highest score first.
    incidents = client.get("/api/incidents").json()
    assert len(incidents) == 2
    assert incidents[0]["score"] >= incidents[1]["score"]

    # Detail includes impact radius + write-backs (tag + glossary term).
    top_id = incidents[0]["id"]
    detail = client.get(f"/api/incidents/{top_id}").json()
    assert len(detail["impact_radius"]) == 3
    kinds = {w["write_type"] for w in detail["writebacks"]}
    assert kinds == {"tag", "glossary_term"}
    assert "datahub_link" in detail

    # Applying remediation writes a real artifact and resolves the incident.
    rem = client.post(f"/api/incidents/{top_id}/apply-remediation").json()
    assert rem["status"] == "resolved"
    artifact = REPO_ROOT / rem["artifact_path"]
    assert artifact.exists()
    assert len(rem["code"]) > 0

    # Risk scores endpoint is populated.
    risks = client.get("/api/risk-scores").json()
    assert len(risks) >= 2


def test_simulate_creates_incident_on_clean_dataset():
    r = client.post(
        "/api/simulate-issue",
        json={"dataset": "fiction-retail", "issue_type": "quality"},
    )
    assert r.status_code == 200
    created = r.json()["incidents"]
    assert any(i["dataset_key"] == "fiction-retail" for i in created)
