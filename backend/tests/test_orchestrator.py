"""Orchestrator tests: the app must run without any LLM key (template fallback)."""
from backend.app.config import settings
from backend.app.services.datahub.fixture_client import FixtureDataHubClient
from backend.app.services.orchestrator import explain_risk
from backend.app.services.remediation import generate_remediation
from backend.app.services.risk_detector import detect
from backend.app.models import MLIncident


def test_llm_disabled_in_tests():
    # conftest sets GEMINI_API_KEY="" so the deterministic path is exercised.
    assert settings.llm_enabled is False


def test_explain_risk_returns_template_text_without_llm():
    client = FixtureDataHubClient()
    finding = detect(client)[0]
    text = explain_risk(finding, client)
    assert isinstance(text, str) and text
    # Template format is deterministic and grounded in the finding.
    assert finding.severity.upper() in text
    assert finding.asset_name in text


def test_remediation_generates_artifact_without_llm(tmp_path):
    client = FixtureDataHubClient()
    finding = next(f for f in detect(client) if f.incident_type == "freshness")
    incident = MLIncident(
        id=999,
        datahub_urn=finding.urn,
        dataset_key=finding.dataset_key,
        incident_type=finding.incident_type,
        severity=finding.severity,
        score=finding.score,
    )
    artifact_path, code, explanation = generate_remediation(incident, client)
    assert artifact_path.endswith(".sql")
    assert "SELECT" in code.upper()
    assert explanation
