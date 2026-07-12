---
name: datahub-ml-guardian
description: >-
  Detect silent ML reliability risks from DataHub metadata (freshness, data
  quality, schema drift), score their severity and downstream impact, write
  incident context back to the graph as tags and glossary terms, and generate
  remediation code. Use when asked to audit ML/data assets for risk, triage a
  suspected pipeline issue, or protect models from upstream data problems.
license: Apache-2.0
---

# DataHub ML Guardian

A reusable workflow that turns DataHub from a passive catalog into a proactive ML
reliability agent. It is designed to run against a live DataHub via the
[`mcp-server-datahub`](https://pypi.org/project/mcp-server-datahub/) tools, and it
mirrors the reference implementation in this repository (which also ships an
offline fixture mode for demos).

## When to use this skill

- "Audit our ML datasets/models for reliability risks."
- "Is `<dataset>` safe to train/score on right now?"
- "Something looks off in `<pipeline>` — trace the impact and propose a fix."
- Continuous monitoring: run on a schedule and open incidents automatically.

## Tools used (real DataHub MCP surface)

Read: `search`, `get_entities`, `list_lineage`, `list_schema_fields`, `get_queries`.
Write: `add_tags`, `add_terms` (and their `remove_*` counterparts).

See `references/datahub-tools.md` for signatures and payload shapes.

## Workflow

1. **Discover** — `search` for ML assets (`type:dataset`, `type:mlModel`) and their
   upstream datasets. For each candidate, `get_entities` to pull schema, ownership,
   and quality/freshness signals; `list_schema_fields` for column-level detail.

2. **Detect** — evaluate each asset against three rules:
   - **Freshness**: `hours_since_update / expected_sla_hours > 1` → stale.
   - **Quality**: `null_rate > ceiling` (default 5%) or anomalies present.
   - **Schema drift**: an expected feature column is missing/renamed vs baseline.

3. **Score & scope** — map each breach to a 0-100 risk score and severity
   (`low <30`, `medium <60`, `high <85`, `critical`). Use `list_lineage(direction=downstream)`
   to compute the **impact radius** (which features, models, and dashboards are at risk).

4. **Write back** — for every incident, attach to the affected URN:
   - a tag `ml_incident:<severity>` via `add_tags`
   - a glossary term (`Data Freshness Incident` / `Data Quality Incident` /
     `Schema Drift Incident`) via `add_terms`
   so humans and other agents inherit the finding. See
   `templates/incident_writeback.md`.

5. **Remediate** — generate a minimal, fail-fast assertion (SQL / dbt test /
   Airflow sensor) grounded in the real table + column names, so the orchestrator
   halts downstream ML jobs before they consume bad data. See
   `templates/remediation_prompt.md`.

## Output contract

Return, per incident: `{urn, incident_type, score, severity, impact_radius[],
explanation, writebacks[], remediation_artifact}`.

## Guardrails

- Never invent columns or tables not present in the DataHub metadata.
- Remediation must be non-destructive (assertions/tests only, no DDL/DML that
  mutates data).
- Skip assets already carrying an open `ml_incident:*` tag of the same type
  (idempotency).
