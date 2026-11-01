Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# Design: Two Ledgers (`ledger-vs-statement`)

Author: Bainazar Seitek · Written 2026-11-01 · Status: draft for v1.0 · About 4 minutes to read

Versions `v1.1` to `v1.7` are the upgrades U1 to U7 in `docs/build_plan.md`.

## Problem and who the output is for

A small web-to-app subscription business takes card payments through one payment service provider (PSP), `psp_alpha`, on two merchant accounts (MIDs): `mid_usd_01` charges and settles in USD, `mid_kzt_01` in KZT. Every sale lands in two ledgers. The **revenue ledger** books it from the PSP's webhooks, by UTC date. The MID's **settlement statement** books it on the acquirer's accounting date and arrives 1 or 2 days later.

Most gaps are harmless timing: a different day boundary, or a statement still on its way. Some need a person: a lost webhook, a sale never settled, a settled amount that differs, a fee above the contract. Finance wants every MID-day where the ledgers disagree, and why.

The output is for:
- a **payments analyst**, who works the exception queue `fct_recon_exceptions`;
- a **finance lead**, who reads `fct_recon_daily`: each MID-day gap split into dated reason codes, with 0 unexplained;
- the **data engineer on duty**, who needs runs that fail loudly and give the same result when rerun.

## Goals

1. **Idempotent daily loads without DML:** one load job replaces one partition per raw table per day, and fingerprints prove that reprocessing changes nothing.
2. **Airflow 3 interval semantics used correctly:** a data-interval timetable, a guard task, a 1-slot pool for dbt, and exact days only through one-day backfills.
3. **A reconciliation finance can trust:** one status per line, dated reason components, and a cross-ledger identity in integer minor units that a mutation check shows can fail.
4. **Honest evidence:** synthetic data labelled, real rates stored as published, the defect catalog committed before any matcher SQL, and every number dated and tied to a `make` target.
5. **$0 and explainable:** about 900 to 1,000 lines of logic that I can explain.

## Non-goals

- Not production experience, real PSP behaviour or file formats, detection quality on real data, scale (about 200 payments a day), or any fact about a real company.
- Not in v1.0 (backlog in `docs/roadmap.md`, never stubs in code): refunds, chargebacks, payouts and statement headers, cross-currency settlement, business-day calendars and holidays, a Postgres app database with a watermark extract, FileSensor, Cosmos, BigQuery check operators, CI, source freshness, incremental models, the held-out world, `scripts/eval.py`, unit tests UT3 and UT4, the bytes-written ledger, app-store, ad-spend and event-integrity lanes, Data Studio, dbt docs on GitHub Pages.

## Data sources

- **SYNTHETIC payments:** `src/recon/generator.py` writes webhook deliveries and per-MID statement lines per arrival date to `landing/` (gitignored). Prices, plan mix and volumes are illustrative assumptions, and every synthetic row and table is labelled. The answer key stays in local files and is never loaded.
- **REAL exchange rates,** for the USD reporting columns only: National Bank of Kazakhstan (NBK) USD/KZT rates via Frankfurter v2, landed once per run in `landing/fx/` (committed, never refetched). NBK's own RSS feed is saved for a weekend cross-check.

The planted defects (D1 to D5) and benign behaviours (B1 to B3) are under "Defect catalog" in `docs/specs/data_and_generator.md`.

## Architecture and data flow

```
        SYNTHETIC (seeded generator)                               REAL
  src/recon/generator.py                                   Frankfurter v2, providers=nbk
  pure f(seed, day_index, MID, purpose)                    USD/KZT as published, R-6..R
  webhooks + per-MID statement lines                       fetched once, never refetched
  answer key (local files only, never loaded)                        |
            |                                                        |
            v                                                        v
  landing/payment_events/arrival_date=R/part-000.ndjson    landing/fx/provider=nbk/arrival_date=R.json
  landing/settlement_lines/arrival_date=R/mid=<mid>.ndjson landing/fx/provider=nbk/arrival_date=R.meta.json
  landing/_truth/booking_date=R.ndjson   (gitignored)      (committed to git)
            |                                                        |
            +----------------------------+---------------------------+
                                         |
  Airflow 3.3.2, DAG recon_daily, CronDataIntervalTimetable("0 0 * * *", timezone="UTC"), catchup off
  check_window -> ensure_tables -> [generate_day, fetch_fx] -> load_raw x 3 (mapped) -> dbt_build (pool dbt_serial)
                                         |
        one WRITE_TRUNCATE load job per (table, R) into table$YYYYMMDD; empty day -> partition delete
                                         v
  BigQuery sandbox (US, no billing, no DML), dataset raw (host dev runs use raw_dev)
     raw.payment_events     raw.settlement_lines     raw.fx_rates        partitioned by _arrival_date
                                         |
  dbt-core 1.12.6 + dbt-bigquery 1.12.1 in /opt/airflow/dbt_venv  ->  dataset analytics (host: analytics_dev)
     staging (views)      stg_recon__as_of | stg_psp__payment_events (dedup) | stg_psp__settlement_lines | stg_fx__rates
     intermediate (views) int_ledger__captures | int_fx__usd_rates_daily
     marts                fct_recon_lines (table)  ->  fct_recon_exceptions (view, one row per line and cause)
                          fct_recon_daily (table, contract): two-calendar bridge, unexplained_minor must be 0
     tests                identity, preservation, redeliveries, completeness (error); business gate, FX restated (warn)
                                         |
  committed evidence: docs/evidence/2026-11-02/ (summary.json, fingerprints, compare, fx report, storage)
  local only: scripts/eval.py (U1) regenerates the answer key and SELECTs the marts
```

