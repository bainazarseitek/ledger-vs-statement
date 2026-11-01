Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# Roadmap

What comes after v1.0, and in which order. Every step names the concept it teaches. This is a learning project, so a step earns its place by adding one idea that a reviewer can see in the code and in the evidence.

## How to read this file

1. v1.0 is the floor: the version that the README and `docs/design.md` describe.
2. Seven upgrades, U1 to U7, come next in a fixed order. Each one ends with a git tag, from `v1.1` (U1) to `v1.7` (U7).
3. After `v1.7` come three lists: v1.x (small additions in this repo, each with its own small tag), the v2 lanes (larger additions) and v3 (later ideas).
4. Hours are planned focused hours for one learner. They are estimates, not measurements. No number in this file is a result: results live only in `docs/evidence/<date>/`.
5. Nothing on this page exists as a stub in the code. An item gets code only when its step starts.
6. Step ids such as S11.1 point to `docs/build_plan.md`.

## Rules every step keeps

1. The sandbox rules hold for every step except the GCP Free Trial lane in v3:
   - no `MERGE`, `INSERT`, `UPDATE` or `DELETE`;
   - no dbt `merge` strategy, no `insert_overwrite` without `copy_partitions: true`, no `microbatch` without `copy_partitions`, no snapshots, no `time_ingestion_partitioning`, no Elementary;
   - no `insert_all`, `insert_rows_json` or other streaming, and no Cloud Storage;
   - every business date stays inside the rolling window that ends yesterday (UTC), and no run writes a date more than 45 days old;
   - no table expiration on a partitioned table.
2. Money stays in INT64 minor units. No FLOAT64 on the money path. Fees use integer arithmetic (`DIV`), with one rounding stage.
3. A new defect class gets its own random-stream purpose in the generator, so existing rows never change.
4. Any change to the generator or the loader means a full re-backfill of the window before the next proof.
5. Where logic changes, the unit test comes first and is seen red before the logic exists.
6. Every new number goes into `docs/evidence/<date>/` with the command that wrote it, and only then into the README.
7. Each step ends with a tag and a README update. An ADR named in a step becomes Accepted only after I rewrite it in my own words.
8. Payments data stays synthetic and labelled. FX data stays real and is stored as published.
9. No company names, no employer and no word from the private banned-word list, in code, data, docs or commit messages.

## Status

| Tag | Step | Planned hours | Status |
|---|---|---|---|
| `v1.0` | the floor | 16.25 (14.75 plus a 1.5-hour buffer) | planned |
| `v1.1` | U1 floor completion | 1.25 | planned |
| `v1.2` | U2 CI | 1.0 | planned |
| `v1.3` | U3 proof and ops hardening | 1.0 | planned |
| `v1.4` | U4 held-out world | 1.5 | planned |
| `v1.5` | U5 point-in-time snapshot and completeness curve | 1.0 | planned |
| `v1.6` | U6 statement batches and a late-batch incident | 1.0 | planned |
| `v1.7` | U7 cross-currency MID and tolerance sweep | 2.0 | planned |
| | Total | 25.0 | |

When a step ships, change its status to "done (YYYY-MM-DD)". If parts of the floor had to be cut, the first tag is `v0.9-call-ready` instead of `v1.0`, and the README lists what is still in progress.

## Upgrades after v1.0 (fixed order)

### U1: Floor completion (tag `v1.1`, 1.25 h)

- **What:**
  1. Unit test UT3 `ut_events_dedup_first_delivery` on `stg_psp__payment_events`: two deliveries of one event at different times, two deliveries of another event at the same `delivered_ts` (the tie is broken by `delivery_id`), and one delivery whose `_arrival_date` is after as_of. Expected: one row per event, the earlier delivery kept, `copies_received = 2`, the late delivery excluded.
  2. Unit test UT4 `ut_lines_fee_boundary_and_two_causes` on `fct_recon_lines`: a fee variance equal to the tolerance is within it and one minor unit more is flagged; one line has both an amount and a fee problem; a KZT gross of 1020 (exact fee 25.5) must give `expected_fee_minor = 26`.
  3. Both unit tests are seen red first. Record each red run in the "Planned red runs" table of `docs/failure_log.md`.
  4. Mutation 5 (half-up fee rounding changed to floor, expected to turn UT4 red), recorded in `docs/testing.md`.
  5. `scripts/eval.py` and `make eval`: the seeded self-test, writing `docs/evidence/<date>/eval.json`.
  6. ADR-0004 to ADR-0007 rewritten in my own words and Accepted.
