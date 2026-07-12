"""Unit tests for the deterministic risk detector."""
from backend.app.config import settings
from backend.app.services.datahub.base import (
    Asset,
    FreshnessSignal,
    QualitySignal,
    SchemaField,
)
from backend.app.services.datahub.fixture_client import FixtureDataHubClient
from backend.app.services.risk_detector import (
    Finding,
    _apply_downstream_weight,
    _check_freshness,
    _check_quality,
    _check_schema,
    detect,
    severity_for,
)


def _finding(score: int, impact: list[str]) -> Finding:
    return Finding(
        urn="urn:li:dataset:(urn:li:dataPlatform:sqlite,k.t,PROD)",
        dataset_key="k",
        asset_name="t",
        asset_type="dataset",
        incident_type="freshness",
        score=score,
        severity=severity_for(score),
        reason="base reason.",
        impact_radius=impact,
    )


def test_downstream_ml_consumers_raise_severity():
    # An isolated table (only a downstream dataset) gets no boost...
    isolated = _finding(70, ["urn:li:dataset:(urn:li:dataPlatform:sqlite,k.d,PROD)"])
    _apply_downstream_weight(isolated, settings)
    assert isolated.score == 70
    assert isolated.severity == "high"

    # ...but one feeding a live model + dashboard is escalated high -> critical.
    feeding_model = _finding(
        70,
        [
            "urn:li:mlModel:(urn:li:dataPlatform:mlflow,k.m,PROD)",
            "urn:li:dashboard:(looker,k.dash)",
        ],
    )
    _apply_downstream_weight(feeding_model, settings)
    assert feeding_model.score == 70 + settings.downstream_model_boost + settings.downstream_dashboard_boost
    assert feeding_model.severity == "critical"
    assert "at risk" in feeding_model.reason


def test_severity_buckets():
    assert severity_for(10) == "low"
    assert severity_for(45) == "medium"
    assert severity_for(70) == "high"
    assert severity_for(90) == "critical"
    assert severity_for(100) == "critical"


def test_detect_over_fixtures_finds_exactly_the_planted_issues():
    findings = detect(FixtureDataHubClient(), settings)
    by_key = {(f.dataset_key, f.incident_type): f for f in findings}

    # nyc-taxi freshness: staging_trips 72h vs 24h SLA => base 90; downstream has
    # 1 model + 1 dashboard => 90 + 15 + 5 => capped 100 critical.
    fresh = by_key[("nyc-taxi", "freshness")]
    assert "staging_trips" in fresh.urn
    assert fresh.score == 100
    assert fresh.severity == "critical"
    # downstream of staging_trips: mart -> model -> dashboard
    assert len(fresh.impact_radius) == 3
    assert any("fare_prediction" in u for u in fresh.impact_radius)

    # healthcare quality on raw_patients: base 64; downstream 1 model + 1 dashboard
    # => 64 + 15 + 5 => 84 high.
    qual = by_key[("healthcare", "quality")]
    assert "raw_patients" in qual.urn
    assert qual.score == 84
    assert qual.severity == "high"
    # downstream: staging -> mart_billing/mart_demographics -> model -> dashboard
    assert len(qual.impact_radius) == 5
    assert any("readmission_risk" in u for u in qual.impact_radius)

    # exactly two incidents overall; fiction-retail clean (true negative)
    assert len(findings) == 2
    assert not any(f.dataset_key == "fiction-retail" for f in findings)


def test_fresh_data_within_sla_is_not_flagged():
    asset = Asset(
        urn="urn:test",
        name="t",
        asset_type="dataset",
        platform="s3",
        dataset_key="k",
        freshness=FreshnessSignal(hours_since_update=5, expected_sla_hours=24),
    )
    assert _check_freshness(asset, settings) is None


def test_stale_data_is_flagged_with_scaled_score():
    asset = Asset(
        urn="urn:test",
        name="t",
        asset_type="dataset",
        platform="s3",
        dataset_key="k",
        freshness=FreshnessSignal(hours_since_update=48, expected_sla_hours=24),
    )
    finding = _check_freshness(asset, settings)
    assert finding is not None
    assert finding.score == 60  # 2x over SLA => 30*2
    assert finding.severity == "high"


def test_quality_null_rate_breach_flagged():
    asset = Asset(
        urn="urn:test",
        name="t",
        asset_type="dataset",
        platform="s3",
        dataset_key="k",
        quality=QualitySignal(row_count=1000, null_rate=0.10, anomaly_count=0),
    )
    finding = _check_quality(asset, settings)
    assert finding is not None
    assert finding.incident_type == "quality"


def test_schema_drift_detected_when_baseline_column_missing():
    asset = Asset(
        urn="urn:test",
        name="t",
        asset_type="dataset",
        platform="s3",
        dataset_key="k",
        schema_fields=[SchemaField(name="id", type="string")],
        baseline_fields=["id", "critical_feature"],
    )
    finding = _check_schema(asset, settings)
    assert finding is not None
    assert "critical_feature" in finding.reason
