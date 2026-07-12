"""Airflow remediation for the nyc-taxi freshness incident.

ML Guardian can emit remediations as Airflow tasks. This task fails (and thus
halts the downstream feature/model tasks) when nyc_taxi.staging_trips is stale
beyond its 24h SLA. Wire it upstream of your feature-engineering and training
tasks. (Root cause: staging_trips lags raw_trips by ~3 days.)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.hooks.sql import DbApiHook

FRESHNESS_SLA_HOURS = 24
TABLE = "nyc_taxi.staging_trips"
TS_COLUMN = "tpep_pickup_datetime"


def assert_fresh(**_context) -> None:
    hook = DbApiHook.get_hook(conn_id="warehouse")
    last_loaded = hook.get_first(f"SELECT MAX({TS_COLUMN}) FROM {TABLE}")[0]
    if last_loaded is None:
        raise AirflowFailException(f"{TABLE} has no rows / no updated_at.")
    hours_stale = (datetime.utcnow() - last_loaded).total_seconds() / 3600
    if hours_stale > FRESHNESS_SLA_HOURS:
        raise AirflowFailException(
            f"Freshness SLA breached: {TABLE} is {hours_stale:.1f}h old "
            f"(> {FRESHNESS_SLA_HOURS}h). Halting downstream ML tasks."
        )


with DAG(
    dag_id="nyc_taxi_freshness_guard",
    start_date=datetime(2026, 1, 1),
    schedule="@hourly",
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
) as dag:
    freshness_gate = PythonOperator(
        task_id="assert_raw_trips_fresh",
        python_callable=assert_fresh,
    )
    # freshness_gate >> build_trip_features >> train_fare_prediction