- **Teaches:** testing the edges where logic breaks first (a dedup tie, an inclusive tolerance boundary, half-up rounding); scoring a detector against an answer key that the pipeline never reads, with raw counts of false alarms and misses instead of one flattering rate.
- **Steps:** S11.1 to S11.5.
- **Done when:** UT3 and UT4 are green after a recorded red run; mutation 5 is in `docs/testing.md`; `eval.json` holds raw counts per cause; tag `v1.1`.
- **README change:** a new section "Seeded self-test (synthetic, not accuracy)" under "Results and how they were measured", from the template below. It never goes in the first-screen results table, and it is never the headline.

How the self-test scores (from the defect catalog in `docs/specs/data_and_generator.md`):
- It looks at lines as of the marts' `as_of_date`, leaving out `before_scope` lines, and only at final lines: the statement line arrived, or as_of has reached the due date.
- For each cause (`missing_in_statement`, `missing_in_ledger`, `amount_mismatch`, `fee_mismatch`), it counts planted (what the generator intended), flagged (exception rows with that cause), right cause, false alarms and misses.
- A benign fee spike flagged as `fee_mismatch` is a false alarm. A D5 overcharge inside the tolerance is a miss. Every `date_mismatch` row is a false alarm, because none is planted.
- D1 is scored as planted extra copies against `SUM(copies_received - 1)`.
- A ledger-only line before its due date must be `in_transit`. Violations are counted.

Template for the README section. Write the sentence about why this is not accuracy in your own words.

````markdown
### Seeded self-test (synthetic, not accuracy)

Seeded self-test (synthetic, not accuracy): [TP] of [N] planted discrepancies got the right cause; [FP] false alarms and [FN] misses, by design of the fee noise. As of [A], seed [s], measured on [date] with `make eval` (`docs/evidence/[date]/eval.json`).

[WRITE: one sentence on why this is not accuracy: the same author planted the defects and wrote the matcher]

| Cause | Planted | Flagged | Right cause | False alarms | Misses |
|---|---|---|---|---|---|
| `missing_in_statement` | [N] | [N] | [N] | [N] | [N] |
| `missing_in_ledger` | [N] | [N] | [N] | [N] | [N] |
| `amount_mismatch` | [N] | [N] | [N] | [N] | [N] |
| `fee_mismatch` | [N] | [N] | [N] | [N] | [N] |
| `date_mismatch` (none planted) | 0 | [N] | 0 | [N] | 0 |

Webhook redeliveries (D1): [N] extra copies planted, [N] removed. Benign final lines: [N]. Ledger-only lines before their due date that are not `in_transit`: [N] (must be 0).
````

### U2: CI on GitHub Actions (tag `v1.2`, 1.0 h)

- **What:**
  1. `.github/workflows/ci.yml`: `uv sync --frozen`, ruff with the Airflow 3 rules AIR301 and AIR302 on `dags/`, and pytest.
  2. `tests/test_dag.py`: installs apache-airflow 3.3.2 with constraints-3.13, imports the DAGs, and asserts `CronDataIntervalTimetable`, `catchup=False`, `max_active_runs=1` and `dbt_build` in pool `dbt_serial`.
  3. `tests/test_load.py`: the partition assertion and the empty-day partition delete, with a fake BigQuery client.
  4. A truth-isolation test: the loader's table list excludes the answer key, and no dbt source points at it.
  5. `dbt parse` with dummy environment variables.
  6. A secret check: `git ls-files keys .env` prints nothing, and a grep for `private_key` finds nothing.
  7. A CI badge.
