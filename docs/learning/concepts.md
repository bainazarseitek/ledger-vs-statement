Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# Concepts: the learning guide for Two Ledgers

This guide explains every idea that `ledger-vs-statement` uses: BigQuery, dbt, Airflow 3, payments and reconciliation, and general data engineering. I read it while I build. AI tutor agents use it to explain and to quiz me.

Three facts frame everything below:
- Payments data is SYNTHETIC (a seeded generator). FX rates are REAL (National Bank of Kazakhstan rates via Frankfurter).
- This is a learning project, not production experience.
- Every number in this guide is a design parameter or an invented example. None is a result. Results live only in `docs/evidence/<date>/`, each with a date and a `make` target.

Contents:
1. [How to use this guide](#how-to-use-this-guide)
2. [Rules for learning with AI](#rules-for-learning-with-ai)
3. [Words I use and words I never use](#words-i-use-and-words-i-never-use)
4. [The project in one page](#the-project-in-one-page)
5. [Part 1. BigQuery](#part-1-bigquery)
6. [Part 2. dbt](#part-2-dbt)
7. [Part 3. Airflow 3](#part-3-airflow-3)
8. [Part 4. Payments and reconciliation](#part-4-payments-and-reconciliation)
9. [Part 5. Data engineering](#part-5-data-engineering)
10. [Explain checks with model answers](#explain-checks-with-model-answers)
11. [Sources](#sources)
12. [Glossary](#glossary)
13. [Learn before each milestone](#learn-before-each-milestone)

---

## How to use this guide

### For me, the learner

1. Before each milestone, open the table "Learn before each milestone" at the end of this file and read the cards it lists.
2. While I work on a step, I search this file for its step id (for example `S4.1`). Every card lists the steps where it appears.
3. Before I close a milestone, I answer its explain checks aloud, with no notes. Then I compare my answers with "Explain checks with model answers".
4. If a card disagrees with the code, the code is the truth. I fix the card in the same commit.

### For AI tutor agents

Follow these rules literally:
1. Explain with this guide's cards first. Use the exact names in backticks: tables, models, tasks, vars, files and `make` targets.
2. Do not write the logic I must write: the generator's world and defect logic, the loader and FX logic, every SQL model and test, the DAGs, the fingerprint SQL and every README sentence. When I ask for an alternative, explain it in prose or pseudocode.
3. Scaffold boilerplate only when I ask, at most 60 lines at a time: Dockerfile, compose edits, Makefile, `.gitignore`, YAML column lists, argparse and IO wrappers, `scripts/g0_probe.py`, schema JSON and CI YAML.
4. When I ask you to examine me, ask one explain-check question, wait for my answer, then compare it with the model answer and name what I missed. Never give the answer first.
5. Never invent a number. Use placeholders such as `[N]`. Never call the seeded self-test "accuracy". Never call this project "production".
6. Never suggest any of these: DML (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE TABLE`), dbt snapshots, the `merge` incremental strategy, `insert_overwrite` without `copy_partitions`, `time_ingestion_partitioning`, Elementary, `insert_all`, `insert_rows_json`, streaming, Cloud Storage, `CURRENT_DATE()` or `CURRENT_TIMESTAMP()` in a model, FLOAT64 money, `POW()`, a table expiration on a partitioned table, any date older than 45 days, or a bare `dbt` command.
7. Never write a word from the private banned-word list, which lives outside the repo. Never name an employer or a target company.
8. If a fact depends on a version (Airflow 3.3.2, dbt-core 1.12.6, dbt-bigquery 1.12.1), point to its official link under "Sources" and say that it should be checked. Do not guess.
9. No em dashes. Plain English. Short sentences.

### How each card is built

Every concept is a card with five parts:
- **What it is:** a plain explanation.
- **Analogy:** an everyday picture, only where it helps.
- **In this project:** where it appears, with step ids from `docs/build_plan.md`. M0 to M10 build the floor (v1.0, call-ready). M11 to M17 are the upgrades U1 to U7. "Not in v1.0" means an upgrade or an item in `docs/roadmap.md`.
- **Common mistakes:** what people get wrong.
- **Interview answer:** one sentence I can say.

---

## Rules for learning with AI

These come from my learning plan:
1. **Try first.** Spend 20 to 30 minutes on my own before asking.
2. **Ask "why", not "do it".** Use AI for concepts. If it writes code, ask follow-ups until I can explain every line.
3. **Debug myself first.** Read the error and the docs before pasting the error anywhere.
4. **Use AI as an examiner.** After each milestone, ask it to quiz me with the explain checks.
5. **Do a weekly no-AI rebuild.** Rebuild one component from scratch and draw the architecture from memory.
6. **Do not trust the feeling of speed.** The test is whether I can explain it in 2 minutes and rebuild it without help.
7. **AI may write boilerplate.** I own the design, the data model and every decision, and the README says so.

Project rules on top of these:
- A step marked "you write" in `docs/build_plan.md` is mine. A step marked "agent may scaffold" allows an AI draft of boilerplate. I annotate the draft, simplify it if it is longer than 60 lines, explain it back in 2 minutes, and commit it with "written with AI, reviewed" in the message.
- Plumbing blockers (Dockerfile, compose, IAM) get about 15 minutes before I ask for help.
- A real bug gets an entry in `docs/failure_log.md` when it happens, about 5 minutes each.

---

## Words I use and words I never use

| Use | Never use |
|---|---|
| learning project | production, production-grade, scalable, real-time |
| seeded self-test (synthetic) | accuracy, precision, recall or detection rate as a headline |
| settled amount differs | partial capture |
| three dates (arrival, booking, accounting), or two time axes | bitemporal (until the U5 snapshot exists) |
| reprocess: rerun finished days | reprocess and backfill as if they meant the same |
| backfill: create runs for a date range | backfill for "any rerun" |
| clear: rerun tasks of existing runs | clear for "start a new run" |
| no DML (the sandbox refuses it) | "upsert" for anything in v1.0 |
| MID (merchant account), PSP (payment service provider) | real PSP brands as if they were this project's PSP |
| "a project convention, not NBK's official rate for that day" | "official weekend rate" for a carried-forward rate |
| prices, mix and volumes are illustrative assumptions | any claim about a real company's numbers or behaviour |
| the statement layout is modelled on the public Adyen settlement-details and Stripe payout-reconciliation docs | "this is how PSP X works" |

Two checks back these words up. S0.2 sets up the private banned-word list (outside the repo) and a local `pre-push` hook that blocks a push containing any of its words. S10.1 writes the README with numbers taken only from `docs/evidence/2026-11-02/summary.json`, and S10.4 adds a manual read of the README, seeds, docs and `git log` before the repo goes public.

---

## The project in one page

**The business (synthetic).** A small web-to-app subscription company sells 1-, 4- and 12-week plans (`p1w`, `p4w`, `p12w`) through one PSP (`psp_alpha`) on two merchant accounts. `mid_usd_01` charges and settles in USD, and its acquirer closes the day at a fixed UTC-5. `mid_kzt_01` charges and settles in KZT, and its acquirer closes the day at a fixed UTC+5. The warehouse books revenue from capture webhooks by UTC date. Each MID's acquirer books the sale on its own accounting date and sends a statement file 1 or 2 days later, with gross, fee and net per line. Finance wants every MID-day where the two ledgers disagree, and why.

**The flow.**

```
SYNTHETIC: src/recon/generator.py            REAL: Frankfurter v2, providers=nbk
webhooks + per-MID statement lines           USD/KZT as published, R-6..R, fetched once
answer key (local files, never loaded)       landed file committed to git
              |                                        |
              v                                        v
landing/payment_events/...  landing/settlement_lines/...  landing/fx/provider=nbk/...
              |
Airflow 3.3.2, DAG recon_daily, CronDataIntervalTimetable("0 0 * * *", timezone="UTC")
check_window -> ensure_tables -> [generate_day, fetch_fx] -> load_raw x 3 (mapped) -> dbt_build
              |
one WRITE_TRUNCATE load job per (table, day) into table$YYYYMMDD; empty day -> partition delete
              v
BigQuery sandbox (US, no billing, no DML): raw.payment_events, raw.settlement_lines, raw.fx_rates
              |
dbt-core 1.12.6 + dbt-bigquery 1.12.1 -> dataset analytics
  staging views -> intermediate views -> fct_recon_lines (table) -> fct_recon_exceptions (view)
                                       -> fct_recon_daily (table, enforced contract)
```

**Datasets (all US):** `raw` (Airflow loads), `raw_dev` (host loads), `analytics` (dbt target `airflow`), `analytics_dev` (dbt target `dev`), `probe` (G0 probes and `smoke_bigquery`).

**What it proves:** a daily idempotent pipeline without DML; Airflow 3 interval semantics used correctly; reconciliation logic a finance reader can trust, with a cross-ledger identity that can fail; honest evidence. The README section "What this does not prove" lists the limits: no production experience, no real PSP behaviour, no detection quality on real data, no scale (about 200 payments a day by design), and no fact about any real company.

---

## Part 1. BigQuery

### Columnar storage

**What it is.** BigQuery stores each column of a table separately, not row by row. A query reads only the columns it names. Analytic queries usually need a few columns of many rows, so column storage makes them fast and cheap. Values in one column look alike, so they also compress well.

**Analogy.** A spreadsheet kept as separate stacks of cards, one stack per column. To add up the amounts, you pick up only the amount stack.

**In this project.**
- S5.2 to S5.6: models select named columns. Marts never use `SELECT *` from raw.
- S8.1: the fingerprint query uses `TO_JSON_STRING(t)`, which reads every column of every row in the window. That is on purpose: the proof must see every column. At kilobyte scale it costs nothing that matters.

**Common mistakes.**
- Believing `LIMIT 10` makes a query cheap. On a table without clustering, `LIMIT` does not reduce the bytes read.
- Running `SELECT *` "just to look". It reads every column.
- Thinking columnar storage keeps rows sorted. Sorting inside storage blocks comes from clustering.

**Interview answer.** "BigQuery is columnar, so a query pays for the columns it reads, not the rows it returns, which is why I name my columns and never rely on LIMIT to save bytes."

### Bytes processed, bytes billed and maximum_bytes_billed

**What it is.** On-demand BigQuery pricing counts bytes processed: the size of the columns a query reads after partition and cluster pruning. Billing rounds up, with a minimum of 10 MB per table referenced and 10 MB per query. The sandbox gives 1 TiB of query processing per month for free. `maximum_bytes_billed` is a safety cap: BigQuery estimates the bytes before it runs the query, and if the estimate is above the cap, the query fails without a charge.

**Analogy.** A taxi meter plus a rule agreed before the ride: "stop if the fare would pass this amount".

**In this project.**
- S1.3: `maximum_bytes_billed: 1000000000` (1 GB) in `dbt/profiles.yml`, for both targets.
- S2.3: `src/recon/bq.py` passes `QueryJobConfig(maximum_bytes_billed=1_000_000_000)` to every Python query.
- Bytes are never a README or slide number. At about 0.1 MB of raw data per day (design estimate), the 10 MB minimum hides every difference.

**Common mistakes.**
- Reporting "bytes saved" at megabyte scale.
- Confusing bytes billed (queries) with bytes stored (storage). The sandbox storage limit is a separate lifetime 10 GiB.
- Forgetting that every dbt test is a query. Under on-demand rules each one counts at least 10 MB, so 100 small test queries count as at least about 1 GB of the monthly allowance.

**Interview answer.** "Every query carries a maximum_bytes_billed cap so a mistake fails for free, and I don't present byte savings at megabyte scale because the 10 MB minimum hides any difference."

### Partitions and partition pruning

**What it is.** A partitioned table is split into segments by one column. Here the column is a DATE, so there is one partition per day. A query that filters the partition column with a constant reads only the matching partitions; this is called pruning. Each partition can also be replaced or deleted on its own, and in the sandbox each partition expires on its own clock.

**Analogy.** A filing cabinet with one drawer per day. You can empty and refill one drawer without touching the others.

**In this project.**
- S2.3: the three raw tables are created with `PARTITION BY _arrival_date`.
- S4.1: each run replaces exactly one partition per raw table (see "Partition decorators" and "Load jobs and write dispositions").
- S5.5 and S5.6: `fct_recon_lines` and `fct_recon_daily` use `partition_by` on `recon_date` (DATE).
- S8.1: the fingerprint proof compares one row per (table, partition).
- S1.4: probes P3 to P6 test partition loads, a mismatched row, a partition delete and the expiry defaults.
- Honest reason: here partitioning gives clean write semantics (replace one day) and predictable expiry. It does not give speed. Google's docs suggest clustering instead when partitions hold less than about 10 GB, and these partitions hold kilobytes.

**Common mistakes.**
- Filters that stop pruning: a subquery as the filter value, arithmetic on the partition column, or `OR` with another column.
- Expecting partitioning to make kilobyte tables faster.
- Forgetting that sandbox partitions expire 60 days after their date (see "Expiry and the rolling date window").
- Re-creating a partitioned table with a plain `CREATE OR REPLACE TABLE t AS SELECT * FROM t`. It fails unless `PARTITION BY` (and `CLUSTER BY`) are repeated.

**Interview answer.** "I partition the raw tables by arrival date so each daily run can replace exactly its own day; at this size that is about safe reruns, not performance."

### Clustering

**What it is.** Clustering sorts data inside a table, or inside each partition, by up to four columns. A query that filters on those columns can skip storage blocks. On a clustered table, BigQuery cannot give an exact cost estimate before the query runs.

**Analogy.** Inside each day's drawer, the folders are sorted by merchant account.

**In this project.**
- S2.3: `raw.payment_events` and `raw.settlement_lines` are clustered by `mid`. `raw.fx_rates` is clustered by `provider`.
- S5.5 and S5.6: both mart tables use `cluster_by` `mid`.
- At this size the gain is negligible. Clustering is here to show the habit and the access pattern: finance questions filter by MID.

**Common mistakes.**
- Expecting clustering to help tiny tables. Google's docs say unpartitioned tables larger than about 64 MB are likely to benefit, and that clustering smaller tables or partitions usually gives a negligible improvement.
- Clustering on a column that queries never filter.
- Treating the dry-run estimate for a clustered table as exact.

**Interview answer.** "I cluster by MID because finance questions filter by merchant account, and I say plainly that at kilobyte scale this shows the pattern rather than a measured speedup."

### Partition decorators

**What it is.** `table$YYYYMMDD` names one day partition of a day-partitioned table. Load jobs, copy jobs and table deletes can target it. A WRITE_TRUNCATE load into `t$20261025` replaces only that day and leaves every other day untouched. Every row must belong to that day, or BigQuery rejects the job. To read one day in SQL, this project filters the partition column instead: `WHERE _arrival_date = '2026-10-25'`.

**Analogy.** An address that points to one drawer, not to the whole cabinet.

**In this project.**
- S1.4: probe P3 loads 2 rows into `probe.raw_pay$<yesterday>`, then 1 different row into the same decorator: only the second file's row may remain, and the other day must be untouched. Probe P4 loads a row dated the day before into `$<yesterday>` and expects a refusal. Probe P5 deletes one partition.
- S2.5: `smoke_bigquery` loads 1 row into `probe.smoke$<yesterday (UTC)>`.
- S4.1: `load_partition` writes `<table>$YYYYMMDD`. On an empty day it calls `client.delete_table("<project>.<dataset>.<table>$YYYYMMDD", not_found_ok=True)`.
- Fallback if P3 fails (decided in advance): daily shard tables `raw.<table>_YYYYMMDD` loaded whole with WRITE_TRUNCATE, read through dbt sources with identifier `<table>_*` and constant `_TABLE_SUFFIX` filters. ADR-0002 records the choice.

**Common mistakes.**
- Typing a decorator in a shell without single quotes. The shell treats `$2026...` as a variable and rewrites the name. In Python strings, `$` needs nothing.
- Loading rows from another day into a decorator. BigQuery refuses it, and the loader asserts it first, so the error is clear.
- Using a decorator with WRITE_APPEND and calling the result idempotent. Only WRITE_TRUNCATE replaces.

**Interview answer.** "A WRITE_TRUNCATE load into table$YYYYMMDD replaces exactly one day and nothing else, which gives me idempotent daily loads without MERGE."

### Load jobs and write dispositions

**What it is.** A load job copies a file (CSV, NDJSON, Avro, Parquet or ORC) into a table. Loads from local files need no Cloud Storage and no billing, and batch loading is free. The write disposition decides what happens to data already there: `WRITE_TRUNCATE` replaces it, `WRITE_APPEND` adds to it, `WRITE_EMPTY` writes only into an empty target. A load job is not DML, so the sandbox allows it.

**Analogy.** Replacing a drawer's contents with a new stack of papers (truncate) versus putting the new stack on top of the old one (append).

**In this project.**
- S4.1: `load_partition` runs one job per (table, day): `NEWLINE_DELIMITED_JSON`, the explicit schema from the JSON contract, `WRITE_TRUNCATE`, `max_bad_records=0`, location US. Before the job it concatenates every landing file of that table for the day (both MID files for statements). After the job it asserts `job.output_rows == len(rows)` and returns `{table, rows, action, output_bytes, job_id}`.
- S4.3: the same `load_day(client, dataset, table, run_date, landing_dir)` runs on the host into `raw_dev`.
- S5.1: `dbt seed` is a load job too.
- Never used: `insert_all`, `insert_rows_json` (both streaming), Cloud Storage, `GCSToBigQueryOperator`.

**Common mistakes.**
- Two WRITE_TRUNCATE jobs into one partition, one per file. The second job wipes the first. Concatenate first, then run one job.
- WRITE_APPEND for daily loads. Every rerun duplicates the day.
- Schema autodetect. A type can drift between days; the explicit schema prevents it.
- `max_bad_records` above 0. Bad rows are skipped silently.

**Interview answer.** "Each run makes exactly one WRITE_TRUNCATE load job per table and day, with an explicit schema and zero bad rows allowed, so a rerun replaces the day instead of appending to it."

### Copy jobs

**What it is.** A copy job copies a table, or one partition, into another table or partition. Copying is free; only the stored copy uses storage. It is not DML. A copy into `table$YYYYMMDD` with WRITE_TRUNCATE replaces that one partition.

**Analogy.** Photocopying one drawer's papers into the matching drawer of another cabinet, after emptying that drawer.

**In this project.**
- Not in v1.0.
- S1.4: optional probe P8 checks dbt's `copy_partitions` path, which uses copy jobs.
- S15.1 to S15.3 (U5): `fct_recon_status_daily` uses `insert_overwrite` with `copy_partitions: true` (see "insert_overwrite and copy_partitions").

**Common mistakes.**
- Thinking copies are free for storage. The copied bytes are written and count toward the sandbox's lifetime storage quota.
- Forgetting dbt's temporary table. A failed dbt run on this path leaves a `__dbt_tmp` table that lives for 12 hours.

**Interview answer.** "In the sandbox, partition copy jobs are the DML-free way to replace partitions incrementally, which is exactly what dbt's copy_partitions option relies on."

### DDL and DML, and why this project has no DML

**What it is.** DDL (data definition language) creates, changes or removes objects: `CREATE TABLE`, `CREATE OR REPLACE TABLE ... AS SELECT` (CTAS), `CREATE OR REPLACE VIEW`, `ALTER`, `DROP`. DML (data manipulation language) changes rows inside a table: `INSERT`, `UPDATE`, `DELETE`, `MERGE`, and in BigQuery also `TRUNCATE TABLE`. The sandbox refuses every DML statement. Load jobs, copy jobs, table and partition deletes through the API, CTAS and views are not DML, so they all work.

**Analogy.** DDL builds or removes shelves. DML moves items on a shelf one by one. The sandbox lets me rebuild a shelf, but never lets me move single items.

**In this project.**
- S1.4: probe P1 (`CREATE OR REPLACE TABLE probe.t AS SELECT 1 AS x`, then a view on it) must succeed. Probe P2 (`INSERT INTO probe.t (x) VALUES (2)`) must be refused; I save the full error text for ADR-0001. The research for this plan expects the text to contain "DML queries are not allowed in the free tier". My probe confirms or corrects that.
- S2.3: `ensure_tables` creates tables through the API with `exists_ok=True`, an idempotent operation.
- S4.1: an empty day deletes its partition with `client.delete_table(..., not_found_ok=True)`, a table operation, not DML.
- S5.2 to S5.6: dbt views and tables compile to `create or replace view` and `create or replace table ... as (select ...)`.
- S13.5 (U3): `make no-dml` greps the compiled SQL and dbt logs for `merge into`, `insert into`, `delete from` and `update ... set`, and expects 0 matches.

**Common mistakes.**
- Assuming `TRUNCATE TABLE` is DDL. In BigQuery it is DML.
- Using a dbt feature that hides DML: the default `merge` incremental strategy, `insert_overwrite` without `copy_partitions`, `microbatch` without `copy_partitions`, `time_ingestion_partitioning`, snapshots (a `MERGE` from the second run on), or Elementary (it INSERTs).
- Believing "no DML" means "no incremental work". Replacing partitions with load jobs and copy jobs is incremental.

**Interview answer.** "The sandbox refuses all DML, so my pipeline replaces whole partitions with load jobs and rebuilds small marts with CREATE OR REPLACE, and a log check shows that no MERGE or INSERT ever ran."

### The BigQuery sandbox and its limits

**What it is.** The sandbox is a BigQuery project with no billing account. It costs $0 and needs no card. Google's sandbox page states the limits: no DML, no streaming and no Data Transfer Service (so no scheduled queries); 1 TiB of query processing per month; "a lifetime limit of 10 GiB of storage", which "is not refunded upon data deletion"; and all tables, views and partitions expire after 60 days. Cloud Storage needs billing, so there is no GCS either. Google does not document how the lifetime storage is counted, so this project assumes every byte ever written counts.

**Analogy.** A free practice room with strict house rules: furniture can be swapped but never rearranged piece by piece, nothing stays longer than 60 days, and I get one lifetime box of storage space.

**In this project.**
- S1.1: personal Gmail, "No organization", a new project with display name `ledger-vs-statement`. The console must show the SANDBOX badge and no billing account. The project id lives only in `.env` as `GCP_PROJECT`.
- S1.4 and S1.5: the G0 probes (P1 to P7, F1, optional P8) measure the limits. The results go into ADR-0001 (`docs/adr/0001-warehouse-bigquery-sandbox.md`) and the README section "Platform constraints (G0 probes)".
- Storage guards: staging and intermediate models are views, so they store nothing. Only `fct_recon_lines` and `fct_recon_daily` are tables, about 1 to 2 MB per build by design. My own cap is 1 GiB written before U3. S9.1 (`scripts/storage.py`) reads `<dataset>.__TABLES__` (and `region-us.INFORMATION_SCHEMA.TABLE_STORAGE` if probe P7 shows it is readable) and writes `docs/evidence/<date>/storage.json`. S13.4 (U3) adds a bytes-written ledger and an 8 GiB stop in `check_window`.
- Plan B, only if probe P3 and the shard fallback both fail, or the storage quota is hit: the GCP Free Trial in a new project with the same code. Stop if sign-up asks for a prepayment, and never upgrade. The steps are in `docs/specs/bigquery_sandbox_and_costs.md`.

**Common mistakes.**
- Using a university account. Managed accounts must choose an organization, and its policies can block service-account keys.
- Creating a second sandbox project to reset the quota. The Google Cloud Terms forbid creating projects to get around quotas.
- Trusting tutorials that say "10 GB per month". The sandbox page changed to a lifetime limit in September 2026.
- Assuming that deleting a dataset gives storage back. It does not.

**Interview answer.** "I built on the BigQuery sandbox for a $0, no-card project and designed around its rules: no DML, a 60-day expiry, and a lifetime storage cap that I track myself."

### Expiry and the rolling date window

**What it is.** In a sandbox dataset, each day partition expires 60 days after its partition date, counted from the partition boundary in UTC. Tables without partitions, and views, expire 60 days after they were created; `CREATE OR REPLACE` resets that clock. Writing rows dated more than 60 days back is worse than an error: the job reports success, and then the rows vanish at once. The sandbox refuses expiry settings longer than 60 days.

**Analogy.** A fridge where every item disappears 60 days after the date printed on its label, not 60 days after I bought it. An item that is already past its date disappears as I close the door.

**In this project.**
- `RECON_WORLD_START = 2026-10-04`. History is 2026-10-04 to 2026-10-31 (28 days, loaded on Sunday night). Monday's 00:00 UTC scheduled run adds 2026-11-01, so the proof window is 29 days. The 2026-10-04 partition lives until about 2026-12-03.
- S6.1: `check_window` refuses a run date older than today (UTC) minus 45 days, so nothing is written into the silent-expiry zone. It also refuses a date on or after today (UTC).
- S1.4: probe P6 reads the defaults with `get_dataset(probe)` and `get_table(probe.raw_pay)`: table and partition expiration of 60 days (5184000000 ms) on the dataset, and no table-level expiration on the partitioned table.
- dbt recreates its views and tables on every build, which resets their 60-day clocks.
- Numbers survive expiry because they are committed under `docs/evidence/`. A later rebuild means resetting the datasets and moving `RECON_WORLD_START` (`make demo`, a v1.x roadmap item). The synthetic data stays the same because the generator keys on `day_index`; only the real FX changes.

**Common mistakes.**
- Setting a table expiration on a partitioned table. A table expiration overrides the partition expiration.
- Setting dbt `hours_to_expiration` on a partitioned model, for the same reason.
- Copying old public datasets into date partitions. They vanish on write.
- Using a world longer than about 30 days. The oldest days fall off during later reruns, and the rerun proof breaks for a reason that has nothing to do with the code.

**Interview answer.** "Sandbox partitions expire 60 days after their date and old-dated writes vanish silently, so every business date stays inside a 28-day window ending yesterday, and the DAG refuses anything older than 45 days."

### Service accounts, roles and keys

**What it is.** A service account is an identity for a program, not a person. Roles grant it permissions. BigQuery Job User "provides permissions to run jobs, including queries, within the project". BigQuery Data Editor lets it create, update and delete tables and views, and read and write their data. A JSON key file works like the account's password: anyone with the file can act as the account.

**Analogy.** A staff badge for a robot. The roles decide which doors it opens. The key file is the badge itself; if it is lost, anyone can walk in.

**In this project.**
- S0.1: `.gitignore` lists `keys/` and `.env` in the first commit, before any key exists. `git check-ignore keys/sa.json .env` must print both paths.
- S1.2: service account `lvs-pipeline` with BigQuery Job User and BigQuery Data Editor at project level. The key is saved as `keys/sa.json` with `chmod 600`.
- S1.3: dbt reads it with `method: service-account` and `keyfile: "{{ env_var('DBT_KEYFILE') }}"`.
- S2.2: compose mounts `./keys:/opt/airflow/keys:ro`. The connection `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT` sets `key_path` to `/opt/airflow/keys/sa.json`. `DBT_KEYFILE` is a literal path in compose and is never in `.env`. The key is never baked into the image.
- Fallback if key creation is blocked: `brew install --cask gcloud-cli`, `gcloud auth application-default login`, dbt `method: oauth`, and the ADC file mounted read-only.
- If a key leaks: delete it in IAM at once, create a new one, and rewrite git history if it was pushed.
- S10.4: `git log --all -- keys .env` must be empty before the repo goes public.

**Common mistakes.**
- Committing the key, or copying it into the Docker image.
- Granting Owner or Editor "to make it work". Two narrow roles are enough.
- A key file that the container user cannot read. `AIRFLOW_UID` in `.env` must be my own `id -u`.

**Interview answer.** "The pipeline runs as a dedicated service account with only Job User and Data Editor, and its key sits in a gitignored folder that is mounted read-only into the containers."

### Data types for money: INT64, NUMERIC and FLOAT64

**What it is.** INT64 stores whole numbers exactly. NUMERIC stores decimals exactly (38 digits, 9 of them after the point). FLOAT64 stores binary approximations, so 0.1 + 0.2 is not exactly 0.3. Money must never touch FLOAT64. Some BigQuery operations quietly return FLOAT64: the `/` operator on two INT64 values, `POW()`, and `CEIL()` on an INT64. `DIV(INT64, INT64)` returns INT64 and truncates. `ROUND` rounds halfway cases away from zero.

**Analogy.** Counting coins one by one (INT64) versus weighing them on a kitchen scale and guessing the count (FLOAT64).

**In this project.**
- S2.3: every amount is INT64 minor units in the schema JSON: `amount_minor`, `gross_minor`, `fee_minor`, `net_minor`.
- S4.2 and S5.4: FX rates arrive as text. Python parses the body with `parse_float=str` into `rate_text`, and dbt casts with `CAST(rate_text AS NUMERIC)`.
- S5.5: fee arithmetic uses `DIV` only (see "Minor units and integer fee arithmetic").
- S5.4 and S5.6: the `to_usd` macro casts to NUMERIC before dividing and rounds once.
- S5.1: `seeds/_seeds.yml` types every INT64 and STRING seed column, so nothing is inferred as FLOAT64.

**Common mistakes.**
- `ROUND(gross * bps / 10000)`. The division makes FLOAT64 before ROUND runs.
- `CEIL(x)` for an integer ceiling. It returns FLOAT64. For a positive x, `DIV(x + 9999, 10000)` gives the ceiling of x / 10000 as INT64.
- Parsing JSON rates with Python's default float.
- Letting dbt infer seed column types.

**Interview answer.** "Money stays in INT64 minor units, rates stay exact text until they become NUMERIC, and I avoid the BigQuery operators that silently return FLOAT64."

---

## Part 2. dbt

### The dbt project and dbt_project.yml

**What it is.** A dbt project is a folder of SQL models, YAML properties, tests, seeds and macros, with `dbt_project.yml` at its root. dbt compiles Jinja-templated SQL, works out the build order from `ref()` and `source()`, and runs the SQL in the warehouse. dbt does not move data between systems. It transforms data that is already in the warehouse: the T in ELT.

**Analogy.** A recipe book whose recipes refer to each other. dbt reads the book, works out which dish needs which, and cooks them in the right order in the warehouse's kitchen.

**In this project.**
- S1.3: a minimal `dbt/dbt_project.yml`, enough for `uv run dbt debug`.
- S5.1: the full file: `name: ledger_vs_statement`, `profile: ledger_vs_statement`, `query-comment: {job-label: true}` (BigQuery jobs carry dbt labels; if BigQuery rejects a label on the first build, remove it and log it in `docs/failure_log.md`), folder materializations, and vars.
- Layers: staging (`stg_`, one model per source table), intermediate (`int_`, business logic), marts (`fct_`, what finance reads). Every model description starts with "One row per ...".
- Versions: dbt-core 1.12.6 with dbt-bigquery 1.12.1. On the host I run `uv run dbt ...` (wrapped by `make`). In the container the DAG runs `/opt/airflow/dbt_venv/bin/dbt`. Never a bare `dbt`: `~/.local/bin/dbt` is dbt v2 (2.0.9), a different engine. `make doctor` prints `which -a dbt` and fails unless `uv run dbt --version` shows Core 1.12.6 and bigquery 1.12.1.

**Common mistakes.**
- Running the wrong dbt binary.
- Hard-coding dataset or table names instead of using `ref()` and `source()`.
- Putting joins or business rules in staging. Here staging does light typing and one deliberate step, the webhook dedup in `stg_psp__payment_events`, so that each source keeps one staging model.

**Interview answer.** "dbt turns my SQL models into a dependency graph and builds them in order inside BigQuery, with the tests and documentation in the same project."

### Profiles and targets

**What it is.** `profiles.yml` tells dbt how to connect: adapter type, auth method, project, dataset, location and limits. A profile holds one or more targets (environments), and `--target` picks one. dbt finds the file through `DBT_PROFILES_DIR`.

**Analogy.** Two address cards for the same recipe book: one for my practice kitchen, one for the kitchen that serves guests.

**In this project.**
- S1.3: `dbt/profiles.yml` is committed and holds no secrets, only `env_var()` calls. Profile `ledger_vs_statement`, default target `dev`. Both targets: `type: bigquery`, `method: service-account`, `keyfile: "{{ env_var('DBT_KEYFILE') }}"`, `project: "{{ env_var('GCP_PROJECT') }}"`, `location: US`, `threads: 4`, `priority: interactive`, `job_execution_timeout_seconds: 300`, `job_retries: 1`, `maximum_bytes_billed: 1000000000`.

| Target | Builds dataset | Used by | Reads raw from |
|---|---|---|---|
| `dev` | `analytics_dev` | the host (`make dbt-build`) | `raw_dev` |
| `airflow` | `analytics` | the DAG | `raw` |

- dbt 1.12 automatically loads a `.env` file from the working directory, and shell variables win over it. That is why `DBT_KEYFILE` is never in `.env`: a manual run could pick up a wrong path.
- No custom schemas, so no `generate_schema_name` override.

**Common mistakes.**
- Putting secrets in the committed profile.
- Building development work into the proof dataset. On the host, always use target `dev`.
- Forgetting `location: US` and then seeing "not found in location" errors.

**Interview answer.** "One committed profile with two targets keeps my development builds in their own datasets, so the proof datasets only ever change through Airflow."

### Sources

**What it is.** A source declares a raw table that dbt did not build. Models read it with `{{ source('psp', 'payment_events') }}`. Sources are declared in YAML, can carry tests and descriptions, and appear in the lineage graph.

**Analogy.** The delivery note listing what arrived at the kitchen. A recipe says "use the delivered tomatoes", not "use the box on shelf 3".

**In this project.**
- S5.1: `models/staging/_sources.yml` declares source `psp` (`payment_events`, `settlement_lines`) and source `fx` (`fx_rates`), each with `database: "{{ env_var('GCP_PROJECT') }}"` and `schema: "{{ env_var('RAW_DATASET', 'raw') }}"`. The host sets `RAW_DATASET=raw_dev`. In U4, S14.1 points it at `raw_heldout`.
- No source freshness in v1.0. In a backfilled window it would only measure when I last ran the DAG. Metadata-based freshness, run as its own command, is a v1.x roadmap item.
- No source points at the answer key in `landing/_truth/`.

**Common mistakes.**
- Selecting raw tables by a hard-coded name inside a model.
- Adding a freshness check that cannot fail for a meaningful reason.

**Interview answer.** "The raw tables are dbt sources whose dataset comes from an environment variable, so the same models run on development, proof and held-out data."

### ref() and the model graph

**What it is.** `{{ ref('model_name') }}` points one model at another. dbt turns it into the right table name for the current target and uses it to build the graph of dependencies, so parents always build before their children.

**Analogy.** A recipe that says "use the sauce from recipe 12" instead of "the pot on the left".

**In this project.**
- S5.2 to S5.6: every model reads its parents with `ref()` or `source()`. For example, `fct_recon_lines` reads `int_ledger__captures`, `stg_psp__settlement_lines`, `stg_recon__as_of` and the `mids` seed.
- The cross-ledger identity compares two different paths through this graph (see "The two-calendar bridge and the identity (and why it is not a tautology)" in Part 4).

**Common mistakes.**
- Hard-coded table names. dbt cannot order the build, and lineage breaks.
- Circular references between models.

**Interview answer.** "ref() gives dbt the dependency graph, so it builds models in the right order and lets me select a model together with its parents or children."

### Materializations

**What it is.** A materialization is how dbt saves a model in the warehouse.
- `view`: stores only the SQL. Every read runs the query. Stores no data.
- `table`: `CREATE OR REPLACE TABLE ... AS SELECT` on every run, a full rebuild.
- `incremental`: builds a table once, then adds or replaces only part of it on later runs.
- `ephemeral`: not saved at all. It is inlined as a CTE into the models that use it.

**Analogy.** A view is a recipe card. A table is a cooked dish in the fridge. An incremental model is topping up the dish. An ephemeral model is a step written inside another recipe.

**In this project.**
- S5.1: `staging` and `intermediate` folders are views; `marts` are tables. S7.2: `fct_recon_exceptions` overrides to `view`.
- S5.5 and S5.6: `fct_recon_lines` and `fct_recon_daily` are tables with `partition_by` `recon_date` (DATE) and `cluster_by` `mid`.
- Views protect the lifetime 10 GiB because they store nothing, and dbt recreates them on every build, which resets their 60-day clock.
- No incremental model in v1.0 (ADR-0008). U5 adds one in S15.2.

**Common mistakes.**
- Making every model a table "for speed" and spending storage.
- Expecting a view's data to stay fixed. It is recomputed on every read.
- Hiding logic you want to test or inspect in ephemeral models; they leave nothing to query.

**Interview answer.** "Views for staging and intermediate, small full-rebuild tables for marts: at this size a full rebuild is cheap, safe and DML-free."

### Incremental models and is_incremental()

**What it is.** An incremental model processes only new or changed data after its first build. Inside the model, `{% if is_incremental() %}` adds a filter. `is_incremental()` returns true only when all three hold: the model already exists as a table, the `--full-refresh` flag is not passed, and the model is configured with `materialized='incremental'`. `{{ this }}` refers to the existing table. `--full-refresh` drops the table and rebuilds it from scratch. `on_schema_change` decides what happens when columns change: `ignore` (default), `fail`, `append_new_columns` or `sync_all_columns`. On BigQuery the strategies are `merge` (the default), `insert_overwrite` and `microbatch`.

**Analogy.** A diary where each day I write only the new page instead of copying out the whole book again.

**In this project.**
- Not in v1.0: the marts are full rebuilds, as recorded in `docs/adr/0008-materialization-and-incremental.md`.
- S15.2 (U5): `fct_recon_status_daily` with `materialized='incremental'`, `incremental_strategy='insert_overwrite'`, `partition_by={'field': 'as_of_date', 'data_type': 'date', 'granularity': 'day', 'copy_partitions': true}`, `on_schema_change='fail'`, `full_refresh=false`. It reads only arrivals up to `var('run_date')`, which the DAG passes.

**Common mistakes.**
- The common course pattern `where review_date > (select max(review_date) from {{ this }})`. It misses late rows and rows from the same day, and it cannot reprocess an arbitrary old day.
- The default `merge` strategy in the sandbox. MERGE is DML and is refused.
- Assuming an incremental table always equals a full rebuild. Prove it, or run a full refresh.

**Interview answer.** "In the sandbox the default merge strategy is DML and is refused, so v1.0 rebuilds its small marts fully, and the planned incremental model uses insert_overwrite with copy_partitions, which swaps partitions with copy jobs."

### insert_overwrite and copy_partitions

**What it is.** `insert_overwrite` replaces whole partitions instead of matching single rows. By default dbt-bigquery does it with a script that ends in a `MERGE` statement, which is DML, so the sandbox refuses it. With `partition_by: {..., copy_partitions: true}` and dynamic partitions, dbt-bigquery 1.12.1 instead builds a temporary table with CTAS, finds which partitions it holds with a plain `select distinct`, copies each one into the target with a WRITE_TRUNCATE copy job, and drops the temporary table. No MERGE and no INSERT run.

**Analogy.** Instead of editing papers inside today's drawer, I prepare a fresh drawer on the side and swap it in.

**In this project.**
- S1.4: optional probe P8 builds a 2-row model with `insert_overwrite` and `copy_partitions: true` into `probe` and runs it twice. Pass: "Copying table(s)" appears in `logs/dbt.log` (it is logged at debug level, so it is not on screen), and a case-insensitive grep for "merge into" or "insert into" finds 0 lines.
- U5: S15.1 (probe P8 if not done), S15.2 (the model), S15.3 (check the log, check that reprocessing one old day changes only its own partition, accept ADR-0008). If P8 fails, U5 builds the snapshot as a full-rebuild model and ADR-0008 says why.
- Rules: dynamic partitions only (no `partitions` list); a NOT NULL partition column with a `not_null` test, because the open dbt-adapters issue #2086 crashes this path on a NULL partition value; never `time_ingestion_partitioning`, which uses INSERT. The dbt docs' own `copy_partitions` example sets `time_ingestion_partitioning`, so do not copy that example.

**Common mistakes.**
- `insert_overwrite` without `copy_partitions` in the sandbox. That is a MERGE.
- A nullable partition column.
- Expecting the copies to be free for storage. The data is written twice: once into the temporary table, once by the copy.

**Interview answer.** "copy_partitions makes insert_overwrite DML-free by swapping partitions with copy jobs, which is the only incremental strategy that works in a sandbox."

### Data tests: generic, singular and severity

**What it is.** A dbt data test is a query that returns the bad rows. Zero rows means pass.
- **Generic tests** are reusable and attached to columns or models in YAML: `unique`, `not_null`, `accepted_values` and `relationships`, plus package tests such as `dbt_utils.unique_combination_of_columns`, `dbt_utils.expression_is_true` and `dbt_utils.accepted_range`.
- **Singular tests** are single SQL files in `tests/`, each for one specific rule.
- **Severity:** `error` (the default) fails the build; `warn` reports and continues. In `dbt build`, a failing error test makes everything downstream skip.

**Analogy.** A smoke detector: silent (zero rows) when all is well, loud when it finds a problem.

**In this project.**
- S5.2 to S5.6 and S7.2: generic tests on every key and status column, written with `data_tests:` and `arguments:` as in my dbt course project. The full list is in `docs/specs/dbt_project.md`.
- S5.6, error level: `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers`, `assert_redeliveries_identical`.
- S7.4: `assert_arrival_days_complete` (error); `warn_exception_share_7d` and `warn_fx_restated` (warn).
- S7.5: the mutation check proves which tests can go red (see "The mutation check").
- Not allowed: tautological tests, such as a uniqueness test filtered by a `ROW_NUMBER` rank, or an identity computed from its own residual.

**Common mistakes.**
- Forty tests on pass-through columns and none on the logic.
- A test that cannot fail. Prove that it can, with a mutation.
- Making a business outcome (many exceptions) an error. Exceptions are the output, not a pipeline failure.

**Interview answer.** "Error-level tests guard the integrity of the pipeline and stop the run, warn-level tests watch business signals, and a mutation check shows that each important test can actually fail."

### Unit tests

**What it is.** A dbt unit test checks a model's SQL logic on small hand-written input rows (`given`) against expected output rows (`expect`). It runs in the warehouse, but on fixtures, not on real data. Facts for dbt 1.12: the model's direct parents must already exist in the warehouse (on a fresh dataset, build them first with `--empty`); BigQuery STRUCT fixtures must list every field; `dbt build` runs a model's unit tests before building the model, and builds it only if they pass. dbt Labs recommends running unit tests only in development or CI.

**Analogy.** Checking a new calculator with 2 + 2 before trusting it with the payroll.

**In this project.**
- All unit tests live in `dbt/models/_unit_tests.yml`. Each is written first and seen failing before the logic exists, and that red run is logged in `docs/failure_log.md`. Every direct parent is mocked in `given`, seeds included.
- S5.3: UT1 `ut_captures_cutoff_both_directions` on `int_ledger__captures`.
- S5.5: UT2 `ut_lines_status_and_date_shift` on `fct_recon_lines`.
- S11.1 (U1): UT3 `ut_events_dedup_first_delivery`. S11.2 (U1): UT4 `ut_lines_fee_boundary_and_two_causes`.
- They run on the host inside `make dbt-build`, or alone with `make dbt-unit` (`dbt test --select "test_type:unit"`). Never in the DAG (`--exclude-resource-type unit_test`) and never in CI, because CI has no warehouse.

**Common mistakes.**
- Writing the unit test after the logic and never seeing it fail.
- Testing trivial SQL instead of boundaries: the cut-off second, the due-date day, the fee tolerance edge.
- Forgetting a parent in `given`, which makes the test read real data.

**Interview answer.** "Unit tests pin the rules a reviewer would probe first, the cut-off seconds and the inclusive due date, and I watched each one fail before I wrote the logic."

### Unit tests versus data tests

**What it is.** The two kinds answer different questions.

| | Unit test | Data test |
|---|---|---|
| Question | Is my SQL logic right? | Is this data right? |
| Input | hand-written fixture rows | the real loaded data |
| When it runs here | host and development only | every build, including the DAG |
| A failure means | the code is wrong | the data or the pipeline is wrong |
| Example here | UT1: a KZT capture at 19:00:00 UTC belongs to the next accounting date | unique `payment_id` on `fct_recon_lines` |

**Analogy.** A unit test checks the recipe on a test kitchen's sample ingredients. A data test tastes tonight's actual dish.

**In this project.** UT1 to UT4 are unit tests. Everything under "Data tests: generic, singular and severity" is a data test. The seeded self-test (U1) is a third kind of evidence: behaviour on planted data.

**Common mistakes.** Expecting unit tests to catch bad data, or data tests to catch a wrong rule that happens to produce clean-looking data.

**Interview answer.** "Unit tests prove the logic on fixtures I control, data tests check every real build, and I report them separately because they prove different things."

### Contracts

**What it is.** A model contract declares the exact columns and data types a model must produce. With `contract: {enforced: true}`, dbt builds the table with that column list and fails the build if the SQL returns different columns or types. Every column needs a `data_type`. On BigQuery only `not_null` constraints are enforced; `primary_key` and `foreign_key` can be defined but are not enforced, and `unique` and `check` are not supported. So uniqueness still needs a data test. Constraints apply only to `table` and `incremental` models, never to views.

**Analogy.** A delivery spec: "the box must contain exactly these items, labelled exactly so". A wrong box is refused at the door.

**In this project.**
- S7.3: `fct_recon_daily` has the only enforced contract. Every column has a `data_type`, and `not_null` constraints sit on `mid`, `currency`, `recon_date`, `as_of_date` and `unexplained_minor`. Uniqueness of (`mid`, `currency`, `recon_date`) is a `dbt_utils.unique_combination_of_columns` test.
- The raw layer has its own contract: one schema JSON per table (see "Data contracts" in Part 5).

**Common mistakes.**
- Expecting BigQuery to enforce uniqueness through a contract.
- Putting a contract on every model. Put it on the mart that people depend on.
- On an enforced incremental model, leaving `on_schema_change` unset. It must be `fail` or `append_new_columns`.

**Interview answer.** "The daily reconciliation mart has an enforced contract, so a changed column or type fails the build before anyone reads wrong numbers, and because BigQuery enforces only not_null, uniqueness stays a test."

### Seeds

**What it is.** Seeds are small CSV files in `seeds/` that `dbt seed` loads as tables. They suit small reference data that rarely changes. In dbt-bigquery 1.12.1 a seed drops its table and reloads it with a load job, so seeds work in the sandbox and get a fresh 60-day clock on every load.

**Analogy.** The laminated price list on the kitchen wall.

**In this project.**
- S5.1: `mids.csv` (contract terms per merchant account), `currencies.csv` (`USD,100` and `KZT,100`, the minor units per major unit from ISO 4217) and `reason_codes.csv` (`code`, `category`, `precedence`, `description`, `analyst_action`). Column types are set in `seeds/_seeds.yml`.
- S3.1: the generator reads the same `mids.csv`, so Python and SQL share one set of contract terms.
- What is not in seeds: noise, defect rates and PSP mistakes. They live only in `src/recon/world.toml`, which dbt never reads.

**Common mistakes.**
- Large or fast-changing data as seeds.
- Letting dbt infer column types, so a fee column becomes FLOAT64.
- Secrets or personal data in a seed. Seeds are committed.

**Interview answer.** "Seeds hold the contract terms both sides legitimately know, with explicit types, while the noise and planted defects stay hidden in the generator's config."

### Vars

**What it is.** A var is a named value that a model reads with `{{ var('name') }}`. Defaults live under `vars:` in `dbt_project.yml`, and `--vars '{"name": value}'` overrides them for one command.

**Analogy.** Oven knobs: the recipe stays the same, and the knob changes the result.

**In this project.** Declared in S5.1:

| Var | Default | Used by (step) |
|---|---|---|
| `statement_grace_days` | 1 | `int_ledger__captures.due_date` (S5.3) |
| `fx_max_carry_days` | 5 | the carry test on `int_fx__usd_rates_daily` (S5.4) |
| `exception_share_warn` | 0.02 | `warn_exception_share_7d` (S7.4) |
| `exception_min_count` | 5 | `warn_exception_share_7d` (S7.4) |
| `gate_window_days` | 7 | `warn_exception_share_7d` (S7.4) |
| `as_of_date` | not set | `stg_recon__as_of`: time travel for host development builds only ("what did we know on day X") |

- The DAG never passes `as_of_date`. Never use it with target `airflow`.
- No `run_date` var in v1.0. U5 adds `run_date` for the snapshot model only (S15.2).

**Common mistakes.**
- Feeding the run's date into full-rebuild marts as a var. Reprocessing an old day would then roll the marts back to an older state.
- Using a var that is not declared, so a typo silently falls back to a default.

**Interview answer.** "Tolerances and windows are declared vars with documented defaults, and the as-of date comes from the data rather than from a var, so reprocessing an old day can never roll the marts back."

### Jinja and macros

**What it is.** Jinja is the template language dbt renders before any SQL reaches BigQuery. `{{ ... }}` prints a value, `{% ... %}` runs logic such as `if` and `for`, and `{# ... #}` is a comment. A macro is a reusable Jinja function saved in `macros/`. `env_var('NAME')` reads an environment variable.

**Analogy.** A mail-merge letter: the placeholders are filled in before the letter is printed.

**In this project.**
- S1.3 and S5.1: `env_var()` in `profiles.yml` and `_sources.yml`.
- S5.4: the only macro, `to_usd(minor_col, minor_per_major_col, units_per_usd_col)`. It renders `ROUND(CAST(minor AS NUMERIC) / minor_per_major / units_per_usd, 2)`.
- Airflow uses Jinja too: `{{ data_interval_start | ds }}` in the `dbt_build` command (S6.1).
- Debugging: read the rendered SQL under the run's target folder, in `compiled/` and `run/`.

**Common mistakes.**
- So much Jinja that the SQL becomes unreadable. One small macro is enough here.
- Forgetting that Jinja runs at compile time on my machine or in the container, not inside BigQuery.

**Interview answer.** "dbt renders Jinja into plain SQL before running it, and I keep one small macro for the USD conversion so the rounding rule lives in exactly one place."

### Packages

**What it is.** A dbt package is another dbt project installed into mine, so I can reuse its macros and tests. `packages.yml` lists packages, `dbt deps` installs them into `dbt_packages/`, and `package-lock.yml` pins the exact versions.

**Analogy.** Borrowing a trusted cookbook's sauce recipes instead of inventing my own.

**In this project.**
- S5.1: `dbt-labs/dbt_utils` 1.4.1, for `unique_combination_of_columns`, `expression_is_true` and `accepted_range`. It is installed on the host with `uv run dbt deps` into `dbt/dbt_packages/`, which is gitignored; the container sees it through the `./dbt` mount. `package-lock.yml` is committed.
- S10.3: the clean-clone check runs `make setup`, which runs `uv run dbt deps`.
- Never: Elementary (it INSERTs), calogica dbt-expectations (no longer maintained), dbt_project_evaluator 2.x (it needs dbt v2).

**Common mistakes.**
- Installing a package that writes with INSERT into a sandbox.
- Not committing the lock file, so a clean clone gets different versions.

**Interview answer.** "I use one pinned package, dbt_utils, for standard tests, and I avoid packages that write with DML because the sandbox refuses it."

### Artifacts: manifest.json and run_results.json

**What it is.** dbt writes JSON artifacts into its target folder (`target/` by default, or `--target-path`). `manifest.json` describes the whole project (models, tests, sources and their dependencies) and is produced by commands that read the project, such as `dbt parse`. `run_results.json` records what a command ran: each node's status, timing and the adapter response (for BigQuery this includes bytes processed and job ids). `catalog.json` is produced by `dbt docs generate`. Each command overwrites the files from the previous one.

**Analogy.** The kitchen's order rail: the menu (manifest) and the receipts for tonight's orders (run results).

**In this project.**
- S6.1: `dbt_build` passes `--target-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/target` and `--log-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/logs`, so every run date keeps its own `run_results.json` and logs. `runs/` is gitignored.
- When a dbt error test fails, in any milestone from M5 on, I read that test's compiled SQL under the failing run's target folder. The failure-modes table in `docs/specs/airflow_and_docker.md` lists the recovery: fix, clear `dbt_build` only, and log it in `docs/failure_log.md`.
- S12.3 (U2): CI runs `dbt parse` with dummy environment variables. It writes `manifest.json` without connecting to BigQuery.
- S13.4 (U3): the `record_run` task writes `runs/daily/<date>.json` after `dbt_build`.

**Common mistakes.**
- Reading `run_results.json` after another command has overwritten it. Per-run target paths prevent this.
- Committing `target/` to git.

**Interview answer.** "Each Airflow run writes dbt's artifacts into a folder named by its run date, so I can audit any day's build after the fact."

### Docs

**What it is.** `dbt docs generate` builds a documentation site from the model and column descriptions plus the warehouse catalog, and `dbt docs serve` shows it locally. In dbt-core 1.12, `dbt docs generate --static` also writes a single `static_index.html` with the manifest and catalog built in, which can be hosted as a static page.

**Analogy.** The recipe book's index and family tree, generated from the recipes themselves.

**In this project.**
- S5.1 to S7.3: every model description starts with "One row per ...", so each model's grain is documented next to its code.
- Not in v1.0: generating and publishing the site (`--static` on GitHub Pages) is a v1.x item in `docs/roadmap.md`.

**Common mistakes.**
- Descriptions that repeat the column name instead of explaining its meaning.
- Publishing a generated site without reading it first. It shows relation names, including the GCP project id.

**Interview answer.** "Every model documents its grain in its description, and dbt can turn those descriptions and the lineage graph into a browsable site."

### Selectors

**What it is.** Node selection chooses which resources a dbt command runs. `--select` (or `-s`) and `--exclude` take model names and methods such as `tag:`, `path:` and `test_type:`. Graph operators extend a selection: `+model` adds its ancestors, `model+` adds its descendants. YAML selectors in `selectors.yml` give a selection a name, used with `--selector`. `--exclude-resource-type` skips a whole resource type.

**Analogy.** Choosing which dishes to cook tonight: "this dish and everything it needs".

**In this project.**
- No YAML selectors in v1.0. Commands use explicit flags.
- S6.1: the DAG runs `dbt build --exclude-resource-type unit_test`.
- S5.3 and S5.5: `make dbt-unit` runs `dbt test --select "test_type:unit"`.
- While developing: `uv run dbt build --target dev -s +fct_recon_lines` builds one model together with its parents.

**Common mistakes.**
- Forgetting the `+` and testing a model against stale parents.
- Not quoting a selection that contains special characters in zsh.

**Interview answer.** "Selectors let me build one model with its parents while I develop, and the DAG excludes unit tests by resource type so scheduled runs only build and test real data."

### dbt build

**What it is.** `dbt build` runs seeds, models, snapshots and tests in graph order in one command. For each model, its unit tests run first, then the model is built, then its data tests run. If an error-level test fails, every resource downstream of it is skipped and the command fails. `--empty` builds schema-only versions, with refs and sources limited to zero rows; this is how a fresh dataset gets the parents that unit tests need.

**Analogy.** Cooking each dish, tasting it straight away, and not starting any dish that depends on one that failed the tasting.

**In this project.**
- S5.2 to S5.6: `make dbt-build` on the host, target `dev`, unit tests included.
- S6.1: the `dbt_build` BashOperator (pool `dbt_serial`, `append_env=True`, retries 0) runs exactly:

```
cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt build --target airflow --exclude-resource-type unit_test --target-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/target --log-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/logs
```

- S7.6: `airflow tasks clear recon_daily -s 2026-11-01 -e 2026-11-01 -t dbt_build -y` rebuilds the latest marts with the final dbt code.

**Common mistakes.**
- Running `dbt run` and then `dbt test` separately in a normal build. Everything is built, including what depends on bad data, before any test runs. (The mutation check does this on purpose: see "The mutation check".)
- Thinking a failed data test rolls the model back. The model whose data test failed is already rebuilt; only its downstream resources are skipped. The failed Airflow run is the alarm. A failed unit test is different: its model is not built at all, and the old table stays.
- Retrying a failed build automatically. A failed test is deterministic and fails again. BigQuery transients are retried inside dbt by `job_retries: 1`.

**Interview answer.** "dbt build tests each model right after building it, skips everything downstream of a failure and fails the Airflow run, so a broken day is visible at once."

---

## Part 3. Airflow 3

### DAG

**What it is.** A DAG (directed acyclic graph) is a workflow: a set of tasks and the order they run in, with no loops. In Airflow it is a Python file in `dags/`. The DAG also carries its run rules: schedule, start date, catchup and how many runs may be active. In Airflow 3, DAG authoring imports come from `airflow.sdk`.

**Analogy.** A recipe's steps with arrows between them: chop before frying, never fry before chopping.

**In this project.**
- S2.4: `dags/smoke_bigquery.py`, manual only (`schedule=None`). It creates `probe.smoke (d DATE NOT NULL, x INT64) PARTITION BY d` if missing, loads 1 row into `probe.smoke$<yesterday (UTC)>` with WRITE_TRUNCATE through the hook, then runs `/opt/airflow/dbt_venv/bin/dbt debug --target airflow`. It never touches `raw` and creates no scheduled runs.
- S6.1: `dags/recon_daily.py` with `schedule=CronDataIntervalTimetable("0 0 * * *", timezone="UTC")`, `start_date=pendulum.datetime(2026, 10, 1, tz="UTC")` (on or before `RECON_WORLD_START`), `catchup=False`, `max_active_runs=1`, `tags=["portfolio", "reconciliation"]` and `doc_md` set to the module docstring.
- Imports: `from airflow.sdk import dag, task, chain, get_current_context, CronDataIntervalTimetable`, `from airflow.sdk.exceptions import AirflowFailException`, `from airflow.providers.standard.operators.bash import BashOperator`.
- Heavy imports (google-cloud-bigquery, the `recon` package) sit inside task functions, because the dag-processor parses the file again and again.

**Common mistakes.**
- Doing work at the top level of the DAG file, such as API calls or heavy imports. It runs on every parse.
- Copying Airflow 2 idioms: `schedule_interval`, `execution_date`, `airflow.decorators` or SLAs. In U2 (S12.1), ruff's rules AIR301 and AIR302 (Airflow 3 removals and moves) run on `dags/` in CI to catch them.

**Interview answer.** "recon_daily is a small DAG with an explicit data-interval timetable, and the file only defines tasks; all heavy work happens inside them."

### Task and operator

**What it is.** A task is one unit of work in a DAG. An operator is a template for a kind of task: `BashOperator` runs a shell command, `PythonOperator` runs a function. The TaskFlow API turns a plain Python function into a task with `@task`. A task instance is one task inside one DAG run, with a state such as queued, running, success, failed or skipped.

**Analogy.** Operators are job descriptions. Tasks are the jobs on today's rota.

**In this project.** S6.1 defines six tasks:

| Task | Type | Does |
|---|---|---|
| `check_window` | `@task` | checks the interval and the date window; returns R |
| `ensure_tables` | `@task` | creates the raw tables from the schema JSON if missing |
| `generate_day` | `@task` | writes the day's synthetic landing files |
| `fetch_fx` | `@task` | lands the NBK rates for R-6..R once |
| `load_raw` | `@task`, mapped over 3 tables | one load job per table, or a partition delete |
| `dbt_build` | `BashOperator` | runs `dbt build` from the dbt venv |

- Dependencies: `chain(rd, ensure_tables(), [generate_day(rd), fetch_fx(rd)], load_raw.partial(run_date=rd).expand(table=TABLES), dbt_build)`, where `rd = check_window()`.
- `BashOperator` facts for providers-standard 1.19.0: `append_env=False` is the default, and passing `env=` without `append_env=True` drops PATH and HOME; a command string ending in `.sh` or `.bash` is treated as a template file, so the dbt command stays inline; exit code 99 means "skip" by default.

**Common mistakes.**
- One giant task for everything. A failure then reruns everything, and the logs are hard to read.
- `env=` without `append_env=True`.

**Interview answer.** "Each task does one thing that can be safely rerun on its own, and dbt runs through a single BashOperator that calls the dbt venv by its full path."

### Scheduler, dag-processor, API server, triggerer and executor

**What it is.** Airflow 3 has separate components:
- The **dag-processor** parses DAG files and stores them, serialized, in the metadata database.
- The **scheduler** creates DAG runs from timetables and backfills, and sends ready tasks to the executor.
- The **executor** is a setting of the scheduler, not a separate service. It decides where tasks run. With LocalExecutor, the scheduler starts task processes on its own machine: here, inside the scheduler container.
- The **API server** serves the UI, the REST API and the Execution API that task processes talk to. Task code never reaches the metadata database directly.
- The **triggerer** runs deferred tasks. This project has none.
- The **metadata database** (Postgres) stores DAG runs, task states, pools and XComs.

**Analogy.** A restaurant: the dag-processor reads the menu, the scheduler calls out orders, the executor decides which cook makes each dish, and the API server is the front desk.

**In this project.**
- S2.2: compose is copied from my Airflow course file (LocalExecutor, postgres:18, FAB auth, `LOAD_EXAMPLES: 'false'`, `DAGS_ARE_PAUSED_AT_CREATION: 'true'`). `build: .` is uncommented, so the scheduler, where tasks run, uses the custom image `ledger-vs-statement-airflow:3.3.2`. The environment variables go into `x-airflow-common`, so the scheduler, dag-processor and triggerer all see them. The API server port is `"127.0.0.1:8083:8080"`. Port 8083 on my Mac goes to port 8080 in the container. `127.0.0.1` keeps it on localhost only, because the login is the well-known airflow / airflow.
- S2.5: `make up`. The UI is at http://localhost:8083 (airflow / airflow).

**Common mistakes.**
- Installing packages only where the UI runs. With LocalExecutor the scheduler runs the tasks.
- Giving Docker Desktop too little memory. Give it at least 6 GB (the compose warns below 4 GB) and keep at least 10 GB of disk free.
- Leaving the course stack running. Stop it with `docker compose down` in the course folder before `make up`.

**Interview answer.** "With LocalExecutor the tasks run inside the scheduler container, so that container must use my custom image with the dbt venv."

### DAG run

**What it is.** A DAG run is one execution of a DAG. It has a run id, a logical date (or none), a data interval, a run type (scheduled, manual, backfill or asset-triggered) and a state.

**Analogy.** One evening's service of the same menu.

**In this project.**
- S6.2: unpausing `recon_daily` creates the scheduled run for the latest complete day (2026-10-31 on the build weekend).
- S6.3: a backfill creates runs for 2026-10-04 to 2026-10-30, newest first.
- S8.2: `--reprocess-behavior completed` reruns days that already have finished runs.
- `max_active_runs=1` allows one scheduled run at a time. Backfills have their own `--max-active-runs`, which the `make` targets set to 1.

**Common mistakes.**
- Reading a run's date as the time it executed. It names the data the run covers (see "Logical date").

**Interview answer.** "Each DAG run owns exactly one UTC arrival day, so a run is identified by the data it covers, not by when it happened to execute."

### Logical date

**What it is.** In Airflow 3 the logical date names a run. With CronDataIntervalTimetable it equals the start of the data interval. With CronTriggerTimetable it is the trigger time. Runs created by an Asset event, or through the REST API without a logical date, have `logical_date = None`; in such a run, reading `ds`, `logical_date` or `data_interval_start` from the context raises `KeyError`. The old `execution_date` no longer exists.

**Analogy.** A newspaper's date names the day it reports on, not the hour the press ran.

**In this project.**
- S6.1: `check_window` reads the interval from `get_current_context()`. If there is none (a `KeyError`), it raises `AirflowFailException("No data interval: create exact days with a one-day backfill")`.
- Templates: only `{{ data_interval_start | ds }}` in the BashOperator. Python tasks receive R from `check_window`. Never `{{ ds }}` for manual runs, and never `datetime.now()` for business dates.
- S7.6 and the runbook: `airflow tasks clear recon_daily -s D -e D` selects runs by logical date.

How a run gets its interval in Airflow 3.3.2, in short:
- The rule: an exact day D runs only through a one-day backfill (`airflow backfill create` with `--from-date D --to-date D`), with `--dry-run` first. A scheduled run, or unpausing with catchup off, processes the latest complete day.
- The traps: `airflow dags trigger recon_daily -l L` processes yesterday relative to now, not L. `airflow dags test recon_daily D` processes D-1. A run without a logical date has no interval, and `check_window` fails it.

The full table, with every way to create a run and the interval each one gets, is "Manual-run semantics" in `docs/specs/airflow_and_docker.md`. This card keeps only the summary above, so the two cannot drift apart.

**Common mistakes.**
- Assuming `{{ ds }}` means "yesterday". Under a trigger timetable it is the trigger date.
- Triggering from the CLI with `-l D` and expecting day D to be processed.

**Interview answer.** "My runs use the data interval, never the wall clock: logical date D means the arrivals of UTC day D, and exact days are only created through one-day backfills."

### Data interval

**What it is.** The data interval is the time window a run is responsible for: `[data_interval_start, data_interval_end)`, with the start included and the end excluded. Under `CronDataIntervalTimetable("0 0 * * *", timezone="UTC")`, the run for day D covers [D 00:00, D+1 00:00) UTC and starts just after D+1 00:00 UTC, once the day is complete.

**Analogy.** A shop prints yesterday's till report after closing, not during the day.

**In this project.**
- Worked example: the run for R = 2026-10-20 covers [2026-10-20 00:00, 2026-10-21 00:00) UTC. It starts just after 2026-10-21 00:00 UTC, which is 05:00 in Astana.
- S6.1: `check_window` asserts that end minus start is exactly 1 day and that start is 00:00 UTC, then returns R as `YYYY-MM-DD` and logs `run_date=...`.
- Run R ingests everything that arrived during UTC day R: webhook deliveries with `DATE(delivered_ts) = R`, statement lines whose arrival date is R, and the FX fetch made for R (rates for R-6..R).
- S6.2: I read the `run_date` log line to confirm which day ran.

**Common mistakes.**
- Treating the end as included, which double-counts midnight.
- Expecting the run for day D to start during day D. It starts after D ends.

**Interview answer.** "Each run processes the half-open UTC day from start to end and begins only after that day is complete, so it never reads a partial day."

### Timetables: CronTriggerTimetable vs CronDataIntervalTimetable

**What it is.** A timetable decides when runs happen and which interval each one covers.

| | CronTriggerTimetable | CronDataIntervalTimetable |
|---|---|---|
| Data interval | none: start equals end (the trigger time) | the period between two cron points |
| Logical date | the trigger time | the interval start |
| A run starts | at each cron time | at the end of its interval |
| How you get it in Airflow 3 | any cron string, including `"@daily"` | only by passing it explicitly |

Airflow 3 changed the default: `create_cron_data_intervals` is False (it was True in Airflow 2), so a cron string becomes a CronTriggerTimetable.

**Analogy.** An alarm clock (trigger) versus a signed timesheet for each finished shift (data interval).

**In this project.**
- S6.1: `schedule=CronDataIntervalTimetable("0 0 * * *", timezone="UTC")`, imported from `airflow.sdk`. `"@daily"` is never used.
- S2.4: `smoke_bigquery` has `schedule=None`.
- S12.2 (U2): `tests/test_dag.py` asserts the timetable class.
- Roadmap (v2): a monthly close DAG on `CronDataIntervalTimetable("0 3 1 * *", timezone="UTC")`.

**Common mistakes.**
- Following an Airflow 2 tutorial, writing `schedule="@daily"`, and then filtering SQL on an empty interval.
- Mixing time zones. The timetable is UTC; Astana is UTC+5.

**Interview answer.** "In Airflow 3 a cron string gives a trigger timetable with an empty interval, so I chose CronDataIntervalTimetable explicitly to give every run one complete UTC day."

### Catchup

**What it is.** With `catchup=True`, an unpaused DAG creates a run for every missed interval since `start_date`. With `catchup=False`, the Airflow 3 default, it creates only the latest one. History is then loaded on purpose with a backfill.

**Analogy.** Back from holiday: with catchup you read every missed newspaper; without it you read only today's.

**In this project.**
- S6.1: `catchup=False`.
- S6.2: unpausing runs only the latest complete interval.
- S6.3: history comes from a backfill with `--max-active-runs 1`.

**Common mistakes.**
- `catchup=True` with an old start date, which releases dozens of runs at once.

**Interview answer.** "Catchup is off, so unpausing runs only the latest day, and history is loaded deliberately with a controlled backfill."

### Backfill, reprocess and clear (the three verbs)

**What it is.**
- **Backfill:** create DAG runs for a past date range. In Airflow 3 the scheduler runs backfills. One is created with `airflow backfill create --dag-id ... --from-date ... --to-date ...` (inclusive dates, only intervals that have ended) or from the UI.
- **Reprocess:** rerun days that already have finished runs. This is a backfill with `--reprocess-behavior completed`. The default `none` skips days that already have runs, and `failed` reruns only failed ones.
- **Clear:** reset task instances of existing runs, so the scheduler runs them again inside the same run, with the same interval.

**Analogy.** Backfill: printing back issues that were never printed. Reprocess: reprinting issues that were already printed. Clear: redoing one page of one issue.

**In this project.**
- S6.3: load history with `make backfill-dry FROM=2026-10-04 TO=2026-10-30` and then `make backfill FROM=2026-10-04 TO=2026-10-30`, which run `airflow backfill create --dag-id recon_daily --from-date 2026-10-04 --to-date 2026-10-30 --run-backwards --max-active-runs 1` (with `--dry-run` for the first one) inside the scheduler container. Before it: tag `g1-freeze`, run `caffeinate -is` in another terminal, keep the Mac on power with the lid open. If one run's wall time times 27 runs is more than about 4 hours, start from 2026-10-18 instead.
- S7.1: the next morning, check the overnight backfill: every run green and the counts plausible (`airflow dags list-runs recon_daily --state failed` should list nothing).
- S8.2: `make reprocess FROM=2026-10-26 TO=2026-11-01` (`--reprocess-behavior completed --max-active-runs 1`), then `make clear-day DAY=2026-10-14`.
- S7.6: `airflow tasks clear recon_daily -s 2026-11-01 -e 2026-11-01 -t dbt_build -y`.
- Airflow 3.3.2 rules: backfills run only on unpaused DAGs, and the compose pauses new DAGs; one backfill may run per DAG at a time; the 3.3.2 CLI has only `backfill create`, so a running backfill is cancelled from the UI backfill banner (or `PUT /api/v2/backfills/{id}/cancel`); `--run-backwards` does not work with `depends_on_past`.
- Why newest first: once the scheduled latest run exists, loading the oldest day first leaves a gap between it and the latest day, and `assert_arrival_days_complete` correctly fails. Newest first, each run sees a contiguous history from its own date to the latest loaded day.
- With the mounted `dags/` folder there is no DAG bundle versioning, so clears and backfills always run the latest code. That is why the generator and loader are frozen at G1 and dbt is frozen after S7.6.

**Common mistakes.**
- Calling every rerun a "backfill". Use the three verbs precisely.
- Creating a backfill on a paused DAG: runs are queued and nothing executes.
- Pausing the DAG during a backfill or during the proof.
- Changing code in the middle of a backfill, which mixes code versions inside one window.

**Interview answer.** "I backfill to create history, reprocess to rerun finished days and clear to rerun tasks inside existing runs, and I check a dry run before any backfill."

### Retries

**What it is.** `retries` is how many times Airflow reruns a failed task before marking it failed, and `retry_delay` is the wait between tries. In the Task SDK shipped with Airflow 3.3.2 (1.3.2), `retry_exponential_backoff` is a float multiplier (default 0, which means off), and `max_retry_delay` caps the wait. `on_failure_callback` runs a function when a task fails for the last time.

**Analogy.** Calling a busy phone line back a few times, waiting longer each time, but not forever.

**In this project.** S6.1:

| Task | Retries | Why |
|---|---|---|
| `check_window` | 0 | a pure check; a retry would give the same answer |
| `ensure_tables` | 2 | idempotent DDL through the API; transient errors are possible |
| `generate_day` | 0 | a pure function |
| `fetch_fx` | 3, delay 30 s, `retry_exponential_backoff=2.0`, `max_retry_delay=timedelta(minutes=10)` | the external API can be slow or down; the request has a 10 s timeout |
| `load_raw` | 2, delay 30 s | one WRITE_TRUNCATE job, safe to repeat |
| `dbt_build` | 0 | a failed test fails again; BigQuery transients are retried by dbt's `job_retries: 1` |

- `default_args = {"retries": 0, "retry_delay": timedelta(seconds=30), "on_failure_callback": log_failure}`. `log_failure` logs one line: dag_id, run_id, task_id, try_number and run date.

**Common mistakes.**
- `retry_exponential_backoff=True`, copied from older code. In this SDK it is a float multiplier.
- Retrying deterministic failures. It wastes time and hides the real problem.
- Retrying a task that is not idempotent, which can duplicate data on each try.

**Interview answer.** "Only tasks that can fail for transient reasons retry, with exponential backoff, while deterministic failures such as dbt tests fail fast."

### Idempotency

**What it is.** An operation is idempotent if running it once or many times gives the same result. For a pipeline: rerunning a day replaces that day's output with exactly the same rows. It never adds a second copy and never changes other days.

**Analogy.** Pressing the lift button five times still brings one lift.

**In this project.**
- Generator (S3.2 to S3.5): a pure function of its inputs. `make day DATE=2026-10-30` run twice must give the same sha256.
- FX (S4.2): fetched once. If `landing/fx/provider=nbk/arrival_date=R.json` exists, it is never fetched again.
- Loader (S4.1, S4.3): one WRITE_TRUNCATE job per partition, or a partition delete on an empty day.
- dbt (S5.2 to S5.6): a full rebuild from raw, with `as_of_date` taken from the data.
- Proof (S8.1, S8.2): fingerprints before and after reprocessing 7 days and clearing 1 older day out of order (see "The fingerprint proof" in Part 5).
- Each task's "safe to rerun because" reason is listed in `docs/specs/airflow_and_docker.md`.

**Common mistakes.**
- WRITE_APPEND, INSERT, or `datetime.now()` inside task outputs.
- A `_loaded_at` column: every reload produces different rows.
- Calling an external API again during a backfill. The provider may have restated its values.

**Interview answer.** "Every task is safe to rerun: the generator is pure, FX is landed once, each load replaces exactly one partition, and partition fingerprints before and after a reprocess prove it."

### Clear and rerun

**What it is.** Clearing a task instance resets its state, so the scheduler runs it again inside the same DAG run. With `-d`, its downstream tasks are cleared too. The run keeps its logical date and data interval. In `airflow tasks clear`, `-t` is a regular expression on task ids.

**Analogy.** Asking the cook to redo one dish of the same order, not opening a new order.

**In this project.** All commands run inside the scheduler container (`docker compose exec airflow-scheduler airflow ...`); `make` targets wrap them.
- Whole day: `airflow tasks clear recon_daily -s D -e D -y`.
- Only dbt: `airflow tasks clear recon_daily -s D -e D -t dbt_build -y` (S7.6).
- A failed task and its downstream: `airflow tasks clear recon_daily -s D -e D -t <task> -d -y`.
- S8.2: `make clear-day DAY=2026-10-14` reruns one older day out of order during the proof.

**Common mistakes.**
- A `-t` pattern that matches more tasks than intended.
- Clearing only a downstream task when the upstream output it needs has changed.

**Interview answer.** "Clearing reruns tasks inside the existing run, with the same interval, which is how I fix one failed step without touching any other day."

### Pause and unpause

**What it is.** A paused DAG gets no new scheduled runs, and its backfill tasks are not queued. Tasks that are already running finish. This compose sets `DAGS_ARE_PAUSED_AT_CREATION: 'true'`, so new DAGs start paused.

**Analogy.** A "closed" sign on the shop door: customers inside finish shopping; nobody new comes in.

**In this project.**
- S2.5: unpause and trigger `smoke_bigquery`.
- S6.2: `airflow dags unpause recon_daily` starts the latest run.
- S8.2: the DAG stays unpaused during the proof.

**Common mistakes.**
- Creating a backfill on a paused DAG and waiting for runs that never start.
- Pausing during a backfill or the proof.

**Interview answer.** "A paused DAG queues nothing, backfills included, so I unpause before any backfill and never pause during one."

### Connections

**What it is.** A connection stores how to reach an external system: type, credentials and extras. Tasks and hooks refer to it by its id. A connection can be defined as an environment variable named `AIRFLOW_CONN_<CONN_ID>` (all uppercase), holding JSON or a URI. Such connections are not stored in the metadata database and are not shown in the UI or by `airflow connections list`. Airflow 3 does not create default connections during `db migrate`.

**Analogy.** A contact card with the phone number and the door code, which tasks look up by name.

**In this project.**
- S2.2: `google_cloud_default` is defined only by `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT`, set to `'{"conn_type": "google_cloud_platform", "extra": {"key_path": "/opt/airflow/keys/sa.json", "project": "${GCP_PROJECT}", "location": "US", "use_legacy_sql": false}}'`.
- S2.4 and S4.1: tasks build the client with `BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")` and `hook.get_client(project_id=hook.project_id, location="US")`. The client's project is not filled from the connection otherwise.
- The Google provider's BigQuery operators and hook still default to legacy SQL, with a warning, unless told otherwise. That is why `use_legacy_sql` is false both in the extras and in the hook call.

**Common mistakes.**
- Typing credentials into the UI. Nobody can review or reproduce them.
- Expecting an environment-variable connection to appear in the UI.
- Forgetting `project_id` when asking the hook for a client.

**Interview answer.** "The BigQuery connection is an environment variable that points at a read-only mounted key, so the setup is reproducible and no secret appears in DAG code."

### Variables

**What it is.** Airflow Variables are key-value settings kept in the metadata database and read with `Variable.get("name")` (`from airflow.sdk import Variable`). They can also come from environment variables named `AIRFLOW_VAR_<NAME>`; those are not shown in the UI or by `airflow variables list`, and they take precedence over UI values. The Airflow docs say Variables are really only for values that are truly runtime-dependent.

**Analogy.** Sticky notes on the kitchen wall that cooks read during service.

**In this project.**
- Not used. Configuration comes from plain environment variables set in compose (`GCP_PROJECT`, `RAW_DATASET`, `RECON_SEED`, `RECON_WORLD_START`, `RECON_LANDING_DIR`, `DBT_PROFILES_DIR`, `DBT_KEYFILE`, `PYTHONPATH`) and read by `src/recon/config.py`.
- Why: the same code runs outside Airflow too (the host CLI and pytest), and plain environment variables need no metadata database.

**Common mistakes.**
- Calling `Variable.get` at the top level of a DAG file, so it runs on every parse.
- Storing secrets in Variables.

**Interview answer.** "Configuration lives in environment variables shared by the host CLI and the DAG, so the pipeline logic does not depend on Airflow's database."

### XCom

**What it is.** XCom ("cross-communication") passes small values between tasks. A `@task` function's return value is stored as an XCom under the key `return_value`, and passing it into another task also creates the dependency. The default backend stores XComs in the metadata database. The Airflow docs say XComs are only for small amounts of data, never for large values such as dataframes. In Airflow 3, `xcom_pull()` without `task_ids` reads only the current task.

**Analogy.** A sticky note passed between cooks, not the pot of soup.

**In this project.** S6.1:
- `check_window` returns R as a `YYYY-MM-DD` string. `generate_day`, `fetch_fx` and `load_raw` receive it.
- `generate_day` returns a dict of counts. `load_raw` returns `{table, rows, action, output_bytes, job_id}`.
- The data itself moves through files in `landing/` and through BigQuery, never through XCom.

**Common mistakes.**
- Returning a dataframe or a list of rows from a task.

**Interview answer.** "XCom carries only the run date and small summaries, while the data moves through landing files and BigQuery."

### Dynamic task mapping

**What it is.** Mapping creates one task instance per item of a list, at run time. `.expand()` takes the mapped arguments and `.partial()` takes the arguments shared by every copy. Each copy gets a `map_index` and its own state, log and retries. `[core] max_map_length` caps the number of copies (default 1024).

**Analogy.** A photocopier that makes one worksheet per pupil from a single master.

**In this project.**
- S6.1: `load_raw.partial(run_date=R).expand(table=["payment_events", "settlement_lines", "fx_rates"])`, three mapped loads, one per raw table.
- Cut-order item 3 in `docs/build_plan.md`: if time runs short, the mapped load becomes a loop inside one task.

**Common mistakes.**
- Mapping over a value that is not a list. It fails at run time.
- Putting a shared argument into `.expand()` instead of `.partial()`.

**Interview answer.** "The three raw loads are one mapped task, so each table gets its own retries and log while the code stays a single function."

### Pools

**What it is.** A pool limits how many tasks can run at the same time across all DAG runs. Each task takes `pool_slots` slots (default 1). When a pool is full, runnable tasks wait in the queued state until a slot frees. Tasks without a pool use `default_pool`, which starts with 128 slots.

**Analogy.** One key to the only oven: whoever holds it bakes, and everyone else waits.

**In this project.**
- S2.2: `airflow-init` runs `/entrypoint airflow pools set dbt_serial 1 "one dbt build at a time"` right after `/entrypoint airflow config list >/dev/null`.
- S2.5 and `make doctor`: `airflow pools get dbt_serial`.
- S6.1: `dbt_build` runs with `pool="dbt_serial"`. This is needed because in Airflow 3.3.2 backfill runs are limited only by the backfill's own `--max-active-runs`, separately from the DAG's `max_active_runs`. Without the pool, a scheduled run and a backfill run could build dbt at the same time.

**Common mistakes.**
- Naming a pool that does not exist. Such a task is never scheduled, so the pool must exist before the first run.
- Assuming `max_active_runs=1` also limits backfill runs.

**Interview answer.** "A one-slot pool keeps dbt builds strictly serial, even when a scheduled run and a backfill overlap."

### Assets, and why recon_daily does not use them

**What it is.** An Asset (called a Dataset in Airflow 2) is a named piece of data. A task can list assets as `outlets`, and a DAG with `schedule=[Asset("name")]` runs when those assets are updated. This is data-aware scheduling.

**Analogy.** A doorbell: when the delivery arrives, the next team starts work.

**In this project.**
- Not used. Asset-triggered runs in Airflow 3 have `logical_date = None` and no data interval, while every `recon_daily` run must own exactly one UTC arrival day. `check_window` fails such a run on purpose and asks for a one-day backfill.
- Assets fit event-driven follow-up DAGs that do not need a day. This project has none.

**Common mistakes.**
- Using assets for a pipeline that must process exact time windows, then reading `data_interval_start` and getting a `KeyError`.

**Interview answer.** "Assets suit event-driven DAGs, but my daily pipeline needs an exact data interval, and asset-triggered runs in Airflow 3 have none, so it runs on a time-based timetable."

### The guard task check_window

**What it is.** A guard task is a first task that checks preconditions and fails fast, before any data is written. It turns silent problems into loud ones.

**Analogy.** A bouncer who checks the date on the ticket before anyone enters.

**In this project.** S6.1: `check_window` reads the interval from `get_current_context()` and checks, in order:
1. An interval exists. If not (`KeyError`), it raises `AirflowFailException("No data interval: create exact days with a one-day backfill")`.
2. End minus start is exactly 1 day, and start is 00:00 UTC.
3. `R >= RECON_WORLD_START` (the business opens that day).
4. `R < today (UTC)`: no partial or future days.
5. `R >= today - 45 days`: nothing is written into the 60-day silent-expiry zone.

Then it logs `run_date=YYYY-MM-DD` and returns R. It is the only wall-clock read in the DAG, and it never shapes data. S13.4 (U3) adds an 8 GiB storage stop here.

**Common mistakes.**
- Lifting the guard to "just get one run through".
- Letting the wall-clock date leak into data, for example into a column or a file name.

**Interview answer.** "The first task refuses any run without an exact one-day UTC interval inside the safe date window, so a wrong run fails before it writes anything."

### Docker images, containers and virtual environments

**What it is.**
- A Docker **image** is a packaged filesystem plus settings. A **container** is a running copy of an image. A **bind mount** shows a host folder inside a container.
- A Python **virtual environment** (venv) is an isolated set of installed packages with its own `bin/python` and its own `bin/dbt`.
- Airflow pins every dependency with a constraints file, here `constraints-3.13.txt` for Python 3.13. Installing other packages into Airflow's environment can break those pins.

**Analogy.** The image is a sealed meal kit, the container is the meal being cooked, and the venv is a separate lunchbox so two meals' ingredients never mix.

**In this project.**
- S2.1: the `Dockerfile` starts `FROM apache/airflow:3.3.2` (Python 3.13.15 inside) and creates `/opt/airflow/dbt_venv` with `dbt-core==1.12.6`, `dbt-bigquery==1.12.1` and `dbt-core-experimental-parser==2.0.8` from `docker/requirements-dbt.txt`. The reason for a separate venv: dbt-bigquery 1.12.1 needs google-cloud-storage below 3.2 and dbt-core 1.12.6 needs pathspec below 1.1, while the Airflow 3.3.2 constraints pin google-cloud-storage 3.14.1 and pathspec 1.1.1. The build needs github.com, because the parser downloads its aarch64 wheel during install. Nothing is installed into Airflow's own environment, and the key is never baked in. Image name: `ledger-vs-statement-airflow:3.3.2`.
- S2.2: bind mounts `./src:/opt/airflow/src`, `./dbt:/opt/airflow/dbt`, `./landing:/opt/airflow/landing`, `./runs:/opt/airflow/runs` and `./keys:/opt/airflow/keys:ro`, next to the course's dags, logs, config and plugins mounts. `.dockerignore` keeps `keys/`, `.env`, `landing/`, `runs/`, `logs/`, `.venv/`, `dbt/target/`, `dbt/dbt_packages/` and `.git/` out of the build context.
- S1.3: the host venv is a uv project pinned to Python 3.13 (`uv python pin 3.13`) with the same three dbt pins. Code runs with `PYTHONPATH=src`.
- S0.1: start Docker Desktop first. S10.3: the clean-clone check runs `docker compose build`.

**Common mistakes.**
- Using `_PIP_ADDITIONAL_REQUIREMENTS` instead of building an image. It is meant for quick checks only.
- Installing dbt into Airflow's environment.
- Running the global `dbt` binary instead of the venv's.
- Letting the host Python drift from the container's 3.13. The generator's golden-hash test (S3.4) would catch it.

**Interview answer.** "dbt lives in its own venv inside the Airflow image because their pinned dependencies conflict, and I call it by its full path so the right binary always runs."

---

## Part 4. Payments and reconciliation

All payment data in this project is synthetic. The cards below explain the real-world ideas the simulation is built on. The statement layout is modelled on public settlement-report documentation (the Adyen settlement details report and the Stripe payout reconciliation report, linked under "Sources"), used as public schemas only. Nothing here describes how any particular company works.

### PSP (payment service provider)

**What it is.** A PSP lets a merchant accept payments online. It offers an API and a checkout, connects to acquirers and card networks, sends webhooks when payment events happen, and delivers settlement reports.

**Analogy.** A ticket agency that sells seats for many theatres and settles the money with each theatre later.

**In this project.**
- One synthetic PSP, `psp_alpha`, in the `psp` column of `dbt/seeds/mids.csv` (S3.1, S5.1).
- S0.3: `docs/design.md` describes the business in my own words.

**Common mistakes.**
- Treating the PSP's data as the truth by default. In reconciliation each ledger is checked against the other.
- Assuming one PSP means one account. One PSP can process for several merchant accounts.

**Interview answer.** "The PSP is the middleman that processes card payments and later tells the merchant, per merchant account, what it settled and what it charged."

### Merchant account (MID)

**What it is.** A merchant account, identified by a merchant ID (MID), is the account under which a merchant's payments are processed and settled. A business can have several MIDs, for example per currency, legal entity, region or acquirer. Each MID has its own contract: settlement currency, settlement schedule, fees and the acquirer's daily cut-off.

**Analogy.** Separate cash registers in one shop, each with its own end-of-day till report.

**In this project.**
- S3.1 and S5.1: `dbt/seeds/mids.csv` holds the contract terms (design parameters, illustrative):

| mid | currency | statement_utc_offset_hours | max_settlement_lag_days | fee_bps | fee_fixed_minor | fee_tol_bps | fee_tol_min_minor |
|---|---|---|---|---|---|---|---|
| `mid_usd_01` | USD | -5 | 2 | 290 | 30 | 10 | 5 |
| `mid_kzt_01` | KZT | 5 | 2 | 250 | 0 | 10 | 500 |

- These are terms that both the merchant and the PSP know, so sharing them with dbt is legitimate.
- S5.6: results are reported per (`mid`, `currency`, `recon_date`) in `fct_recon_daily`.

**Common mistakes.**
- Reconciling across MIDs. Each statement belongs to exactly one MID.

**Interview answer.** "I reconcile per merchant account and day because each MID has its own statement, currency, cut-off and fees."

### Acquirer, issuer and card network

**What it is.** The acquirer (acquiring bank) processes card payments for the merchant and pays the merchant. The issuer is the cardholder's bank. The card network, also called the scheme (for example Visa or Mastercard), carries messages and money between them. A card fee can bundle several parts: interchange (to the issuer), scheme fees (to the network) and the acquirer's markup.

**Analogy.** The merchant's bank, the customer's bank, and the postal service that runs between them.

**In this project.**
- Simplified on purpose: each MID's acquirer exists only through its cut-off offset and its statement. There are no issuers or schemes in the data, and one blended fee per line (bps plus a fixed amount) stands in for all fee parts.

**Common mistakes.**
- Confusing the acquirer with the PSP. A PSP can work with several acquirers.

**Interview answer.** "The issuer approves the card payment, the acquirer collects it for the merchant and the network connects them; my synthetic statement collapses their fees into one per-line fee."

### Authorization and capture

**What it is.** Authorization: the issuer approves the payment and reserves the amount on the card; no money moves yet. Capture: the merchant asks to collect the authorized amount, and only captured payments settle. Many online businesses authorize and capture in one step.

**Analogy.** A hotel holds an amount on your card at check-in (authorization) and charges it at check-out (capture).

**In this project.**
- v1.0 models captures only: `event_type` `payment.captured` (S3.2), guarded by an `accepted_values` test (S5.2).
- S5.3: `int_ledger__captures` has one row per captured payment; a unique test on `payment_id` fails if a second capture event ever appears for one payment.
- Authorizations, declines and voids are not in v1.0.

**Common mistakes.**
- Counting authorized amounts as revenue.
- Calling a settled amount that differs from the booked amount a "partial capture". This project says "settled amount differs" (defect D4).

**Interview answer.** "Only captured payments settle, so my ledger books revenue from capture events and nothing earlier."

### Settlement and the settlement statement

**What it is.** Settlement is when captured payments are cleared and the money is credited to the merchant. The PSP or acquirer reports it in a settlement statement: one line per transaction, with gross, fee and net amounts, the merchant account, references and dates.

**Analogy.** The ticket agency sends each theatre a list of every seat it sold, its commission, and what it owes.

**In this project.**
- S3.3: the generator writes one statement file per MID per arrival day: `landing/settlement_lines/arrival_date=YYYY-MM-DD/mid=<mid>.ndjson`. Statement id: `stmt_<mid>_<yyyymmdd of arrival>`. Line id: `ln_<payment_id>`. Record type: `SALE`.
- S2.3: `raw.settlement_lines` columns: `statement_id`, `line_id`, `mid`, `record_type`, `payment_id`, `captured_ts` (the PSP's capture time in UTC, like Adyen's "Creation Date"), `accounting_date`, `gross_minor`, `fee_minor`, `net_minor`, `currency`, `is_synthetic`, `_arrival_date`, `_source_file`.
- S5.2: `stg_psp__settlement_lines` has one row per `line_id`, with `_arrival_date` renamed to `statement_arrival_date`.
- S7.4: `assert_arrival_days_complete` fails if a MID has no statement lines on a day in (`scope_start`, `as_of`]. A missing file is an incident that fails the run, not a pile of `missing_in_statement` lines. (The v1.0 assumption is that every MID settles lines every day; U6 replaces this with statement headers.)

**Common mistakes.**
- Expecting today's sales in today's statement.
- Reading one missing file as hundreds of missing payments.

**Interview answer.** "The settlement statement is the PSP's ledger: per merchant account and day, every settled line with its gross, fee and net."

### Payout

**What it is.** A payout transfers net settled money from the PSP to the merchant's bank account, usually grouping many settled lines into one batch. Reconciling payouts means matching each bank credit to the lines it contains.

**Analogy.** The agency's bank transfer that pays for all the seats sold this week, minus commission.

**In this project.**
- Not in v1.0: no payouts and no statement headers (listed in the README backlog and `docs/roadmap.md`).
- U6 (S16.1, S16.2): `raw.statement_batches` with control totals per MID per arrival date, and `assert_statement_foots` (error), a step toward payout-level checks.

**Common mistakes.**
- Comparing revenue directly with bank credits. Fees, refunds, chargebacks, reserves and timing all sit in between.

**Interview answer.** "My project stops at the statement level; payouts add a third ledger, the bank, which is on the roadmap."

### T+1 and settlement lag

**What it is.** T+1 means a transaction settles one day after its trade or accounting date. The lag between a sale and its statement line is normal. A line that is still waiting is "in transit", not missing.

**Analogy.** A letter posted today arrives tomorrow. It is not lost until it is late.

**In this project.**
- S3.2: the lag is in calendar days after the accounting date: +1 day for 90% of lines and +2 days for 10% (design parameters in `src/recon/world.toml`). Business-day calendars and holidays are a roadmap item.
- S5.3: `due_date = expected_accounting_date + max_settlement_lag_days + statement_grace_days`, which is 2 + 1 = 3 days after the expected accounting date.
- S5.5: a ledger-only line is `in_transit` while `as_of_date < due_date` and becomes `missing_in_statement` from the due date on (the due date itself counts as missing).
- Worked example (synthetic): `pay_20261020_kzt_00042` is captured at 2026-10-20 20:15:07 UTC. Its accounting date is 2026-10-21 (the KZT cut-off shift). Its statement line arrives on 2026-10-22, and its due date is 2026-10-24. The runs for 10-20 and 10-21 see it `in_transit`. From the run for 10-22 it is `matched`.
- S15.4 (U5): `rpt_settlement_completeness` shows the share of booked amount matched 0 to 5 days after booking, as a chart in the README. It makes "in transit is not missing" visible.

**Common mistakes.**
- Flagging every unmatched sale on its first day.
- Measuring "late" against the wall clock instead of the data's as-of date.

**Interview answer.** "A sale is in transit until its contractual settlement lag plus one grace day has passed, judged against the latest loaded data, and only then does it become missing."

### Gross, fee, net and basis points

**What it is.** Gross is the full amount charged. The fee is what the PSP or acquirer keeps. Net is what the merchant receives: net = gross - fee. Card fees are often a percentage in basis points (bps; 1 bps = 0.01%, so 100 bps = 1%) plus a fixed amount per transaction.

**Analogy.** A 1,000 tenge sale with a 2.5% card fee: gross 1,000, fee 25, net 975.

**In this project.**
- Design fees in `mids.csv`: `mid_usd_01` charges 290 bps plus 30 cents; `mid_kzt_01` charges 250 bps plus 0.
- S5.2: `dbt_utils.expression_is_true` "net_minor = gross_minor - fee_minor" on `stg_psp__settlement_lines`.
- S5.5: a fee check on every line that has a statement leg (see the next card).
- The cross-ledger identity uses gross only. Fees change net and payout, not gross, so they are reported in their own columns (`statement_fee_minor`, `expected_fee_minor`, `fee_variance_minor`) and never mixed into the gross identity.

**Common mistakes.**
- Comparing ledger revenue (gross) with statement net and calling the fee a discrepancy.
- Mixing up percent and bps: 2.9% is 290 bps.

**Interview answer.** "I reconcile gross against gross and check fees separately against the contracted rate, because net differs from gross by design."

### Minor units and integer fee arithmetic

**What it is.** Minor units are a currency's smallest unit: cents for USD and tiyn for KZT, 100 per major unit (ISO 4217). Money stored as integers in minor units adds up exactly. Fee rules then need integer arithmetic with an explicit rounding rule, written the same way in Python and SQL:

```
expected_fee_minor  = DIV(statement_gross_minor * fee_bps + 5000, 10000) + fee_fixed_minor            -- half-up for positive gross
fee_tolerance_minor = GREATEST(fee_tol_min_minor, DIV(statement_gross_minor * fee_tol_bps + 9999, 10000))  -- ceiling
fee_variance_minor  = statement_fee_minor - expected_fee_minor
is_fee_mismatch     = ABS(fee_variance_minor) > fee_tolerance_minor                                   -- equal counts as within
```

- Adding 5000 before dividing by 10000 rounds half up, for positive amounts.
- Adding 9999 before dividing rounds up, which is a ceiling.
- Python uses `//`, which gives the same result for positive values.

**Analogy.** A cashier who always rounds the commission to the nearest coin by one fixed rule, written on a card, so every till agrees.

**In this project.** Worked examples (synthetic, from the unit-test design):
- KZT gross 1020 tiyn at 250 bps: the exact fee is 25.5. `DIV(1020 * 250 + 5000, 10000) = DIV(260000, 10000) = 26`. Rounding down would give 25. That is why UT4 asserts `expected_fee_minor = 26` and mutation 5 (half-up changed to floor) turns UT4 red.
- KZT gross 999000 tiyn: expected fee `DIV(249755000, 10000) = 24975`. Tolerance `GREATEST(500, DIV(9999999, 10000)) = 999`. A charged fee of 25974 has variance 999, which is within. A fee of 25975 has variance 1000, which is flagged.
- USD gross 1999 cents at 290 bps plus 30: `DIV(1999 * 290 + 5000, 10000) + 30 = 58 + 30 = 88`.
- Steps: S3.2 (the generator computes fees and noise with the same formula), S5.5 (`fct_recon_lines`), S11.2 (UT4), S11.3 (mutation 5).
- Refunds (negative amounts, v1.x) will need a sign-aware version.

**Common mistakes.**
- `ROUND(gross * bps / 10000)`. In BigQuery the `/` returns FLOAT64.
- Different rounding in Python and SQL, so the generator and the matcher disagree by one unit.
- An inclusive boundary in one place and an exclusive one in another.

**Interview answer.** "All money is INT64 minor units, and fees use one integer formula with half-up rounding shared by the generator and the SQL, so both sides agree to the last tiyn."

### FX rates, direction, cross rates and the carry-forward

**What it is.** An exchange rate is the price of one currency in another. Direction matters: in this project "USD/KZT" means KZT per 1 USD (base USD, quote KZT). A cross rate is derived through a third currency: KZT per EUR = (KZT per USD) / (EUR per USD). Central banks publish official rates on working days, so a provider's series can have gaps on weekends and holidays. Filling a gap day with the last earlier rate is called a carry-forward.

**Analogy.** A price board at an exchange office that is updated only on weekdays. On Sunday you either use Friday's board or ask the bank what it published for Sunday.

**In this project.**
- Worked example (invented numbers, not real rates): 450.00 KZT per USD and 0.90 EUR per USD give 450.00 / 0.90 = 500.00 KZT per EUR. A KZT amount of 999000 tiyn is 9990.00 KZT, which at 450.00 KZT per USD is 22.20 USD.
- Source (S4.2): Frankfurter v2, provider-pinned, `https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT&from=<R-6>&to=<R>`. Always pass `base` and `quotes`. Never blended rates, which mix sources and can be restated. Never request a date on or after today (UTC). Asking for R-6..R means a weekend-only window never comes back empty.
- Landing (S4.2): `fetch_fx` writes the response body byte for byte to `landing/fx/provider=nbk/arrival_date=R.json`, plus `R.meta.json` (`url`, `fetched_at`, `http_status`, `sha256`), atomically. The folder is committed to git. If the file exists, it is never fetched again.
- Parsing: `json.loads(body, parse_float=str)`, so `rate_text` keeps the published digits exactly. The cast to NUMERIC happens only in dbt. Floats never touch a rate.
- S5.2: `stg_fx__rates` keeps the first-seen value per (`provider`, `base`, `quote`, `rate_date`), ordered by fetch partition. S7.4: `warn_fx_restated` reports any rate date whose text differs between fetches.
- S5.4: `int_fx__usd_rates_daily` has one row per (currency, day) from the earliest fetched `rate_date` to `as_of_date`. A day without a row takes the latest earlier rate (`LAST_VALUE(... IGNORE NULLS)`), with `rate_date` and `carry_days` showing where it came from. USD gets identity rows (1 USD per USD, carry 0). Tests: `carry_days` from 0 to `var('fx_max_carry_days')` (5), and `dbt_utils.accepted_range` 300 to 700 KZT per USD, which catches unit and direction errors.
- The carry-forward is "a project convention, not NBK's official rate for that day". NBK's own feed publishes rates for weekend days. S9.2 (`scripts/fx_report.py`, number N3) compares the carried-forward rates with NBK's RSS feed for each day, requires exact agreement on weekdays, and measures the weekend and holiday gaps.
- Conversion is for reporting only: once per MID-day, after summing minor units, with the `to_usd` macro and the rate of the recon date (S5.6). The reconciliation itself never converts currency in v1.0.
- U7 (S17.1 to S17.3): a cross-currency MID, cross rates in NUMERIC, and NBK RSS as a second dbt provider with a weekday-agreement test.

**Common mistakes.**
- Inverting the rate: 0.0022 instead of about 450. The range test catches it.
- Presenting a carried-forward weekend rate as the official rate.
- Fetching rates again during a backfill.
- Converting each line, rounding, summing and rounding again: several rounding stages that no longer add up.

**Interview answer.** "FX is real NBK data, stored exactly as published and landed once; weekend gaps are filled by an explicit, labelled carry-forward rule, and a separate check measures how far that rule is from NBK's own weekend rates."

### Presentment currency vs settlement currency

**What it is.** Presentment currency is the currency the customer is charged in. Settlement currency is the currency the merchant receives. When they differ, the amount is converted, usually at a rate with a markup, and the conversion becomes another source of differences between ledgers.

**Analogy.** A traveller pays in tenge, and the shop's foreign bank account receives dollars.

**In this project.**
- v1.0: each MID charges and settles in the same currency. So the gross tolerance is exactly 0, and the reconciliation needs no conversion.
- U7 (S17.1, S17.2): `mid_kzt_usd_01` charges in KZT and settles in USD at a PSP markup on the previous day's NBK rate. An FX component per line, in INT64 cents with one rounding stage, joins the identity, and the cost of processing is reported in bps.

**Common mistakes.**
- Reconciling converted amounts without saying which rate, from which date, was used.

**Interview answer.** "In v1.0 presentment and settlement currency are the same for each MID, so FX is reporting-only; the cross-currency case, with its own FX component, is the next version."

### Refunds

**What it is.** A refund returns money to the customer at the merchant's initiative. It reduces revenue, often settles in a later batch than the sale, and can be partial.

**Analogy.** Taking an item back to the shop and getting your money back.

**In this project.**
- Not in v1.0. On the roadmap (v1.x): refunds settled in later batches. The integer fee formula will need a sign-aware version for negative amounts.

**Common mistakes.**
- Booking a refund on the sale date in one ledger and on the refund date in the other, then calling the timing gap an error.

**Interview answer.** "Refunds are left out of v1.0 on purpose, because they add a later-batch timing difference and negative amounts, which the roadmap covers."

### Chargebacks

**What it is.** A chargeback is a forced reversal that the cardholder starts through the issuer, called a dispute. The money is taken back from the merchant, often weeks later and usually with a fee, and the merchant can contest it. Card networks monitor dispute and fraud ratios per merchant.

**Analogy.** The customer asks their own bank to cancel a payment, and the bank takes the money back from the shop.

**In this project.**
- Not in v1.0. On the roadmap: chargebacks as statement-only debits (v1.x), and a chargeback ratio per MID with a count-based definition (v2).

**Common mistakes.**
- Treating a chargeback like a refund. It starts at the issuer, carries a fee and can be reversed again.

**Interview answer.** "Chargebacks appear only on the PSP side, often weeks later, so they would arrive as statement-only debits, which the roadmap models."

### Webhooks and redelivery

**What it is.** A webhook is an HTTP request that a PSP sends to the merchant's server when an event happens, such as a capture. Delivery is at least once: if the merchant's server does not answer with success quickly, the PSP sends the event again, so the same event can arrive two or more times. Events can also arrive out of order. The receiver therefore deduplicates on the event id. Public PSP documentation describes both behaviours (see the webhook guide under "Sources").

**Analogy.** A courier who leaves a second copy of the same parcel notice because he is not sure the first one was seen.

**In this project.**
- S3.2 and S3.3: defect D1 `webhook_redelivery`. About 4% of events get extra deliveries: 1 extra copy (75%) or 2 (25%), each 60 to 21,600 seconds after the first delivery, so a copy often lands in the next UTC day's file. Each copy has a new `delivery_id` (`dlv_<event_id>_<attempt>`) and the same `event_id` (`evt_<payment_id>_cap`). The first delivery arrives 1 to 30 seconds after the capture.
- S5.2: dedup in `stg_psp__payment_events` (see "Deduplication with QUALIFY" in Part 5).
- S5.6: `assert_redeliveries_identical` fails if two deliveries of one `event_id` differ in `payment_id`, `mid`, `amount_minor`, `currency`, `event_ts` or `event_type`. Keeping the first delivery is only safe if every copy agrees.
- S11.1 (U1): UT3 pins the tie-break.
- Held back for U4: H4 `redelivery_payload_changed`, a redelivery with a different amount.

**Common mistakes.**
- Deduplicating inside one day's partition only. Redeliveries cross midnight.
- Picking the copy to keep without a stated, deterministic rule.

**Interview answer.** "Webhooks are delivered at least once, so the ledger deduplicates on the event id across days, and a test proves that every copy carried the same payload."

### Idempotency keys

**What it is.** An idempotency key is a unique id that a client sends with a request, for example in an `Idempotency-Key` header, so that the server performs the action only once even if the request is retried. On the receiving side, the event id plays the same role: process each id once.

**Analogy.** A numbered queue ticket: a second ticket with the same number is not served twice.

**In this project.**
- This project calls no PSP API, so it sends no idempotency keys.
- The same idea appears as deterministic ids: `event_id` is the dedup key, `delivery_id` identifies each delivery attempt, and `payment_id` is the reference shared with the statement.
- The pipeline as a whole is idempotent per partition (see "Idempotency" in Part 3).

**Common mistakes.**
- Reusing one key for a different request.
- Using personal data, such as an email address, as a key.

**Interview answer.** "Idempotency keys make retries safe on the sending side; in my pipeline, event ids and partition replacement give the same guarantee on the receiving side."

### Cut-off times, time zones and the accounting date

**What it is.** An acquirer closes its business day at a cut-off time in its own time zone. A payment after the cut-off belongs to the next accounting day. So one payment can carry different dates in two ledgers. Kazakhstan has used UTC+5 all year since 2024-03-01.

**Analogy.** A shop closes its till at 20:00; a sale at 20:05 goes into tomorrow's report.

**In this project.**
- Booking date is `DATE(event_ts)` in UTC. The accounting date is the capture time shifted by the MID's fixed offset: `expected_accounting_date = DATE(TIMESTAMP_ADD(event_ts, INTERVAL statement_utc_offset_hours HOUR))` (S5.3).
- `mid_usd_01` (UTC-5): captures between 00:00 and 04:59 UTC belong to the previous accounting date. `mid_kzt_01` (UTC+5): captures between 19:00 and 23:59 UTC belong to the next one. So timing differences run in both directions, which tests both sides of the bridge. With the evening-peak hour profile in `world.toml`, the design expects about 36% of USD captures and about 7.5% of KZT captures to shift (a design consequence, not a result).
- S5.3: UT1 pins the seconds around both cut-offs: KZT captures at 18:59:59, 19:00:00 and 19:30:00 UTC; USD captures at 04:59:59, 05:00:00 and 03:00:00 UTC.
- S5.5: on matched lines, `date_shift` is `none` if the accounting date equals the booking date, else `timing_cutoff` if it equals the expected accounting date (explained), else `date_mismatch` (an exception). UT2 pins both cases.

**Common mistakes.**
- Comparing two ledgers by calendar day without the offset.
- Using a named time zone with daylight saving when the design says fixed offset.

**Interview answer.** "Each merchant account closes its day at its own fixed offset, so a capture near midnight UTC can belong to another accounting day, and the matcher explains that as timing rather than an error."

### Ledger vs statement: reconciliation

**What it is.** Reconciliation compares two independent records of the same money and explains every difference. Here our ledger (revenue booked from capture webhooks by UTC day) is compared with the PSP's statement (lines by accounting day). Every difference is matched, explained (a benign, evidenced cause) or an exception (it needs an analyst). Whatever is left is unexplained, and it must be zero.

**Analogy.** Checking my own notebook of purchases against my bank statement, line by line.

**In this project.**
- Vocabulary:

| Term | Meaning |
|---|---|
| matched | both sides are present for the payment |
| explained | a difference with a benign, evidenced cause: `timing_cutoff`, `in_transit`, `before_scope` |
| exception | a difference that needs an analyst: `missing_in_statement`, `missing_in_ledger`, `amount_mismatch`, `fee_mismatch`, `date_mismatch` |
| unexplained | what is left of a MID-day's gap after all dated components; must be exactly 0 minor units, anything else is a pipeline bug that fails the run |

- Matching (S5.5): an exact key, `payment_id`, in a FULL OUTER JOIN (see "FULL OUTER JOIN matching" in Part 5). The question is not "within how many days do we match" but "how long do we wait before calling a line missing", which is the due date.
- S5.1: `reason_codes.csv` gives each code a category, a precedence, a description and an `analyst_action`.
- Outputs: `fct_recon_lines` (one status per line, S5.5), `fct_recon_exceptions` (the analyst work queue with one row per line and cause, S7.2) and `fct_recon_daily` (the two-calendar bridge per MID-day, S5.6).
- S0.3: the defect catalog (`docs/specs/data_and_generator.md`, heading "Defect catalog") lists planted defects D1 to D5 and benign behaviours B1 to B3 with their expected outcomes. It is committed in M0, before any matcher SQL.

**Common mistakes.**
- Reconciling totals only. Offsetting errors cancel each other out.
- Forcing one reason onto a line that has two causes, such as an amount difference and a fee overcharge. The exceptions view gives one row per cause.
- Claiming that v1.0 reconciles "all web-to-app revenue". It does not reconcile refunds, chargebacks, reserves, payouts and bank arrival, presentment versus settlement currency, cascades and approval rates, test transactions, app-store revenue, or revenue recognition over the service period.

**Interview answer.** "I match every payment line on its PSP reference, give each difference one status and dated reason components, and require the unexplained remainder to be exactly zero per MID-day."

### Line statuses, due dates and scope

**What it is.** Each line in `fct_recon_lines` gets exactly one `match_status`:

```
case
  when has_ledger and has_statement              then 'matched'
  when has_ledger and booking_date < scope_start then 'before_scope'
  when has_ledger and as_of_date < due_date      then 'in_transit'
  when has_ledger                                then 'missing_in_statement'
  when date(captured_ts) < scope_start           then 'before_scope'
  else                                                'missing_in_ledger'
end
```

- `scope_start` is the oldest loaded arrival date. `before_scope` covers one-sided lines older than that, so partial windows (a development subset, a 14-day history, the 60-day expiry) never create false exceptions.
- Flags on top of the status: `date_shift` (matched lines), `amount_diff_minor = ledger_amount_minor - statement_gross_minor` with `is_amount_mismatch = amount_diff_minor != 0`, and the fee check.
- `primary_reason`, one label per line, first match wins: `missing_in_statement`, `missing_in_ledger`, `amount_mismatch`, `fee_mismatch`, `date_mismatch`, `in_transit`, `timing_cutoff`, `before_scope`, `matched`.
- `is_exception` is true when any exception cause applies.
- `fct_recon_exceptions` signs and dates: `missing_in_statement` is +L on the booking date; `missing_in_ledger` is -S on the accounting date; `amount_mismatch` is L - S on the accounting date; `fee_mismatch` is the fee variance on the accounting date; `date_mismatch` is L on the accounting date. Positive means the ledger has more, or the PSP overcharged. `before_scope` lines never appear there.

**Analogy.** A parcel tracker: delivered, on its way, overdue, or never sent.

**In this project.**
- S5.5: UT2 fixes the cases with `as_of_date` 2026-10-28 and `scope_start` 2026-10-20: `pay_a` ledger-only, due 10-29, is `in_transit`; `pay_b` ledger-only, due 10-28, is `missing_in_statement` (the due date is inclusive); `pay_c` is `matched` with `timing_cutoff`; `pay_d` is `matched` with `date_mismatch` (an exception); `pay_e` (statement-only, captured 10-26) is `missing_in_ledger`; `pay_f` (statement-only, captured 10-18) is `before_scope`.
- S7.5: mutation 2 changes `as_of_date < due_date` to `<=`, and UT2 must go red.

**Common mistakes.**
- Judging statuses against the wall clock.
- Leaving out `before_scope`, so the first loaded day shows many false "missing" lines.

**Interview answer.** "Every line gets exactly one status from an ordered rule, judged against the latest loaded data, with a scope rule so a partial history never invents exceptions."

### Tolerance

**What it is.** A tolerance is the difference allowed before a line counts as a mismatch. It needs a stated boundary rule (is a difference equal to the tolerance inside or outside?) and a reason.

**Analogy.** A market scale that is allowed to be a few grams off either way.

**In this project.**
- Gross amount: exactly 0, because both sides use the same currency.
- Fee: per-MID bps with a minimum (`fee_tol_bps`, `fee_tol_min_minor` in `mids.csv`). A variance equal to the tolerance is within (S5.5). UT4 pins the boundary (S11.2).
- Benign fee noise (B3) is designed to cross the tolerance about 1% of the time, so false alarms are possible. PSP overcharges (D5) at or below the tolerance are misses by design. Both keep the seeded self-test honest (see Part 5).
- All tolerances live in seeds or vars, so U7's sweep (S17.4) can vary them.

**Common mistakes.**
- No stated boundary rule, so Python and SQL disagree at the edge.
- A tolerance hidden inside SQL instead of a seed or var.

**Interview answer.** "Every tolerance lives in a seed or var, with an inclusive boundary pinned by a unit test, so its effect can be measured instead of argued."

### The two-calendar bridge and the identity (and why it is not a tautology)

**What it is.** For each (`mid`, `currency`, `recon_date`) in `fct_recon_daily`:
- **Top-down:** `gap_minor` = the sum of ledger amounts by booking date (from `int_ledger__captures`) minus the sum of statement gross by accounting date (from `stg_psp__settlement_lines`, SALE lines). This path never touches the matcher.
- **Bottom-up:** the sum of 7 dated components built from `fct_recon_lines`: `timing_cutoff_minor`, `date_mismatch_minor`, `amount_mismatch_minor`, `in_transit_minor`, `missing_in_statement_minor`, `missing_in_ledger_minor` and `before_scope_minor`.
- **The identity:** `unexplained_minor = gap_minor - components` must be 0 on every row.

A tautology is a check that cannot fail: for example, computing "unexplained" as gap minus explained and then testing that gap equals explained plus unexplained. This identity can fail, because its two sides come from different models. It fails when the matcher loses a one-sided line, duplicates a line, puts money on the wrong day, uses the wrong sign or forgets a component.

How each line contributes, with L = the ledger amount on booking date a and S = the statement gross on accounting date b:

| Line | Component(s) |
|---|---|
| matched, a = b | `amount_mismatch`: L - S on b (if not zero) |
| matched, a != b | `timing_cutoff` or `date_mismatch` (by `date_shift`): +L on a and -L on b; plus `amount_mismatch`: L - S on b |
| ledger-only | `in_transit`, `missing_in_statement` or `before_scope` (by status): +L on a |
| statement-only | `missing_in_ledger` or `before_scope` (by status): -S on b |

Worked example (synthetic): L = 1000 booked on 10-20, S = 900 on accounting date 10-21. On 10-20 the gap is +1000, and the timing component is +1000. On 10-21 the gap is -900, made of timing -1000 plus amount_mismatch +100. Timing nets to zero over the two days, and the 100 difference appears exactly once.

**Analogy.** Adding up a shop's takings from the till rolls and, separately, from the list of explained differences. If the two totals disagree, someone's arithmetic lost a receipt.

**In this project.**
- S5.6: `fct_recon_daily` and `assert_recon_decomposition_closes` (error).
- S5.6: `assert_no_money_lost_between_layers` (error) checks, per MID, that (count, sum of amount) of `int_ledger__captures` equals the ledger side of `fct_recon_lines`, and that (count, sum of gross, sum of fee) of `stg_psp__settlement_lines` equals the statement side. It catches a dropped same-day matched line with equal amounts, which adds 0 to the gap, so the identity alone cannot see it.
- S7.5: mutations 1 (INNER JOIN) and 4 (the SALE filter moved after the join) must turn both tests red.
- S9.1: number N2 counts the MID-days and sums `ABS(unexplained_minor)`; the claim is used only if that sum is 0 and the latest `assert_recon_decomposition_closes` passed.
- What these tests do not prove: that the labels are right. Labels are covered by unit tests (logic) and, from U1, by the seeded self-test (behaviour on planted data). The README lists the three kinds of evidence separately.

**Common mistakes.**
- Computing "unexplained" from itself.
- Mixing fees into the gross identity.
- Rounding converted amounts before summing them.

**Interview answer.** "Each MID-day's gap is computed top-down from the inputs and bottom-up from the matcher's dated reason components; they come from different models, so the zero-unexplained test can fail, and a mutation check shows that it does."

### Metric definitions

**What it is.** A metric is only useful with a written definition and its counts. These are the definitions used in the README and the dbt docs:

| Metric | Definition |
|---|---|
| Booked gross | sum of deduplicated captured amounts by UTC booking date |
| Statement gross / net | sum of statement gross / net by accounting date |
| Gap | booked gross minus statement gross per MID-day (two calendars) |
| Break amount | sum of absolute exception amounts (missing on either side, amount mismatch, fee mismatch); offsetting breaks cannot cancel |
| Break share | break amount / booked gross over a rolling 7-day window, shown with the count |
| Match rate | matched lines / lines due (in-transit lines excluded), by count and by amount |
| Duplicate delivery rate | removed copies / deliveries received |
| Exception age | `as_of_date` minus `recon_date` |
| Unexplained | must be 0 |

**Analogy.** A recipe that says "a cup" only works if everyone uses the same cup.

**In this project.** `fct_recon_daily` carries `exception_count` and `exception_abs_minor` (added in S7.2). `warn_exception_share_7d` (S7.4) uses the break share with a minimum count. Every rate is shown next to its counts.

**Common mistakes.**
- A rate without its denominator, or computed over lines that are not due yet.
- Signed sums of breaks, where an overcharge and an undercharge cancel.

**Interview answer.** "Every metric has a written definition and is shown with its counts, and break amounts use absolute values so offsetting errors cannot hide each other."

---

## Part 5. Data engineering

### Grain

**What it is.** The grain of a table is what one row means. State the grain first; the keys, joins and tests follow from it.

**Analogy.** A shop receipt has one line per item bought, not one line per customer.

**In this project.** Every model description starts with "One row per ..." (S5.1 to S7.3):

| Table or model | One row per |
|---|---|
| `raw.payment_events` | webhook delivery that arrived on `_arrival_date` |
| `raw.settlement_lines` | line of a per-MID statement file that arrived on `_arrival_date` |
| `raw.fx_rates` | rate observation returned by the fetch made for `_arrival_date` |
| `stg_recon__as_of` | one row in total |
| `stg_psp__payment_events` | `event_id` |
| `stg_psp__settlement_lines` | `line_id` |
| `stg_fx__rates` | (`provider`, `base`, `quote`, `rate_date`) |
| `int_ledger__captures` | `payment_id` |
| `int_fx__usd_rates_daily` | (`currency`, `day`) |
| `fct_recon_lines` | `payment_id` seen on either side |
| `fct_recon_exceptions` | (`payment_id`, `cause`) |
| `fct_recon_daily` | (`mid`, `currency`, `recon_date`) |

**Common mistakes.**
- A join that quietly multiplies rows (fan-out).
- No uniqueness test on the grain's key.

**Interview answer.** "I state each model's grain in its description and test it with a uniqueness test on the grain's key."

### Keys

**What it is.** A key identifies a row. A natural or business key comes from the domain (`payment_id`). A surrogate key is generated, for example a hash. A primary key is unique and never null for the grain. A foreign key points to a key in another table. A composite key uses several columns together.

**Analogy.** A passport number identifies one person; a family name does not.

**In this project.**
- S3.2: ids are readable and deterministic: `pay_20261025_kzt_00042`, `ord_20261025_kzt_00042`, `evt_<payment_id>_cap`, `dlv_<event_id>_<attempt>`, `stmt_<mid>_<yyyymmdd>`, `ln_<payment_id>`. No personal data anywhere.
- Tests: `unique` and `not_null` on `event_id`, `line_id` and `payment_id`; `dbt_utils.unique_combination_of_columns` on composite keys; `relationships` from `mid` to the `mids` seed, and from `primary_reason` and `cause` to `reason_codes`.
- BigQuery does not enforce primary keys, so every key is tested.

**Common mistakes.**
- Random UUIDs in synthetic data. Every rerun changes the ids, and the rerun proof fails.
- Keys built from personal data.
- Assuming the warehouse enforces a primary key.

**Interview answer.** "Keys are deterministic and readable, so a rerun produces the same ids and a reviewer can follow one payment through every layer."

### Deterministic replay: the seeded generator

**What it is.** Deterministic replay means the same inputs always produce exactly the same outputs, byte for byte, so any day can be rebuilt at any time and in any order.

**Analogy.** A music box: the same cylinder always plays the same tune.

**In this project.**
- S3.2 and S3.3: `day_index = (booking_date - RECON_WORLD_START).days`. Payments are a pure function of (seed, `day_index`, `mid`). Nothing depends on the weekday or the real date, so moving `RECON_WORLD_START` reproduces the same synthetic data on new dates.
- One random stream per purpose: `random.Random(f"{seed}|{day_index}|{mid}|{purpose}")` for day-level draws, and `random.Random(f"{seed}|{day_index}|{mid}|{n}|{purpose}")` for payment n. Purposes: `plan`, `time`, `delivery`, `redelivery`, `lag`, `money`, `amount_delta`, `combo`, `fee_defect`, `fee_noise`. A new defect class gets a new purpose, so it never reshuffles existing rows.
- String seeds are converted to an integer using all of their bits (CPython hashes them with SHA-512), so they are stable across processes, unlike Python's `hash()`, which is randomized per process for strings.
- Only `Random.random()` is used. Python guarantees that `random()` produces the same sequence for the same seed across versions; other methods can change. Two helpers are built on it: `draw_int(rng, lo, hi)` and `draw_weighted(rng, weights)`. No `randint`, `choices` or `uniform`.
- Output is byte-identical: rows sorted by key, `json.dumps(sort_keys=True, separators=(",", ":"))`, a trailing newline, written to a temporary name and renamed atomically.
- `lookback_days` = 5: `emit` for run date R recomputes the payments booked on R-5..R and writes only what arrives on R. A pytest proves that 5 days is enough.
- S3.4: a golden-hash pytest (the sha256 of one emitted day, committed) catches drift. Host and container both run Python 3.13.
- Frozen at gate G1 (tag `g1-freeze`). Any later change to the generator or loader means a full re-backfill before the proof.
- FX is real data, so it is made replayable by landing it once (see "FX rates, direction, cross rates and the carry-forward" in Part 4).

**Common mistakes.**
- Seeding one global generator at the top, so every draw depends on the order of all earlier draws.
- Seeding with `hash()` of a string.
- `datetime.now()` anywhere in the generator.
- Writing dicts without sorted keys.
- Different Python versions on the host and in the container.

**Interview answer.** "The generator is a pure function of seed, day index, merchant account and purpose, so any day regenerates byte for byte, which is what makes reruns and backfills safe to prove."

### Late data

**What it is.** Late data arrives after the period it belongs to. In payments it is normal: statement lines arrive 1 to 2 days after the sale, and a webhook redelivery can arrive the next day. A pipeline must decide where late data lands and how long to wait before calling something missing.

**Analogy.** A birthday card that arrives the day after the party still belongs to the birthday.

**In this project.**
- Raw tables are partitioned by arrival date, so late data simply lands in a later partition. Nothing earlier is rewritten.
- The marts rebuild from all loaded partitions, and `as_of_date` is the latest loaded arrival date, so a line that arrives late turns `in_transit` into `matched` on the next run.
- The waiting rule is the due date (see "T+1 and settlement lag" in Part 4).
- Roadmap: a `ledger_pending` grace status for late webhooks, before `missing_in_ledger`.

**Common mistakes.**
- An incremental filter such as `> max(date)` that skips rows arriving late.
- Treating "not arrived yet" as "missing".

**Interview answer.** "Partitioning by arrival date means late data never rewrites the past, and the marts recompute statuses as of the latest arrival, so late lines move from in transit to matched."

### Deduplication with QUALIFY

**What it is.** Deduplication keeps exactly one row per key. In BigQuery, `QUALIFY` filters on the result of a window function, so one query can rank the rows of each key and keep the first:

```
qualify row_number() over (partition by event_id order by delivered_ts, delivery_id) = 1
```

The second ORDER BY column, `delivery_id`, is a tie-break. Without it, two deliveries with the same `delivered_ts` could swap places between runs. If BigQuery asks for a WHERE clause with QUALIFY, add `where true`.

**Analogy.** Several copies of the same letter arrive; you file the one that came first and note how many copies there were.

**In this project.**
- S5.2: `stg_psp__payment_events` first filters `_arrival_date <= as_of_date`, then keeps the first delivery per `event_id`. It adds `copies_received = COUNT(*) OVER (PARTITION BY event_id)` and keeps `first_delivery_id`, `first_delivered_ts` and `first_arrival_date`.
- Tests: `unique` and `not_null` on `event_id`, plus `unique` on `payment_id` downstream in `int_ledger__captures`.
- S7.5: mutation 3 removes the QUALIFY; both uniqueness tests must go red.
- S11.1 (U1): UT3 pins the tie-break and the as-of filter: two deliveries at different times, two at the same `delivered_ts` (the tie goes to `dlv_..._1`), and one delivery with `_arrival_date` after as_of, which is excluded.

**Common mistakes.**
- No tie-break, so the "first" row can change between runs.
- Deduplicating inside one day's partition only.
- A uniqueness test filtered by the rank, which can never fail.

**Interview answer.** "I deduplicate with QUALIFY ROW_NUMBER over the event id, ordered by delivery time with a delivery-id tie-break, so the same row wins on every rebuild."

### FULL OUTER JOIN matching

**What it is.** A FULL OUTER JOIN keeps every row from both sides: matched pairs, plus rows found only on the left or only on the right, with NULLs on the missing side. Reconciliation needs exactly that, because one-sided lines are the interesting ones. BigQuery rejects a FULL OUTER JOIN whose condition has no equality between the two sides (for example conditions joined with OR), with the error "FULL OUTER JOIN cannot be used without a condition that is an equality of fields from both sides of the join".

**Analogy.** Laying two guest lists side by side: names on both, names only on mine, and names only on yours.

**In this project.**
- S5.5: `fct_recon_lines` joins `int_ledger__captures` to the statement lines with a FULL OUTER JOIN on `payment_id`. The statement side is filtered to `record_type = 'SALE'` in a CTE before the join; a filter after the join would drop the ledger-only rows. `has_ledger` and `has_statement` record which sides exist, and `recon_date = COALESCE(booking_date, DATE(captured_ts))` is never NULL.
- S7.5: mutation 1 (INNER JOIN) and mutation 4 (the SALE filter after the join) must turn the identity and preservation tests red.
- Roadmap: a second matching pass over the leftovers on (`order_id`, amount, currency, plus or minus 1 day), as a separate join. Every FULL OUTER JOIN keeps an equality condition.

**Common mistakes.**
- A WHERE filter on one side after the join, which silently turns the FULL OUTER JOIN into a narrower join.
- OR conditions in the ON clause.
- Duplicate keys on one side, which multiply rows. The unique test on `payment_id` in `fct_recon_lines` catches it.

**Interview answer.** "A FULL OUTER JOIN on the PSP reference keeps lines that are missing on either side, and I filter each side before the join so those one-sided rows survive."

### As-of joins, date spines and carry-forward

**What it is.** An as-of join gives each row the latest value known on or before its date, for example the latest FX rate on or before a reporting day. A date spine is a table with one row per day, so every day exists even when the source has gaps. Carry-forward fills a gap day with the last earlier value.

**Analogy.** A thermometer log that writes yesterday's reading again, clearly marked, on a day the thermometer was not checked.

**In this project.**
- S5.4: `int_fx__usd_rates_daily` builds the spine per currency from the earliest fetched `rate_date` to `as_of_date` and carries rates forward with `LAST_VALUE(... IGNORE NULLS)`. `rate_date` and `carry_days` show where each value came from. Tests: unique (`currency`, `day`), not_null `units_per_usd` and `rate_date`, and `carry_days` between 0 and `var('fx_max_carry_days')`.
- S5.6: `fct_recon_daily` joins the rate for its `recon_date` and currency (`units_per_usd`, `fx_rate_date`, `fx_carry_days`). Its own spine covers every MID in the seed times every day from the minimum to the maximum date in the inputs, so quiet days show zeros instead of missing rows.
- S9.2: `scripts/fx_report.py` compares the carried rates with NBK's own published rates for the same days.

**Common mistakes.**
- Joining on an exact date and losing weekends.
- Carrying a value forward without recording how far it was carried.
- Using a rate from a later date (look-ahead).

**Interview answer.** "A daily spine with LAST_VALUE IGNORE NULLS gives every day a rate and records which day it came from, so the carry-forward is visible and testable."

### Data contracts

**What it is.** A data contract is an explicit, machine-checked agreement about the shape of data between a producer and a consumer: columns, types, required fields and rules.

**Analogy.** A shipping label that the warehouse scanner checks before the box is accepted.

**In this project.**
- Raw contract (S2.3, S3.4, S4.1): one JSON file per raw table in `src/recon/schemas/` (`payment_events.json`, `settlement_lines.json`, `fx_rates.json`). The same file drives table creation (`ensure_tables`), the load job's explicit schema and a pytest that checks generated rows against it. Before any job, the loader asserts that every row's `_arrival_date` equals R and, for payment events, that `DATE(delivered_ts)` equals R. A wrong row fails the task before anything is written.
- Labels travel with the data: synthetic tables have a description that starts with "SYNTHETIC: generated by src/recon/generator.py" and the label `data_origin=synthetic`; `raw.fx_rates` starts with "REAL: NBK rates via Frankfurter v2" and has `data_origin=real`. Synthetic rows carry `is_synthetic = true`.
- Mart contract (S7.3): the enforced dbt contract on `fct_recon_daily` (see "Contracts" in Part 2).

**Common mistakes.**
- Schema autodetect.
- A contract that exists only in a document and is never checked.
- Silent type coercion between layers.

**Interview answer.** "One schema file per raw table drives table creation, loading and a test, and the reconciliation mart has an enforced dbt contract, so a shape change fails loudly at both ends."

### Data quality checks: integrity gates and business gates

**What it is.** Data quality checks test that data is complete, unique, valid, consistent and on time. Two kinds matter here:
- **Integrity gates:** if one fails, the numbers cannot be trusted, so the run must fail (severity error).
- **Business gates:** they describe the business, for example many exceptions on one MID. They warn, because exceptions are the product that analysts work on, not a pipeline failure.

**Analogy.** A smoke alarm (integrity: everyone leaves the building) versus a "low on milk" note on the fridge (business: someone should look).

**In this project.**
- Error (S5.2 to S5.4): unique and not_null keys, `accepted_values`, `relationships`, `net_minor = gross_minor - fee_minor`, the FX range (300 to 700 KZT per USD) and FX staleness (`carry_days`).
- Error (S5.6): `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers`, `assert_redeliveries_identical`.
- Error (S7.4): `assert_arrival_days_complete`. A day in [`scope_start`, `as_of`] without a `payment_events` partition, or a MID with no statement lines on a day in (`scope_start`, `as_of`], fails the run.
- Warn (S7.4): `warn_exception_share_7d` fires per MID when, over the last `gate_window_days` (7) days to as_of, `SUM(exception_abs_minor) / SUM(ledger_gross_minor)` is above `exception_share_warn` (0.02) and `SUM(exception_count)` is at least `exception_min_count` (5). The minimum count means one break among about 70 KZT payments a day cannot trip it. `warn_fx_restated` fires when a rate date has more than one `rate_text` across fetches.
- U6 (S16.2, S16.4): `assert_statement_foots` (error) and a business gate at error level for a break share above 10%, with the minimum count. S16.3 plants D6 `late_batch` (one MID-day file 3 days late) on its own stream: the integrity gate must stay red until the batch lands, then turn green.

**Common mistakes.**
- Everything at error level, so normal business events stop the pipeline.
- Everything at warn level, so nothing stops bad data.
- Rate-based alerts without a minimum count, so random noise trips them.

**Interview answer.** "Integrity checks fail the run because they mean the pipeline is wrong, while business checks only warn, because exceptions are the output the analysts work on."

### Three dates and as_of_date

**What it is.** Each payment in this project can carry three different dates:

| Date | Meaning | Where |
|---|---|---|
| Arrival date | the UTC day a webhook or statement file reached us; one Airflow run owns one arrival date | `_arrival_date`, the raw partition key |
| Booking date | our revenue day: `DATE(event_ts)` in UTC | `int_ledger__captures.booking_date` |
| Accounting date | the PSP's day for the sale: the capture time shifted by the MID's fixed UTC offset | `settlement_lines.accounting_date` |

`as_of_date` means "what we know": the latest loaded arrival date, `MAX(_arrival_date)` of the payment events source. Deliveries arrive every day, so it is never NULL, even on day 1. It is stored on every mart row. `scope_start` is the oldest loaded arrival date. Statuses are judged against `as_of_date`, never against the wall clock, and no model uses `CURRENT_DATE()`. So an old rerun never rolls the marts back, and a rebuild of the same data always gives the same statuses.

**Analogy.** A letter has the date it was written, the postmark date and the date it arrived. Mixing them up starts arguments.

**In this project.**
- S3.2 and S3.3: the generator creates all three dates.
- S5.2: `stg_recon__as_of` computes `as_of_date` (or takes the `as_of_date` var for host time travel) and `scope_start`.
- S5.5: statuses use `as_of_date`, `scope_start` and `due_date`.
- S8.2: the proof requires the same `as_of_date` in the snapshots before and after.
- Wording rule: say "three dates" or "two time axes". Never "bitemporal" until the U5 snapshot exists.
- Worked example (synthetic), payment `pay_20261020_kzt_00042`, 999000 tiyn, captured 2026-10-20 20:15:07 UTC:
  1. The first webhook delivery at 20:15:30 UTC arrives on 10-20. A redelivery at 02:10 UTC on 10-21 arrives on 10-21 and is removed by dedup (`copies_received = 2`).
  2. Accounting date: 20:15 UTC plus 5 hours is 01:15 on 10-21, so the PSP books the sale on 10-21 (benign behaviour B1, the cut-off shift).
  3. With a 1-day lag, the statement line arrives on 10-22 in `stmt_mid_kzt_01_20261022`. Due date: 10-21 + 2 + 1 = 10-24.
  4. In the runs for 10-20 and 10-21 the line is `in_transit`. From the run for 10-22 it is `matched` with `date_shift = timing_cutoff`.
  5. In `fct_recon_daily` it adds +999000 on 10-20 and -999000 on 10-21. Timing nets to zero over the two days.

**Common mistakes.**
- Mixing booking and accounting dates in one total.
- Taking as-of from the statements, so that one missing statement file rolls it back.
- The wall clock inside a model.

**Interview answer.** "I keep three dates apart, arrival, booking and accounting, and judge every status as of the latest loaded arrival day, so results depend only on the data."

### The fingerprint proof

**What it is.** A fingerprint is a short value computed from data that changes whenever any row changes. Comparing fingerprints before and after a rerun shows, with very high probability, whether the data changed. The query, per partition group:

```sql
select {part_col} as part,
       count(*) as n,
       bit_xor(farm_fingerprint(to_json_string(t))) as xor_fp,
       sum(cast(farm_fingerprint(to_json_string(t)) as bignumeric)) as sum_fp
from `{project}.{dataset}.{table}` as t
where {part_col} between @from and @to
group by part
order by part
```

- `TO_JSON_STRING(t)` turns the whole row into text, `FARM_FINGERPRINT` hashes that text to an INT64, and `BIT_XOR` combines the hashes in any order.
- XOR alone cancels identical pairs: two identical duplicated rows XOR to 0. So COUNT and a SUM of the hashes are kept too. The SUM is cast to BIGNUMERIC so it cannot overflow INT64.
- No column needs to be excluded: there are no wall-clock columns, and `fetched_at` is frozen in the landed FX meta file.

**Analogy.** Weighing a sealed box before and after shipping. If the weight is identical to the gram, nothing was added or removed.

**In this project.**
- S8.1: `scripts/prove_idempotency.py snapshot|compare`. Tables: `raw.payment_events`, `raw.settlement_lines` and `raw.fx_rates` (part = `_arrival_date`); `analytics.fct_recon_lines` and `analytics.fct_recon_daily` (part = `recon_date`). Each snapshot also records `as_of_date` from `analytics.stg_recon__as_of`.
- S8.2, the procedure, all inside one UTC day (00:00 UTC is 05:00 Astana):
  1. Code frozen: the generator and loader since G1, dbt since S7.6.
  2. Confirm that the 00:00 UTC scheduled run for the latest day has finished and nothing is running. The DAG stays unpaused.
  3. `make snapshot OUT=docs/evidence/2026-11-02/fp_before.json FROM=2026-10-03 TO=2026-11-01`.
  4. `make reprocess FROM=2026-10-26 TO=2026-11-01` (7 days).
  5. When all 7 are green: `make clear-day DAY=2026-10-14` (one older day, out of order).
  6. When it is green: `make snapshot OUT=docs/evidence/2026-11-02/fp_after.json FROM=2026-10-03 TO=2026-11-01`.
  7. `make compare BEFORE=... AFTER=...` writes `docs/evidence/2026-11-02/compare.json` and prints "[P] of [P] (table, partition) groups identical, [R] rows, as_of [A] in both". It exits non-zero on any changed group or a changed as_of.
- FROM starts one day before world_start because USD accounting dates can fall on world_start minus 1.
- A non-zero result is a finding for `docs/failure_log.md`, never something to hide.
- U3: S13.1 (full-window reprocess), S13.2 (negative control: reload one day with seed + 1, and the compare must report changes; reload with the right seed, and it must be identical again), S13.3 (cross-runtime check: `raw_dev` against `raw` for the 7 overlapping days).

**Common mistakes.**
- Fingerprinting load timestamps, so every reload looks different.
- XOR only.
- Taking the two snapshots on different as-of dates, for example when midnight UTC passes in between and the scheduled run adds a day.
- A proof that has never been seen to fail. That is what the negative control is for.

**Interview answer.** "I fingerprint every partition before and after reprocessing with a count, an XOR and a sum of row hashes, and the comparison fails on any change, including a changed as-of date."

### The mutation check

**What it is.** A mutation check breaks the code on purpose, in a small and realistic way, and records whether a test goes red. It proves that the tests can fail. Only after it has run may the README or a slide say that a test "fails when ...".

**Analogy.** A fire drill: you light a match under the smoke alarm to check that it really rings.

**In this project.** On a scratch branch, for each mutation: apply it, run `(cd dbt && uv run dbt run --target dev)`, then `(cd dbt && uv run dbt test --target dev)`, record every test that ends in FAIL or ERROR, and revert with `git checkout -- <file>`. After the last mutation, run `make dbt-build` on `main` to rebuild `analytics_dev` from the correct code. Why not `make dbt-build` for each mutation? `dbt build` does not materialize a model whose unit test fails. Mutations 1 and 4 also break UT2, so `dbt build` would leave the old tables in place: the identity tests would show as skipped, or pass on the old tables in a later `dbt test`. `dbt build` also skips everything downstream of a failed test, so mutation 3 would show only one of its two unique tests red. `dbt run` skips unit tests and builds the mutated model. The results go into `docs/testing.md` as a table: mutation, file, expected red, observed red, result.

| # | Mutation | Expected red tests | Step |
|---|---|---|---|
| 1 | FULL OUTER JOIN changed to INNER JOIN in `fct_recon_lines` | `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers` | S7.5 |
| 2 | `as_of_date < due_date` changed to `<=` | UT2 | S7.5 |
| 3 | QUALIFY removed from `stg_psp__payment_events` | unique `event_id`, unique `payment_id` | S7.5 |
| 4 | the statement-side `record_type = 'SALE'` filter moved after the join | `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers` | S7.5 |
| 5 | half-up fee rounding changed to floor | UT4 | S11.3 (U1) |

The "[K] of [K]" in number N2 comes from this table.

**Common mistakes.**
- Claiming that a test catches a bug without ever trying it.
- Running a mutation with `make dbt-build`. When a unit test fails, the old tables stay, so a caught bug looks like a miss.
- Leaving a mutation in the code.
- Changing the test instead of the code to make the table look good.

**Interview answer.** "I broke the matcher on purpose in realistic ways and recorded which tests went red, so my claims about the tests are evidence rather than hope."

### The seeded self-test, and why it is not accuracy

**What it is.** The generator writes an answer key that lists, for each payment, which defects were planted. A local script scores the marts against that key. I wrote both the defects and the matcher, so the score is a self-test on synthetic data. It catches regressions. It does not measure accuracy on real data.

**Analogy.** Marking your own homework with your own answer sheet: useful practice, not an exam.

**In this project.**
- Answer key: `landing/_truth/booking_date=YYYY-MM-DD.ndjson`, written by `emit` (S3.3). It is gitignored and never loaded into BigQuery. The loader's table list excludes it, no dbt source points at it, and only `scripts/eval.py` reads it, regenerating it in memory from (seed, world_start) if the files are absent. U2's CI asserts the isolation (S12.2).
- Scoring (U1, S11.4, `make eval`): as of the marts' `as_of_date`, over lines that are not `before_scope` and are final (the statement has arrived, or `as_of_date >= due_date`). For each cause (`missing_in_statement`, `missing_in_ledger`, `amount_mismatch`, `fee_mismatch`): planted (the generator's intent, not the matcher's rule), flagged, and raw counts of true positives, false positives and false negatives. Benign fee spikes that get flagged are false alarms. D5 overcharges within tolerance are misses. Any `date_mismatch` row is a false alarm, because none is planted. D1 is scored as planted extra copies against `SUM(copies_received - 1)`.
- Built to be less circular: the defect catalog was committed in M0, before any matcher SQL; benign noise crosses the tolerance on purpose, so false alarms and misses are possible by construction; U4 (S14.1 to S14.4) scores a held-out world, generated only after tag `v1.3`, with a new seed, doubled defect rates and defects the matcher was not designed for (H1 `duplicate_statement_line`, H2 `undeclared_deduction`, H3 `late_settlement_t3`, H4 `redelivery_payload_changed`), and publishes the misses.
- Name: "seeded self-test (synthetic, not accuracy)". It is never the headline, and it appears only after U1.

**Common mistakes.**
- Presenting a near-perfect self-score as detection quality.
- Letting any model read the answer key.
- Changing the defect catalog after seeing the matcher's results.

**Interview answer.** "My planted-defect score is a seeded self-test on synthetic data, useful for catching regressions but not evidence of accuracy, and the held-out world is where I publish what it misses."

---

## Explain checks with model answers

I answer each question aloud, with no notes, before I close the milestone. An AI examiner asks one question at a time and compares my answer with the model answer below. A model answer is a minimum, not a script. The plan defines explain checks for M0 to M10 only.

### M0. Design-first repo

**Why is the defect catalog committed before any matcher SQL?**
The commit history then proves that the expected outcome of every planted defect and benign behaviour was fixed before the matcher existed. I cannot quietly reshape the catalog to fit what the matcher happens to catch. It is the first defence against "you graded your own homework".

### M1. G0 sandbox probes

**Why can't dbt's default incremental run here?**
On BigQuery the default incremental strategy is `merge`, which runs a MERGE statement. MERGE is DML, and the sandbox refuses all DML.

**What did the DML refusal say?**
I quote the exact text saved from probe P2 in ADR-0001. The research expected it to contain "DML queries are not allowed in the free tier", but only the text from my own probe counts.

**What happens to a row dated 70 days ago?**
Its partition is older than the 60-day partition expiry, so BigQuery expires it right after the write while the job still reports success. The loss is silent. That is why `check_window` refuses run dates older than today minus 45 days. (This case is documented by Google, not probed.)

### M2. Walking skeleton

**Why does dbt have its own venv?**
dbt-bigquery 1.12.1 needs google-cloud-storage below 3.2 and dbt-core 1.12.6 needs pathspec below 1.1, while the Airflow 3.3.2 constraints pin google-cloud-storage 3.14.1 and pathspec 1.1.1. Installing dbt into Airflow's environment would break one side, so dbt lives in `/opt/airflow/dbt_venv` and is called by its full path.

**How does the key reach the container?**
`keys/sa.json` stays on the host, gitignored, with `chmod 600`. Compose bind-mounts `./keys` read-only at `/opt/airflow/keys`. The connection's `key_path` and dbt's `DBT_KEYFILE` both point at `/opt/airflow/keys/sa.json`. The key is never in the image, never in `.env` and never in git.

**Why does `smoke_bigquery` not touch `raw`?**
It is a health check. A stub row in `raw` would put fake data into the proof dataset and break the completeness and fingerprint checks. It writes only to `probe`, and with `schedule=None` it creates no scheduled runs.

### M3. Generator

**Why is the generator a pure function of (seed, day_index, MID)?**
So any day can be regenerated byte for byte, at any time and in any order: reruns, newest-first backfills, reprocessing and a moved world start all give the same rows. Keying on `day_index` instead of the calendar date means a moved `RECON_WORLD_START` reproduces the same synthetic data on new dates.

**Why only random()?**
Python guarantees that `random()` returns the same sequence for the same seed across versions. Methods such as `randint`, `choices` and `uniform` may change their algorithms between versions. Building `draw_int` and `draw_weighted` on `random()` keeps every stream stable.

**Which defect can cross midnight, and what does that do to arrival files?**
D1, the webhook redelivery. A copy comes 60 seconds to 6 hours after the first delivery, so it often lands in the next UTC day's file. (A capture at 23:59:50 can also have its first delivery after midnight.) One payment's deliveries can therefore sit in two arrival files, which is why dedup runs across all loaded partitions, not inside one day.

### M4. Loader and FX

**Why one load job per table per day?**
A WRITE_TRUNCATE job replaces the whole partition with what it loads. Two WRITE_TRUNCATE jobs into one partition, one per file, would overwrite each other, and WRITE_APPEND would duplicate the day on every rerun. So the loader concatenates every file of that table and day and runs exactly one job.

**What exactly does WRITE_TRUNCATE on `t$20261025` replace?**
Only partition 2026-10-25 of table `t`. Every other partition stays untouched. Every loaded row must belong to that day: the loader asserts it first, and BigQuery refuses a mismatch.

**What happens on an empty day?**
The loader deletes the partition with `client.delete_table("<project>.<dataset>.<table>$YYYYMMDD", not_found_ok=True)`, a table operation and not DML. Rerunning an empty day therefore leaves the partition empty instead of keeping stale rows from an earlier run.

### M5. dbt core

**Why a tie-break in QUALIFY?**
Two deliveries can share a `delivered_ts`. Without `delivery_id` as the second ORDER BY key, `ROW_NUMBER` could pick a different copy on each build, the output would not be deterministic, and the fingerprint proof could fail.

**Why must the FULL OUTER JOIN keep an equality?**
BigQuery refuses a FULL OUTER JOIN without an equality condition between the two sides. And the design matches on one exact key, `payment_id`. Any fuzzy matching would be a separate pass over the leftovers that still keeps an equality.

**Why can the identity test fail?**
Its two sides come from different models. The top-down gap comes from the input models, and the components come from the matcher's output. If the matcher loses, duplicates or misdates a line, uses a wrong sign or forgets a component, the sides differ and `unexplained_minor` is not 0.

**Why is there no `CURRENT_DATE()` in any model?**
Statuses must depend only on the data. With the wall clock, rebuilding the same data on a later day would turn `in_transit` into `missing_in_statement`, the rerun proof would fail, and no result could be reproduced. The as-of date comes from the latest loaded arrival date instead.

### M6. DAG end to end, gate G1

**Which interval does run 2026-10-25 process?**
[2026-10-25 00:00, 2026-10-26 00:00) UTC: everything that arrived during UTC day 2026-10-25. The run starts just after 2026-10-26 00:00 UTC.

**Why CronDataIntervalTimetable?**
It gives every run one complete day as its interval, with the logical date at the interval start. In Airflow 3 a cron string such as `"@daily"` becomes a CronTriggerTimetable whose interval is empty, so the run would not know which day it owns.

**What does a CLI trigger process?**
`airflow dags trigger recon_daily -l L` infers its interval from the trigger time, not from L, so it processes yesterday relative to now while recording logical date L. It is never used for exact days; a one-day backfill is.

**Why newest first?**
The scheduled run for the latest day already exists. Loading history oldest first would leave a gap between the loaded old days and the latest day, and `assert_arrival_days_complete` would correctly fail those runs. Newest first, every run sees a contiguous history from its own date to the latest loaded day.

### M7. dbt complete and mutation check

**What does each mutation prove?**
Mutation 1 (INNER JOIN): the identity and preservation tests catch dropped one-sided lines. Mutation 2 (`<` changed to `<=`): UT2 pins the inclusive due-date boundary. Mutation 3 (QUALIFY removed): the uniqueness tests catch redelivered duplicates. Mutation 4 (SALE filter after the join): the identity and preservation tests catch a filter that silently drops ledger-only rows. Mutation 5 comes in U1: UT4 pins half-up fee rounding.

**Why is the exception share a warning and the identity an error?**
The exception share describes the business: exceptions are what the analysts work on, so a high share is news, not a broken pipeline. A non-zero unexplained means the pipeline itself lost, duplicated or misdated money, so nothing it produced can be trusted and the run must fail.

### M8. Rerun proof

**What do the fingerprints compare?**
For each (table, partition) group in the window: the row count, the BIT_XOR and the BIGNUMERIC SUM of `FARM_FINGERPRINT(TO_JSON_STRING(row))`, before and after the reprocess and the out-of-order clear, plus the as-of date. Identical groups mean identical rows, with very high probability.

**What would a `_loaded_at` column do to the proof?**
It changes on every reload, so every reloaded partition would look different and the proof would fail for a trivial reason. This design has no wall-clock columns, and `fetched_at` is frozen in the landed meta file.

**Why must as_of match in both snapshots?**
The mart statuses depend on `as_of_date`. If a new arrival day were loaded between the snapshots, for example because midnight UTC passed and the scheduled run added a day, mart rows would change for a legitimate reason. The same as-of proves that both snapshots describe the same state of knowledge.

### M9. Results and the real-data number

**Which numbers are synthetic and which are real?**
Everything about payments is synthetic. N1 (the rerun proof) and N2 (MID-days with zero unexplained, plus the mutation count) measure my pipeline's behaviour on synthetic data; they are not facts about any business. The FX rates are real NBK rates, so N3 compares two real sources: the carried-forward provider series and NBK's own published rates.

**Why is the carry-forward a convention?**
The provider series has no row for some days, so I fill those days with the last earlier rate. That is my reporting rule, not NBK's official rate for that day. NBK's own feed publishes weekend rates, and N3 measures the difference.

### M10. Publish, gate G2

**What does this project not prove?**
Production experience; real PSP behaviour or file formats; detection quality on real data; scale (about 200 payments a day by design); any fact about any real company. On its own it adds no skill claim to my CV.

**What did AI write?**
The planning documents were drafted with an AI assistant before the build and reviewed by me. Boilerplate was scaffolded: the Dockerfile, compose edits, Makefile, `.gitignore`, YAML column lists, argparse and IO wrappers, `g0_probe.py`, the schema JSON and later the CI YAML. I wrote the generator's world and defect logic, the loader and FX logic, every SQL model and test, the DAGs, the fingerprint SQL and every README sentence. I verified it with tests, probes, the mutation check and an explain-any-file drill.

---

## Sources

Official documentation used for this guide. Check the page for the pinned version when a detail matters.

**BigQuery and Google Cloud**
- Sandbox: https://docs.cloud.google.com/bigquery/docs/sandbox
- Storage overview (columnar storage): https://docs.cloud.google.com/bigquery/docs/storage_overview
- Cost best practices (LIMIT, maximum bytes billed): https://docs.cloud.google.com/bigquery/docs/best-practices-costs
- Pricing (10 MB minimum, free operations): https://cloud.google.com/bigquery/pricing
- Partitioned tables (decorators, small partitions): https://docs.cloud.google.com/bigquery/docs/partitioned-tables
- Querying partitioned tables (pruning): https://docs.cloud.google.com/bigquery/docs/querying-partitioned-tables
- Managing partitioned tables (expiry): https://docs.cloud.google.com/bigquery/docs/managing-partitioned-tables
- Loading partitioned tables: https://docs.cloud.google.com/bigquery/docs/load-data-partitioned-tables
- Batch loading data: https://docs.cloud.google.com/bigquery/docs/batch-loading-data
- Clustered tables: https://docs.cloud.google.com/bigquery/docs/clustered-tables
- DML statements (includes TRUNCATE TABLE): https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax
- DDL statements: https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/data-definition-language
- Mathematical functions (DIV, ROUND, POW, CEIL): https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/mathematical_functions
- Aggregate functions (BIT_XOR): https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/aggregate_functions
- Hash functions (FARM_FINGERPRINT): https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/hash_functions
- Roles and permissions: https://docs.cloud.google.com/bigquery/docs/access-control
- Application Default Credentials (search order, the S1.2 fallback): https://docs.cloud.google.com/docs/authentication/application-default-credentials
- Free Trial and Free Tier (Plan B): https://docs.cloud.google.com/free/docs/free-cloud-features
- Google Cloud Terms: https://cloud.google.com/terms

**dbt (dbt-core 1.12, dbt-bigquery 1.12)**
- Incremental models and `is_incremental()`: https://docs.getdbt.com/docs/build/incremental-models
- BigQuery configs (`insert_overwrite`, `copy_partitions`): https://docs.getdbt.com/reference/resource-configs/bigquery-configs
- Unit tests: https://docs.getdbt.com/docs/build/unit-tests
- `dbt build` (order, skipping, `--empty`): https://docs.getdbt.com/reference/commands/build
- `dbt parse`: https://docs.getdbt.com/reference/commands/parse
- Constraints and contracts: https://docs.getdbt.com/reference/resource-properties/constraints
- Artifacts: https://docs.getdbt.com/reference/artifacts/dbt-artifacts
- Node selection: https://docs.getdbt.com/reference/node-selection/syntax
- Resource type flags (`--exclude-resource-type`): https://docs.getdbt.com/reference/global-configs/resource-type
- Upgrading to 1.12 (`.env` loading): https://docs.getdbt.com/docs/dbt-versions/core-upgrade/upgrading-to-v1.12
- `query-comment` and job labels: https://docs.getdbt.com/reference/project-configs/query-comment
- Docs command: https://docs.getdbt.com/reference/commands/cmd-docs
- Staging models guide: https://docs.getdbt.com/best-practices/how-we-structure/2-staging
- Open issue on NULL partition values with `copy_partitions`: https://github.com/dbt-labs/dbt-adapters/issues/2086

**Airflow 3.3.2**
- Architecture overview: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html
- DAGs for 3.3.2 (trigger rules, the `TriggerRule` import): https://airflow.apache.org/docs/apache-airflow/3.3.2/core-concepts/dags.html
- Timetables: https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/timetable.html
- Backfill: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html
- CLI reference for 3.3.2: https://airflow.apache.org/docs/apache-airflow/3.3.2/cli-and-env-variables-ref.html
- Upgrading to Airflow 3: https://airflow.apache.org/docs/apache-airflow/stable/installation/upgrading_to_airflow3.html
- Release notes (logical_date None for asset and API runs): https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html
- XComs: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html
- Variables: https://airflow.apache.org/docs/apache-airflow/stable/howto/variable.html
- Connections: https://airflow.apache.org/docs/apache-airflow/stable/howto/connection.html
- Pools: https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/pools.html
- Dynamic task mapping: https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html
- Best practices: https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html
- DAG bundles (versioning): https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-bundles.html
- Docker image: https://airflow.apache.org/docs/docker-stack/index.html
- Constraints for 3.3.2 on Python 3.13: https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.13.txt

**Payments (public documentation, used as public schemas and definitions only)**
- Adyen settlement details report: https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report/
- Stripe payout reconciliation report: https://docs.stripe.com/reports/payout-reconciliation
- Stripe webhooks (duplicate events, ordering): https://docs.stripe.com/webhooks
- Stripe idempotent requests: https://docs.stripe.com/api/idempotent_requests
- Stripe currencies (presentment, settlement, minor units): https://docs.stripe.com/currencies

**FX and Python**
- Frankfurter: https://frankfurter.dev/
- NBK RSS feed: `https://nationalbank.kz/rss/get_rates.cfm?fdate=DD.MM.YYYY`
- Python `random` (notes on reproducibility): https://docs.python.org/3.13/library/random.html

---

## Glossary

| Term | Meaning in this project |
|---|---|
| accounting date | the PSP's day for a sale: the capture time shifted by the MID's fixed UTC offset (`accounting_date`) |
| acquirer | the bank that processes card payments for a merchant and pays the merchant |
| ADC | Application Default Credentials: how Google's client libraries find credentials, in order: the file named by `GOOGLE_APPLICATION_CREDENTIALS` (on the host, the key), then the gcloud login file `~/.config/gcloud/application_default_credentials.json`; the S1.2 fallback ("G0 fallbacks" in `docs/build_plan.md`) replaces the key with my own gcloud login, with dbt `method: oauth` and the file mounted read-only |
| ADR | architecture decision record: one file per decision in `docs/adr/` (Status, Date, Context, Options, Decision, Consequences); drafts start Proposed and become Accepted after I rewrite them in my own words (ADR-0001 to 0003 in S10.2, ADR-0004 to 0007 in S11.5) |
| answer key | the generator's per-payment list of planted defects in `landing/_truth/`; never loaded into BigQuery |
| API server | the Airflow 3 component that serves the UI, the REST API and the Execution API |
| arrival date | the UTC day a webhook or statement file reached us; the raw partition key `_arrival_date` |
| `as_of_date` | the latest loaded arrival date; what the marts know; stored on every mart row |
| Asset | an Airflow named piece of data that can trigger DAG runs; not used here |
| authorization | the issuer's approval and hold of an amount on a card; no money moves yet |
| backfill | creating DAG runs for a past date range (`airflow backfill create`) |
| basis point (bps) | 0.01%; 100 bps = 1% |
| `before_scope` | the status of a one-sided line older than the oldest loaded day |
| BIGNUMERIC | BigQuery's high-precision decimal type; used for the fingerprint SUM so it cannot overflow |
| BIT_XOR | an aggregate that XORs integers; combines row hashes in any order |
| booking date | our revenue day: `DATE(event_ts)` in UTC |
| break amount, break share | the sum of absolute exception amounts; that sum divided by booked gross over 7 days, shown with the count |
| bytes billed | the bytes a query is charged for, with a 10 MB minimum per table and per query |
| capture | the merchant's request to collect an authorized amount; only captures settle |
| carry-forward | filling a gap day with the last earlier value; for FX here, a labelled project convention |
| catchup | whether an unpaused DAG creates runs for every missed interval; off here |
| chargeback | a forced reversal that the cardholder starts through the issuer |
| clear | resetting task instances of existing runs so they run again (`airflow tasks clear`) |
| clustering | sorting data inside a table or partition by up to four columns |
| columnar storage | storing each column separately, so queries read only the columns they name |
| connection | Airflow's stored settings for an external system; here `google_cloud_default`, from an environment variable |
| contract | a dbt model's declared columns and types, enforced at build time |
| copy job | a free BigQuery job that copies a table or one partition |
| `copy_partitions` | the dbt-bigquery option that replaces partitions with copy jobs instead of MERGE |
| CronDataIntervalTimetable | a timetable whose runs each cover the interval between two cron points |
| CronTriggerTimetable | a timetable that runs at cron times with no data interval; the Airflow 3 default for cron strings |
| cross rate | an exchange rate derived through a third currency |
| CTAS | `CREATE TABLE ... AS SELECT`; DDL |
| cut-off | the time an acquirer closes its business day |
| cut order | the fixed list of floor items to drop first when time runs short (`docs/build_plan.md`) |
| DAG | a directed acyclic graph of tasks: one Airflow workflow |
| DAG run | one execution of a DAG for one interval |
| dag-processor | the Airflow 3 component that parses DAG files |
| data interval | the half-open window `[start, end)` that a run is responsible for |
| data test | a dbt query that returns bad rows; zero rows means pass |
| date spine | a table with one row per day, used to fill gaps |
| `date_mismatch` | an exception: a matched line whose accounting date the MID's cut-off does not explain |
| `date_shift` | the flag on matched lines: `none`, `timing_cutoff` or `date_mismatch` |
| `dbt build` | one command that runs seeds, models, snapshots and tests in graph order |
| `dbt deps` | installs the packages listed in `packages.yml` |
| `dbt_serial` | the one-slot Airflow pool that serializes dbt builds |
| DDL | statements that create, change or drop objects |
| decorator | `table$YYYYMMDD`, the name of one day partition |
| dedup | keeping exactly one row per key |
| defect catalog | the pre-registered list of planted defects D1 to D5 and benign behaviours B1 to B3 with expected outcomes, under the heading "Defect catalog" in `docs/specs/data_and_generator.md` |
| `delivery_id` | the id of one webhook delivery attempt: `dlv_<event_id>_<attempt>` |
| DIV | BigQuery integer division; returns INT64 and truncates |
| DML | statements that change rows: INSERT, UPDATE, DELETE, MERGE and TRUNCATE TABLE; refused by the sandbox |
| `due_date` | expected accounting date + `max_settlement_lag_days` + `statement_grace_days`; from this day on, a ledger-only line is missing |
| `event_id` | the webhook event id, `evt_<payment_id>_cap`; the dedup key |
| exception | a difference that needs an analyst |
| executor | the scheduler setting that decides where tasks run; LocalExecutor here |
| expiry | in the sandbox, tables, views and partitions expire after 60 days; partitions count from their date |
| explained | a benign, evidenced difference: `timing_cutoff`, `in_transit` or `before_scope` |
| FARM_FINGERPRINT | a BigQuery function that hashes a value to INT64 |
| fee tolerance | the per-MID allowed fee variance: bps with a minimum; equal counts as within |
| fingerprint proof | comparing per-partition COUNT, BIT_XOR and SUM of row hashes before and after a rerun |
| FLOAT64 | binary floating point; never used for money |
| FULL OUTER JOIN | a join that keeps unmatched rows from both sides |
| G0, G-skel, G1, G2, Freeze | the build's gates: write path chosen, skeleton green in Docker, one run green end to end, repo public, code freeze (`docs/build_plan.md`) |
| generic test | a reusable dbt test attached in YAML |
| grain | what one row of a table means |
| gross, fee, net | the amount charged; the amount the PSP keeps; the amount the merchant receives |
| held-out world | the U4 synthetic world with a new seed and unseen defects, generated after the matcher is tagged |
| idempotency | running once or many times gives the same result |
| idempotency key | a unique id sent with a request so that retries perform the action only once |
| `in_transit` | explained: a ledger line still waiting for its statement, before its due date |
| incremental model | a dbt model that processes only new or changed data after its first build |
| `insert_overwrite` | a dbt incremental strategy that replaces whole partitions |
| INT64 | BigQuery's whole-number type; used for all money, in minor units |
| `is_incremental()` | a dbt macro that is true only when the table exists, no full refresh is requested and the model is incremental |
| issuer | the cardholder's bank |
| Jinja | the template language dbt renders before running SQL |
| landing | the local `landing/` folder where generated files and FX responses are written before loading |
| late data | data that arrives after the period it belongs to |
| ledger | our own revenue record, booked from capture webhooks |
| load job | a free BigQuery job that loads a file into a table or partition |
| LocalExecutor | an executor that runs tasks as processes started by the scheduler on its own machine |
| logical date | the date that names a DAG run; here, the start of its data interval |
| macro | a reusable Jinja function in `macros/` |
| `manifest.json` | the dbt artifact that describes the whole project |
| materialization | how dbt saves a model: view, table, incremental or ephemeral |
| `maximum_bytes_billed` | a cap that makes a too-large query fail without a charge |
| MERGE | a DML statement that inserts, updates or deletes by key; refused by the sandbox |
| MID | merchant ID: a merchant account |
| minor units | a currency's smallest unit: cents for USD, tiyn for KZT |
| `missing_in_ledger` | an exception: settled by the PSP but never booked |
| `missing_in_statement` | an exception: a ledger line with no statement line by its due date |
| mutation check | breaking code on purpose to prove that a test goes red |
| N1, N2, N3 | the three measured numbers: the rerun proof, the zero-unexplained identity, the real NBK weekend gap |
| NDJSON | newline-delimited JSON: one JSON object per line |
| negative control | a deliberate change (U3) that the fingerprint compare must report, to show the proof can fail |
| NUMERIC | BigQuery's exact decimal type (38 digits, 9 after the point) |
| operator | an Airflow template for a kind of task, such as BashOperator |
| partition | a segment of a table by one column's value; one day here |
| partition pruning | skipping the partitions that a filter excludes |
| payout | a transfer of net settled money to the merchant's bank |
| pool | an Airflow limit on concurrent tasks; `dbt_serial` has 1 slot |
| presentment currency | the currency the customer is charged in |
| `primary_reason` | the single label per line, chosen by precedence |
| probe | a G0 test (S1.1 to S1.3, P1 to P8, F1), and the throwaway `probe` dataset |
| profile, target | dbt's connection settings; one environment inside them (`dev`, `airflow`) |
| PSP | payment service provider |
| QUALIFY | a BigQuery clause that filters on a window function's result |
| reason code | the label for a difference, defined in `reason_codes.csv` |
| `recon_date` | a line's reconciliation day: its booking date, or the capture date for statement-only lines |
| reconciliation | comparing two independent records of the same money and explaining every difference |
| redelivery | a second or later delivery of the same webhook event |
| `ref()` | the dbt function that points one model at another and builds the graph |
| refund | money returned to the customer at the merchant's initiative |
| reprocess | rerunning finished days: a backfill with `--reprocess-behavior completed` |
| retries | how many times Airflow reruns a failed task |
| `run_results.json` | the dbt artifact that records the results of the last command |
| sandbox | a BigQuery project without billing: no DML, 60-day expiry, lifetime 10 GiB of storage |
| scheduler | the Airflow component that creates runs and queues tasks |
| `scope_start` | the oldest loaded arrival date |
| seed | a small CSV loaded by `dbt seed` |
| seeded self-test | scoring the marts against the generator's answer key; never called accuracy |
| selector | a dbt node selection: `--select`, `--exclude` or a YAML selector |
| service account | an identity for a program, with roles and a key file |
| `settle_rank` | planned for v1.4 (S14.4, U4), not in v1.0: a rank over the statement lines of one payment, so one line is matched and each repeat gets the new status `duplicate_in_statement`; the fix for held-out defect H1 `duplicate_statement_line` |
| settlement | clearing captured payments and crediting the merchant |
| settlement currency | the currency the merchant receives |
| settlement lag | the days between the accounting date and the statement line's arrival: 1 or 2 here |
| singular test | a one-off SQL test file in `tests/` |
| slip rule | for each hour the start time slips, one item is cut from the cut order |
| source | a raw table declared to dbt |
| statement | the PSP's per-MID file of settled lines with gross, fee and net |
| streaming insert | row-by-row inserts such as `insert_all`; not available in the sandbox |
| T+1 | settlement one day after the transaction's date |
| task, task instance | one unit of work; that unit inside one DAG run |
| tautology | a check that cannot fail |
| timetable | the Airflow object that decides when runs happen and what each one covers |
| `timing_cutoff` | explained: a matched line booked on another accounting day because of the MID's cut-off |
| tolerance | the difference allowed before a mismatch; inclusive here |
| trigger rule, `NONE_FAILED` | when a task may start, judged by the states of its upstream tasks; the default `all_success` needs all of them to succeed; `TriggerRule.NONE_FAILED` (imported from `airflow.sdk`) needs only that none failed or is upstream_failed, so skipped ones are fine; S13.4 (U3) gives it to `record_run` after `dbt_build` |
| unexplained | what is left of a MID-day's gap after the dated components; must be 0 |
| unit test | a dbt test of model logic on fixture rows |
| var | a named dbt value read with `var()` |
| Variable | Airflow's stored key-value setting; not used here |
| venv | a Python virtual environment |
| view | a saved query that stores no data |
| webhook | an HTTP request a PSP sends when an event happens |
| WRITE_APPEND, WRITE_TRUNCATE | load dispositions that add to, or replace, the target |
| XCom | Airflow's way of passing small values between tasks |

---

## Learn before each milestone

Read the listed cards before starting the milestone. Each name in quotes is a card's exact heading, so a search finds it; a note in parentheses after the quotes says what to focus on. For M0 to M10, finish by answering that milestone's explain checks above.

| Milestone | Read these cards first | Skim this official page |
|---|---|---|
| M0 Design-first repo | "Ledger vs statement: reconciliation"; "Grain"; "Three dates and as_of_date"; "The seeded self-test, and why it is not accuracy"; "PSP (payment service provider)"; "Merchant account (MID)" | Adyen settlement details report; Stripe payout reconciliation report |
| M1 G0 sandbox probes | "The BigQuery sandbox and its limits"; "DDL and DML, and why this project has no DML"; "Partition decorators"; "Load jobs and write dispositions"; "Expiry and the rolling date window"; "Service accounts, roles and keys"; "Profiles and targets"; "Bytes processed, bytes billed and maximum_bytes_billed" | BigQuery sandbox; Loading partitioned tables |
| M2 Walking skeleton | "Docker images, containers and virtual environments"; "Scheduler, dag-processor, API server, triggerer and executor"; "DAG"; "Task and operator"; "Connections"; "Pools"; "Pause and unpause" | Airflow architecture overview; Airflow connections |
| M3 Generator | "Deterministic replay: the seeded generator"; "Keys"; "Webhooks and redelivery"; "Cut-off times, time zones and the accounting date"; "T+1 and settlement lag"; "Gross, fee, net and basis points"; "Minor units and integer fee arithmetic"; "Late data" | Python `random` notes on reproducibility |
| M4 Loader and FX | "Load jobs and write dispositions"; "Partition decorators"; "Data contracts"; "Idempotency"; "FX rates, direction, cross rates and the carry-forward"; "Data types for money: INT64, NUMERIC and FLOAT64" | BigQuery batch loading; Frankfurter |
| M5 dbt core | "The dbt project and dbt_project.yml"; "Profiles and targets"; "Sources"; "ref() and the model graph"; "Materializations"; "Seeds"; "Vars"; "Jinja and macros"; "Packages"; "Data tests: generic, singular and severity"; "Unit tests"; "Unit tests versus data tests"; "Deduplication with QUALIFY"; "FULL OUTER JOIN matching"; "As-of joins, date spines and carry-forward"; "Line statuses, due dates and scope"; "The two-calendar bridge and the identity (and why it is not a tautology)"; "dbt build" | dbt unit tests; `dbt build` |
| M6 DAG end to end, gate G1 | "Timetables: CronTriggerTimetable vs CronDataIntervalTimetable"; "Data interval"; "Logical date"; "DAG run"; "Catchup"; "Backfill, reprocess and clear (the three verbs)"; "Retries"; "XCom"; "Dynamic task mapping"; "The guard task check_window"; "Assets, and why recon_daily does not use them" | Airflow timetables; Airflow backfill |
| M7 dbt complete and mutation check | "Contracts"; "Data quality checks: integrity gates and business gates"; "The mutation check"; "Artifacts: manifest.json and run_results.json"; "Clear and rerun"; "Metric definitions" | dbt constraints |
| M8 Rerun proof | "Idempotency"; "The fingerprint proof"; "Three dates and as_of_date"; "Backfill, reprocess and clear (the three verbs)"; "Pause and unpause" | BigQuery hash functions; BigQuery aggregate functions |
| M9 Results and the real-data number | "FX rates, direction, cross rates and the carry-forward"; "Bytes processed, bytes billed and maximum_bytes_billed"; "The seeded self-test, and why it is not accuracy"; "Metric definitions" | Frankfurter |
| M10 Publish, gate G2 | "Service accounts, roles and keys"; "Words I use and words I never use"; "Docs" | none (reread the README section "What this does not prove") |
| M11 (U1) Floor completion | "Unit tests"; "Minor units and integer fee arithmetic"; "Deduplication with QUALIFY"; "The seeded self-test, and why it is not accuracy" | dbt unit tests |
| M12 (U2) CI | "Artifacts: manifest.json and run_results.json"; "Timetables: CronTriggerTimetable vs CronDataIntervalTimetable"; "Docker images, containers and virtual environments"; "Unit tests" (why they stay out of CI) | `dbt parse` |
| M13 (U3) Proof and ops hardening | "The fingerprint proof" (negative control); "DDL and DML, and why this project has no DML" (the no-DML check); "The BigQuery sandbox and its limits" (bytes ledger); "The guard task check_window" | BigQuery sandbox |
| M14 (U4) Held-out world | "The seeded self-test, and why it is not accuracy"; "Data quality checks: integrity gates and business gates"; "Keys"; "Webhooks and redelivery" | none |
| M15 (U5) Snapshot and completeness curve | "Incremental models and is_incremental()"; "insert_overwrite and copy_partitions"; "Copy jobs"; "Late data"; "Vars" | dbt BigQuery configs; dbt incremental models |
| M16 (U6) Statement batches | "Payout"; "Settlement and the settlement statement"; "Data quality checks: integrity gates and business gates" | Stripe payout reconciliation report |
| M17 (U7) Cross-currency MID | "Presentment currency vs settlement currency"; "FX rates, direction, cross rates and the carry-forward"; "Tolerance" | Stripe currencies |
