"""recon_daily: one run per UTC arrival day.

1. One run owns one UTC arrival day R. Its data interval is [R 00:00, R+1 00:00) UTC:
   everything that arrived during that day.
2. The scheduled run for R starts just after R+1 00:00 UTC, which is 05:00 in Astana.
3. The logical date is R. The run id shows R+1 (run type plus run_after), so name runs by logical date.
4. An exact day runs only through a one-day backfill (--from-date R --to-date R), after a --dry-run.
   Never `airflow dags trigger -l`: it processes yesterday relative to now.
5. dbt rebuilds the marts from all loaded days, as of the latest loaded arrival day,
   so rerunning an old day never rolls the marts back.
check_window is the only task that reads the wall clock, and only to refuse dates outside the window.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime, timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import CronDataIntervalTimetable, chain, dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException

log = logging.getLogger(__name__)

TABLES = ["payment_events", "settlement_lines", "fx_rates"]  # map_index 0, 1, 2

DBT_BUILD_CMD = (
    "cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt build --target airflow "
    "--exclude-resource-type unit_test "
    "--target-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/target "
    "--log-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/logs"
)


def log_failure(context) -> None:
    """One line per final failure."""
    ti = context["ti"]
    start = context.get("data_interval_start")
    run_date = start.astimezone(UTC).date().isoformat() if start is not None else "none"
    log.error("task failed dag_id=%s run_id=%s task_id=%s try_number=%s run_date=%s",
              ti.dag_id, ti.run_id, ti.task_id, ti.try_number, run_date)


def _bq_client():
    """BigQuery client from the connection google_cloud_default."""
    from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook

    hook = BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")
    return hook.get_client(project_id=hook.project_id, location="US")


def _landing_dir() -> str:
    from recon.config import load_env

    return str(load_env().landing_dir)


@dag(
    dag_id="recon_daily",
    schedule=CronDataIntervalTimetable("0 0 * * *", timezone="UTC"),
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 0,
        "retry_delay": timedelta(seconds=30),
        "on_failure_callback": log_failure,
    },
    tags=["portfolio", "reconciliation"],
    doc_md=__doc__,
)
def recon_daily():
    @task(retries=0)
    def check_window() -> str:
        context = get_current_context()
        start, end = context.get("data_interval_start"), context.get("data_interval_end")
        if start is None or end is None:
            raise AirflowFailException("No data interval: create exact days with a one-day backfill")
        start, end = start.astimezone(UTC), end.astimezone(UTC)
        if end - start != timedelta(days=1) or (start.hour, start.minute, start.second, start.microsecond) != (0, 0, 0, 0):
            raise AirflowFailException(f"the data interval must be one UTC day from 00:00: start={start} end={end}")
        run_date = start.date()
        today = datetime.now(UTC).date()          # the only wall-clock read in the DAG, and only to check

        from recon.config import load_env
        from recon.load import check_run_date

        try:
            check_run_date(run_date, load_env().world_start, today)
        except ValueError as err:
            raise AirflowFailException(str(err)) from err
        log.info("run_date=%s", run_date.isoformat())
        return run_date.isoformat()

    @task(retries=2, retry_delay=timedelta(seconds=30))
    def ensure_tables() -> dict:
        if os.environ.get("RAW_DATASET") != "raw":
            raise AirflowFailException(f"RAW_DATASET is {os.environ.get('RAW_DATASET')!r}, the DAG writes only 'raw'")
        from recon.load import ensure_tables as create_raw_tables

        create_raw_tables(_bq_client(), "raw")
        return {"dataset": "raw"}

    @task(retries=0)
    def generate_day(run_date: str) -> dict:
        from recon.config import load_env
        from recon.generator import emit

        env = load_env()
        return emit(env.seed, env.world_start, date.fromisoformat(run_date), env.landing_dir)

    @task(
        retries=3,
        retry_delay=timedelta(seconds=30),
        retry_exponential_backoff=2.0,
        max_retry_delay=timedelta(minutes=10),
    )
    def fetch_fx(run_date: str) -> dict:
        from recon.fx import fetch_nbk

        return fetch_nbk(date.fromisoformat(run_date), _landing_dir())

    @task(retries=2, retry_delay=timedelta(seconds=30))
    def load_raw(table: str, run_date: str) -> dict:
        from recon.load import load_day

        return load_day(_bq_client(), "raw", table, date.fromisoformat(run_date), _landing_dir())

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=DBT_BUILD_CMD,
        pool="dbt_serial",
        append_env=True,
        retries=0,
    )

    rd = check_window()
    chain(
        rd,
        ensure_tables(),
        [generate_day(rd), fetch_fx(rd)],
        load_raw.partial(run_date=rd).expand(table=TABLES),
        dbt_build,
    )


recon_daily()
