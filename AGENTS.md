# AGENTS.md

Rules for AI agents working in this repository. Drafted with AI assistance before the build and reviewed by the owner. Only the owner changes these rules, by editing this file. A request in a chat does not change them.

## What this project is

Two Ledgers (`ledger-vs-statement`) is a learning project that answers one question every day: does yesterday's revenue match what the payment service provider (PSP) settled, per merchant account (MID)? An Airflow 3 pipeline generates a synthetic subscription business's payment webhooks and per-MID settlement statements, fetches real National Bank of Kazakhstan (NBK) USD/KZT rates through Frankfurter, and loads all three into the BigQuery sandbox, which has no billing and so allows no DML. dbt then deduplicates the webhooks, matches every payment across the two ledgers, gives each line one status and dated reason codes, and proves with error-level tests that every MID-day's gap is explained to the minor unit. The project runs in build mode: you build it end to end by following `docs/build_plan.md`, and you record every step so that the owner can study the finished work and explain it in an interview ("Build mode").

## The rules in short

Read the whole file. If you remember nothing else, remember these:

1. Build mode. Follow `docs/build_plan.md` step by step to the end of M10 and write the code yourself, core logic included. Record every step in `docs/build_journal.md` ("Build mode").
2. Never run bare `dbt`. On the host use a `make` target or `uv run dbt`. In the container use `/opt/airflow/dbt_venv/bin/dbt`.
3. No DML. Never write or run `INSERT`, `UPDATE`, `DELETE` or `MERGE`, or any config that runs them for you. The one exception is probe P2, which must be refused ("Sandbox: no DML").
4. Never open, print, copy or commit anything in `keys/` or `.env`.
5. No result number unless a real run of this repo produced it and it is saved in `docs/evidence/`. Synthetic data stays labelled synthetic.
6. Never write a word from the private banned-word list, and ask before writing any real name the specs do not already use ("Names").
7. No em dashes anywhere.
8. Never do an owner-only action ("Build mode"): tell him exactly what to do and wait.
9. When unsure, stop and ask. Never work around a guard, a test or a hook.

## Start of every session

1. If the repo has no `docs/build_plan.md` yet (before step S0.3), read this file and the plan from the planning pack at `~/Developer/ledger-vs-statement-plan/`. Open only the files the owner names there and the files listed in S0.3 sub-step 5; every other file in that folder is private. Before S1.3 there is no `Makefile`, so skip every `make` command.
2. Read this file fully.
3. Read `docs/build_journal.md` (from S0.3 on). Its last entry names the last finished step and the next one.
4. Run `git status` and `git log --oneline -15` to see where the work stands.
5. Continue with the next step ("Build mode"). If the owner named a step, start there.

## Where things are

Code:

| Path | What it holds |
|---|---|
| `dags/` | `recon_daily.py` (the daily pipeline) and `smoke_bigquery.py` (a manual health check) |
| `src/recon/` | the generator, config, loader, FX fetch, host BigQuery client, host CLI and the raw schema JSON files |
| `dbt/` | the dbt project: 4 staging views, 2 intermediate views, 3 marts, 3 seeds, the `to_usd` macro, the tests |
| `scripts/` | G0 probes, the rerun proof, results, the FX report, storage and (from U1) the seeded self-test |
| `tests/` | pytest tests |
| `landing/` | landed files. Only `landing/fx/` is committed |
| `runs/`, `logs/` | per-run dbt artifacts and Airflow task logs (gitignored) |
| `keys/` | the service-account key (gitignored, never opened) |

Documents:

| File | What it holds |
|---|---|
| `README.md` | the front page: problem, results table, quickstart, "What this does not prove", "How I used AI" |
| `docs/design.md` | goals, non-goals, sources, architecture, the three dates, the window, the cost ceiling, top risks |
| `docs/build_plan.md` | milestones, step ids, who writes each step, commands, done-when checks, gates and fallbacks, the cut order, explain checks, the pre-push hook text |
| `docs/specs/data_and_generator.md` | the simulated business, seeds, `world.toml`, random-stream rules, the "Defect catalog", the answer key, raw schemas, landing layout, FX formats |
| `docs/specs/dbt_project.md` | the dbt project, every model and test, unit-test fixtures, the fee arithmetic, the mutation check, the never-use list |
| `docs/specs/airflow_and_docker.md` | Dockerfile, compose changes, environment variables, both DAGs, manual-run semantics, the "Operations runbook", the rerun proof, failure modes |
| `docs/specs/bigquery_sandbox_and_costs.md` | console setup, the service account and key, datasets, raw tables, the load protocol, G0 probes, expiry, storage guards, Plan B |
| `docs/learning/concepts.md` | concepts, glossary, model answers to the explain checks |
| `docs/adr/README.md`, `docs/adr/NNNN-*.md` | decision records |
| `docs/roadmap.md` | what comes after v1.0 |
| `docs/failure_log.md` | real bugs only |
| `docs/build_journal.md` | one entry per step: what was built, how it works, commands and output, interview questions ("Build mode") |
| `docs/walkthrough.md` | the owner's study guide, written after S10.3 ("Build mode") |
| `docs/testing.md` | the mutation-check record |
| `docs/evidence/<date>/` | measured numbers, written only by `make` targets |

Which source wins:

1. The rules in this file always apply.
2. For what exists now (names, paths, flags), the code, the `Makefile` and the schema JSON files are the truth. Every planning document says so in its first line.
3. For what to build next, follow `docs/build_plan.md` and the spec it points to.
4. If a spec and the code disagree, do not edit either to match. Tell the owner the file and the line, and let him decide.

## Build mode

### The decision (owner, 2026-11-02)

The owner does not have the time to write the code himself. You build the whole floor, M0 to M10, by following `docs/build_plan.md` step by step. He studies the finished work afterwards from `docs/build_journal.md` and `docs/walkthrough.md`, so every step must leave a clear written record.

