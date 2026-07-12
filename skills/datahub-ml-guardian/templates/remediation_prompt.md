# Remediation generation template

Prompt an LLM (or use the fixed templates below) to produce a minimal, fail-fast
assertion grounded in the real table and column names from DataHub.

## Prompt

> You are a senior data engineer. Given the DataHub asset context (table name,
> incident type, affected columns, description), propose a minimal, production-ready
> remediation as a data quality / freshness assertion. Use the exact table and
> column names provided; do not invent columns. Prefer a single SQL assertion (or
> dbt test / Airflow sensor) that fails fast so the orchestrator halts downstream ML
> jobs before consuming bad data. No destructive statements. Return a fenced code
> block plus a 1-2 sentence explanation.

## Freshness assertion (SQL)

```sql
SELECT MAX(updated_at) AS last_loaded_at,
       DATEDIFF('hour', MAX(updated_at), CURRENT_TIMESTAMP) AS hours_stale
FROM <table>
HAVING DATEDIFF('hour', MAX(updated_at), CURRENT_TIMESTAMP) > <sla_hours>;
```

## Quality assertion (SQL)

```sql
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN <col> IS NULL THEN 1 ELSE 0 END)::float / COUNT(*) AS null_rate
FROM <table>
HAVING SUM(CASE WHEN <col> IS NULL THEN 1 ELSE 0 END)::float / COUNT(*) > <ceiling>;
```

## Schema contract (SQL)

```sql
SELECT <required_columns>
FROM <table>
LIMIT 0;  -- fails at parse time if a required column is dropped/renamed
```
