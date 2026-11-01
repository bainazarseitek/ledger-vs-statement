Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0008: Materialization and incremental

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** U5 (M15), step S15.3, after probe P8 and the log check

## Context

1. A materialization is how dbt stores a model: a view, a full-rebuild table, or an incremental table.
2. The sandbox refuses DML (ADR-0001). In dbt-bigquery 1.12.1, `merge` and `insert_overwrite` or `microbatch` without `copy_partitions` all run `MERGE`; snapshots `MERGE` from their second run; `time_ingestion_partitioning` and Elementary use `INSERT`.
3. With `copy_partitions: true`, `insert_overwrite` uses a CTAS plus `WRITE_TRUNCATE` copy jobs: no DML. Third parties report it working in sandboxes (October 2026), Google does not document it, and open bug dbt-adapters #2086 crashes it on a NULL partition value.
4. The data is a few MB, and every byte written may count against the lifetime 10 GiB.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| `merge`, or `insert_overwrite` without `copy_partitions` | dbt's defaults | run `MERGE` | Rejected |
| `insert_overwrite` + `copy_partitions: true` | no DML; free copy jobs | undocumented for the sandbox; writes twice; bug #2086 | U5 only, gated on P8 |
| `microbatch` + `copy_partitions` | built-in batching | no public sandbox run | Rejected |
| Full rebuild: views, then small mart tables | no DML; deterministic; simple | rewrites the marts each build | **Chosen for v1.0** |
| Tables or ephemeral models for staging | fast, or no storage | use the quota, or cannot be queried | Rejected |
| dbt snapshots | the standard history tool | `MERGE` from the second run | Rejected |

## Decision

1. v1.0: `staging` and `intermediate` are `view`; `marts` are `table`, except `fct_recon_exceptions` (`view`). No incremental models and no custom schemas.
2. `fct_recon_lines` and `fct_recon_daily`: `partition_by` on `recon_date` (DATE), `cluster_by` `mid`; `fct_recon_daily` has an enforced contract.
3. U5 adds `fct_recon_status_daily`: `materialized='incremental'`, `incremental_strategy='insert_overwrite'`, `partition_by={'field': 'as_of_date', 'data_type': 'date', 'granularity': 'day', 'copy_partitions': true}`, `on_schema_change='fail'`, `full_refresh=false`, reading arrivals up to `var('run_date')`. `as_of_date` is NOT NULL, with a `not_null` test.
4. U5 is accepted only after probe P8 and a `logs/dbt.log` with "Copying table(s)" and no "merge into" or "insert into". If P8 fails, the model is a full rebuild and this ADR says why.
5. Never: `merge` or default `insert_overwrite`; `insert_overwrite` or `microbatch` without `copy_partitions`; `time_ingestion_partitioning`; snapshots; Elementary; `hours_to_expiration` on partitioned models; Python models; `CURRENT_DATE()` or `CURRENT_TIMESTAMP()`; `POW()`; FLOAT64 money; `SELECT *` from raw in marts.
6. Keep `dbt-bigquery==1.12.1` pinned: an unreleased change alters how first builds create tables.

## Consequences

**Cost.** About 1 to 2 MB per build, under 0.25 GiB over about 80 builds (design estimates; `scripts/storage.py` measures).

**Better.** The same raw data always gives the same marts, with no `is_incremental()` logic to get wrong.

**Worse.** Incremental models appear only in U5, and each build rewrites the marts (fine at MB size, wasteful at scale).

**Revisit when.** A build writes tens of MB or takes minutes, P8 fails, the project moves to billing (`copy_partitions` stays cheaper than `MERGE`), or a dbt-bigquery release changes the copy path (run P8 again).

## Sources (checked 2026-11-01)

Configs https://docs.getdbt.com/reference/resource-configs/bigquery-configs; macro https://github.com/dbt-labs/dbt-adapters/blob/main/dbt-bigquery/src/dbt/include/bigquery/macros/materializations/incremental_strategy/insert_overwrite.sql; bug #2086 https://github.com/dbt-labs/dbt-adapters/issues/2086; first-build change https://github.com/dbt-labs/dbt-adapters/pull/2189; pricing https://cloud.google.com/bigquery/pricing; sandbox runs (self-reported) https://github.com/HabilMB/indonesia-haze-monitor/pull/2 and https://github.com/artichautttt/gcp-taxi-pipeline/pull/1; Elementary https://github.com/elementary-data/dbt-data-reliability/blob/master/macros/utils/table_operations/insert_rows.sql.