- **Teaches:** what CI can prove without a warehouse or secrets; lint rules that catch Airflow 2 idioms; a DAG import test as a contract on schedule and concurrency; keeping keys out of CI.
- **Steps:** S12.1 to S12.3.
- **Done when:** the badge is green, and a deliberately broken branch fails CI; tag `v1.2`.
- **README change:** the CI badge goes in front of the banner line.

### U3: Proof and ops hardening (tag `v1.3`, 1.0 h)

- **What:**
  1. A full-window reprocess and compare, run in the background.
  2. A negative control: reload one day with seed + 1, and the compare must report changes; reload it with the right seed, and the compare must say identical again.
  3. A cross-runtime check: `raw_dev` against `raw` for the 7 days both hold must match.
  4. A `record_run` task after `dbt_build` (trigger rule `NONE_FAILED`) that writes `runs/daily/<date>.json`.
  5. A bytes-written ledger (each load's `output_bytes` plus the size of every table each build rewrote) and a stop at 8 GiB in `check_window`.
  6. `make no-dml`: a grep of the compiled SQL and the dbt logs for `merge into`, `insert into`, `delete from` and `update ... set` must find 0 lines.
  7. ADR-0009 Accepted.
- **Teaches:** a proof counts only if it can fail (the negative control); two runtimes that should agree, checked against each other; run records as basic observability; budgeting writes against a quota that nobody can read; checking what the tools really sent to the warehouse.
- **Steps:** S13.1 to S13.5.
- **Done when:** the negative control reports changes and then identical; the cross-runtime check is identical; `make no-dml` finds 0 lines; tag `v1.3`.
- **README change:** the full-window and negative-control results go under N1, with their own evidence date.

### U4: Held-out world (tag `v1.4`, 1.5 h)

- **What:**
  1. Only after `v1.3` is tagged, so the matcher is frozen first: a held-out world with a new seed, doubled defect rates and four defects the matcher was not designed for:
     - H1 `duplicate_statement_line`: the PSP repeats a line in a later file.
     - H2 `undeclared_deduction`: net is below gross minus fee.
     - H3 `late_settlement_t3`: a line arrives later than the contract allows.
     - H4 `redelivery_payload_changed`: a redelivery carries a different amount.
  2. Datasets `raw_heldout` and `analytics_heldout`. A 14-day load and build from the host.
  3. `make eval` on the held-out world, and a README table of planted, caught and missed, with every miss explained.
  4. v1.4 fixes, each with a failing-first unit test (`settle_rank`, status `duplicate_in_statement`).
  5. ADR-0010 Accepted.
- **Predictions to check, not to assume:** H1 fails the grain test loudly, H2 fails the statement arithmetic test (`net_minor = gross_minor - fee_minor`), and H4 fails `assert_redeliveries_identical`.
- **Teaches:** out-of-sample evaluation; why a test whose author also planted the defects is circular, and how a held-out world reduces that; publishing misses instead of hiding them; fixing with failing-first tests.
- **Steps:** S14.1 to S14.4.
- **Done when:** the misses are published; tag `v1.4`.
- **README change:** the held-out table under "Results and how they were measured".

### U5: Point-in-time snapshot and completeness curve (tag `v1.5`, 1.0 h)

- **What:**
  1. Probe P8, if it was not run in G0.
  2. `fct_recon_status_daily` with `materialized='incremental'`, `incremental_strategy='insert_overwrite'`, `partition_by={'field': 'as_of_date', 'data_type': 'date', 'granularity': 'day', 'copy_partitions': true}`, `on_schema_change='fail'` and `full_refresh=false`. It reads only arrivals up to `var('run_date')`, which the DAG passes for this model only.
  3. `as_of_date` is NOT NULL, with a not_null test: a NULL partition value crashes `copy_partitions` runs (dbt-adapters issue #2086).
  4. A log check: "Copying table(s)" is in the dbt log, and there is no `merge into` or `insert into`. Reprocessing one old day changes only its own partition.
  5. ADR-0008 Accepted, or the full-rebuild fallback recorded in it.
  6. `rpt_settlement_completeness`: the share of booked amount matched by 0 to 5 days after booking, with a Mermaid xychart in the README.
- **Teaches:** a dbt incremental model without MERGE (copy jobs replace whole partitions); point-in-time state, "what did we know on day X"; why "in transit" is not "missing", shown as a curve.
- **Steps:** S15.1 to S15.4.
- **Done when:** the log check passes and a one-day reprocess changes only its partition, or the fallback is recorded; tag `v1.5`.
- **README change:** the completeness chart, and two new rows in the data model table.

### U6: Statement batches and a late-batch incident (tag `v1.6`, 1.0 h)

- **What:**
  1. `raw.statement_batches`: one row per MID per arrival date with line count, gross, fee and net, plus its schema JSON and loader.
  2. `assert_statement_foots` (error): the lines of a batch add up to the batch totals.
  3. The completeness check switches to due accounting dates per batch.
  4. D6 `late_batch` (one MID-day file arrives 3 days late), planted on its own random stream (generator 1.1.0). The affected days are reloaded in order.
  5. The business gate moves to error level: a break share above 10%, with the minimum count.
- **Teaches:** control totals and footing; integrity gates, which stop the run, against business gates, which report and stop only past a threshold; watching a planted incident turn the gate red, then green when the batch lands.
- **Steps:** S16.1 to S16.4.
- **Done when:** the gate was seen red while the batch was late and green after it landed; tag `v1.6`.
- **README change:** `assert_statement_foots` joins the tests table, and the limitation "every MID sends lines every day" goes.

### U7: Cross-currency MID and tolerance sweep (tag `v1.7`, 2.0 h)

- **What:**
  1. A third MID, `mid_kzt_usd_01`: KZT presentment, USD settlement at a PSP markup on the previous day's NBK rate.
  2. `fetch_fx` runs before `generate_day`, and the generator fails loudly if a rate is missing.
  3. An FX component per line in INT64 cents with one rounding stage. The identity is extended and must still close. Cost of processing in bps.
  4. NBK's own daily feed as a second dbt provider, with an exact weekday-agreement test.
  5. ADR-0004 updated: which provider is primary for weekends, with the measured gap as evidence.
  6. A tolerance sweep over the fee and FX bands, as a small table and a Mermaid chart.
- **Teaches:** presentment against settlement currency; FX as a reconciliation component in integer minor units; choosing a data provider with evidence; how a tolerance trades false alarms against misses.
- **Steps:** S17.1 to S17.4.
- **Done when:** the extended identity closes on every MID-day and ADR-0004 is updated; tag `v1.7`.
- **README change:** the limitations no longer exclude presentment against settlement currency for this MID; the sweep chart is added.

### Swap rule

If the next interview is a data-engineering technical round, build the Postgres `app_db` watermark extract from the v1.x list (about 1.5 to 2 hours) in place of U7. This is the only swap allowed.

## v1.x: small additions in this repo (after `v1.7`)

Each item gets its own small tag. The order is open.

| Item | What | Teaches |
|---|---|---|
| A third ledger: Postgres `app_db` | a local Postgres holds the backend's payments; they are extracted on a `received_at` watermark with a 1-hour overlap (no CDC), and the two dedup layers are counted separately | watermark extraction; overlap windows for late commits; why CDC is not needed here; three-way matching |
| More payment events | refunds settled in later batches; chargebacks as statement-only debits; double-submits with two-layer dedup (event id, then business key); test transactions; cascade retries onto a second MID, with an approval-rate mart | sign-aware fee arithmetic for negative amounts; payment lifecycles that span days; business-key dedup; defining an approval rate |
| Business-day calendars | settlement lags in business days with holidays, through a running business-day spine in SQL and Python | calendars as data; the same rule written in two languages |
| A second matching pass | leftovers matched on (`order_id`, amount, currency, plus or minus 1 day) in a separate join; every FULL OUTER JOIN keeps an equality condition | multi-pass matching that stays deterministic |
| Late-webhook grace | a `ledger_pending` status before `missing_in_ledger` | waiting rules that are fair to both ledgers |
| Source freshness | metadata-based freshness, run as its own command | freshness that measures the source, not the date of the last backfill |
| Cosmos `DbtTaskGroup` | pinned to 1.15.0, which is confirmed on Airflow 3.3; time-boxed to 45 minutes; never a 1.16 release candidate | one Airflow task per dbt model, with retries and visibility per model |
| Docs and portability | dbt docs `--static` on GitHub Pages, an exposure, `dbt_project_evaluator` 1.4.1, and a DuckDB target so reviewers can run dbt without a GCP account | discoverability; linting a dbt project; adapter portability |
| `make demo` | reset the datasets, move `RECON_WORLD_START`, and rebuild a fresh window after the 60-day expiry | rebuilding from code instead of keeping data |

## v2 lanes

Lanes B and C come from alternative designs I considered before choosing this one. Lanes A and D extend this design's own payments side. Each lane builds on the v1 ledgers instead of starting from scratch, so its numbers rest on payments that were reconciled first.

### Lane A: App-store revenue and a three-way reconciliation

- **What:** synthetic App Store Server Notifications V2 (dedup on `notificationUUID`) and Google Play RTDN messages (dedup on `messageId`) in their documented public schemas; store commission; gross to proceeds; Apple fiscal months. The backend, the PSP and the app stores become three ledgers to reconcile.
- **Teaches:** how platform notifications repeat and how to dedup them; commission and proceeds; fiscal calendars that differ from calendar months; reconciling three sources instead of two.
- **Keep in mind:** no data about any real app or company. The notifications are synthetic and labelled.

### Lane B: Ad spend and recommend-only ROAS rules

- **What:** synthetic ad-platform reports that restate recent days (the latest pull wins); the attribution window as a dbt var, with a monotonicity test; D0 ROAS computed on reconciled revenue; rules that only recommend pause, scale or notify, with a human approval step in Airflow; window sensitivity on top (how much revenue moves between channels when the window changes).
- **Teaches:** restated data and "latest pull wins"; attribution windows as configuration, not facts; monotonicity tests; ROAS on reconciled revenue instead of raw events; human-in-the-loop decisions.
- **Known pitfalls from the earlier design review:**
  - ROAS and CPA computed on synthetic spend demonstrate the mechanism. They are never findings.
  - "The mart built day by day equals a full rebuild" is true by construction when the marts are full rebuilds. The proof means something only with an incremental model.
  - Keep platform-reported and warehouse-attributed conversions in separate columns.
  - Check the human-in-the-loop operator names in the pinned providers-standard version before building.

### Lane C: Event integrity

- **What:** purchase events against PSP payments; a keyed dedup audit; a completeness gate; provisional against final counts.
- **Teaches:** event keys and dedup across days; late data; completeness gates that fail loudly; why yesterday's number is provisional.
- **Known pitfalls from the earlier design review:**
  - Each run must own exactly one arrival-day output. Rewriting the last 3 days on every run is not idempotent: rerunning an old day rolls later tables back.
  - A gate threshold must be big enough to trip on the planted outage. A lost 2-hour batch is too small for a "50% of median" daily gate.
  - Public event samples have old dates. In the sandbox, query them through views, or shift the dates inside the 60-day window.

### Lane D: Payments risk and the monthly close

- **What:** a chargeback ratio per MID with a count-based, VAMP-style definition; a planted card-testing burst; a monthly close DAG on `CronDataIntervalTimetable("0 3 1 * *", timezone="UTC")`; MRR movements on reconciled revenue; SCD2 history built from daily state partitions, with no dbt snapshots.
- **Teaches:** ratio metrics with explicit numerator and denominator dates; detecting a burst; monthly data intervals; MRR movement categories; slowly changing dimensions without MERGE.

## v3: later ideas

### GCP Free Trial lane: MERGE and dbt snapshots

- **Why:** the sandbox refuses DML, so v1 shows the DML-free way. This lane shows the MERGE way next to it, on the same data.
- **Where:** a new project linked to a Free Trial billing account. Never link the sandbox project: its datasets keep their 60-day settings.
- **Eligibility:** an account that has never paid for Google Cloud, Firebase or Google Maps Platform and has never started a Free Trial.
- **Steps:**
  1. Sign up as "Individual" with your own Visa or Mastercard. Turn any VPN off.
  2. Stop if the form asks for a prepayment or refuses the card.
  3. Create a new project and link it to the trial billing account.
  4. Create the datasets fresh.
  5. On day 1, set `maximum_bytes_billed` in the dbt profile and in every script, and a budget alert.
  6. Never click Activate or Upgrade. One click starts automatic charges.
  7. Put two dates in the calendar: day 80, export the evidence; day 90, the trial ends. Resources then stop, and they are deleted after a 30-day grace period.
- **What to build:** a `merge` incremental model with a `unique_key`, and a dbt snapshot, each next to its DML-free version (the v1.5 `copy_partitions` snapshot, and the SCD2 history from lane D). The DML-free code runs unchanged.
- **Teaches:** MERGE semantics; dbt snapshot strategies; how a MERGE that updates or deletes is billed (the bytes of both the source and the target), against free copy jobs; cost guardrails on a billed project (a budget only alerts, while `maximum_bytes_billed` makes a too-big query fail at no charge).
- **Limits:** a one-time offer that cannot be paused or extended; the live warehouse is gone after day 90; reviewers need their own billing-enabled project for these parts.
- **Also:** this is the fallback platform if the sandbox write path or the storage quota fails (ADR-0001).

### Other v3 ideas

| Idea | Teaches |
|---|---|
| Terraform for the datasets and IAM | infrastructure as code for the warehouse |
| CI against a CI dataset with Workload Identity Federation (check that it works first) | keyless authentication from CI |
| Stripe test mode with test clocks (availability from Kazakhstan unverified) | a real PSP API in test mode; simulated subscription time |
| A dbt-artifacts observability mart | run metadata as data: what ran, how long it took, what failed |
| A SELECT-only text-to-SQL assistant over the marts, with an eval set | guardrails and evaluation for generated SQL |
| A Kafka micro-batch webhook lane, only if a job I target needs it | streaming ingestion with at-least-once delivery and dedup |

## Where each v1.0 non-goal lands

| Not in v1.0 | Lands in |
|---|---|
| Refunds | v1.x, more payment events |
| Chargebacks | v1.x, more payment events; v2 lane D (chargeback ratio) |
| Statement headers (batch control totals) | U6 (`v1.6`) |
| Payouts and bank arrival | not planned yet |
| Cross-currency settlement | U7 (`v1.7`) |
| Business-day calendars and holidays | v1.x |
| Postgres `app_db` and the watermark extract | v1.x (or in place of U7, by the swap rule) |
| FileSensor | not planned yet |
| Cosmos | v1.x |
| BigQuery check operators | not planned yet |
| CI | U2 (`v1.2`) |
| Source freshness | v1.x |
| Incremental models | U5 (`v1.5`) |
| Held-out world | U4 (`v1.4`) |
| `scripts/eval.py` (the seeded self-test) | U1 (`v1.1`) |
| UT3 and UT4 | U1 (`v1.1`) |
| Bytes-written ledger | U3 (`v1.3`) |
| App-store lane | v2 lane A |
| Ad-spend lane | v2 lane B |
| Event-integrity lane | v2 lane C |
| Data Studio | not planned yet |
| dbt docs on GitHub Pages | v1.x |
| Reserves, revenue recognition over the service period | not planned yet |

## Changing this roadmap

1. Add an item only with the concept it teaches and the evidence it will produce.
2. A change of design gets an ADR before the code.
3. Keep the order of U1 to U7. The swap rule is the only exception.
4. When an item ships, update the Status table here and the roadmap section of the README in the same commit.
