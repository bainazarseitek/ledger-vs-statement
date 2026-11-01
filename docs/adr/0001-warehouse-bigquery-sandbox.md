Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0001: Warehouse

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** M10, step S10.2. Fill in the G0 results below at step S1.5.

## Context

1. The project practises BigQuery with Airflow 3 and dbt, on about 0.1 MB a day (design estimate). It must cost $0, never charge automatically, and stay rebuildable by anyone without a card.
2. The sandbox is a project with no billing account. It refuses DML (`INSERT`, `UPDATE`, `DELETE`, `MERGE`) and streaming inserts, and Cloud Storage needs billing. "All tables, views, and partitions automatically expire after 60 days."
3. Storage is "a lifetime limit of 10 GiB", "not refunded upon data deletion", with undocumented metering. It replaced a monthly limit between the page revisions of 2026-08-26 and 2026-09-04.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| BigQuery sandbox, DML-free | $0, no card, real BigQuery | no `MERGE` or snapshots | **Chosen** |
| GCP Free Trial | no sandbox limits | a card; a possible prepayment; once only; 90 days | **Plan B** |
| Paid account in the free tier | no limits | overage is charged automatically | Rejected |
| Snowflake trial | no card; `MERGE` | 30 days (120 with the student link, unconfirmed), then suspended; terms provide for deleting data after termination; not BigQuery | Rejected |
| Databricks Free Edition | no card, no end date | unpublished daily limit; deletion after 60 days without login; terms bar publishing benchmarks; not BigQuery | Rejected |
| DuckDB on the laptop | $0, offline | not a cloud warehouse | Rejected |

## Decision

1. The BigQuery sandbox is the only warehouse: a personal Google account with "No organization" (never a university account), one project with display name `ledger-vs-statement`, no billing account. The project id lives only in `.env` (`GCP_PROJECT`).
2. All datasets in `US`: `raw`, `raw_dev`, `analytics`, `analytics_dev`, `probe`.
3. No DML, no `insert_all` or `insert_rows_json`, no Cloud Storage: load jobs (ADR-0002), views and small tables (ADR-0008).
4. `maximum_bytes_billed: 1000000000` in the dbt profile and every Python query. Every byte written counts: a 1 GiB self-cap until U3 adds an 8 GiB stop.
5. Never a second sandbox project to reset the quota: the Google Cloud Terms forbid it.
6. Plan B, the GCP Free Trial, has two triggers only: P3 and the shard-table fallback both fail, or a storage-quota error appears. Its steps and stop rules (a new project, stop on a prepayment or a refused card, never Activate or Upgrade) are under "Plan B: the GCP Free Trial" in `docs/specs/bigquery_sandbox_and_costs.md`. Record "Plan B in use since [date] because [trigger]" here. If sign-up is blocked, record what the screen said and stop: Snowflake and Databricks are never fallbacks.

### G0 results

Fill in from `scripts/g0_probe.py` by Sunday 12:00 (hard stop 13:00). Never paste the project id or a job id. Code, fallbacks and decision rules: "G0 probes runbook" and "Decision rules at G0" in `docs/specs/bigquery_sandbox_and_costs.md`.

| Id | Checks | Pass when | Result |
|---|---|---|---|
| S1.1 | new project | SANDBOX badge, no billing account | PASS |
| S1.2 | key at `keys/sa.json` | `git check-ignore` prints its path | PASS |
| S1.3 | `uv run dbt debug` | Core 1.12.6, bigquery 1.12.1, "All checks passed!" | PASS |
| P1 | a CTAS and a view in `probe` | both succeed | PASS |
| P2 | `INSERT INTO probe.t (x) VALUES (2)` | refused with "DML queries are not allowed in the free tier" | PASS |
| P3 | two `WRITE_TRUNCATE` loads into `probe.raw_pay$<yesterday>`, one into another day | only the second load's row remains; the other day untouched; timestamps load | PASS |
| P4 | a wrong-day row into `$<yesterday>` | refused | PASS |
| P5 | partition delete, then COUNT | 0 | PASS |
| P6 | expirations | 60 days (5184000000 ms); no table expiration on `raw_pay` | PASS |
| P7 | `__TABLES__`, `INFORMATION_SCHEMA.TABLE_STORAGE` | one readable | PASS: `__TABLES__` readable; TABLE_STORAGE not enabled for the project |
| F1 | one Frankfurter request | HTTP 200; weekday rows only | PASS |
| P8 | optional `copy_partitions` model, run twice | "Copying table(s)"; no "merge into" or "insert into" | not run |

- P2 error text, verbatim from your own run: `403 Billing has not been enabled for this project. Enable billing at https://console.cloud.google.com/billing. DML queries are not allowed in the free tier. Set up a billing account to remove this restriction.; reason: billingNotEnabled`
- Write path: decorator loads. Authentication: service-account key.
- Notes: empty-day rule (P5) partition delete; storage source (P7) `__TABLES__`; FX fetch (F1) live task.
- Probes run at: 2026-11-01 15:03 UTC

## Consequences

**Cost.** $0 with no card; under 0.25 GiB written in v1.0 (design estimate); bytes are never a reported result.

**Better.** Real BigQuery practice in a repo anyone can rebuild; the limits become the README heading "Platform constraints (G0 probes)".

**Worse.** No `MERGE` or snapshots; a date outside the window loses its rows silently (ADR-0009); the storage counter cannot be read.

**Revisit when.** A Plan B trigger fires; the U3 ledger hits its 8 GiB stop, or a Google change stops load jobs or DDL (not triggers: stop writes and decide here, because the trial is once only); a version must run `MERGE` or snapshots (the v3 trial).

## Sources (checked 2026-11-01)

Sandbox https://docs.cloud.google.com/bigquery/docs/sandbox, revisions https://web.archive.org/web/20260831134612/https://docs.cloud.google.com/bigquery/docs/sandbox and https://web.archive.org/web/20260905040453/https://docs.cloud.google.com/bigquery/docs/sandbox; trial https://docs.cloud.google.com/free/docs/free-cloud-features; prepayment https://docs.cloud.google.com/billing/docs/how-to/payment-methods; budgets https://docs.cloud.google.com/billing/docs/how-to/budgets; terms https://cloud.google.com/terms; Snowflake https://docs.snowflake.com/en/user-guide/admin-trial-account, https://www.snowflake.com/en/legal/terms-of-service/self-service-on-demand-terms-of-service/ and https://signup.snowflake.com/?trial=student; Databricks https://docs.databricks.com/aws/en/getting-started/free-edition-limitations and https://www.databricks.com/legal/acceptable-use-policy-fe.
