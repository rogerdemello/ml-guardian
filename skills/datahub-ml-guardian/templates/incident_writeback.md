# Incident write-back template

For each detected incident, write the following back to the affected asset URN so
the finding is visible in DataHub and reusable by other agents.

## Tag (via `add_tags`)

```
ml_incident:<severity>     # severity in {low, medium, high, critical}
```

## Glossary term (via `add_terms`)

| incident_type | glossary term            |
|---------------|--------------------------|
| freshness     | Data Freshness Incident  |
| quality       | Data Quality Incident    |
| schema        | Schema Drift Incident    |

## Suggested description / note (optional, if your DataHub build supports it)

```
[<SEVERITY>] <incident_type> risk on <asset_name>. <detector_reason>
Impact radius: <n> downstream asset(s): <urn list>.
Detected by ML Guardian at <timestamp>.
```

## Idempotency

Before writing, check whether the URN already carries an open
`ml_incident:*` tag of the same `incident_type`; if so, skip to avoid duplicates.
