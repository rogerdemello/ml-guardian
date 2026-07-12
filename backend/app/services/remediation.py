"""Generate remediation artifacts (SQL / dbt / Airflow) for an incident.

Uses Gemini when available (grounded in the asset schema), otherwise emits a
metadata-aware template. Artifacts are written under examples/generated/ so
judges can inspect real code.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import REPO_ROOT, settings
from ..models import MLIncident
from .datahub.base import DataHubClient
from .orchestrator import _load_prompt

GENERATED_DIR = REPO_ROOT / "examples" / "generated"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _table_name(urn: str) -> str:
    # urn:li:dataset:(urn:li:dataPlatform:s3,nyc_taxi.raw_trips,PROD) -> nyc_taxi.raw_trips
    m = re.search(r"dataPlatform:[^,]+,([^,]+),", urn)
    return m.group(1) if m else "target_table"


def _template_code(incident: MLIncident, columns: list[str]) -> tuple[str, str, str]:
    table = _table_name(incident.datahub_urn)
    cols = columns or ["id", "updated_at"]
    ts_col = next(
        (c for c in cols if any(k in c.lower() for k in ("updated", "datetime", "timestamp", "date"))),
        "updated_at",
    )
    if incident.incident_type == "freshness":
        code = (
            f"-- Freshness guard for {table}\n"
            f"-- Fail the pipeline early if upstream data is stale, preventing\n"
            f"-- models from training/scoring on outdated records.\n"
            f"SELECT\n"
            f"    MAX({ts_col}) AS last_loaded_at,\n"
            f"    DATEDIFF('hour', MAX({ts_col}), CURRENT_TIMESTAMP) AS hours_stale\n"
            f"FROM {table}\n"
            f"HAVING DATEDIFF('hour', MAX({ts_col}), CURRENT_TIMESTAMP) > 24;\n"
        )
        explanation = (
            f"Adds a freshness assertion on `{table}`: the query returns rows only "
            f"when data is >24h old, so the orchestrator can halt downstream ML jobs "
            f"before they consume stale features."
        )
        return code, explanation, f"{_slug(table)}_freshness_check.sql"

    if incident.incident_type == "quality":
        col = next((c for c in cols if c not in ("id",)), cols[0])
        code = (
            f"-- Data quality assertion for {table}\n"
            f"-- Blocks the load when null rate on a key feature column exceeds 5%.\n"
            f"SELECT\n"
            f"    COUNT(*) AS total_rows,\n"
            f"    SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS null_rows,\n"
            f"    SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)::float / COUNT(*) AS null_rate\n"
            f"FROM {table}\n"
            f"HAVING SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)::float / COUNT(*) > 0.05;\n"
        )
        explanation = (
            f"Adds a null-rate quality check on `{table}.{col}`. If more than 5% of "
            f"values are null the assertion fails, stopping degraded features from "
            f"reaching the model."
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


def _gemini_code(incident: MLIncident, columns: list[str]) -> tuple[str, str] | None:
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
        return None


def generate_remediation(incident: MLIncident, client: DataHubClient) -> tuple[str, str, str]:
    """Return (artifact_path, code, explanation)."""
    assets = client.get_entities([incident.datahub_urn])
    columns = [f.name for f in assets[0].schema_fields] if assets else []

    _, explanation, filename = _template_code(incident, columns)
    code = _template_code(incident, columns)[0]

    if settings.llm_enabled:
        llm = _gemini_code(incident, columns)
        if llm:
            code, explanation = llm

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GENERATED_DIR / f"incident_{incident.id}_{filename}"
    out_path.write_text(code, encoding="utf-8")
    rel = out_path.relative_to(REPO_ROOT).as_posix()
    return rel, code, explanation
