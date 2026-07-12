"""Agent orchestration via Google Gemini, with a deterministic fallback.

If GEMINI_API_KEY is set, Gemini produces a concise incident explanation
grounded in the DataHub metadata for the affected asset. Otherwise a template
explanation is used so the app runs fully offline.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import settings
from .datahub.base import DataHubClient

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _asset_context(finding, client: DataHubClient) -> dict:
    assets = client.get_entities([finding.urn])
    asset = assets[0] if assets else None
    ctx = {
        "urn": finding.urn,
        "asset_name": finding.asset_name,
        "asset_type": finding.asset_type,
        "incident_type": finding.incident_type,
        "score": finding.score,
        "severity": finding.severity,
        "detector_reason": finding.reason,
        "downstream_impact": finding.impact_radius,
    }
    if asset:
        ctx["schema_fields"] = [f.name for f in asset.schema_fields]
        if asset.freshness:
            ctx["hours_since_update"] = asset.freshness.hours_since_update
            ctx["expected_sla_hours"] = asset.freshness.expected_sla_hours
        if asset.quality:
            ctx["null_rate"] = asset.quality.null_rate
            ctx["anomaly_count"] = asset.quality.anomaly_count
    return ctx


def _template_explanation(finding, ctx: dict) -> str:
    impact = ctx.get("downstream_impact") or []

    def _short(urn: str) -> str:
        import re

        m = re.search(r"dataPlatform:[^,]+,([^,]+),", urn) or re.search(r"\(([^)]+)\)", urn)
        return m.group(1) if m else urn

    impact_line = (
        f" Impact radius: {len(impact)} downstream asset(s) - "
        + ", ".join(_short(a) for a in impact)
        if impact
        else " No downstream assets are affected."
    )
    return (
        f"[{finding.severity.upper()}] {finding.incident_type.title()} risk on "
        f"{finding.asset_name}. {finding.reason}{impact_line}"
    )


def _gemini_explanation(ctx: dict) -> str | None:
    try:
        from google import genai
    except ImportError:
        return None
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = _load_prompt("risk_analysis.txt")
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=f"{prompt}\n\nDataHub context (JSON):\n{json.dumps(ctx, indent=2)}",
        )
        text = (resp.text or "").strip()
        return text or None
    except Exception:
        # Never let the LLM path break a scan; fall back to the template.
        return None


def explain_risk(finding, client: DataHubClient) -> str:
    ctx = _asset_context(finding, client)
    if settings.llm_enabled:
        text = _gemini_explanation(ctx)
        if text:
            return text
    return _template_explanation(finding, ctx)
