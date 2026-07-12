# Examples

Sample outputs ML Guardian produces, for judges to inspect without running the stack.

- `nyc_taxi_freshness_fix.sql` — freshness assertion for the nyc-taxi incident
  (`staging_trips` lags `raw_trips` by ~3 days, silent to naive checks).
- `healthcare_quality_check.sql` — validity assertion for the healthcare incident
  on `raw_patients` (negative billing, out-of-range age, swapped dates, null names).
- `dbt_healthcare_quality.yml` — the same validity checks expressed as dbt tests.
- `airflow_freshness_sensor.py` — an Airflow task that blocks downstream ML jobs
  when `staging_trips` is stale.
- `sample_writeback.json` — the exact tag + glossary-term metadata ML Guardian
  writes back to DataHub for these incidents.

`generated/` (git-ignored) is where the live app writes artifacts when you click
**Generate remediation** in the dashboard or call
`POST /api/incidents/{id}/apply-remediation`.
