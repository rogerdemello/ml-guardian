# ML Guardian: Metadata-Driven ML Risk Sentinel

> Autonomous ML reliability agent built on DataHub's context platform.
> It monitors ML lineage, data quality, and freshness to detect silent failures,
> creates incidents, writes context back into DataHub as tags and glossary terms,
> and generates remediation code — so humans and agents inherit the knowledge.

**Build with DataHub: The Agent Hackathon** (Devpost) · Track: **Production ML Agents**
(+ Agents That Do Real Work, Metadata-Aware Code Generation).
Submission deadline: **Aug 10, 2026**.

---

## Why this is different

Production ML fails quietly: an upstream table goes stale, a null rate creeps up,
a column is renamed — and a model keeps scoring on bad data until a KPI moves days
later. DataHub already knows how data flows from raw tables to features to models
to dashboards. ML Guardian **uses that context** to catch the problem, name the
exact downstream models/dashboards at risk, write the finding back into the graph,
and propose a fail-fast fix.

It is not a chatbot. It is a scan → score → incident → **write-back** → remediate loop.

## Runs in 60 seconds, zero infrastructure

ML Guardian is **offline-first**. Out of the box it runs against bundled fixtures
that mirror DataHub's official sample datasets (nyc-taxi, healthcare, fiction-retail)
with planted issues — no Docker, no DataHub instance, no API keys required. A single
env var (`DATAHUB_MODE=mcp`) switches it onto a live DataHub via the real
[`mcp-server-datahub`](https://pypi.org/project/mcp-server-datahub/).

```bash
# Windows
./run.ps1
# macOS / Linux
./run.sh
```

Then open <http://localhost:8000>, click **Run scan**, and explore the incidents.

### Manual setup (equivalent)

```bash
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt   # Windows path
uvicorn backend.app.main:app --port 8000
```

No `.env` is needed for the default offline demo. Copy `.env.example` to `.env`
only to enable a live DataHub (`DATAHUB_MODE=mcp`) or LLM explanations
(`GEMINI_API_KEY`, Google Gemini).

---

## Architecture

```
Browser dashboard (vanilla JS)  ──►  FastAPI  ──►  Risk detector (pure heuristics)
        (served at "/")                 │                 │
                                        │                 ├─► Orchestrator (Gemini, optional)
                                        │                 ├─► Metadata writer (write-back)
                                        │                 └─► Remediation generator
                                        ▼                 ▼
                                    SQLite            DataHub client
                              (incidents, risk,   ┌───────────────┴──────────────┐
                               actions, writes)   │ FixtureDataHubClient (offline)│
                                                  │ McpDataHubClient  (live MCP)  │
                                                  └──────────────────────────────┘
```

- **DataHub client** (`backend/app/services/datahub/`) — a single interface with two
  implementations. Fixtures now; real `mcp-server-datahub` tools behind config.
- **Risk detector** (`risk_detector.py`) — deterministic, unit-tested heuristics for
  freshness, quality, and schema drift; computes impact radius from lineage.
- **Orchestrator** (`orchestrator.py`) — Google Gemini explains each incident when
  `GEMINI_API_KEY` is set; falls back to templates so it always runs.
- **Metadata writer** (`metadata_writer.py`) — writes `ml_incident:<severity>` tags
  and incident glossary terms back to DataHub. Offline, these are recorded in
  `writeback_log.json` + the `datahub_writebacks` table as visible proof.
- **Remediation** (`remediation.py`) — generates SQL/dbt/Airflow assertions grounded
  in the real schema; artifacts land in `examples/generated/`.

## DataHub integration (real tools)

Read: `search`, `get_entities`, `list_lineage`, `list_schema_fields`, `get_queries`.
Write: `add_tags`, `add_terms`.

These are the actual `mcp-server-datahub` (v0.5.0+) tool names. `McpDataHubClient`
is a thin adapter over them; the offline path needs none of it.

## API

All under `/api`:

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health` | mode + LLM status |
| POST | `/api/scan` | detect, persist, write back, explain |
| GET  | `/api/incidents` | list (filter `severity`, `status`) |
| GET  | `/api/incidents/{id}` | detail: impact radius, write-backs, remediation |
| POST | `/api/incidents/{id}/apply-remediation` | generate artifact + resolve |
| GET  | `/api/risk-scores` | current scores per asset |
| POST | `/api/simulate-issue` | worsen a signal then re-scan (fixture mode) |

## Data model (SQLite)

`ml_incidents`, `risk_scores`, `agent_actions`, `datahub_writebacks`. Assets and
lineage stay in DataHub, referenced by URN.

## Tests

```bash
./.venv/Scripts/python -m pytest backend/tests -q
```

Covers the detector heuristics and a full fixture-mode API flow
(scan → incident → write-back → remediation), 9 tests, no external services.

## Open-source contribution

`skills/datahub-ml-guardian/` is a reusable DataHub **Skill** in the registry format
(`SKILL.md` + `references/` + `templates/`), so any DataHub agent tool (Gemini CLI,
Claude Code, Cursor, etc.) can run the same detect → write-back → remediate workflow.

## Repository layout

```
backend/app/        FastAPI app, services, fixtures, prompts
backend/tests/      pytest (detector + API e2e)
frontend/           static dashboard (no build step)
skills/datahub-ml-guardian/   reusable DataHub Skill
examples/           sample remediation artifacts + write-back
DOCS_HACKATHON.md   judge guide
```

## License

Apache 2.0 — see `LICENSE`.