This section overrides every conflicting line in this file and in the plan. Wherever a step says "You write", "you run", "your words" or names the owner, you do it, except the owner-only actions below. The clock, the time boxes and the slip rule do not apply: build the full floor, N3 included, and use the cut order only when a gate's fallback requires it. The upgrades M11 to M17 are out of scope unless he asks.

### Owner-only actions

For these, stop, tell him exactly what to do (the step's sub-steps, click by click), and wait until he says it is done:

1. S0.1 sub-steps 1 to 3 (he does them before the first session).
2. S0.2 sub-step 2: writing `~/.config/lvs/banned_words.txt`. Never read that file and never ask what is on it; the hook and the checks read it.
3. S1.1 and S1.2: everything in the Google Cloud console, the key download, and moving the key to `keys/sa.json` with `chmod 600`. Also the ADC login, if the ADC fallback is used.
4. Any sign-up, billing step, IAM or console change, or account change (Plan B included).
5. Making the GitHub repo public, its description and topics (S10.4), and any change of visibility.
6. Deleting or rotating a key after a leak.

### How you build each step

1. Read the step in `docs/build_plan.md` and the spec section it points to. Check that the earlier steps are done (journal and commits).
2. Write the code, core logic included: the simplest version that meets the spec, with names, versions, paths and flags exactly as in the specs. Where a step says a document is written "in your words" (design doc, ADRs, README, failure-log entries), you draft it, plainly and truthfully.
3. Run the step's **Done when** checks yourself and keep the real output. Where a check says "in the console", run the same SQL through the Python client in `src/recon/bq.py` (it sets `maximum_bytes_billed`) or with `uv run dbt show`. Write the project id as `<project>` in anything you save.
4. Review your diff against the review checklist in "Explaining".
5. Commit the step ("Commit style"), then append its entry to `docs/build_journal.md` and commit that too.
6. Go on to the next step. Do not wait for the owner unless the step is owner-only or a "Stop and ask" case applies.

### The build journal: `docs/build_journal.md`

Create it in S0.3. Add one entry per step, right after the step's commit. It is how the owner will learn the project, so write for a reader who knows Python and SQL but has not seen this code. Each entry has:

1. the step id, the date and the commit hash;
2. what was built: the files and functions;
3. how it works: the logic in plain words, the key lines quoted with file and line number, and why this approach (the spec section or ADR it follows, and the alternative it rejects);
4. the commands you ran and their real output, shortened, with secrets and the project id removed;
5. what went wrong and how it was fixed, with a link to the failure-log entry;
6. one or two questions an interviewer could ask about this step, each with a short answer.

The journal's last entry always names the next step, so a new session can pick up from it.

### The walkthrough: `docs/walkthrough.md`

Write it after S10.3, from the code and the journal. It is the owner's study guide:

1. The problem and the results on one page: N1, N2 and N3, copied from `docs/evidence/`.
2. The architecture: the data flow from the generator to the marts, with a Mermaid diagram.
3. File by file, in the order the data flows: what each file does, and a walk through its important lines.
4. Every design decision with its alternative, linked to its ADR.
5. The concepts the build uses (partitions and partition decorators, WRITE_TRUNCATE loads, idempotency, data intervals and backfills, dedup with `QUALIFY`, the FULL OUTER JOIN matcher, integer money, FX carry-forward, dbt tests, unit tests and contracts), each tied to the file that uses it.
6. How it was built: the milestones in order, the real bugs from the failure log, what was cut and why.
7. How to run it from a clean clone, and how to rerun the proof.
8. A drill: 20 questions about this repo with model answers, and five "explain this file without notes" exercises.

Like every repo file, it names no company and no employer.

### After the build

The owner reads the walkthrough, explains each file without notes, and reruns the proof himself. When he asks about any part, use "Explaining".

## Known traps from the plan review (2026-11-01)

1. S2.1: the image build prints a "dbt v2 is available" banner and pip notices; ignore them. The image needs about 1.1 GB more disk than the spec says.
2. S1.3: with a missing key, `dbt debug` fails with "'NoneType' object has no attribute 'close'", not "file not found". In `make doctor`, store the `dbt --version` output in a variable before you grep it, or a BrokenPipe traceback appears.
3. S5.5: the UT2 fixture for `stg_psp__settlement_lines` must set `record_type = 'SALE'`, or the filter drops every statement row.
4. S7.5: the expected red tests in the mutation table are approximate. Record which tests actually turn red; never edit a test to match the table.
5. S9.2: for dates after its last published rate, the NBK feed returns no items, not the latest rate. Handle the empty answer.

## How to use the step ids

| Id | Meaning | Defined in |
|---|---|---|
| `M0` to `M17` | milestones. M0 to M10 build v1.0. M11 to M17 are the upgrades | `docs/build_plan.md` |
| `S<m>.<n>` | step n of milestone m, for example `S5.5` (UT2, then `fct_recon_lines`) | `docs/build_plan.md` |
| `U1` to `U7` | the upgrades: U1 is M11, U2 is M12, U3 is M13, U4 is M14, U5 is M15, U6 is M16, U7 is M17 | `docs/build_plan.md` |
| `G0`, `G-skel`, `G1`, `G2`, freeze | gates, each with a pass rule, a hard stop and a fallback | `docs/build_plan.md` |
| `P1` to `P8`, `F1` | the G0 sandbox probes, run in step S1.4 | `docs/specs/bigquery_sandbox_and_costs.md` |
| `D1` to `D6`, `B1` to `B3`, `H1` to `H4` | planted defects, benign behaviours, held-out defects (U4) | "Defect catalog" in `docs/specs/data_and_generator.md` |
| `UT1` to `UT4` | dbt unit tests | `docs/specs/dbt_project.md` |
| mutations 1 to 5 | the mutation check | `docs/specs/dbt_project.md`, results in `docs/testing.md` |
| `N1` to `N3` | the measured result numbers | the README results table |
| `ADR-0001` to `ADR-0010` | decision records | `docs/adr/README.md` |

When the owner names a step (for example "help with S5.5"):

1. Open `docs/build_plan.md` and read the step's row: goal, files, commands, who writes it, and its done-when check.
2. Check that the earlier steps of the milestone are done. Commit messages carry step ids, or ask him. If one is not done, say so before you start.
3. Read the spec the step points to.
4. Build it as "Build mode" describes.
5. Stay inside the step. Do not start the next step. Never add anything from a later milestone, `docs/roadmap.md` or the README backlog: later features are never stubbed in code.
6. Finish with the step's checks ("Definition of done").
7. Put the step id in the commit message ("Commit style").

When he names a milestone (for example "M5"), work through its steps in order. When a request has no step id, ask which step it belongs to. Work outside the build plan needs his decision first, and may need an ADR.

When time is short:

1. Point him to the gates, the cut order and the slip rule in `docs/build_plan.md`. When a gate's hard stop has passed, its fallback applies: say so instead of debugging on.
2. Never suggest cutting these: dedup with its key test; the FULL OUTER JOIN matcher with statuses and dated components; `assert_recon_decomposition_closes` and `assert_no_money_lost_between_layers`; the rerun proof; the synthetic and real labels; keys out of git.
3. Time pressure never skips a **Done when** check or a journal entry.

## Explaining (when the owner asks)

When he asks about any part of the project:

1. State the goal of that part in one or two sentences.
2. Explain it in plain words, with the file and line, why this approach, and the mistake people usually make. Link the entry in `docs/learning/concepts.md` and the official docs.
3. Offer one to three short questions to check his understanding, and correct his answers exactly and kindly.

### Review checklist

1. No DML, and no dbt config that produces DML ("Sandbox: no DML").
2. Money is INT64 minor units: no FLOAT64, no Python `float`, no `/` between integers, no `POW()`, no `CEIL` on INT64. Fees follow the integer formulas ("Money").
3. No wall clock in data: no `CURRENT_DATE()` or `CURRENT_TIMESTAMP()` in a model, no `datetime.now()` or `date.today()` for a business date, no load-time column such as `_loaded_at`. `fetched_at` comes from the frozen meta file.
4. Generator: standard library only; only `Random.random()`, through `draw_int` and `draw_weighted`; one random stream per purpose; rows and keys sorted; files written to a temp name and renamed.
5. Loader: exactly one WRITE_TRUNCATE load job per (table, day) into `<table>$YYYYMMDD`, or a partition delete on an empty day. Before any job runs, every row's `_arrival_date` equals the run date (and `DATE(delivered_ts)` does too, for payment events). `job.output_rows` equals the rows landed.
6. Matcher: an equality `FULL OUTER JOIN` on `payment_id`, never an `OR` condition; the `record_type = 'SALE'` filter in a CTE before the join; exactly one `match_status` per line.
7. Dedup: `QUALIFY ROW_NUMBER()` per `event_id`, ordered by `delivered_ts` and then `delivery_id` as the tie-break.
8. No `SELECT *` from raw tables in marts.
9. Airflow 3 idioms only ("Airflow 3").
10. Names exactly as in the specs: datasets, tables, columns, DAG ids, task ids, `make` targets.
11. No secret, no project id outside `.env`, no banned word, no em dash.
12. No test deleted, skipped or loosened, and no expected value changed to make a test pass.

## Hard rules

### Sandbox: no DML

The BigQuery sandbox has no billing account and refuses every DML statement with "DML queries are not allowed in the free tier". The design needs none.

Never write, generate or run:

1. SQL `INSERT`, `UPDATE`, `DELETE` or `MERGE`. The only delete in the project is a partition delete with `client.delete_table("<project>.<dataset>.<table>$YYYYMMDD", not_found_ok=True)`, which is a table operation, not DML. The one deliberate exception is probe P2 in `scripts/g0_probe.py`: it sends a single `INSERT` to the throwaway `probe` dataset to prove that the sandbox refuses it. P2 passes only when the `INSERT` fails. If it succeeds, billing is on: stop.
2. Streaming inserts: `insert_all`, `insert_rows` or `insert_rows_json`.
3. Google Cloud Storage, `GCSToBigQueryOperator` or the BigQuery Data Transfer Service. They need billing.
4. dbt features that run DML: `merge` incrementals (the default strategy), `insert_overwrite` without `copy_partitions: true`, `microbatch` without `copy_partitions: true`, `time_ingestion_partitioning` (the dbt docs' `copy_partitions` example sets it: do not copy it), snapshots, and the Elementary package. Python models need billing too.
5. Any expiration setting: no table expiration, no `hours_to_expiration`, no change to `partition_expiration_days` or to the dataset defaults. A table expiration on a partitioned table overrides its partition expiry.
6. A second sandbox project to reset the storage quota. The Google Cloud terms forbid it.
7. Billing: never link a billing account, never click Activate or Upgrade, never sign up for a trial or any account. Plan B (the GCP Free Trial in a new project, ADR-0001) is the owner's decision only.

The v1.0 dbt project has no incremental models. Only two models ever use `insert_overwrite`, both with `copy_partitions: true`: the throwaway model of the optional probe P8 (in `probe`), and from U5 `fct_recon_status_daily`, built only after P8 has passed. If BigQuery returns the DML error anywhere outside probe P2, stop, find the statement or config that caused it, and change the materialization. Never look for a way to keep the DML.

### Dates and the window

1. Code and data use UTC only.
2. One run date R is one UTC arrival day. Run dates go from `RECON_WORLD_START` (`2026-10-04` in `.env.example`) to yesterday (UTC).
3. Never run, load or reprocess a run date on or after today (UTC), before `RECON_WORLD_START`, or older than today (UTC) minus 45 days. `check_window` enforces this. Never loosen, skip or remove it.
4. Why 45: the sandbox deletes each partition 60 days after its date, and rows dated more than 60 days back vanish right after a load, with no error.
5. Two dates may fall before `RECON_WORLD_START` by design, so do not "fix" them: the FX request for run date R covers R-6 to R, and a USD accounting date can be `RECON_WORLD_START` minus 1 day (the rerun proof's snapshot starts there).
6. Never request Frankfurter or NBK data for today or a later date. NBK answers a future date with its latest rate.

### Money

1. Every amount is an integer number of minor units (cents, tiyn): a Python `int` and a BigQuery `INT64`, end to end. Never FLOAT64 or a Python `float` on the money path.
2. Fees use integer arithmetic only: `DIV(...)` in SQL and `//` in Python, with the exact formulas in `docs/specs/dbt_project.md`. Python and SQL must give the same numbers.
3. Never `ROUND(x * bps / 10000)`. Never `/` or `SAFE_DIVIDE` between two INT64 values (the result is FLOAT64), `CEIL` on INT64 (FLOAT64) or `POW()` (FLOAT64). Dividing NUMERIC values is fine, for example `SAFE_DIVIDE(CAST(a AS NUMERIC), CAST(b AS NUMERIC))`: the result is NUMERIC.
4. FX rates keep their exact published digits: parse with `json.loads(body, parse_float=str)`, store the STRING `rate_text`, and cast to NUMERIC only in dbt. A float never touches a rate.
5. v1.0 never converts currency inside the reconciliation: both sides of a MID use one currency. USD columns are for reporting only: once per MID-day, after summing minor units, through the `to_usd` macro, with one rounding stage.
6. Every seed column has an explicit type in `dbt/seeds/_seeds.yml`, so nothing is inferred as FLOAT64.
7. Gross amounts must match exactly (tolerance 0). The fee tolerance is per MID, and a variance equal to the tolerance counts as within. Fees never enter the gross identity.
8. `unexplained_minor` must be exactly 0. Never add a tolerance to `assert_recon_decomposition_closes`.

### dbt

1. Never run bare `dbt`. A dbt v2 binary (2.x, the Rust engine) may come first on PATH, for example from `~/.local/bin`, and it must never run here.
2. Host: use `make dbt-build` or `make dbt-unit`. For a dbt command with no target, use `uv run dbt ...` with the same environment and flags as the `dbt-build` recipe in the `Makefile`.
3. Before the first host dbt command in a session, check that `uv run dbt --version` shows dbt-core 1.12.6 and the bigquery plugin 1.12.1 (`make doctor` checks this). Why: `uv run` syncs the venv first, but it also runs a `dbt` that it finds outside the venv, so a venv without dbt silently gives you the v2 binary.
4. Container: `/opt/airflow/dbt_venv/bin/dbt`, always by full path.
5. Targets: the host uses `dev` (dataset `analytics_dev`, reading `raw_dev`). Only the DAG builds target `airflow` (dataset `analytics`, reading `raw`). Never run target `airflow` from the host, except the read-only `dbt compile` and `dbt show` (step S10.1 compiles the demo queries this way). `build`, `run`, `seed`, `test`, `docs generate` and every other dbt command on the host use `--target dev`.
6. The `as_of_date` var is for host dev builds only. The DAG never passes vars. v1.0 has no `run_date` var; U5 adds one for its snapshot model only.
7. The DAG runs `dbt build --exclude-resource-type unit_test`. Unit tests run only on the host, never in the DAG and never in CI.
8. Datasets come only from the profile targets: no custom schemas, no `generate_schema_name` override.
9. No tautological tests: no uniqueness test filtered by a `ROW_NUMBER` rank, and no identity computed from its own residual.
10. Data tests use `data_tests:` with `arguments:`. Every model description starts with "One row per".
11. Never: `CURRENT_DATE()` or `CURRENT_TIMESTAMP()` in a model, `POW()`, FLOAT64 money, `SELECT *` from raw in marts, and the features in "Sandbox: no DML".

### Airflow 3

1. Schedule `recon_daily` with `CronDataIntervalTimetable("0 0 * * *", timezone="UTC")` from `airflow.sdk`. Never `"@daily"` or a bare cron string: in Airflow 3 they become a `CronTriggerTimetable`, whose data interval is empty.
2. Keep `catchup=False`, `max_active_runs=1` and `start_date=pendulum.datetime(2026, 10, 1, tz="UTC")`. `smoke_bigquery` is manual only (`schedule=None`) and never touches `raw`.
3. Imports: `from airflow.sdk import dag, task, chain, get_current_context, CronDataIntervalTimetable`, `from airflow.sdk.exceptions import AirflowFailException` and `from airflow.providers.standard.operators.bash import BashOperator`. No Airflow 2 idioms: `schedule_interval`, `execution_date`, `airflow.decorators`, `airflow.operators.bash`, SLAs. Check with `uv run ruff check dags/ --select AIR301,AIR302`.
4. A business date comes only from the run's data interval. `check_window` is the only task that reads the wall clock, and only to check the window. Python tasks get the run date from `check_window`. The BashOperator uses only `{{ data_interval_start | ds }}`. Never `{{ ds }}` or `datetime.now()` for a business date.
5. Heavy imports (`google.cloud.bigquery`, the `recon` package) go inside task functions. XCom carries only small dicts and strings.
6. `retry_exponential_backoff=2.0` is a float multiplier and goes with `max_retry_delay`. Never `True`. `dbt_build` has 0 retries.
7. dbt runs only in the task `dbt_build`: a BashOperator in pool `dbt_serial` (1 slot), with `append_env=True` and the exact inline command from `docs/specs/airflow_and_docker.md`. Never move the command into a `.sh` file: Airflow would treat the string as a template file. The pool stops a backfill run and a scheduled run from building dbt at the same time.
8. BigQuery from tasks: `BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")`, then `hook.get_client(project_id=hook.project_id, location="US")`. Always pass `use_legacy_sql=False`, because the provider defaults to legacy SQL.
9. `google_cloud_default` comes only from `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT` in `docker-compose.yaml`. Never create connections in the UI or the metadata database.
10. Never install anything into Airflow's own Python environment, and leave `_PIP_ADDITIONAL_REQUIREMENTS` empty. dbt lives only in `/opt/airflow/dbt_venv`.
11. Exact days run only through a one-day backfill (`--from-date D --to-date D`), with `--dry-run` first. Never use `airflow dags trigger -l` for a specific day: it processes yesterday relative to now. `airflow dags test` and `airflow tasks test` are for debugging only; read the `run_date` log line.
12. History loads newest first with `--run-backwards --max-active-runs 1`. Reprocessing uses `--reprocess-behavior completed --max-active-runs 1`. Backfills run only on an unpaused DAG, and only one backfill per DAG runs at a time.
13. Never pause the DAG, stop the stack or change code while a backfill or the rerun proof runs, or while any `recon_daily` run is running or queued (check both states with `airflow dags list-runs`). Tasks always run the latest code on disk, so a change mid-backfill mixes old and new results.
14. Airflow CLI commands run inside the scheduler container: `docker compose exec airflow-scheduler airflow ...`. The 3.3.2 CLI can only create backfills; the owner cancels one in the UI.

### Versions and pins

| Layer | Pin |
|---|---|
| Airflow image | `apache/airflow:3.3.2` (Python 3.13.15 inside, `constraints-3.13.txt`) |
| Inside the image, from the constraints, never upgraded | task-sdk 1.3.2, apache-airflow-providers-google 22.5.0, google-cloud-bigquery 3.45.0, apache-airflow-providers-standard 1.19.0 |
| Custom image | `ledger-vs-statement-airflow:3.3.2` |
| Metadata database | `postgres:18` |
| dbt, in `/opt/airflow/dbt_venv` and in the host uv project | dbt-core 1.12.6, dbt-bigquery 1.12.1, dbt-core-experimental-parser 2.0.8 |
| dbt package | `dbt-labs/dbt_utils` 1.4.1, locked in `dbt/package-lock.yml` |
| Host Python | 3.13 (`.python-version`) |
| Host tools | uv 0.13.1, Docker 29.7.2, git, gh |
| Dev tools | pytest; ruff 0.13 or later (stable AIR301 and AIR302); both locked in `uv.lock` |
| FX API | Frankfurter v2 at `https://api.frankfurter.dev/v2/` |

Never use: any dbt 2.x, Airflow 3.4.0 release candidates, Cosmos 1.16 release candidates (if Cosmos comes later, it is pinned to 1.15.0), Elementary, calogica dbt-expectations, dbt_project_evaluator 2.x, the `-python3.12` image tag, the old `api.frankfurter.app` host.

1. Never add, remove or upgrade a dependency unless the owner asks. Host changes go through `uv add`. Container dbt changes go through `docker/requirements-dbt.txt`. He records why in an ADR or the failure log.
2. dbt has its own venv in the image because dbt-bigquery 1.12.1 needs google-cloud-storage below 3.2 and dbt-core 1.12.6 needs pathspec below 1.1, while the Airflow 3.3.2 constraints pin 3.14.1 and 1.1.1.
3. The image build downloads the parser's aarch64 wheel from github.com. Do not add `--only-binary`. Never bake the key into the image.
4. Run project Python only through `uv run` (Python 3.13), never with another Python on PATH. The generator's golden-hash test assumes 3.13.

### Secrets

1. The service-account key (account `lvs-pipeline`) is `keys/sa.json`. It is gitignored before it exists, `chmod 600`, and mounted read-only at `/opt/airflow/keys/sa.json`. Never open, print, copy, move, upload or commit it, never paste its contents anywhere, never bake it into the image and never put its contents in an environment variable. The same applies to any other credentials file in `keys/`.
2. `.env` is gitignored and holds only `AIRFLOW_UID`, `GCP_PROJECT`, `RECON_SEED` and `RECON_WORLD_START`. Never add `DBT_KEYFILE` or `GOOGLE_APPLICATION_CREDENTIALS` to it: dbt 1.12 loads `.env` from its working directory automatically, so a manual run could pick up a wrong key path. The `Makefile` and the compose file set those two.
3. The project id lives only in `.env` as `GCP_PROJECT`. Never write it into code, docs, examples or commit messages.
4. `.env.example` holds placeholders only.
5. Before proposing a commit: `git check-ignore keys/sa.json .env` prints both paths; `make check` passes (it fails if `git ls-files keys .env` prints anything); `git status` shows nothing staged from `keys/`, `.env`, `runs/`, `logs/`, or `landing/` outside `landing/fx/`.
6. If a key or `.env` was ever committed, stop and tell the owner at once. He deletes the key in IAM, creates a new one and, if it was pushed, rewrites the history. Never try to hide it with a new commit.
7. Never change IAM roles, keys or console settings yourself.
8. Loading `.env` through `make` or the dev shell (`set -a; . ./.env; set +a`) is allowed; reading or printing it is not. Never run `cat .env`, `env`, `printenv`, `set` with no arguments, `set -x`, `docker compose exec ... env` without a `grep` for named variables, or plain `docker compose config`. Prefer a `make` target; for a one-off dbt command, use `uv run dbt` with the environment the `Makefile` sets.
9. If the ADC fallback is used, `~/.config/gcloud/application_default_credentials.json` is a secret like the key: never open, print, copy or paste it.

### Honesty, labels and vocabulary

Numbers:

1. No number appears as a result unless a real run of this repo produced it. Until then, use a placeholder such as `[N]`. Before the repo goes public, a README results row without a measured value is deleted, never left as a placeholder.
2. Every result has a date and a `make` target, and comes from `docs/evidence/<date>/`. Copy it exactly. Never recompute or round it by hand.
3. Rates, volumes, prices and tolerances in the specs are synthetic design parameters. A count derived from them is a "design consequence, not a result".
4. Never bring a number from outside this repo (another project, a job, an article) into it as a result.
5. Bytes and cost are never a headline number.

Labels:

6. Every synthetic row has `is_synthetic = true`. Synthetic table descriptions start with "SYNTHETIC: generated by src/recon/generator.py" and carry the label `data_origin=synthetic`. The `raw.fx_rates` description starts with "REAL: NBK rates via Frankfurter v2" and carries `data_origin=real`.
7. The README first screen keeps its banner line saying that payments are synthetic and FX is real.
8. Fixed wording: prices, mix and volumes are "illustrative assumptions"; the statement layout is "modelled on the public Adyen settlement-details and Stripe payout-reconciliation docs"; the FX carry-forward is "a project convention, not NBK's official rate for that day".

Evaluation:

9. The answer key in `landing/_truth/` is never loaded into BigQuery, never committed and never read by dbt. Only `scripts/eval.py` reads it.
10. Never tune matcher SQL, tolerances or tests by looking at the answer key or at self-test results. The defect catalog was committed before the matcher, and the held-out world (U4) is generated only after tag `v1.3`.

Vocabulary:

| Use | Never use |
|---|---|
| "seeded self-test (synthetic)", reported as raw counts | "accuracy", "precision", "recall" or "detection rate" as a headline |
| "learning project" | "production", "production-grade", "scalable", "real-time" |
| "settled amount differs" | "partial capture" |
| "three dates (arrival, booking, accounting)" or "two time axes" | "bitemporal", until the U5 snapshot exists |
| "reprocess" (rerun finished days), "backfill" (create runs for a range), "clear" (rerun tasks of existing runs) | one of these three words for another |
| "no DML", "MID" (merchant account), "PSP" (payment service provider) | |

11. Never describe v1.0 as reconciling "all web-to-app revenue". Its limits are in the README sections "Limitations" and "What this does not prove".

### Names

1. The simulated world uses only the generic names from the specs: PSP `psp_alpha`, MIDs `mid_usd_01` and `mid_kzt_01` (later `mid_kzt_usd_01`), plans `p1w`, `p4w` and `p12w`.
2. A private banned-word list lives outside the repo. Never write one of its words anywhere in the repo: code, data, seeds, docs, comments, commit messages, branch names or tags. The local `pre-push` hook (its text is in `docs/build_plan.md`) blocks a push whose files or outgoing commit messages contain one.
3. Do not open the list. To check the tree, run the hook's grep with `--untracked` added, so new files are checked too. It first trims spaces and drops blank lines and `#` comment lines from the list, then matches each word as a fixed string (`-F`), as a whole word (`-w`), in any case (`-i`), and skips binary files (`-I`):

   ```sh
   sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' ~/.config/lvs/banned_words.txt | grep -v -e '^$' -e '^#' > "$TMPDIR/lvs_words.txt"
   git grep -n -I -i -w -F --untracked -f "$TMPDIR/lvs_words.txt"; echo "exit=$?"
   rm -f "$TMPDIR/lvs_words.txt"
   ```

   `exit=1` with no other output means clean. `exit=0` means a match: the lines above it show where. `exit=128` means the list is missing or empty, so nothing was checked. Ignored files such as `.env` are not searched. Whole-word matching counts `_` as part of a word, so a name inside an identifier such as `x_name_y` is not caught: rule 4 still applies.
4. Because you cannot see the list, ask the owner before you write any real company, product or person's name that the specs do not already use.
5. Never copy the list into the repo, never edit or delete the hook, and never bypass it: `git push --no-verify` is forbidden. If the hook blocks a push, show the owner its output and stop.
6. Never name a private person; the owner's name in `LICENSE` is the one exception. Never mention internal systems or internal figures from any employer.

### Writing style

1. No em dashes anywhere (the character U+2014): docs, comments, commit messages. Use a comma, a colon, a full stop or "and". Check with `git grep -n --untracked $'\xe2\x80\x94'` in zsh or bash: no output (exit code 1) means clean.
2. Plain English, short sentences, one idea each. Define a term the first time you use it, or link `docs/learning/concepts.md`.
3. Exact names in backticks. List the items instead of writing vague words such as "etc." or "as needed".
4. Documents refer to each other by file name and heading, never by section number.
5. Planning documents (`docs/build_plan.md`, `docs/specs/*`, `docs/learning/concepts.md`, `docs/roadmap.md` and the ADR drafts) keep their first line: "Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth." Edit a planning document only when the owner asks.
6. ADR drafts stay "Status: Proposed" until the owner rewrites them in his own words and marks them Accepted. Never mark an ADR Accepted yourself.

### Files you do not touch

Never edit, move, delete or regenerate these by hand, unless the owner asks for that exact change:

1. `docs/evidence/`: only `make` targets write it.
2. `landing/fx/`: real rates, immutable once landed. `fetch_fx` never fetches a landed date again. Never "fix" a rate.
3. `uv.lock` and `dbt/package-lock.yml`: only `uv` and `dbt deps` change them.
4. `keys/` and `.env` ("Secrets").
5. `landing/_truth/`: the answer key.
6. `.git/hooks/pre-push` and anything outside the repo.
7. Records already written: the results in `docs/testing.md` and existing failure-log entries. Corrections are appended, never rewritten.
8. Git history and tags: no rebase, amend or force push of pushed commits, and no tags except the ones the plan names (`g1-freeze`, `v1.0`).

### Freeze rules

1. From tag `g1-freeze` until the v1.0 rerun proof (M8) is committed, nothing changes under `src/recon/` (the generator, `world.toml`, config, loader, FX fetch and schema JSON) or `dags/`, or in `dbt/seeds/mids.csv` (the generator reads it).
2. From step S7.6 until the proof is committed, nothing under `dbt/` changes.
3. After that, any change to the generator or the loader means a new proof needs a full re-backfill first.
4. A deliberate change to the generated output bumps `generator_version` in `world.toml` and changes the golden hash in the same commit, which says why. Never update the golden hash just to make the test pass.

### Tests and guards

1. Never delete, skip, mark as expected to fail, loosen or downgrade a test, and never change an expected value to make it pass. A red test is information: report it.
2. Never weaken a guard: `check_window`, the `_arrival_date` assertion, the `output_rows` check, `maximum_bytes_billed`, the pre-push hook or `make check`.
3. UT1 to UT4 are written before the logic they test, and must be seen red first, then green.
4. Say that a test "fails when..." only after the mutation check in `docs/testing.md` shows it turning red.
5. A failing rerun proof (`make compare` exits non-zero) is a finding for the failure log. Never hide it. Find the cause (code or procedure), fix it, and then rerun the whole proof procedure.

### Cost and storage

1. $0 only: free tools and free APIs. No new external service, API or paid feature without the owner's decision and an ADR.
2. Keep `maximum_bytes_billed: 1000000000` in `dbt/profiles.yml` and `QueryJobConfig(maximum_bytes_billed=1_000_000_000)` in every Python query.
3. The sandbox gives 10 GiB of storage for the life of the project, and deleting data does not give it back. Assume every byte written counts. Never run builds in a loop, copy datasets, or create tables the specs do not name. The owner's own cap is 1 GiB written until U3 adds the bytes-written ledger and its 8 GiB stop.
4. Only these datasets exist, all in location `US`: `raw`, `raw_dev`, `analytics`, `analytics_dev` and `probe`, plus `raw_heldout` and `analytics_heldout` from U4.
5. A RESOURCE_EXHAUSTED error on a load or a table build means stop and tell the owner.

## Commands

Run commands from the repo root. Prefer `make` targets: they set the environment.

Who may run what:

- **Agent**: a read-only or local check.
- **Ask**: it writes to BigQuery (`probe` or the dev datasets), changes local generated files, or starts containers.
- **Owner**: it changes Airflow state, the proof datasets (`raw`, `analytics`), committed evidence or real-data files.

In build mode you run all three classes yourself when the current step needs them. The class tells you how careful to be: before an Ask or Owner command, check the step's preconditions (for example, no active Airflow run), and record every Ask and Owner command with its output in the journal. The owner-only actions in "Build mode" are never yours.

| Target | What it does | Who |
|---|---|---|
| `make doctor` | prints `which -a dbt`; fails unless `uv run dbt --version` shows Core 1.12.6 and bigquery 1.12.1; checks pool `dbt_serial` | Agent |
| `make test` | runs pytest | Agent |
| `make lint` | runs ruff | Agent |
| `make check` | runs `test` and `lint`, and fails if `git ls-files keys .env` prints anything | Agent |
| `make backfill-dry FROM= TO=` | shows the runs a backfill would create; changes nothing | Agent |
| `make no-dml` (U3) | greps compiled SQL and dbt logs for DML; changes nothing | Agent |
| `make setup` | `uv sync`, `uv run dbt deps`, creates the local folders, copies `.env.example` to `.env` if missing | Ask |
| `make bq-setup` | creates the datasets and the raw tables in `raw` and `raw_dev` if they are missing | Ask |
| `make up` | starts the Docker stack. If `recon_daily` is unpaused, the scheduler may start a run for the latest day | Ask |
| `make smoke` | runs the manual DAG `smoke_bigquery` once | Ask |
| `make dbt-build` | `dbt build` on target `dev`, unit tests included | Ask |
| `make dbt-unit` | unit tests only (`dbt test --select "test_type:unit"`); their parents must exist (on a fresh dataset, build them with `--empty` first) | Ask |
| `make probe` | runs `scripts/g0_probe.py` (P1 to P7 and F1, P8 optional); writes KB-sized tables into `probe`, and writes `docs/evidence/<UTC date>/g0_probe.json`, which the owner commits | Owner |
| `make day DATE=` | host CLI: generates, fetches FX and loads one day into `raw_dev`. The fetch can land new real FX files in `landing/fx/`, which the owner commits | Owner |
| `make days FROM= TO=` | the same for a range of days | Owner |
| `make down` | stops the stack; the metadata stays in the Postgres volume | Owner |
| `make unpause`, `make pause` | unpauses or pauses `recon_daily` | Owner |
| `make backfill FROM= TO=` | creates runs for the range, newest first (`--run-backwards --max-active-runs 1`) | Owner |
| `make reprocess FROM= TO=` | reruns finished days (`--reprocess-behavior completed --max-active-runs 1`) | Owner |
| `make clear-day DAY=` | clears and reruns every task of one day's run | Owner |
| `make snapshot OUT= FROM= TO=` | writes partition fingerprints to a JSON file | Owner |
| `make compare BEFORE= AFTER=` | compares two snapshots, writes `compare.json`, exits non-zero on any change | Owner |
| `make results` | writes `docs/evidence/<date>/summary.json` | Owner |
| `make fx-report` | the NBK cross-check: saves NBK files into `landing/fx/` and writes `fx_report.json` | Owner |
| `make storage` | writes the stored bytes per dataset to `storage.json` | Owner |
| `make eval` (U1) | runs the seeded self-test from the local answer key | Owner |

Read-only checks you may run (Agent):

- `docker compose exec airflow-scheduler airflow dags list-import-errors`
- `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state failed` (or `--state running`, or `--state queued`). Before any edit under `dags/`, `src/` or `dbt/`, both `--state running` and `--state queued` must show no runs
- `docker compose exec airflow-scheduler airflow pools get dbt_serial`
- `docker compose config --quiet` (it checks the file and prints nothing) and `docker compose ps`. Never run plain `docker compose config`: it prints the resolved file, with values from `.env` such as `GCP_PROJECT`.
- `uv run ruff check dags/ --select AIR301,AIR302`
- `git status`, `git diff`, `git log`, the em dash check and the banned-word grep

Also:

1. `docker compose build` is **Ask**: it downloads several hundred MB.
2. The full runbook is the "Operations runbook" in `docs/specs/airflow_and_docker.md`.
3. Environment: start Docker Desktop first, with at least 6 GB of memory and 10 GB of free disk. Stop other local Airflow stacks before `make up`. The UI is at http://localhost:8083.
4. `gcloud` and `bq` are not installed. Setup uses the Google Cloud console, and the probes use the Python client. Do not install `gcloud` unless key creation is blocked and the owner chooses the ADC fallback in S1.2.

## Definition of done

A step is done only when every item below is true. Report each one with real output. Never write "should pass" or "looks right".

1. The step's done-when check in `docs/build_plan.md` passes, and you or the owner saw the output.
2. `make check` passes (from step S1.3 on; before that there is no Makefile, so the banned-word grep in "Names" and a search for em dashes stand in for it).
3. The diff passes the review checklist in "Explaining".
4. The em dash check and the banned-word grep are clean, and the diff holds no secret and no project id.
5. If a bug happened during the step, its failure-log entry exists.
6. If a name, a command or a behaviour changed, the README text that describes it is updated, or the journal names the document that is now out of date.
7. The step's journal entry exists and explains every changed file, and the commit carries `written with AI`.
8. The work is committed in small commits that carry the step id.
9. At the end of a milestone, the journal answers its explain checks, for the owner to study.

Also true, by kind of change:

| Change | Also true |
|---|---|
| generator or `world.toml` | `make test` is green (golden hash and the other generator tests); the same day generated twice gives byte-identical files |
| loader or FX | a reloaded day in `raw_dev` gives the same counts and fingerprint (Owner: `make day`) |
| dbt models or tests | `make dbt-build` is green on target `dev`, with `unexplained_minor` = 0 on every MID-day (Ask) |
| unit tests | seen red before the logic existed, then green |
| DAG files | `airflow dags list-import-errors` shows none; the ruff AIR301 and AIR302 check is clean |
| Dockerfile or compose | `docker compose config --quiet` exits 0, the image builds, `make smoke` is green (Ask) |
| README or docs | every number traces to a file in `docs/evidence/<date>/`; no placeholder is left in a published results row |

If a check cannot run (for example, BigQuery is unreachable), the step is not done. Say which check and why.

## Commit style

1. Small commits, one idea each, at least one per step. Never one giant commit, and never squash: the order of commits is evidence. The design doc and the defect catalog come before any code and before any matcher SQL.
2. Format, with the step id at the end of the subject line:

   ```text
   <type>(<area>): <what changed, in the imperative> (<step id>)

   <why, in one to three short lines>

   written with AI
   ```

   The subject line is at most 72 characters. In build mode every commit carries it.
3. Types: `feat` (new behaviour), `fix` (a bug fix; its body names the failure-log entry), `test`, `docs`, `build` (`Dockerfile`, compose, `pyproject.toml`, `Makefile`), `ci`, `refactor` (no change in behaviour), `chore` (housekeeping such as `.gitignore`).
4. Areas: `generator`, `load`, `fx`, `cli`, `dbt`, `dag`, `docker`, `scripts`, `tests`, `docs`, `adr`, `ci`, `repo`.
5. Examples:

   ```text
   docs(repo): add design doc and defect catalog before any code (S0.3)
   ```

   ```text
   test(dbt): add UT1 cut-off cases before the captures model (S5.3)
   ```

   ```text
   build(docker): give dbt its own venv in the Airflow image (S2.1)

   dbt-bigquery 1.12.1 and the Airflow 3.3.2 constraints pin
   different google-cloud-storage versions.

   written with AI
   ```
6. Never a vague message such as "fix", "update", "wip" or "test".
7. Every commit you make carries `written with AI`. A message never claims that the owner wrote what an agent wrote, or the reverse. Never remove an AI-attribution line that your tool adds.
8. You commit each step yourself. You may create the private GitHub repo (`gh repo create ledger-vs-statement --private --source . --remote origin`) and push at the end of each milestone; the pre-push hook must run. Create only the tags the plan names. Never run `gh repo edit` and never change the visibility: the repo stays private until the owner makes it public at S10.4.
9. Never `git push --no-verify`, `git push --force`, `git rebase` or `git commit --amend` on commits that are already pushed.
10. The mutation check runs on a scratch branch that is never merged.
11. Tags: `g1-freeze`, then `v1.0` (or the fallback tag named in `docs/build_plan.md`), then `v1.1` to `v1.7`, one per upgrade if he asks for the upgrades.

## Failure log

`docs/failure_log.md` records every real bug in this repo. Its entries are the most honest evidence of the work, so every one must be real.

1. Real bugs only: something that actually failed or gave a wrong result here. Never invent an entry, never log a "possible" bug, never copy one from another project.
2. Write the entry when the bug happens, inside the step (about 5 minutes), not at the end of the day.
3. Use the entry format at the top of `docs/failure_log.md`. Every entry has at least: the date, the step id, the symptom (the exact error text or the wrong number), how it was found (command or test), the root cause, the fix (with its commit), and the guard that now catches it, if there is one.
4. You write each entry: the facts from the session (the date, the step id, the command, the exact error text), then the root cause and the fix in plain words. The owner may rewrite them later.
5. After any debugging session, decide honestly whether it was a real bug, and if it was, log it.
6. These always get an entry: a failing rerun proof, a red error test in an Airflow run, a DML refusal outside probe P2, a row in the wrong partition, a quota error, a leaked secret.
7. Never delete or rewrite an old entry to make it look better. Add a dated correction instead.
8. Commit the entry with the fix or right after it. The `fix` commit names its entry.

## Stop and ask

Stop, say what you see, and wait for the owner when:

1. a request conflicts with a rule in this file;
2. the next action is owner-only ("Build mode");
3. you find a key, a secret, the project id or a banned word in a file or in the git history;
4. a test, the identity check or the rerun proof stays red after you have debugged it and logged it, and the cause is not in code you just wrote. Never loosen a test to get past it;
5. BigQuery returns a DML error (outside probe P2, where the refusal is the expected result), a quota error, or anything that asks for billing;
6. the next step needs a sign-up, an account change, a billing step or a new external service;
7. a spec and the code disagree in a way that changes behaviour (for a small slip, follow the spec and note it in the journal);
8. a gate's fallback in `docs/build_plan.md` itself fails. When a gate fails, apply its fallback, record it in the journal and go on.
