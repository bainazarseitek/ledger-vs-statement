Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# Architecture decision records

An architecture decision record (ADR) is a short, dated file about one decision. It says what forced the decision (context), which options were weighed, what was chosen, and what follows from the choice (consequences), including the cost and the signs that it should be revisited. Old decisions are never edited away: a new ADR replaces an old one, and the old one says so.

New terms are explained in `docs/learning/concepts.md`.

## Index

| ADR | Title | Status | Decision in one line | Accept at |
|---|---|---|---|---|
| [0001](0001-warehouse-bigquery-sandbox.md) | Warehouse | Proposed | BigQuery sandbox with no billing and a DML-free design. Plan B is the GCP Free Trial in a new project (stop on prepayment, never upgrade). Snowflake trial and Databricks Free Edition rejected (an expiring trial; an unpublished daily limit, possible deletion after 60 days without login, terms that bar publishing benchmark results without permission) | M10, step S10.2 (G0 results filled in at S1.5) |
| [0002](0002-raw-write-path-and-time-model.md) | Raw write path and time model | Proposed | One `WRITE_TRUNCATE` load job per (table, arrival day) into `table$YYYYMMDD` from one JSON schema contract, and a partition delete on empty days. Three dates; raw partitioned by arrival date; marts as of the latest loaded arrival date, stored on every row; `before_scope` for one-sided lines older than the oldest loaded day; no run-date var in full-rebuild marts | M10, step S10.2 |
| [0003](0003-reconciliation-method.md) | Reconciliation method | Proposed | Exact match on `payment_id` in settlement-currency INT64 minor units; one status per line plus flags; dated additive components; the cross-ledger identity and layer preservation as error tests; one exception row per (line, cause); an integer fee check with an inclusive per-MID tolerance | M10, step S10.2 |
| [0004](0004-fx-policy.md) | FX policy | Proposed | Frankfurter v2 with provider `nbk`, stored as published; immutable landing committed to git; first-seen value per rate date; the weekend carry-forward labelled a project convention; the NBK RSS cross-check measured, with the policy switch decided in U7 on evidence | U1 (M11), step S11.5 |
| [0005](0005-orchestration-and-run-semantics.md) | Orchestration and run semantics | Proposed | `CronDataIntervalTimetable` at 00:00 UTC, catchup off, `max_active_runs` 1, a 1-slot `dbt_serial` pool, retries by task type, exact days only through one-day backfills, history loaded newest first | U1 (M11), step S11.5 |
| [0006](0006-dbt-runtime-in-airflow.md) | dbt runtime in Airflow | Proposed | A BashOperator calling `/opt/airflow/dbt_venv/bin/dbt` (a separate venv because of pinned-dependency conflicts) with per-run target and log paths; Cosmos deferred to v1.x | U1 (M11), step S11.5 |
| [0007](0007-evaluation-and-answer-key.md) | Evaluation and answer key | Proposed | The answer key is never loaded into BigQuery and is scored by a local script; a "seeded self-test" with raw counts; benign fee noise that can cross the tolerance; a held-out world generated only after the matcher is tagged | U1 (M11), step S11.5 |
| [0008](0008-materialization-and-incremental.md) | Materialization and incremental | Proposed | Views for staging and intermediate, small full-rebuild tables for marts, no incremental model in v1.0; one `copy_partitions` snapshot model in U5, gated on probe P8, with a full-rebuild fallback | U5 (M15), step S15.3 |
| [0009](0009-window-and-expiry.md) | Window and expiry | Proposed | A 28-day world from 2026-10-04 ending yesterday (UTC), a 45-day write guard, evidence committed so the numbers survive the 60-day expiry, and a rebuild by moving the world start | U3 (M13), step S13.5 |
| [0010](0010-synthetic-world-design.md) | Synthetic world design | Proposed | A standard-library generator with pure streams per (seed, day_index, MID, purpose) that use only `random()`; emission by arrival date; fixed UTC offsets in both directions; calendar-day lags; contract terms shared through a seed and everything else hidden | U4 (M14), step S14.4 |

v1.0 ships with ADR-0001 to ADR-0003 Accepted and the others Proposed. A Proposed ADR is an honest draft, not a finished record.

## Statuses

| Status | Meaning |
|---|---|
| Proposed | A draft written before the build. It can still change. |
| Accepted | The author checked it against the code and the evidence and rewrote it in his own words. |
| Superseded by NNNN | A later ADR replaced it. The file stays, with a link to the new ADR. |

## How to accept an ADR (author only)

1. Accept it at the step named in "Accept at", not earlier.
2. Fill in every placeholder in square brackets, such as `[PASS or FAIL]` or `[T]`, from your own run and the files in `docs/evidence/`. If a value was never measured, delete the line. Never guess a value.
3. Check every statement against the code and `docs/failure_log.md`. Where the code differs, change the ADR to match the code.
4. Rewrite each part in your own words. Delete anything you cannot explain aloud.
5. Change `**Status:** Proposed` to `**Status:** Accepted` and add a line `**Accepted on:** YYYY-MM-DD`. Keep the first line of the file.
6. Change the Status column in the index above.
7. Commit the ADRs accepted in one step together, with the updated index, in that step's commit. Use the commit message the step names in `docs/build_plan.md`. The format is under its heading "Commit messages".

## Rules for AI agents

1. Never change the Status of an ADR. Only the author accepts or supersedes one.
2. Never write a measured number into an ADR. Leave the placeholder in square brackets.
3. Never rewrite the decision of an Accepted ADR. Propose a new ADR that supersedes it instead.
4. Follow the naming, honesty and writing rules in `AGENTS.md`.

## Adding a new ADR

1. Copy the template below into `docs/adr/NNNN-short-title.md`, using the next free number and lowercase words joined by hyphens.
2. Start with Status Proposed and add a row to the index.
3. If it replaces an older ADR, the author sets the older one's Status to "Superseded by NNNN".
4. If an AI assistant drafted it, start the file with the same planning-document line as the files in this folder.

Template:

```markdown
# ADR-NNNN: Title

- **Status:** Proposed
- **Date:** YYYY-MM-DD
- **Accept at:** milestone and step

## Context

What forces the decision. Every fact has a source.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|

## Decision

Numbered steps with exact names.

## Consequences

**Cost.** **Better.** **Worse.** **Revisit when.**

## Sources (checked YYYY-MM-DD)
```
