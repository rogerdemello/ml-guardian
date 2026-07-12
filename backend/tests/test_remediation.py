"""Remediation codegen: dialect-aware + syntax-validated, no LLM required."""
from backend.app.models import MLIncident
from backend.app.services.datahub.fixture_client import FixtureDataHubClient
from backend.app.services.remediation import _template_code, generate_remediation

STAGING = "urn:li:dataset:(urn:li:dataPlatform:sqlite,nyc_taxi.staging_trips,PROD)"
PATIENTS = "urn:li:dataset:(urn:li:dataPlatform:sqlite,healthcare.raw_patients,PROD)"


def _incident(urn: str, itype: str) -> MLIncident:
    return MLIncident(
        id=1, datahub_urn=urn, dataset_key="k", incident_type=itype,
        severity="critical", score=100,
    )


def test_freshness_sql_uses_sqlite_dialect_and_is_validated():
    _, code, explanation = generate_remediation(_incident(STAGING, "freshness"), FixtureDataHubClient())
    assert "julianday" in code          # sqlite dialect
    assert "DATEDIFF" not in code       # not Snowflake/Postgres
    assert "syntax-validated (sqlite)" in explanation.lower()


def test_generated_sql_parses_with_sqlglot():
    import sqlglot

    _, code, _ = generate_remediation(_incident(STAGING, "freshness"), FixtureDataHubClient())
    stmt = code.strip().rstrip(";").split(";")[0]
    sqlglot.parse_one(stmt, read="sqlite")  # raises on invalid SQL


def test_quality_template_uses_sqlite_cast_and_config_threshold():
    cols = ["name", "age", "billing_amount"]
    code, explanation, filename = _template_code(_incident(PATIENTS, "quality"), cols, "sqlite", 24, 0.05)
    assert "CAST(" in code and "::float" not in code
    assert "> 0.05" in code
    assert filename.endswith("_quality_check.sql")


def test_schema_template_renders_contract():
    code, _, filename = _template_code(_incident(PATIENTS, "schema"), ["a", "b"], "sqlite", 24, 0.05)
    assert "LIMIT 0" in code
    assert filename.endswith("_schema_contract.sql")


def test_warehouse_dialect_keeps_datediff():
    code, _, _ = _template_code(_incident(STAGING, "freshness"), ["updated_at"], "snowflake", 24, 0.05)
    assert "DATEDIFF" in code
    assert "julianday" not in code
