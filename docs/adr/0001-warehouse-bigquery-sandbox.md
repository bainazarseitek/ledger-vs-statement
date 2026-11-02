Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0001: Warehouse

- **Status:** Accepted
- **Date:** 2026-11-01
- **Accepted on:** 2026-11-02
- **Accept at:** M10, step S10.2. The G0 results below were filled in at step S1.5.
- **Written by:** an AI agent in build mode (the owner's decision of 2026-11-02 in `AGENTS.md`, heading "Build mode"), checked against the code and `docs/evidence/`. "I" below is the project's voice.

## Context

1. I wanted to practise BigQuery with Airflow 3 and dbt on a small daily load, about 0.1 MB a day (a design estimate, not a result). The project must cost $0, must never charge me automatically, and anyone without a card must be able to rebuild it.
2. The BigQuery sandbox is a project with no billing account. It refuses DML (`INSERT`, `UPDATE`, `DELETE`, `MERGE`) and streaming inserts. Cloud Storage needs billing. The sandbox page says: "All tables, views, and partitions automatically expire after 60 days."
3. Storage is "a lifetime limit of 10 GiB", "not refunded upon data deletion", and Google does not document how it is metered. The page changed from a monthly limit to this lifetime limit between its revisions of 2026-08-26 and 2026-09-04.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| BigQuery sandbox, DML-free | $0, no card, real BigQuery | no `MERGE` or snapshots | **Chosen** |
| GCP Free Trial | no sandbox limits | a card; a possible prepayment; once only; 90 days | **Plan B** |
| Paid account in the free tier | no limits | overage is charged automatically | Rejected |
| Snowflake trial | no card; `MERGE` | 30 days (120 with the student link, unconfirmed), then suspended; terms provide for deleting data after termination; not BigQuery | Rejected |
| Databricks Free Edition | no card, no end date | unpublished daily limit; deletion after 60 days without login; terms bar publishing benchmarks; not BigQuery | Rejected |
| DuckDB on the laptop | $0, offline | not a cloud warehouse | Rejected |

I chose the sandbox because it is the only option that is real BigQuery, needs no card and cannot bill me. The price is that the whole design must work without DML. The trials either end, delete data or are not BigQuery, so they are not fallbacks for this project.

## Decision

1. The BigQuery sandbox is my only warehouse. It runs under a personal Google account with "No organization" (never a university account), in one project with display name `ledger-vs-statement` and no billing account.
2. The project id lives only in `.env`, as `GCP_PROJECT`. Code reads it from that variable, and every saved file writes `<project>` instead. On 2026-11-01 I kept the project id that the console proposed, so it is the same string as the repo name. It is deliberately not on the private banned-word list: the repo name is written all over the repo, so listing it would block every push. The rule ("never write the id"), the environment variable and the `redact` functions in `scripts/g0_probe.py` and `scripts/storage.py` guard it, not the pre-push hook. One side effect: `redact` also replaces the repo name with `<project>` wherever it appears in saved probe output.
3. All datasets are in `US`: `raw`, `raw_dev`, `analytics`, `analytics_dev` and `probe`.
4. No DML, no `insert_all` or `insert_rows_json`, and no Cloud Storage. Data goes in only through load jobs (ADR-0002), and dbt builds only views and small tables (ADR-0008).
5. `maximum_bytes_billed: 1000000000` is set in `dbt/profiles.yml` for both targets, and `src/recon/bq.py` sets the same cap on every Python query. I treat every byte written as counted: my own cap is 1 GiB written until U3 adds a bytes-written ledger with an 8 GiB stop.
6. Never a second sandbox project to reset the quota: the Google Cloud Terms forbid it.
7. Plan B is the GCP Free Trial. It has two triggers only: probe P3 and the shard-table fallback both fail, or a storage-quota error appears. Its steps and stop rules (a new project, stop on a prepayment or a refused card, never Activate or Upgrade) are under "Plan B: the GCP Free Trial" in `docs/specs/bigquery_sandbox_and_costs.md`. If sign-up is blocked, I record what the screen said and stop: Snowflake and Databricks are never fallbacks.
8. Plan B is not in use (`"plan_b": false` in `docs/evidence/2026-11-01/g0_probe.json`). P3 passed, so the first trigger never fired, and `docs/failure_log.md` holds no storage-quota error, so the second one has not fired either.

### G0 results

Only the rows P1 to P7 and F1 are from `scripts/g0_probe.py` (`make probe`), saved in `docs/evidence/2026-11-01/g0_probe.json`. The rows S1.1 to S1.3 are setup checks, not probe output, and that file does not hold them: they are recorded in the S1.1, S1.2 and S1.3 entries of `docs/build_journal.md` (the owner's console check, the `git check-ignore keys/sa.json` output, and `make doctor` with `Command dbt debug succeeded`). P8 is optional and was not run, so that file has no P8 entry; the S1.5 entry of `docs/build_journal.md` records that. No project id and no job id appear here. Code, fallbacks and decision rules: "G0 probes runbook" and "Decision rules at G0" in `docs/specs/bigquery_sandbox_and_costs.md`.

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

- P2 error text, verbatim from my run (first line; the job id on a later line is left out): `403 Billing has not been enabled for this project. Enable billing at https://console.cloud.google.com/billing. DML queries are not allowed in the free tier. Set up a billing account to remove this restriction.; reason: billingNotEnabled, message: Billing has not been enabled for this project. Enable billing at https://console.cloud.google.com/billing. DML queries are not allowed in the free tier. Set up a billing account to remove this restriction.`
- Write path: decorator loads. Authentication: service-account key.
- Notes: empty-day rule (P5) partition delete; storage source (P7) `__TABLES__`; FX fetch (F1) live task.
- Probes run at: 2026-11-01 15:03 UTC

What the probes told me: the refusal in P2 is the reason the design has no DML at all. P3, P4 and P5 together are the reason the raw write path in ADR-0002 works: a `WRITE_TRUNCATE` load into one partition replaces only that day, a row for another day is refused, and an empty day is handled by deleting the partition. P7 means I can read stored bytes from `__TABLES__`, but not the lifetime counter.

## Consequences

**Cost.** $0, with no card. On 2026-11-02, `make storage` read 5600870 logical bytes stored across the five datasets through `__TABLES__` (`docs/evidence/2026-11-02/storage.json`). That file says it is a lower bound, because the lifetime quota may count every byte ever written. Bytes are never a headline result.

**Better.** I practise on real BigQuery in a repo that anyone can rebuild without a card. The platform limits are written down in the README heading "Platform constraints (G0 probes)".

**Worse.** No `MERGE` and no snapshots. A date outside the window loses its rows silently (ADR-0009). I cannot read the storage counter that the quota uses: `INFORMATION_SCHEMA.TABLE_STORAGE` is not enabled for the project (P7, and again in `storage.json`).

**Revisit when.** A Plan B trigger fires. Or the U3 ledger hits its 8 GiB stop, or a Google change stops load jobs or DDL: these are not Plan B triggers, so I stop writing and decide here, because the trial can be used only once. Or a version must run `MERGE` or snapshots.

## Sources (checked 2026-11-01)

Sandbox https://docs.cloud.google.com/bigquery/docs/sandbox, revisions https://web.archive.org/web/20260831134612/https://docs.cloud.google.com/bigquery/docs/sandbox and https://web.archive.org/web/20260905040453/https://docs.cloud.google.com/bigquery/docs/sandbox; trial https://docs.cloud.google.com/free/docs/free-cloud-features; prepayment https://docs.cloud.google.com/billing/docs/how-to/payment-methods; budgets https://docs.cloud.google.com/billing/docs/how-to/budgets; terms https://cloud.google.com/terms; Snowflake https://docs.snowflake.com/en/user-guide/admin-trial-account, https://www.snowflake.com/en/legal/terms-of-service/self-service-on-demand-terms-of-service/ and https://signup.snowflake.com/?trial=student; Databricks https://docs.databricks.com/aws/en/getting-started/free-edition-limitations and https://www.databricks.com/legal/acceptable-use-policy-fe.
