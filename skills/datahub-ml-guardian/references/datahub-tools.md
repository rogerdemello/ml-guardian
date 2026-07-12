# DataHub tool reference (mcp-server-datahub)

Tool names and shapes as exposed by `mcp-server-datahub` (v0.5.0+). Verify against
your installed version with the MCP server's tool listing.

## Read tools

- `search(query)` — structured keyword search (`/q` syntax) with boolean logic,
  filters, pagination. Returns matching entities (datasets, models, dashboards).
- `get_entities(urns)` — batch fetch full metadata (schema, owners, tags,
  descriptions, quality/freshness aspects) for one or more URNs.
- `list_lineage(urn, direction)` — upstream or downstream lineage for any entity,
  with hop control and query-within-lineage. Used to compute impact radius.
- `list_schema_fields(urn)` — columns and types for a dataset, with filtering.
- `get_queries(urn)` — real SQL queries referencing a dataset or column.

## Write tools (mutations)

- `add_tags(urn, tags)` / `remove_tags(urn, tags)` — attach/detach tags on entities
  or schema fields; supports bulk operations.
- `add_terms(urn, terms)` / `remove_terms(urn, terms)` — attach/detach glossary
  terms (business definitions / classifications).

## Notes

- ML Guardian's write-back uses `add_tags` (`ml_incident:<severity>`) and
  `add_terms` (incident-category glossary term). There is intentionally no reliance
  on a document/runbook write API, keeping the skill portable across versions.
- URN examples:
  - dataset: `urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.table,PROD)`
  - model:   `urn:li:mlModel:(urn:li:dataPlatform:mlflow,name,PROD)`
  - dashboard:`urn:li:dashboard:(looker,id)`
