"""Generate remediation artifacts (SQL / dbt / Airflow) for an incident.

Uses Gemini when available (grounded in the asset schema), otherwise emits a
metadata-aware template. Artifacts are written under examples/generated/ so
judges can inspect real code.
"""
from __future__ import annotations

import json
import logging
import re

from ..config import REPO_ROOT, settings
from ..models import MLIncident
from .datahub.base import DataHubClient

logger = logging.getLogger("ml_guardian.remediation")

GENERATED_DIR = REPO_ROOT / "examples" / "generated"

# DataHub platform -> sqlglot dialect (None = generic ANSI).
_DIALECT = {
    "sqlite": "sqlite",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "postgres": "postgres",
    "redshift": "redshift",
    "mysql": "mysql",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _table_name(urn: str) -> str:
    # urn:li:dataset:(urn:li:dataPlatform:sqlite,nyc_taxi.staging_trips,PROD) -> nyc_taxi.staging_trips
    m = re.search(r"dataPlatform:[^,]+,([^,]+),", urn)
    return m.group(1) if m else "target_table"


def _template_code(
    incident: MLIncident,
    columns: list[str],
    platform: str,
    sla_hours: float,
    null_ceiling: float,
) -> tuple[str, str, str]:
    """Dialect-aware assertion grounded in the asset's real SLA / thresholds."""
    table = _table_name(incident.datahub_urn)
    cols = columns or ["id", "updated_at"]
    ts_col = next(
        (c for c in cols if any(k in c.lower() for k in ("updated", "datetime", "timestamp", "date"))),
        "updated_at",
    )
    is_sqlite = platform == "sqlite"
    sla = int(round(sla_hours)) if sla_hours else 24

    if incident.incident_type == "freshness":
        if is_sqlite:
            stale_expr = f"(julianday('now') - julianday(MAX({ts_col}))) * 24"
        else:
            stale_expr = f"DATEDIFF('hour', MAX({ts_col}), CURRENT_TIMESTAMP)"
        code = (
            f"-- Freshness guard for {table} (SLA {sla}h)\n"
            f"-- Fail the pipeline early if upstream data is stale, preventing\n"
            f"-- models from training/scoring on outdated records.\n"
            f"SELECT\n"
            f"    MAX({ts_col}) AS last_loaded_at,\n"
            f"    {stale_expr} AS hours_stale\n"
            f"FROM {table}\n"
            f"HAVING {stale_expr} > {sla};\n"
        )
        explanation = (
            f"Adds a freshness assertion on `{table}`: it returns a row only when data "
            f"is older than the {sla}h SLA, so the orchestrator can halt downstream ML "
            f"jobs before they consume stale features."
        )
        return code, explanation, f"{_slug(table)}_freshness_check.sql"

    if incident.incident_type == "quality":
        col = next((c for c in cols if c not in ("id",)), cols[0])
        pct = f"{null_ceiling:.2f}"
        null_frac = f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)"
        rate = (
            f"CAST({null_frac} AS FLOAT) / COUNT(*)"
            if is_sqlite
            else f"{null_frac}::float / COUNT(*)"
        )
        code = (
            f"-- Data quality assertion for {table}\n"
            f"-- Blocks the load when the null rate on a key feature column exceeds {pct}.\n"
            f"SELECT\n"
            f"    COUNT(*) AS total_rows,\n"
            f"    {null_frac} AS null_rows,\n"
            f"    {rate} AS null_rate\n"
            f"FROM {table}\n"
            f"HAVING {rate} > {pct};\n"
        )
        explanation = (
            f"Adds a null-rate quality check on `{table}.{col}`. If more than "
            f"{null_ceiling:.0%} of values are null the assertion fails, stopping "
            f"degraded features from reaching the model."
        )
        return code, explanation, f"{_slug(table)}_quality_check.sql"

    # schema
    code = (
        f"-- Schema contract test for {table}\n"
        f"-- Verifies required feature columns still exist before extraction.\n"
        f"SELECT {', '.join(cols)}\n"
        f"FROM {table}\n"
        f"LIMIT 0;  -- fails at parse time if a column was dropped/renamed\n"
    )
    explanation = (
        f"Adds a schema contract test on `{table}` that fails fast if an expected "
        f"feature column is dropped or renamed."
    )
    return code, explanation, f"{_slug(table)}_schema_contract.sql"


def _validate_sql(code: str, dialect: str | None) -> str:
    """Best-effort syntax validation of generated SQL. Never raises."""
    try:
        import sqlglot
    except ImportError:
        return ""
    try:
        # Validate the first statement (assertions are single statements).
        stmt = code.strip().rstrip(";").split(";")[0]
        sqlglot.parse_one(stmt, read=dialect)
        return f" Syntax-validated ({dialect or 'ansi'})."
    except Exception as exc:  # sqlglot.errors.ParseError and friends
        logger.warning("Generated SQL failed validation: %s", exc)
        return " (Note: could not syntax-validate the generated SQL.)"


def _gemini_code(incident: MLIncident, columns: list[str]) -> tuple[str, str] | None:
    from .orchestrator import _load_prompt

    try:
        from google import genai
    except ImportError:
        return None
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = _load_prompt("remediation.txt")
        ctx = {
            "table": _table_name(incident.datahub_urn),
            "incident_type": incident.incident_type,
            "severity": incident.severity,
            "columns": columns,
            "description": incident.description,
        }
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=f"{prompt}\n\nContext (JSON):\n{json.dumps(ctx, indent=2)}",
        )
        text = (resp.text or "").strip()
        if not text:
            return None
        # Split code fence from explanation if present.
        m = re.search(r"```[a-zA-Z]*\n(.*?)```", text, re.DOTALL)
        if m:
            code = m.group(1).strip()
            explanation = text.replace(m.group(0), "").strip() or "LLM-generated remediation."
            return code, explanation
        return text, "LLM-generated remediation."
    except Exception:
        logger.exception("Gemini remediation call failed; falling back to template.")
        return None


def generate_remediation(incident: MLIncident, client: DataHubClient) -> tuple[str, str, str]:
    """Return (artifact_path, code, explanation)."""
    assets = client.get_entities([incident.datahub_urn])
    asset = assets[0] if assets else None
    columns = [f.name for f in asset.schema_fields] if asset else []
    platform = asset.platform if asset else "unknown"
    sla_hours = asset.freshness.expected_sla_hours if (asset and asset.freshness) else 24.0

    code, explanation, filename = _template_code(
        incident, columns, platform, sla_hours, settings.quality_null_rate_max
    )

    if settings.llm_enabled:
        llm = _gemini_code(incident, columns)
        if llm:
            code, explanation = llm

    # Best-effort syntax validation of whatever code we ship.
    explanation += _validate_sql(code, _DIALECT.get(platform))

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GENERATED_DIR / f"incident_{incident.id}_{filename}"
    out_path.write_text(code, encoding="utf-8")
    rel = out_path.relative_to(REPO_ROOT).as_posix()
    return rel, code, explanation
