Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0002: Raw write path and time model

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** M10, step S10.2

## Context

1. The sandbox refuses DML and streaming, and Cloud Storage needs billing (ADR-0001). Load jobs and API table operations work, for free.
2. Every run must be idempotent: rerunning any day, in any order, leaves the same rows. The rerun proof (N1) depends on it.
3. Data arrives late (synthetic design): a redelivery often comes on the next UTC day, and a statement line 1 or 2 days after the accounting date.
4. Three dates: arrival (the UTC day data reached us), booking (`DATE(event_ts)` in UTC) and accounting (the PSP's day, set by the MID's fixed UTC offset). The marts are full rebuilds (ADR-0008).

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

## Decision

1. Raw tables `raw.payment_events`, `raw.settlement_lines` and `raw.fx_rates`: `PARTITION BY _arrival_date`, clustered by `mid`, `mid` and `provider`. Host runs use `raw_dev`.
2. One JSON per table in `src/recon/schemas/` is the contract for `ensure_tables`, `LoadJobConfig.schema` and a pytest.
3. `recon.load.load_day`, the same in the DAG and on the host, follows "Load protocol" in `docs/specs/bigquery_sandbox_and_costs.md`: check `_arrival_date == R` on every row first; on an empty day, delete the partition (not DML); otherwise run exactly one `WRITE_TRUNCATE` load job and check `job.output_rows == len(rows)`.
4. `stg_recon__as_of`: `as_of_date` is `MAX(_arrival_date)` of `source('psp', 'payment_events')` (never NULL, even on day 1); `scope_start` is the earliest arrival date up to it. Staging keeps `_arrival_date <= as_of_date`; every mart row stores `as_of_date`.
5. No run-date var in full-rebuild marts (U5's snapshot adds one). The `as_of_date` var is for host time travel only, never with target `airflow`.
6. One-sided lines dated before `scope_start` get `before_scope` (ADR-0003).

## Consequences

**Cost.** Load jobs and partition deletes are free; raw data is about 0.1 MB a day (design estimate).

**Better.** Reprocess, clear and backfill are safe in any order; late data lands on its arrival day; an old rerun cannot change the marts.

**Worse.** One partition sits in memory (fine at about 200 rows); everything rests on P3; the marts answer "as of now" only.

**Revisit when.** P3 fails (switch to shard tables and record it here), a source cannot be tied to one arrival day, or the project moves to billing (`MERGE` costs bytes; load and copy jobs stay free).

## Sources (checked 2026-11-01)

Decorator loads https://docs.cloud.google.com/bigquery/docs/load-data-partitioned-tables; atomic `writeDisposition` https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/Job; partition delete https://docs.cloud.google.com/bigquery/docs/managing-partitioned-tables; free loads https://cloud.google.com/bigquery/pricing; DML pricing https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax; wildcard tables https://docs.cloud.google.com/bigquery/docs/querying-wildcard-tables; a self-reported sandbox run https://github.com/HabilMB/indonesia-haze-monitor/pull/1.