### Three dates

| Date | Meaning | Column |
|---|---|---|
| Arrival | the UTC day a webhook or a statement file reached us; one run owns one arrival date | `_arrival_date`, the raw partition key |
| Booking | our revenue day: `DATE(event_ts)` in UTC | `int_ledger__captures.booking_date` |
| Accounting | the PSP's day: capture time shifted by the MID's fixed offset (UTC-5 for USD, UTC+5 for KZT) | `settlement_lines.accounting_date` |

`as_of_date` (the latest loaded arrival date) and `scope_start` (the earliest) come from the data, never from the clock. So rerunning an old day never rolls the marts back.

### The date window

- `RECON_WORLD_START = 2026-10-04`. History is 2026-10-04 to 2026-10-31 (28 days), loaded newest first. The scheduled run on 2026-11-02 adds 11-01, so the proof window has 29 days.
- Sandbox partitions expire 60 days after their date, and rows dated more than 60 days back vanish silently on load. So `check_window` and the host CLI refuse any day older than 45 days: 10-04 can be rerun until 2026-11-18 (UTC).
- After expiry, the numbers survive in `docs/evidence/`.

## Cost, storage and sandbox constraints

$0: one BigQuery sandbox project on a personal Google account, "No organization", no billing account. The sandbox rules out MERGE upserts and dbt snapshots. Incremental raw loads, safe reruns, backfills, tests and contracts all still work.

| Sandbox rule | Design response |
|---|---|
| No DML (INSERT, UPDATE, DELETE, MERGE) | load jobs, views and full-rebuild tables only; never dbt `merge` or default `insert_overwrite`, `insert_overwrite` or `microbatch` without `copy_partitions`, `time_ingestion_partitioning`, snapshots or Elementary |
| No streaming, Cloud Storage or Data Transfer Service | no `insert_all`, no GCS; Airflow does all scheduling |
| Everything expires after 60 days | the 29-day window, the 45-day guard, and no table expiration on partitioned tables |
| Lifetime 10 GiB of storage, not refunded, metering undocumented | count every byte written; staging and intermediate are views; self-cap of 1 GiB until v1.3 adds a bytes-written ledger with an 8 GiB stop; never a second sandbox project to reset the quota (the Google Cloud Terms forbid it) |
| 1 TiB of queries a month | `maximum_bytes_billed: 1000000000` (1 GB per query) in the profile and in every Python query |

Plan B, only if both decorator loads and shard tables fail or the quota is hit: the GCP Free Trial in a new project. Stop if sign-up asks for a prepayment, and never click Activate or Upgrade.

## Top risks

| Risk | Mitigation |
|---|---|
| A sandbox write path or the key fails | probes before any pipeline code (gate G0), with fallbacks chosen in advance: shard tables, Application Default Credentials, Plan B |
| The rerun proof fails for a trivial reason | no wall-clock columns; `fetched_at` frozen in the landed meta file; FX never refetched; the proof stays inside one UTC day and compares `as_of_date` |
| A check that cannot fail, or that grades itself | catalog committed first; identity built from two models; the mutation check; fee noise that crosses the tolerance on purpose; a held-out world in v1.4 |
| More scope than time | a minimum scope, a cut order and gates with hard stops, all in `docs/build_plan.md` |

## Where the details live

- Components: "Where things are" in `AGENTS.md`.
- Data model, reconciliation method, testing and data quality: "Models", "`fct_recon_lines`", "`fct_recon_daily`" and "Tests" in `docs/specs/dbt_project.md`.
- Orchestration, failure modes and recovery: "The DAGs", "Operations runbook" and "Failure scenarios and what to do" in `docs/specs/airflow_and_docker.md`.
- Security, secrets and Plan B: "Key handling rules" and "Plan B: the GCP Free Trial" in `docs/specs/bigquery_sandbox_and_costs.md`. The key stays in `keys/`, gitignored and mounted read-only, and `.env` is never committed.
- Decisions: `docs/adr/README.md`.
- Success criteria: "Results and how they were measured" in `README.md`.
