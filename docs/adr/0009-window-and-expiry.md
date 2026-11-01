Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0009: Window and expiry

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** U3 (M13), step S13.5

## Context

1. In the sandbox, "all tables, views, and partitions automatically expire after 60 days"; longer expirations are refused (community reports).
2. A partition expires 60 days after its date. Rows dated more than 60 days back vanish right after a load, copy or CTAS, while the job reports success.
3. In a sandbox dataset, a date-partitioned table gets no table-level expiration; setting one would override partition expiry. Views and unpartitioned tables expire 60 days after creation, and dbt recreates them.
4. The proof must stay reproducible for weeks after 1-2 Nov 2026. Reviewers advised at most about 30 days of history; the warehouse research allowed about 55.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| About 55 days | the most history | old partitions expire within 15 days, breaking later reruns | Rejected |
| 28 days from 2026-10-04, ending yesterday (UTC) | weeks of margin; four weekends of NBK rates | less history | **Chosen** |
| 14 or 7 days | a faster backfill | thin for the 7-day gate and weekend FX | Cut-order fallback |
| INT64 range partitions | no partition expiry | the table expires 60 days after creation | Rejected |
| Raise `partition_expiration_days` | keeps data | refused in the sandbox | Not possible |
| No write guard | less code | the failure is silent | Rejected: a 45-day guard |

## Decision

1. `RECON_WORLD_START = 2026-10-04`; no payment exists before it. History for v1.0 is 2026-10-04 to 2026-10-31 (28 days), loaded newest first; the 00:00 UTC run on 2 Nov adds 2026-11-01, so the proof window is 29 days.
2. `check_window` refuses run dates before `RECON_WORLD_START`, on or after today (UTC), or older than today minus 45 days. Never lift the guard.
3. Never a table expiration on a partitioned table, a `partition_expiration_days` change, or dbt `hours_to_expiration` on partitioned models.
4. The proof's date range starts on 2026-10-03, because a USD accounting date can fall a day before its booking date.
5. Results are committed in `docs/evidence/<date>/`, so the numbers survive the expiry. After the window ages out, reset the datasets and move `RECON_WORLD_START` (v1.x `make demo`): keyed on `day_index` (ADR-0010), the synthetic numbers repeat and only real FX changes.
6. U3 adds an 8 GiB stop to `check_window`, fed by a bytes-written ledger.

## Consequences

**Cost.** None; a shorter window writes fewer bytes.

**Better.** The 2026-10-04 partition lives until about 2026-12-03; the whole window can be reprocessed until 2026-11-18 (UTC); `before_scope` keeps aged-out one-sided lines out of the exceptions (ADR-0003).

**Worse.** After 2026-11-18 the full window cannot be reprocessed; from about 2026-12-03 old partitions disappear; idle views and tables expire 60 days after their last build.

**Revisit when.** A demo must run after 2026-11-18 (`make demo`), a feature needs more history, Google changes the expiry rules, or the follow-up check on or after 2026-12-31 ("Rolling window and expiry" in `docs/specs/bigquery_sandbox_and_costs.md`) finds a table expiration. Result: [not run yet].

## Sources (checked 2026-11-01)

Sandbox https://docs.cloud.google.com/bigquery/docs/sandbox; partition expiry https://docs.cloud.google.com/bigquery/docs/managing-partitioned-tables; dataset defaults https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/datasets; which expiration wins https://docs.cloud.google.com/bigquery/docs/updating-datasets; silent row loss and the 60-day cap (self-reported) https://github.com/Ardiyanto24/nirwana-database/blob/main/milestones/2.3-layer-intermediate-mart-cleaned/logs.md and https://github.com/ayush-ranjan-official/people-analytics-warehouse/blob/main/docs/platform-notes.md.
