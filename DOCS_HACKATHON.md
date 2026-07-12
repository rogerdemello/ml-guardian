# ML Guardian – Hackathon Submission & Judge Guide

This document is optimized for hackathon judges and organizers. It explains **what ML Guardian is**, **how it uses DataHub**, how to **run the demo**, and how it meets all **Agent Hackathon** requirements and judging criteria.

---

## 1. Quick Summary (For Judges)

- **Project**: ML Guardian – Metadata-Driven ML Risk Sentinel  
- **Hackathon**: Build with DataHub – The Agent Hackathon (Devpost)  
- **Track(s)**:  
  - Production ML Agents  
  - Agents That Do Real Work  
  - Metadata-Aware Code Generation (remediation artifacts)  
- **DataHub Features Used**:  
  - Agent Context Kit  
  - MCP Server  
  - DataHub Skills (search, lineage, quality, enrichment)  
- **Key Idea**:  
  ML Guardian continuously monitors DataHub’s ML lineage and data quality metadata to detect silent ML risks, creates incidents, generates remediation code, and writes context back into the metadata graph.

---

## 2. Problem Statement & Use Case

### 2.1 Real Problem

ML models in production fail quietly due to upstream data issues:

- Pipelines stop or lag (freshness issues).  
- Schema changes break feature extraction.  
- Data quality deteriorates (missing values, anomalies).  

Most teams notice only when KPIs move or downstream dashboards misbehave. Root cause analysis is slow because lineage and ownership are scattered.

### 2.2 How ML Guardian Solves It

ML Guardian uses DataHub as the **source of truth** for lineage, assets, and quality metadata:

- Reads ML lineage from training datasets → features → models → deployments.  
- Monitors freshness and quality signals from upstream datasets.  
- Identifies incidents where a change endangers an ML model or downstream dashboards.  
- Records incidents and remediation suggestions in both ML Guardian’s DB and DataHub’s metadata graph.  
- Produces code artifacts (SQL/dbt/Airflow) that can be reviewed and merged.

This turns DataHub from a passive catalog into a **proactive ML reliability agent**.

---

## 3. Hackathon Requirements Mapping

### 3.1 What to Build (Requirement)

From the Agent Hackathon: [web:1][web:3]

> “Create a working software application that uses DataHub to solve one of the challenges below… Pick one of the four challenges (Agents That Do Real Work, Metadata-Aware Code Generation & Development, Production ML Agents, Open/Wildcard).”

**ML Guardian Implementation**

- **Working application** with backend, frontend, and agent logic.  
- Uses **DataHub Agent Context Kit** and **MCP Server** to access metadata, lineage, quality signals, and catalog workflows. [web:1][web:2][web:10]  
- Directly solves **Production ML Agents** by protecting models using end-to-end ML lineage. [web:1][web:3][web:10]

### 3.2 What to Submit

Hackathon submission requires: [web:1][web:3]

- **Live demo URL or setup instructions**  
  - Provided via this repo; see “Run the Demo” section below.  
- **Public GitHub repository with Apache 2.0 license**  
  - This repo includes `LICENSE` (Apache 2.0) and is public.  
- **Text description of features, technologies, data**  
  - Covered in `README.md` and this `DOCS_HACKATHON.md`.  
- **Demonstration video (< 3 minutes)**  
  - See `docs/demo_video.md` for script and link (to be added when recorded).  
- **Optional sample outputs**  
  - `examples/` folder contains generated SQL/dbt/Airflow code for review.

---

## 4. How ML Guardian Uses DataHub

### 4.1 Read Operations (Context)

ML Guardian uses DataHub’s Agent Context Kit and Skills to **understand** the environment: [web:2][web:5][web:10]

(These are the real `mcp-server-datahub` v0.5.0+ tool names.)

- **search**  
  - Find ML models, datasets, and dashboards relevant to a use case.  
- **get_entities**  
  - Retrieve full entity details: schemas, owners, descriptions, tags.  
- **list_lineage**  
  - Obtain upstream/downstream lineage for datasets and models (impact radius).  
- **list_schema_fields**  
  - Get columns and their types for safe code generation.  
- **get_queries** (optional)  
  - Read and reason about existing SQL queries referencing an asset. [web:9][web:10]

### 4.2 Write Operations (Metadata Graph)

A key judging criterion is **writing back** to the metadata graph. [web:1][web:3]

ML Guardian writes (via the real mutation tools `add_tags` and `add_terms`):

- **Incident tags** (e.g., `ml_incident:critical`) attached to affected assets, via `add_tags`.  
- **Glossary terms** for the incident category (e.g., "Data Freshness Incident", "Data Quality Incident"), via `add_terms`. [web:5]  

