Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0002: Raw write path and time model

- **Status:** Accepted
- **Date:** 2026-11-01
- **Accepted on:** 2026-11-02
- **Accept at:** M10, step S10.2
- **Written by:** an AI agent in build mode (the owner's decision of 2026-11-02 in `AGENTS.md`, heading "Build mode"), checked against the code and `docs/evidence/`. "I" below is the project's voice.

## Context

1. The sandbox refuses DML and streaming inserts, and Cloud Storage needs billing (ADR-0001). Load jobs and API table operations, such as deleting a partition, work and are free.
2. Every run must be idempotent: rerunning any day, in any order, must leave the same rows. The rerun proof (N1) tests exactly this.
3. In the synthetic world, data arrives late by design: a webhook redelivery often comes on the next UTC day, and a statement line comes 1 or 2 days after its accounting date.
4. Each payment has three dates: arrival (the UTC day the data reached me), booking (`DATE(event_ts)` in UTC) and accounting (the PSP's day, set by the MID's fixed UTC offset). The marts are full rebuilds (ADR-0008).

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| One `WRITE_TRUNCATE` load per (table, arrival day) into `table$YYYYMMDD` | atomic, free, not DML; wrong-day rows refused | probe P3 must pass | **Chosen** |
| `MERGE`, streaming or Cloud Storage | familiar | refused, or needs billing | Rejected |
| `WRITE_APPEND` plus dedup views | works | each rerun adds a copy | Rejected |
| Daily shard tables | load jobs only | many tables; fixed schemas | **Fallback** if P3 fails |
| Raw by arrival date | a run owns its day | marts regroup by date | **Chosen** |
| Raw by booking date | the revenue calendar | late data rewrites old partitions | Rejected |
| `as_of` from a `run_date` var or `CURRENT_DATE()` | explicit, or no input | reruns roll the marts back, or differ | Rejected |
| `as_of` = latest loaded arrival date | deterministic | "what we know now" only | **Chosen** |

Why these three choices:

1. A `WRITE_TRUNCATE` load into one partition replaces that day and nothing else. Running it twice gives the same result as running it once, which is what idempotent means. `WRITE_APPEND` would add a copy on every rerun.
2. Partitioning raw by arrival date means a run for day R writes only partition R. Late data lands on the day it arrived, so an old partition is never rewritten. If I partitioned by booking date, a late redelivery would have to change an old partition.
3. "Today" for the marts is the newest loaded arrival date, read from the data. A `run_date` var would make an old rerun roll the marts back to that day, and `CURRENT_DATE()` would give a different answer each day.

## Decision

1. The raw tables are `raw.payment_events`, `raw.settlement_lines` and `raw.fx_rates`. All three are `PARTITION BY _arrival_date`. They are clustered by `mid`, `mid` and `provider`. Host runs use the same tables in `raw_dev`.
2. One JSON file per table in `src/recon/schemas/` is the contract. `ensure_tables` creates the tables from it, `load_partition` passes the same fields as `LoadJobConfig.schema`, and the pytest `test_rows_match_schema` checks generated rows against it.
3. `recon.load.load_day` is the same code in the DAG and on the host. It follows "Load protocol" in `docs/specs/bigquery_sandbox_and_costs.md`. Before any job, it checks that every row's `_arrival_date` equals the run date R, and, for payment events, that `DATE(delivered_ts)` does too. On an empty day it deletes the partition with `client.delete_table(..., not_found_ok=True)`, which is a table operation, not DML. Otherwise it runs exactly one `WRITE_TRUNCATE` load job into `<table>$YYYYMMDD` and checks `job.output_rows == len(rows)`.
4. `stg_recon__as_of` returns one row. `as_of_date` is `MAX(_arrival_date)` of `source('psp', 'payment_events')`, and `scope_start` is the earliest arrival date up to it. The staging models keep only rows with `_arrival_date <= as_of_date`, and every mart row stores `as_of_date`.
5. The full-rebuild marts take no run-date var (U5's snapshot model adds one). The `as_of_date` var is only for host time travel on target `dev`: `stg_recon__as_of` raises a compile error if it is passed with target `airflow`.
6. A one-sided line dated before `scope_start` gets the status `before_scope` (ADR-0003). It belongs to a day I never loaded, so it is not a missing payment.

## Consequences

**Cost.** Load jobs and partition deletes are free. Raw data is about 0.1 MB a day (a design estimate, not a result).

**Better.** Reprocess, clear and backfill are safe in any order. Late data lands on its arrival day, and an old rerun cannot change the marts. The rerun proof measured this on 2026-11-02 on synthetic payments: after reprocessing 7 days (2026-10-26 to 2026-11-01) and clearing the older day 2026-10-14 out of order, `make compare` found 146 of 146 (table, partition) groups identical, 17595 rows, with `as_of_date` 2026-11-01 before and after (`docs/evidence/2026-11-02/compare.json` and `summary.json`, N1).

**Worse.** `load_day` holds one partition in memory, which is fine at about 200 rows a day (a design estimate). Everything rests on probe P3, which passed on 2026-11-01 (ADR-0001, "G0 results"). The marts answer "as of now" only: they do not keep what an earlier day knew.

**Revisit when.** P3 fails (then I switch to shard tables and record it here), a source cannot be tied to one arrival day, or the project moves to billing (`MERGE` costs bytes, while load and copy jobs stay free).

## Sources (checked 2026-11-01)

Decorator loads https://docs.cloud.google.com/bigquery/docs/load-data-partitioned-tables; atomic `writeDisposition` https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/Job; partition delete https://docs.cloud.google.com/bigquery/docs/managing-partitioned-tables; free loads https://cloud.google.com/bigquery/pricing; DML pricing https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax; wildcard tables https://docs.cloud.google.com/bigquery/docs/querying-wildcard-tables; a self-reported sandbox run https://github.com/HabilMB/indonesia-haze-monitor/pull/1.
