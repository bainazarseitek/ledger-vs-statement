Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0005: Orchestration and run semantics

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** U1 (M11), step S11.5

## Context

1. One run must process exactly one UTC arrival day (ADR-0002).
2. In Airflow 3, a cron string or `"@daily"` becomes a `CronTriggerTimetable` with an empty data interval.
3. A manual trigger gets the last complete period before the trigger time, so it means "yesterday, as of now". Runs without a logical date have no interval.
4. Backfill runs obey their own `--max-active-runs`, separately from the DAG's, and run only on an unpaused DAG. Two dbt builds must never overlap.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| `"@daily"`, a cron string or Asset triggers | short, or event-driven | no usable data interval | Rejected |
| `CronDataIntervalTimetable("0 0 * * *", timezone="UTC")` | each run covers one UTC day | an explicit import | **Chosen** |
| `catchup=True`, or history oldest first | automatic, or natural | no dry run; early runs see a gap | Rejected: backfills, newest first |
| `max_active_runs=1` as the only guard | simple | backfills are limited separately | Rejected: add a pool |
| One retry policy for all tasks | simple | deterministic failures only wait longer | Rejected: by task type |
| Exact days by UI, REST or CLI trigger | quick | the interval comes from the trigger time | Rejected: one-day backfills |

## Decision

1. `recon_daily` uses `CronDataIntervalTimetable("0 0 * * *", timezone="UTC")` from `airflow.sdk`, `start_date=pendulum.datetime(2026, 10, 1, tz="UTC")`, `catchup=False` and `max_active_runs=1`, with Task SDK imports only. The walking skeleton is a separate manual DAG, `smoke_bigquery`, that writes only to `probe`.
2. `check_window` runs first and is the only wall-clock read. With no interval it fails with "No data interval: create exact days with a one-day backfill". It asserts a 1-day interval from 00:00 UTC, `R >= RECON_WORLD_START`, `R < today (UTC)` and `R >= today - 45 days`, then passes R to the other tasks.
3. Retries (delay 30 s): 0 for `check_window`, `generate_day` and `dbt_build` (deterministic; dbt retries BigQuery jobs itself); 2 for `ensure_tables` and `load_raw`; 3 for `fetch_fx`, with `retry_exponential_backoff=2.0` and `max_retry_delay=timedelta(minutes=10)`.
4. `dbt_build` runs in the 1-slot pool `dbt_serial`, created by `airflow-init` and checked by `make doctor`.
5. Templates: only `{{ data_interval_start | ds }}`. Never `{{ ds }}` for manual runs or `datetime.now()` for a business date.
6. Exact days only through one-day backfills, `--dry-run` first. History loads newest first (`--run-backwards`) on an unpaused DAG, which is never paused during a backfill or the proof. Commands: "Operations runbook" in `docs/specs/airflow_and_docker.md`.

## Consequences

**Cost.** Local Docker, $0. One run takes [T] minutes (measured at S6.2); the overnight load needs the Mac on power, lid open, with `caffeinate -is`.

**Better.** Every run names its day, any finished day reruns in any order, and dbt never builds twice at once.

**Worse.** Manual triggers are a trap (see "Manual-run semantics" in `docs/specs/airflow_and_docker.md`); one backfill per DAG runs at a time, and the 3.3.2 CLI cannot cancel one.

**Revisit when.** Airflow 3.4 ships (re-check the CLI and manual inference), a source becomes hourly, or another DAG must react to the marts (Assets).

## Sources (checked 2026-11-01)

Timetables https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/timetable.html; Airflow 3 upgrade https://airflow.apache.org/docs/apache-airflow/stable/installation/upgrading_to_airflow3.html; backfill https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html; CLI https://airflow.apache.org/docs/apache-airflow/3.3.2/cli-and-env-variables-ref.html; manual inference https://github.com/apache/airflow/blob/3.3.2/airflow-core/src/airflow/timetables/interval.py; unpaused-only queueing https://github.com/apache/airflow/blob/3.3.2/airflow-core/src/airflow/jobs/scheduler_job_runner.py; backoff https://github.com/apache/airflow/blob/3.3.2/task-sdk/src/airflow/sdk/bases/operator.py; runs without a logical date https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html.