These write operations make ML Guardian's actions visible in DataHub and reusable by other agents or humans. The implementation deliberately relies only on `add_tags` / `add_terms` (no document-write API) to stay portable across DataHub versions. In the default offline mode the same write-backs are recorded to `writeback_log.json` and the `datahub_writebacks` table as visible proof.

### 4.3 Sample Datasets & Lineage

ML Guardian mirrors the official DataHub sample datasets from the
[`datahub-project/static-assets`](https://github.com/datahub-project/static-assets/tree/main/datasets)
repo (SQLite pipelines, loaded into a live DataHub via each dataset's `ingest.yaml`
recipe; `add_lineage.py` / `add_metadata.py` add lineage + governance): [web:1][web:3]

- `nyc-taxi` – 3-stage SQLite pipeline `raw_trips → staging_trips → mart_daily_summary`;
  planted freshness issue (staging halts ~3 days before raw's max date).  
- `healthcare` – `raw_patients → staging_patients → mart_billing / mart_demographics`
  (~55.5k rows); planted validity issues (negative billing, invalid ages, swapped
  dates, null names).  
- `fiction-retail` – clean 10-table retail schema (50k customers, 150k orders).

The bundled fixtures (`backend/app/fixtures/*.json`) reproduce these tables, columns,
lineage, and planted issues so the offline demo is faithful to the real datasets. The
downstream ML model + dashboard per pipeline are illustrative ML consumers added to
show impact radius. Lineage and quality signals let us demonstrate:

- A pipeline with stale data feeding a model (silent staleness).  
- Quality anomalies propagating into ML features.  
- How incidents affect downstream dashboards.

---

## 5. Project Architecture (Judge-Friendly View)

### 5.1 Components

- **Frontend**  
  - Static vanilla-JS dashboard (no build step) served by FastAPI at `/`.  
  - Lists incidents and risk scores; links to DataHub UI for affected URNs.  

- **Backend API** (FastAPI, endpoints under `/api`)  
  - `/api/scan`, `/api/incidents`, `/api/risk-scores`, `/api/simulate-issue`, `/api/incidents/{id}` endpoints.  
  - Talks to DataHub through a client interface: offline fixtures by default, real `mcp-server-datahub` tools when `DATAHUB_MODE=mcp`. [web:2]

- **Agent Orchestrator**  
  - LLM-based agent using DataHub Skills to:  
    - Gather context (search, lineage, quality).  
    - Compute risk scores and severity.  
    - Generate remediation code.

- **Risk Detection Worker**  
  - Polls DataHub or triggers checks on sample datasets.  
  - Stores risk scores and incidents in local DB.

- **Remediation Generator**  
  - Generates SQL/dbt/Airflow artifacts for pipelines and quality checks.  
  - Stores artifacts under `examples/`.

### 5.2 Data Flow

1. **Detection**  
   - Worker identifies potential issues (freshness/quality/schema).  
   - Calls Agent Orchestrator with asset URNs and metadata.

2. **Analysis**  
   - Orchestrator uses Agent Context Kit tools: `get_lineage`, `get_entities`, `data quality tools`. [web:2][web:10]  
   - LLM computes risk score and severity.

3. **Incident Creation**  
   - Backend persists incident in app DB.  
   - Metadata writer tags assets and adds notes and docs in DataHub.

4. **Remediation**  
   - Remediation generator uses schema and lineage to craft code.  
   - Recommended code stored in `examples/` and optionally structured for PR.

5. **Visualization**  
   - Frontend shows incidents and risk; judges can click through to DataHub.

---

## 6. Run the Demo (Judge Instructions)

### 6.1 Minimal Setup (Local) — offline, ~60 seconds, no DataHub required

The default mode needs **no Docker, no DataHub instance, and no API keys**. It uses
bundled fixtures that mirror the official sample datasets with planted issues.

1. **Launch**  
   ```bash
   ./run.ps1        # Windows
   ./run.sh         # macOS / Linux
   # or: uvicorn backend.app.main:app --port 8000
   ```

2. **Open dashboard**  
   - Navigate to `http://localhost:8000`, click **Run scan**.

3. **(Optional) Go live against real DataHub**  
   - Start DataHub Quickstart. Clone `datahub-project/static-assets` and load the
     sample datasets by running each dataset's `ingest.yaml`
     (`datahub ingest -c ingest.yaml`, then `add_lineage.py` / `add_metadata.py`). [web:1][web:3]  
   - In `.env`, set `DATAHUB_MODE=mcp`, `DATAHUB_TOKEN`, `DATAHUB_GMS_URL` (and optionally `GEMINI_API_KEY` for Gemini-powered LLM explanations). [web:2]

### 6.2 Demo Flow

We recommend the following demo flow (mirrors the video):

1. **Intro (30 seconds)**  
   - Explain the ML reliability problem and DataHub’s context.  

2. **Scenario 1: Freshness Issue (nyc-taxi)**  
   - Click **Run scan**. A CRITICAL freshness incident on `nyc_taxi.staging_trips`
     appears (staging halted ~3 days before raw_trips' max date — a *silent* staleness
     ingestion metadata alone would miss).  
   - Open it to see severity, the 3-asset downstream impact radius (mart → model →
     dashboard), and the tag + glossary term written back to DataHub.  
   - Click **Generate remediation** to produce a fail-fast SQL assertion.

3. **Scenario 2: Data Quality Issue (healthcare)**  
   - The same scan flags a HIGH data-quality incident on `healthcare.raw_patients`
     (negative billing, out-of-range age, swapped admission/discharge dates, null
     names). `fiction-retail` stays clean (true negative).  
   - Inspect the incident and the generated validity check; compare with the static
     samples in `examples/`.

   - Use **Simulate** buttons to worsen a signal live and watch severity escalate.

4. **Wrap-Up**  
   - Point to OSS skill, metadata write-back, and how this generalizes to real production stacks.

---

## 7. Judge FAQ (Answers)

### Q1: Is this just a chatbot?

**Answer**: No. It’s a continuous ML risk monitoring and incident-management agent. It uses DataHub’s ML lineage and quality metadata to automatically discover incidents, compute risk, write metadata back, and propose code changes, with a dashboard for humans. [web:1][web:3][web:10]

### Q2: How deeply does it integrate with DataHub?

**Answer**: ML Guardian uses DataHub’s Agent Context Kit and MCP Server to call multiple skills: search, lineage, schema fields, quality metadata, tags, glossary terms, documents, and domain/owner management. It both reads and writes metadata to the graph, following DataHub’s recommended agent patterns. [web:2][web:5][web:10]

### Q3: What makes this submission “production ML agent” rather than a toy?

**Answer**: It is designed around real ML reliability concerns: pipeline freshness, data quality, schema changes, and impact on models and downstream analytics. It leverages DataHub’s ML lineage to identify exactly which models and assets are impacted, then produces remediation artifacts that mimic production code. [web:1][web:3][web:6][web:10]

### Q4: How could a real company use this after the hackathon?

**Answer**: They would point ML Guardian at their own DataHub instance, configure which ML models and thresholds to monitor, and run the agents on a schedule. Incidents and remediation suggestions would appear in their own dashboards and metadata graph, integrating into existing ops processes. The open-source skill and templates are reusable building blocks. [web:2][web:5][web:10]

### Q5: What open-source contributions does this project make?

**Answer**:  
- A reusable DataHub **Skill** (`skills/datahub-ml-guardian/`) in the official
  registry format (`SKILL.md` + `references/` + `templates/`) for ML incident
  detection, write-back, and remediation, runnable by any DataHub agent tool (Gemini CLI, Claude Code,
  Cursor, etc.). [web:5]  
- Incident write-back and remediation templates (`templates/`) plus a DataHub tool
  reference (`references/datahub-tools.md`).  
- Documentation and example artifacts (`examples/`) demonstrating best practices for
  agent usage with DataHub.

---

## 8. Alignment with Judging Criteria

### 8.1 Meaningful Use of DataHub

- Uses Agent Context Kit, MCP server, and DataHub Skills for rich agent workflows. [web:2][web:5][web:10]  
- Read/write interaction with metadata graph. [web:1][web:3]  
- Leverages official sample datasets and datapacks.

### 8.2 Technical Execution

- Clear separation of concerns (backend, frontend, agent, skills, examples).  
- End-to-end flow tested and documented.  
- Reasonable tests and examples provided.

### 8.3 Originality

- Focus on ML reliability and incident management instead of generic data chat.  
- Incident-based write-back pattern that expands DataHub’s role.

### 8.4 Real-World Usefulness

- Directly applicable to any DataHub user running ML in production.  
- Uses realistic sample datasets for demonstration. [web:1][web:3]

### 8.5 Submission Quality

- Comprehensive `README.md` and this `DOCS_HACKATHON.md`.  
- Clear demo instructions and scenarios.  
- Example artifacts for offline review.

### 8.6 Open-Source Impact

- Skill and templates that can be integrated into other DataHub-based agents. [web:5]

---

## 9. Future Work (Beyond Hackathon)

- **Multi-Agent Orchestration**  
  - Dedicated planner, detector, remediator, and documenter agents. [web:10]  

- **Alerting Integrations**  
  - Slack/Teams/email notifications for new incidents.  

- **Custom DataHub Entity Types**  
  - “ML Incident” entity if supported in DataHub’s schema evolution.

- **Advanced Analytics**  
  - Use Analytics Agent to produce risk dashboards and charts. [web:9][web:10]

---

## 10. Contact & Community

- **DataHub Community Slack**: Join `#agent-hackathon` for questions about DataHub and agents. [web:1][web:3]  
- **Project Contributors**: Add your names, roles, and contact info here.

Thank you for reviewing ML Guardian!