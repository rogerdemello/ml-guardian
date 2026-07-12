# Running ML Guardian against a live DataHub

By default ML Guardian runs **offline** (`DATAHUB_MODE=fixture`) against bundled
fixtures — no DataHub required. This guide switches it to a **real DataHub**
instance so incidents are detected from live metadata and write-backs (tags +
glossary terms) land in the actual graph.

> The offline fixture mode is the verified/demo path. The live client
> (`backend/app/services/datahub/mcp_client.py`) is implemented against the
> DataHub Python SDK and is exercised against a running DataHub, not the offline
> test suite.

## 1. Start DataHub

```bash
pip install acryl-datahub          # DataHub CLI + Python SDK
datahub docker quickstart          # spins up DataHub locally (needs Docker)
```

The UI comes up at <http://localhost:9002> and GMS at <http://localhost:8080>.

## 2. Load the sample datasets

Clone the official sample datasets and ingest each one:

```bash
git clone https://github.com/datahub-project/static-assets
cd static-assets/datasets/nyc-taxi
datahub ingest -c ingest.yaml
python add_lineage.py && python add_metadata.py
# repeat for ../healthcare and ../fiction-retail
```

## 3. Point ML Guardian at it

Get a personal access token from DataHub (Settings → Access Tokens), then in `.env`:

```bash
DATAHUB_MODE=mcp
DATAHUB_GMS_URL=http://localhost:8080
DATAHUB_UI_URL=http://localhost:9002
DATAHUB_TOKEN=<your-token>
# optional: GEMINI_API_KEY for LLM explanations
```

Install the live dependency (kept optional so offline installs stay lean):

```bash
pip install acryl-datahub
```

## 4. Run

```bash
./run.ps1        # or: uvicorn backend.app.main:app --port 8000
```

Click **Run scan**. ML Guardian reads schema/lineage from DataHub, detects
freshness risks (derived from the `operation` aspect), and on each incident
writes an `ml_incident:<severity>` **tag** and an incident **glossary term** back
onto the affected dataset — visible in the DataHub UI.

### Notes / limitations
- Freshness is derived best-effort from the dataset's last-operation timestamp
  (SLA defaults to 24h — DataHub has no native SLA field).
- Quality signals require DataHub **Assertions**; deriving them is a follow-up, so
  live mode currently focuses on freshness + the tag/term write-back.
- Reads use `DataHubGraph`; lineage uses `searchAcrossLineage`; writes use a
  read-modify-write of `globalTags` / `glossaryTerms` via `emit_mcp`.
