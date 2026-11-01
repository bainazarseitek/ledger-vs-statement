Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# dbt project specification

This file specifies everything inside `dbt/`:
- the profile and the project file;
- packages, seeds and sources;
- all nine models, the macro and every test;
- the mutation check;
- how dbt runs on the host and inside Airflow;
- the documentation site.

It is written for two readers. The first is me, using dbt on BigQuery for the first time. The second is an AI agent that follows it literally. Rules use the words "must" and "never". Logic is given as plain steps and CTE outlines, not finished SQL: I write every model and test myself.

Other files cover the rest:
- `docs/specs/data_and_generator.md`: the raw tables, schema JSON files, generator and seeds' business meaning (heading "Defect catalog").
- `docs/specs/airflow_and_docker.md`: the Dockerfile, compose file, both DAGs and the commands to operate them (heading "Operations runbook").
- `docs/specs/bigquery_sandbox_and_costs.md`: sandbox setup, the G0 probes and the storage guards.
- `docs/build_plan.md`: the hour-by-hour steps (ids such as S5.3) and the Makefile.
- `docs/adr/`: the reasons. ADR-0002 (time model), ADR-0003 (reconciliation method), ADR-0006 (dbt runtime in Airflow) and ADR-0008 (materialization and incremental) matter most here.
- `docs/learning/concepts.md`: the concepts behind this file, with a glossary.

Words used in a fixed sense in this file:
- **Host**: my Mac, running dbt from the project's uv venv.
- **Container**: the Airflow scheduler container, running dbt from `/opt/airflow/dbt_venv`.
- **Proof datasets**: `raw` and `analytics`. Only Airflow writes them.
- **Dev datasets**: `raw_dev` and `analytics_dev`. Only the host writes them.
- **R**: one run date (one UTC arrival day).

---

## Rules for every dbt file

1. Never run bare `dbt`. `~/.local/bin/dbt` is dbt v2 (2.0.9) and must never touch this project. On the host, use `uv run dbt`. In the container, use `/opt/airflow/dbt_venv/bin/dbt`.
2. No DML. The sandbox refuses `INSERT`, `UPDATE`, `DELETE` and `MERGE`. dbt may only create views and tables (`CREATE OR REPLACE`), load seeds (load jobs) and run `SELECT` queries.
3. Money is INT64 minor units from raw to marts. Never FLOAT64, never `POW()`, never INT64 / INT64 (BigQuery returns FLOAT64), never `CEIL` on INT64. Fees use `DIV`. USD conversion happens once, in NUMERIC, through the `to_usd` macro.
4. No wall clock in any model. Never `CURRENT_DATE()` or `CURRENT_TIMESTAMP()`. "Today" for dbt is `as_of_date`, read from the loaded data (see "The as-of rule").
5. Every model, seed and source table description starts with "One row per". A source's own description (the `psp` or `fx` entry, above its `tables:` list) has no rows to count, so it says what its tables hold instead.
6. Data tests use `data_tests:`. Test inputs go under `arguments:`. Filters (`where`) and `severity` go under `config:`.
7. Every `FULL OUTER JOIN` has an equality condition, and every table in a join has an alias (dbt unit tests need aliases to test join logic).
8. Synthetic and real data stay labelled. Payment models carry the BigQuery label `data_origin: synthetic`; FX models carry `data_origin: real`.
9. No secret is ever written in `dbt/`. `profiles.yml` holds `env_var()` calls only.
10. Unit tests run only on the host. Never in the DAG, never in CI.

---

## Versions and where dbt runs

| Item | Host | Container |
|---|---|---|
| dbt-core | 1.12.6 | 1.12.6 |
| dbt-bigquery | 1.12.1 | 1.12.1 |
| dbt-core-experimental-parser | 2.0.8 | 2.0.8 |
| Python | 3.13 (uv project, `.python-version`) | 3.13.15 (inside `apache/airflow:3.3.2`) |
| Where installed | `.venv/` from `uv sync` | `/opt/airflow/dbt_venv` (built by the Dockerfile) |
| How to call dbt | `cd dbt && uv run dbt <command>` | `cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt <command>` |
| Target | `dev` | `airflow` |
| dbt package | dbt-labs/dbt_utils 1.4.1 | the same files, through the `./dbt` mount |

`uv run` finds the project by walking up from the current folder to the repo-root `pyproject.toml`. So `cd dbt && uv run dbt` uses the repo venv.

`make doctor` prints `which -a dbt` and fails unless the output of `uv run dbt --version` contains both of these lines (dbt may add " - Up to date!" after each):
```
  - installed: 1.12.6
  - bigquery: 1.12.1
```
`which -a dbt` will also list `~/.local/bin/dbt`. That is the dbt v2 binary. Its presence is fine. Calling it is not.

### The `.env` file and dbt

dbt 1.12 loads a `.env` file by itself. In dbt-core 1.12.6, `cli/main.py` calls `load_dotenv(find_dotenv(usecwd=True), override=False)`. `find_dotenv` starts in the working folder and walks up the parent folders until it finds a `.env`. What this means here:
1. A host run from `dbt/` loads the repo-root `.env`. So `GCP_PROJECT` arrives without exporting it.
2. Shell variables win over `.env` values (`override=False`). The Makefile's values always win.
3. `DBT_KEYFILE` must never be in `.env`. The key path differs between host and container. A `.env` value would follow every manual run.
4. In the container, the working folder is `/opt/airflow/dbt`. No `.env` exists in it or in its parents, because the compose file never mounts the repo root. So nothing is loaded there.

---

## Project layout

```
dbt/
  dbt_project.yml            project settings (committed)
  profiles.yml               two targets, env_var() calls only (committed)
  packages.yml               package pins (committed)
  package-lock.yml           exact package version and hash, written by `dbt deps` (committed)
  seeds/
    _seeds.yml               seed descriptions and column types
    mids.csv                 merchant accounts and contract terms (SYNTHETIC)
    currencies.csv           minor units per currency (ISO 4217)
    reason_codes.csv         reason codes, categories, precedence, analyst actions
  macros/
    to_usd.sql               the only macro in v1.0
  models/
    _unit_tests.yml          every unit test, in one file
    staging/
      _sources.yml           the three raw tables as dbt sources
      _staging.yml           descriptions and tests of the 4 staging models
      stg_recon__as_of.sql
      stg_psp__payment_events.sql
      stg_psp__settlement_lines.sql
      stg_fx__rates.sql
    intermediate/
      _intermediate.yml
      int_ledger__captures.sql
      int_fx__usd_rates_daily.sql
    marts/
      _marts.yml             includes the fct_recon_daily contract
      fct_recon_lines.sql
      fct_recon_exceptions.sql
      fct_recon_daily.sql
  tests/                     singular tests
    assert_recon_decomposition_closes.sql
    assert_no_money_lost_between_layers.sql
    assert_redeliveries_identical.sql
    assert_arrival_days_complete.sql
    warn_exception_share_7d.sql
    warn_fx_restated.sql
  analyses/                  saved demo queries; dbt compiles them but never builds them
    one_mid_day_bridge.sql
    exceptions_queue.sql
```

Generated folders, gitignored, never committed: `dbt/target/`, `dbt/dbt_packages/`, `dbt/logs/`. Airflow runs write `runs/dbt/<run_date>/target/` and `runs/dbt/<run_date>/logs/` (also gitignored) and never write into `dbt/target/`.

Naming:
- `stg_<source>__<entity>`: one staging model per source table, plus the shared helper `stg_recon__as_of`.
- `int_<area>__<what>`: reusable logic between staging and marts.
- `fct_recon_<what>`: the marts.
- YAML property files start with an underscore so they sort first in each folder.

### Order of work (build plan step ids)

| Step | What gets written in `dbt/` |
|---|---|
| S1.3 | `profiles.yml`, a minimal `dbt_project.yml` (name, profile, version guard). `uv run dbt debug --target dev` must end with "All checks passed!" |
| S5.1 | The full `dbt_project.yml`, `packages.yml`, `dbt deps` (writes `package-lock.yml`), the 3 seeds with `_seeds.yml`, `_sources.yml` |
| S5.2 | The 4 staging models and their generic tests |
| S5.3 | UT1 first (seen red), then `int_ledger__captures` |
| S5.4 | `int_fx__usd_rates_daily` with its tests, and the `to_usd` macro |
| S5.5 | UT2 first (seen red), then `fct_recon_lines` |
| S5.6 | `fct_recon_daily` without the two exception columns, plus `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers`, `assert_redeliveries_identical` |
| S7.2 | `fct_recon_exceptions` with its tests. Then add `exception_count` and `exception_abs_minor` to `fct_recon_daily` |
| S7.3 | The enforced contract on `fct_recon_daily` (all 29 columns) |
| S7.4 | `assert_arrival_days_complete`, `warn_exception_share_7d`, `warn_fx_restated` |
| S7.5 | Mutations 1 to 4, recorded in `docs/testing.md` |
| S11.1 to S11.3 (U1) | UT3, UT4 (each seen red first), mutation 5 |
| S15.2 (U5) | `fct_recon_status_daily`, the only incremental model (see "Incremental models") |

The overnight backfill (S6.3) runs the dbt code as it is at gate G1. That is fine: every `dbt build` rebuilds every mart from all loaded raw partitions, so the Monday builds replace whatever the overnight builds wrote.

---

## Profile (`dbt/profiles.yml`)

The profile is committed. It contains no secret: the key file path and the project id come from environment variables.

```yaml
ledger_vs_statement:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: service-account
      keyfile: "{{ env_var('DBT_KEYFILE') }}"
      project: "{{ env_var('GCP_PROJECT') }}"
      dataset: analytics_dev
      location: US
      threads: 4
      priority: interactive
      job_execution_timeout_seconds: 300
      job_retries: 1
      maximum_bytes_billed: 1000000000
    airflow:
      type: bigquery
      method: service-account
      keyfile: "{{ env_var('DBT_KEYFILE') }}"
      project: "{{ env_var('GCP_PROJECT') }}"
      dataset: analytics
      location: US
      threads: 4
      priority: interactive
      job_execution_timeout_seconds: 300
      job_retries: 1
      maximum_bytes_billed: 1000000000
```

What each field does:

| Field | Value | Meaning |
|---|---|---|
| `type` | `bigquery` | Use the dbt-bigquery adapter |
| `method` | `service-account` | Authenticate with the JSON key of `lvs-pipeline` |
| `keyfile` | `env_var('DBT_KEYFILE')` | Host: `<repo>/keys/sa.json`. Container: `/opt/airflow/keys/sa.json`. If the variable is missing, dbt stops with "Env var required but not provided" |
| `project` | `env_var('GCP_PROJECT')` | The sandbox project id. In dbt-bigquery 1.12.1, `project` is the legacy name of `database` |
| `dataset` | `analytics_dev` or `analytics` | Where dbt builds. `dataset` is the legacy name of `schema`. dbt creates the dataset if it is missing |
| `location` | `US` | Must match the datasets. A mismatch gives "Not found: Dataset ... in location US" |
| `threads` | `4` | dbt runs up to 4 independent models or tests at once |
| `priority` | `interactive` | Queries start at once (the other value is `batch`) |
| `job_execution_timeout_seconds` | `300` | A query running longer than 5 minutes fails |
| `job_retries` | `1` | dbt retries a failed BigQuery job once (1 is also the adapter default). This is why the Airflow task `dbt_build` has `retries=0` |
| `maximum_bytes_billed` | `1000000000` | Any query that would scan more than 1 GB fails before it runs, at no cost. BigQuery rejects values below 10485760 (10 MiB) |

Targets:

| Target | Dataset dbt builds | Sources read from | Used by |
|---|---|---|---|
| `dev` (default) | `analytics_dev` | `raw_dev` | the host (`make dbt-build`, `make dbt-unit`) |
| `airflow` | `analytics` | `raw` | the DAG task `dbt_build` and `smoke_bigquery` (`dbt debug`) |

There are no custom schemas. dbt writes every model into the target's dataset, so no `generate_schema_name` override exists.

### Environment variables dbt reads

| Variable | Read by | Host value | Container value |
|---|---|---|---|
| `GCP_PROJECT` | `profiles.yml` (`project`), `_sources.yml` (`database`) | from the root `.env` (exported by the Makefile, and also auto-loaded by dbt) | `${GCP_PROJECT}` from the compose file |
| `RAW_DATASET` | `_sources.yml` (`schema`), the guard in `stg_recon__as_of` | `raw_dev` | `raw` |
| `DBT_KEYFILE` | `profiles.yml` (`keyfile`) | `<repo>/keys/sa.json` | `/opt/airflow/keys/sa.json` |
| `DBT_PROFILES_DIR` | the dbt CLI (where `profiles.yml` is) | `<repo>/dbt` | `/opt/airflow/dbt` |

`DBT_PROFILES_DIR` matters because dbt otherwise also looks in `~/.dbt/`. With it set, the project's own `profiles.yml` is always the one used.

### Commands that use the profile

Host, from the repo root. The Makefile wraps these (see `docs/build_plan.md`); the dbt part of each target must be exactly this:

```
uv sync                                        # installs the pinned versions from uv.lock
cd dbt && uv run dbt --version                 # make doctor: Core 1.12.6, bigquery 1.12.1
cd dbt && uv run dbt deps                      # make setup: installs dbt_utils into dbt/dbt_packages/
cd dbt && uv run dbt debug --target dev        # S1.3: must end with "All checks passed!"
```

Container:
```
cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt debug --target airflow
```
`smoke_bigquery` runs this. `dbt debug` also checks that `git` is installed. The `apache/airflow:3.3.2` image installs `git` (it is in the image's runtime package list), so the check passes.

Rule for the host: `--target airflow` is allowed only with the read-only commands `dbt compile` and `dbt show`. `build`, `run`, `seed`, `test`, `docs generate` and every other command on the host use `--target dev`. The proof datasets belong to Airflow.

### Fallback: Application Default Credentials (only if G0 step S1.2 fails)

Use this only if Google refuses to create the service-account key. Record the switch in ADR-0001.
1. Install the Google Cloud CLI: `brew install --cask gcloud-cli`.
2. Sign in with the personal Gmail account: `gcloud auth application-default login`. This writes `~/.config/gcloud/application_default_credentials.json`. If dbt later reports `invalid_scope`, run the longer form from the dbt docs: `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/bigquery,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/iam.test,https://www.googleapis.com/auth/cloud-platform`.
3. In `profiles.yml`, in both targets, change `method: service-account` to `method: oauth` and delete the `keyfile` line. Nothing else changes.
4. On the host, `DBT_KEYFILE` and `GOOGLE_APPLICATION_CREDENTIALS` must not point to a file that does not exist. The Google auth library reads `GOOGLE_APPLICATION_CREDENTIALS` first and fails on a missing file. So the Makefile must stop exporting both in this mode.
5. In the container, the same file must be mounted read-only where the Google auth library looks for it: `$HOME/.config/gcloud/application_default_credentials.json`, and `HOME` is `/home/airflow` in the image. The Airflow connection `google_cloud_default` also drops `key_path` from its extras. The exact compose lines live in `docs/specs/airflow_and_docker.md`.
6. A warning saying the credentials have no quota project is harmless. To silence it: `gcloud auth application-default set-quota-project <project-id>`.

---

## Project file (`dbt/dbt_project.yml`)

```yaml
name: ledger_vs_statement
version: "1.0.0"
profile: ledger_vs_statement
require-dbt-version: [">=1.12.6", "<1.13.0"]

model-paths: ["models"]
seed-paths: ["seeds"]
test-paths: ["tests"]
macro-paths: ["macros"]
analysis-paths: ["analyses"]
clean-targets: ["target", "dbt_packages"]

query-comment:
  job-label: true

flags:
  send_anonymous_usage_stats: false

vars:
  statement_grace_days: 1
  fx_max_carry_days: 5
  exception_share_warn: 0.02
  exception_min_count: 5
  gate_window_days: 7
  # as_of_date is never set here. Host dev builds may pass it with --vars.

models:
  ledger_vs_statement:
    +labels:
      data_origin: synthetic
    staging:
      +materialized: view
    intermediate:
      +materialized: view
    marts:
      +materialized: table
      +on_schema_change: fail
```

What each block does:

| Block | Why it is there |
|---|---|
| `name`, `profile` | The project name and the profile in `profiles.yml` |
| `require-dbt-version` | dbt refuses to run this project on a version below 1.12.6 or from 1.13.0 on, and so on dbt v2. This is a second guard against the v2 binary, after `make doctor` |
| paths | The dbt defaults, written out so the layout is visible in one place. Never set `target-path` or `log-path` here; they are CLI flags |
| `clean-targets` | `dbt clean` deletes `target/` and `dbt_packages/`. After a `dbt clean`, run `make setup` again, or the next `dbt build` (on the host or in the DAG) fails because `dbt_packages/` is empty |
| `query-comment` with `job-label: true` | dbt prepends a JSON comment to every query (app, dbt_version, profile_name, target_name, node_id). dbt-bigquery 1.12.1 turns those keys into BigQuery job labels, cleaned to lowercase letters, digits, `_` and `-` and cut to 63 characters. It also adds a `dbt_invocation_id` label to every job. No custom comment macro is needed. If BigQuery ever rejects a label, remove the `query-comment` block and log it in `docs/failure_log.md` |
| `flags: send_anonymous_usage_stats: false` | dbt sends no usage events. It also stops dbt from writing its user-id file `.user.yml` into the profiles folder, which here is `dbt/` |
| `vars` | Business parameters, see the table below |
| `+labels` | Every model gets the BigQuery label `data_origin: synthetic`. The two FX models override it with `data_origin: real` in their own config. A model's labels replace the project labels; dbt does not merge the two sets |
| `+materialized` | Staging and intermediate are views (they store nothing). Marts are tables. `fct_recon_exceptions` overrides to `view` in its config |
| `+on_schema_change: fail` | Applies only to incremental models, and v1.0 has none, so today it changes nothing. It is set on marts so that U5's snapshot, or any later incremental mart, fails instead of silently ignoring a changed column. U5 also sets it in the model itself |

Settings that are deliberately absent:
- `store_failures`: off. dbt would write failing rows into a new dataset (`analytics_dbt_test__audit`), which adds storage and breaks the "no custom schemas" rule. To see failing rows, run the test's compiled SQL in the BigQuery console (see "Reading a failed build").
- `persist_docs`: off. Model descriptions stay in the dbt docs site. The "SYNTHETIC:" table description rule applies to the raw tables, which the loader creates.
- `on-run-start` and `on-run-end` hooks: none. Hooks are where packages such as Elementary insert rows.
- `require_partition_filter`, `partition_expiration_days`, `hours_to_expiration`: never set. The first would break the tests and the identity queries. The other two change expiry, and the sandbox default of 60 days must stay.
- The flag `require_generic_test_arguments_property`: not needed. Its default in 1.12.6 is already true, which is what makes `arguments:` the required place for test inputs.

### Vars

| Var | Default | Used by | Meaning |
|---|---|---|---|
| `statement_grace_days` | 1 | `int_ledger__captures.due_date` | Days to wait after the latest contracted settlement day before a missing statement line becomes an exception |
| `fx_max_carry_days` | 5 | test on `int_fx__usd_rates_daily.carry_days` | Longest allowed carry-forward of an FX rate. A weekend gives 2 |
| `exception_share_warn` | 0.02 | `warn_exception_share_7d` | Warn above this share of break amount over booked gross |
| `exception_min_count` | 5 | `warn_exception_share_7d` | Warn only with at least this many exceptions in the window |
| `gate_window_days` | 7 | `warn_exception_share_7d` | Length of the rolling window, ending on `as_of_date` |
| `as_of_date` | not set | `stg_recon__as_of` | Host-only time travel: "what did we know on day X". The DAG never passes it. A compile guard stops it with `--target airflow` |

There is no `run_date` var in v1.0. U5 adds one for its snapshot model only.

Use `var('as_of_date', none)` everywhere, so an unset var is `none` and not an error.

How to pass a var on the host (example: rebuild the dev marts as known on 2026-10-28):
```
cd dbt
export RAW_DATASET=raw_dev DBT_PROFILES_DIR="$PWD" DBT_KEYFILE="$(cd .. && pwd)/keys/sa.json"
uv run dbt build --target dev --vars '{"as_of_date": "2026-10-28"}'
uv run dbt build --target dev        # afterwards: rebuild without the var
```
Var values used in SQL must keep the money rules. `exception_share_warn` renders as `0.02`, which BigQuery reads as FLOAT64. In SQL, write it as `numeric '{{ var("exception_share_warn") }}'`.

---

## Packages (`dbt/packages.yml` and `dbt/package-lock.yml`)

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.4.1
```

1. `make setup` runs `cd dbt && uv run dbt deps`. It downloads dbt_utils into `dbt/dbt_packages/` and writes `dbt/package-lock.yml` with the exact version and a hash.
2. Commit `package-lock.yml`. Later `dbt deps` runs install exactly what the lock says. Never run `dbt deps --upgrade`.
3. `dbt/dbt_packages/` is gitignored. The container sees it through the `./dbt:/opt/airflow/dbt` mount. Never run `dbt deps` inside the container.
4. dbt_utils supplies three tests used here: `expression_is_true`, `unique_combination_of_columns` and `accepted_range`. All three compile to plain `SELECT` queries.

Packages that must never be added:
- Elementary: it inserts rows with `insert into`.
- calogica dbt-expectations: unmaintained. If expectations are ever needed, the maintained fork is metaplane/dbt_expectations.
- dbt_project_evaluator 2.x: it requires dbt v2. Version 1.4.1 is on the roadmap only for a DuckDB target, because it also writes its graph tables with inserts.

---

## Seeds (`dbt/seeds/`)

Seeds are small CSV files that dbt loads as tables in the target dataset. dbt-bigquery loads a seed with a load job (`WRITE_TRUNCATE`), not with DML. On every `dbt seed` or `dbt build` it drops the seed table and loads it again, which also gives the table a fresh 60-day expiry clock. Every column type is set explicitly, so no column is ever inferred as FLOAT64.

### `mids.csv`

The contract terms of the two merchant accounts. The generator reads the same file, so finance and the simulator agree on the terms (see `docs/specs/data_and_generator.md`). What finance cannot know (noise, defects) is never in a seed.

```
mid,psp,currency,statement_utc_offset_hours,max_settlement_lag_days,fee_bps,fee_fixed_minor,fee_tol_bps,fee_tol_min_minor
mid_usd_01,psp_alpha,USD,-5,2,290,30,10,5
mid_kzt_01,psp_alpha,KZT,5,2,250,0,10,500
```

### `currencies.csv`

```
currency,minor_per_major
USD,100
KZT,100
```

### `reason_codes.csv`

Fields with a comma are wrapped in double quotes.

```
code,category,precedence,description,analyst_action
missing_in_statement,exception,10,ledger line with no statement line by its due date,ask the PSP or check for a void
missing_in_ledger,exception,20,"settled by the PSP, never booked (lost webhook)",replay the webhook or book the revenue
amount_mismatch,exception,30,settled gross differs from the booked amount,check the ledger price and PSP adjustments
fee_mismatch,exception,40,fee outside the contracted tolerance,raise with the PSP
date_mismatch,exception,45,accounting date not explained by the MID's cut-off,check the PSP's cut-off
in_transit,explained,50,"ledger line waiting for its statement, before the due date",wait
timing_cutoff,explained,60,booked on another accounting day because of the MID's cut-off,none
before_scope,explained,80,one-sided line dated before the oldest loaded day,none
matched,matched,90,"both sides present, amounts equal, fee within tolerance, date explained",none
```

The text `none` stays a string. dbt treats only an empty field and the text `null` as NULL in seeds.

### `seeds/_seeds.yml`

```yaml
seeds:
  - name: mids
    description: "One row per merchant account (MID): currency, cut-off offset, settlement lag and fee terms. SYNTHETIC contract terms shared by the generator and dbt."
    config:
      column_types:
        mid: STRING
        psp: STRING
        currency: STRING
        statement_utc_offset_hours: INT64
        max_settlement_lag_days: INT64
        fee_bps: INT64
        fee_fixed_minor: INT64
        fee_tol_bps: INT64
        fee_tol_min_minor: INT64
  - name: currencies
    description: "One row per currency: minor units per major unit (ISO 4217)."
    config:
      column_types:
        currency: STRING
        minor_per_major: INT64
  - name: reason_codes
    description: "One row per reason code: category, precedence (lower wins) and the analyst's next action."
    config:
      column_types:
        code: STRING
        category: STRING
        precedence: INT64
        description: STRING
        analyst_action: STRING
```

Type names are written in upper case (`INT64`, `STRING`). dbt-bigquery passes them unchanged into the load job's schema.

---

## Sources (`dbt/models/staging/_sources.yml`)

The raw tables are created and loaded by Python (`recon.load`), never by dbt. dbt only reads them.

```yaml
sources:
  - name: psp
    description: "SYNTHETIC webhook deliveries and PSP statement lines, loaded by Airflow into raw or by the host CLI into raw_dev."
    database: "{{ env_var('GCP_PROJECT') }}"
    schema: "{{ env_var('RAW_DATASET', 'raw') }}"
    tables:
      - name: payment_events
        description: "One row per webhook delivery that arrived on _arrival_date. SYNTHETIC."
      - name: settlement_lines
        description: "One row per line of a per-MID statement file that arrived on _arrival_date. SYNTHETIC."
  - name: fx
    description: "REAL USD/KZT rates published by the National Bank of Kazakhstan, fetched through Frankfurter v2 and stored as published."
    database: "{{ env_var('GCP_PROJECT') }}"
    schema: "{{ env_var('RAW_DATASET', 'raw') }}"
    tables:
      - name: fx_rates
        description: "One row per rate observation returned by the fetch made for _arrival_date. REAL."
```

The columns of each raw table, and the JSON schema files that define them, are in `docs/specs/data_and_generator.md`. Every raw column is REQUIRED in BigQuery, so BigQuery itself rejects a NULL at load time. That is why the sources carry no `not_null` tests.

### Source freshness: not in v1.0

v1.0 has no freshness checks. In a backfilled window they would only measure when I last ran the DAG. v1.x adds metadata-based freshness. dbt-bigquery reads the table's last-modified time when no `loaded_at_field` is given. The v1.x shape is:

```yaml
      - name: payment_events
        config:
          freshness:
            warn_after: {count: 26, period: hour}
            error_after: {count: 50, period: hour}
```

It runs as its own command, `cd dbt && uv run dbt source freshness --target dev`, never inside `dbt build`. The newer docs describe a `dbt freshness` command; that exists only in dbt v2, not in dbt-core 1.12.6.

---

## The as-of rule

Every model must know what "now" is without reading the clock. It uses two dates from `stg_recon__as_of`:
- `as_of_date`: the newest loaded arrival day of `payment_events`. Webhook deliveries arrive every day, so this is never NULL, even after the first load.
- `scope_start`: the oldest loaded arrival day, up to `as_of_date`.

Rules that follow from it:
1. Every staging model keeps only rows with `_arrival_date <= as_of_date`.
2. Every status (in transit or missing) is judged against `as_of_date`, never against the wall clock.
3. A line that has only one side and is dated before `scope_start` is `before_scope`, not an exception. Its other side may sit in a day that was never loaded (a dev subset, a 14-day history, or a partition that expired).
4. When Airflow reprocesses an old day, `as_of_date` stays the newest loaded day. An old rerun never rolls the marts back.
5. The marts are therefore a pure function of what is loaded. That is exactly what the rerun proof compares.

The `as_of_date` var replaces the newest loaded day in host dev builds only. If it is set later than the newest loaded day, `assert_arrival_days_complete` fails, because days without partitions fall inside the window. That failure is intended.

---

## Models

| Model | Folder | Materialization | Grain | Key | Partition | Cluster | Contract | `data_origin` label |
|---|---|---|---|---|---|---|---|---|
| `stg_recon__as_of` | staging | view | one row | none | none | none | no | synthetic |
| `stg_psp__payment_events` | staging | view | one row per `event_id` | `event_id` | none | none | no | synthetic |
| `stg_psp__settlement_lines` | staging | view | one row per `line_id` | `line_id` | none | none | no | synthetic |
| `stg_fx__rates` | staging | view | one row per (`provider`, `base`, `quote`, `rate_date`) | those four | none | none | no | real |
| `int_ledger__captures` | intermediate | view | one row per `payment_id` | `payment_id` | none | none | no | synthetic |
| `int_fx__usd_rates_daily` | intermediate | view | one row per (`currency`, `day`) | those two | none | none | no | real |
| `fct_recon_lines` | marts | table | one row per `payment_id` seen on either side | `payment_id` | `recon_date`, day | `mid` | no | synthetic |
| `fct_recon_exceptions` | marts | view | one row per (`payment_id`, `cause`) | those two | none | none | no | synthetic |
| `fct_recon_daily` | marts | table | one row per (`mid`, `currency`, `recon_date`) | those three | `recon_date`, day | `mid` | yes, enforced | synthetic |

Views cannot be partitioned. `copy_partitions` is not set on any v1.0 model: it only applies to incremental `insert_overwrite` models, and v1.0 has none.

Two things are true of every model below:
- The final `SELECT` lists its columns explicitly, in the order of the columns table. Never `SELECT *` from a source.
- Joins alias every table (`as l`, `as s`, `as m`).

Lineage. Each model, then everything it reads:
```
stg_recon__as_of           <- source psp.payment_events
stg_psp__payment_events    <- source psp.payment_events, stg_recon__as_of
stg_psp__settlement_lines  <- source psp.settlement_lines, stg_recon__as_of
stg_fx__rates              <- source fx.fx_rates, stg_recon__as_of
int_ledger__captures       <- stg_psp__payment_events, seed mids
int_fx__usd_rates_daily    <- stg_fx__rates, stg_recon__as_of
fct_recon_lines            <- int_ledger__captures, stg_psp__settlement_lines, stg_recon__as_of, seed mids
fct_recon_exceptions       <- fct_recon_lines, seed reason_codes
fct_recon_daily            <- stg_recon__as_of, seed mids, seed currencies, int_ledger__captures,
                              stg_psp__settlement_lines, fct_recon_lines, fct_recon_exceptions,
                              int_fx__usd_rates_daily
```

### `stg_recon__as_of`

**Purpose.** One place that says which loaded days the build may use. The three other staging models, `int_fx__usd_rates_daily`, `fct_recon_lines` and `fct_recon_daily` read it directly; the rest inherit its filter through their parents.

**Grain.** Exactly one row.

**Materialization and config.** View, from the folder default. No extra config.

**Inputs.** `source('psp', 'payment_events')`; the var `as_of_date`.

**Columns.**

| Column | Type | Description |
|---|---|---|
| `as_of_date` | DATE | Newest loaded arrival day, or the `as_of_date` var in host dev builds. Statuses are judged against it |
| `scope_start` | DATE | Oldest loaded arrival day up to `as_of_date`. One-sided lines dated before it are `before_scope` |

**Guards (compile time).** The model starts with three checks that stop the build with a clear message. They are wrapped in `{% if execute %}` so `dbt parse` (used in CI with dummy values) never trips them:

```sql
{% if execute %}
  {% if target.name == 'airflow' and var('as_of_date', none) is not none %}
    {{ exceptions.raise_compiler_error("as_of_date is for host dev builds only. Never pass it with --target airflow.") }}
  {% endif %}
  {% if target.name == 'airflow' and env_var('RAW_DATASET', 'raw') != 'raw' %}
    {{ exceptions.raise_compiler_error("Target airflow must read RAW_DATASET=raw.") }}
  {% endif %}
  {% if target.name == 'dev' and env_var('RAW_DATASET', 'raw') != 'raw_dev' %}
    {{ exceptions.raise_compiler_error("Target dev must read RAW_DATASET=raw_dev. Run dbt through make, or export RAW_DATASET=raw_dev.") }}
  {% endif %}
{% endif %}
```

Why: a dev build that reads the proof data, or a DAG build with a time-travel var, would quietly break the rerun proof. A loud stop costs nothing. When U4 adds a held-out target, its pairing is added here.

**Logic.**
1. Read `_arrival_date` from the payment-events source.
2. If the `as_of_date` var is set, keep only rows with `_arrival_date <= DATE '<var>'`.
3. Return one row: `as_of_date` = the var if set, else `MAX(_arrival_date)`; `scope_start` = `MIN(_arrival_date)` of the kept rows.

**Tests.** `not_null` on `as_of_date` and on `scope_start`. The `scope_start` test also catches a var set earlier than every loaded day.

**Contract.** No.

### `stg_psp__payment_events`

**Purpose.** Turn raw webhook deliveries into one row per event. This is the first dedup layer (D1 redeliveries are removed here).

**Grain.** One row per `event_id`.

**Materialization and config.** View, from the folder default.

**Inputs.** `source('psp', 'payment_events')`, `ref('stg_recon__as_of')`.

**Columns.**

| Column | Type | Description |
|---|---|---|
| `event_id` | STRING | Webhook event id, `evt_<payment_id>_cap`. The same on every redelivery. Primary key |
| `event_type` | STRING | `payment.captured` in v1.0 |
| `payment_id` | STRING | PSP reference, shared with the statement line |
| `order_id` | STRING | Order id. Not used for matching in v1.0 |
| `mid` | STRING | Merchant account |
| `plan_id` | STRING | `p1w`, `p4w` or `p12w` |
| `amount_minor` | INT64 | Captured amount in minor units |
| `currency` | STRING | ISO 4217 code |
| `event_ts` | TIMESTAMP | Capture time, UTC |
| `first_delivery_id` | STRING | The delivery that was kept: the earliest one |
| `first_delivered_ts` | TIMESTAMP | When the kept delivery reached the backend |
| `first_arrival_date` | DATE | Arrival day of the kept delivery |
| `copies_received` | INT64 | Deliveries of this event loaded up to `as_of_date`. 1 means no redelivery |
| `is_synthetic` | BOOL | Always true |

**Logic.**
1. Read every delivery from the source with `_arrival_date <= as_of_date` (cross join `stg_recon__as_of`).
2. Count the deliveries per event: `COUNT(*) OVER (PARTITION BY event_id)` as `copies_received`.
3. Keep the earliest delivery per event: `QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY delivered_ts, delivery_id) = 1`. Window functions are computed before `QUALIFY` filters, so the count in step 2 still sees every copy.
4. Rename the kept delivery's `delivery_id`, `delivered_ts` and `_arrival_date` to `first_delivery_id`, `first_delivered_ts` and `first_arrival_date`.

If BigQuery ever demands a `WHERE` clause next to `QUALIFY`, the filter in step 1 already is one; otherwise add `where true`.

Why the tie-break on `delivery_id`: two copies can share one `delivered_ts`. Without a second sort key, `ROW_NUMBER` may keep either copy, and a rerun could keep a different one. The fingerprints would then change. Attempt numbers stay at 1 to 3, so the text sort of `dlv_..._1`, `dlv_..._2`, `dlv_..._3` matches the attempt order.

Keeping the first copy is only safe if every copy carries the same business fields. `assert_redeliveries_identical` checks exactly that.

**Tests.** `unique` and `not_null` on `event_id`; `accepted_values` on `event_type` with `['payment.captured']`; `relationships` from `mid` to `ref('mids')`, field `mid`. Unit test UT3 (U1).

**Contract.** No.

### `stg_psp__settlement_lines`

**Purpose.** The PSP's side: one row per statement line, typed and filtered to what is loaded.

**Grain.** One row per `line_id`.

**Materialization and config.** View, from the folder default.

**Inputs.** `source('psp', 'settlement_lines')`, `ref('stg_recon__as_of')`.

**Columns.**

| Column | Type | Description |
|---|---|---|
| `line_id` | STRING | `ln_<payment_id>`. Primary key |
| `statement_id` | STRING | `stmt_<mid>_<yyyymmdd of arrival>`: the file the line came in |
| `mid` | STRING | Merchant account |
| `record_type` | STRING | `SALE` in v1.0 |
| `payment_id` | STRING | PSP reference, shared with the webhook |
| `captured_ts` | TIMESTAMP | The PSP's capture time, UTC |
| `accounting_date` | DATE | The PSP's day for the sale |
| `gross_minor` | INT64 | Settled gross |
| `fee_minor` | INT64 | PSP fee |
| `net_minor` | INT64 | Gross minus fee |
| `currency` | STRING | Settlement currency |
| `statement_arrival_date` | DATE | Renamed from `_arrival_date` |
| `is_synthetic` | BOOL | Always true |

**Logic.**
1. Read every line with `_arrival_date <= as_of_date`.
2. Select the columns above in order. Rename `_arrival_date` to `statement_arrival_date`. Drop `_source_file`.

There is no dedup here on purpose. A repeated line is a PSP defect (H1, held for U4) and must fail the grain test loudly.

**Tests.** `unique` and `not_null` on `line_id`; `not_null` on `payment_id`; `accepted_values` on `record_type` with `['SALE']`; `dbt_utils.expression_is_true` with `net_minor = gross_minor - fee_minor`; `relationships` from `mid` to `ref('mids')`, field `mid`.

**Contract.** No.

### `stg_fx__rates`

**Purpose.** Real NBK rates, one value per rate date, exactly as first published.

**Grain.** One row per (`provider`, `base`, `quote`, `rate_date`).

**Materialization and config.** View. Its own config sets the label:
```sql
{{ config(labels={'data_origin': 'real'}) }}
```

**Inputs.** `source('fx', 'fx_rates')`, `ref('stg_recon__as_of')`.

**Columns.**

| Column | Type | Description |
|---|---|---|
| `provider` | STRING | `nbk` in v1.0 |
| `base` | STRING | `USD` |
| `quote` | STRING | `KZT` |
| `rate_date` | DATE | The date of the published rate |
| `rate_text` | STRING | The exact published digits, for example `453.71` |
| `rate` | NUMERIC | `CAST(rate_text AS NUMERIC)`. KZT per 1 USD |
| `first_seen_arrival_date` | DATE | The fetch partition that first carried this rate date |

**Logic.**
1. Read every row with `_arrival_date <= as_of_date`. A rate date appears in up to 9 fetch partitions: each run fetches R-6 to R, and a run whose R-6 has no rate also gets the last published row before R-6.
2. Keep the first-seen value per key: `QUALIFY ROW_NUMBER() OVER (PARTITION BY provider, base, quote, rate_date ORDER BY _arrival_date, rate_text) = 1`. `rate_text` is a tie-break that keeps the result the same on every rerun.
3. Cast `rate_text` to NUMERIC as `rate`. The text is never parsed as a float anywhere.
4. Rename `_arrival_date` to `first_seen_arrival_date`.

If NBK ever restates a rate between fetches, this model keeps the first value and `warn_fx_restated` reports it.

**Tests.** `dbt_utils.unique_combination_of_columns` on (`provider`, `base`, `quote`, `rate_date`); `not_null` on `rate`; `dbt_utils.accepted_range` on `rate` from 300 to 700 with the filter `quote = 'KZT'` (catches unit and direction errors).

**Contract.** No.

### `int_ledger__captures`

**Purpose.** Our revenue ledger: one deduplicated capture per payment, with the dates the matcher needs.

**Grain.** One row per `payment_id`.

**Materialization and config.** View, from the folder default.

**Inputs.** `ref('stg_psp__payment_events')`, `ref('mids')`; the var `statement_grace_days`.

**Columns.**

| Column | Type | Description |
|---|---|---|
| `payment_id` | STRING | Primary key. A second capture event for one payment fails the unique test |
| `event_id` | STRING | The capture event |
| `order_id` | STRING | Order id |
| `mid` | STRING | Merchant account |
| `currency` | STRING | Settlement currency of the MID |
| `plan_id` | STRING | Plan |
| `amount_minor` | INT64 | Booked amount in minor units |
| `event_ts` | TIMESTAMP | Capture time, UTC |
| `first_arrival_date` | DATE | Arrival day of the first loaded delivery |
| `copies_received` | INT64 | Deliveries received for the event |
| `booking_date` | DATE | Our revenue day: `DATE(event_ts)` in UTC |
| `expected_accounting_date` | DATE | The day the MID's fixed cut-off predicts the PSP will book the sale |
| `due_date` | DATE | From this day on (inclusive) a missing statement line is an exception |

**Logic.**
1. Take the events with `event_type = 'payment.captured'`.
2. `LEFT JOIN` the `mids` seed on `mid`. A left join keeps an unknown MID visible: its dates come out NULL and the `not_null` tests fail. An inner join would drop the payment silently.
3. `booking_date = DATE(event_ts)`.
4. `expected_accounting_date = DATE(TIMESTAMP_ADD(event_ts, INTERVAL statement_utc_offset_hours HOUR))`. The offset is +5 for KZT and -5 for USD, so shifts happen in both directions.
5. `due_date = DATE_ADD(expected_accounting_date, INTERVAL (max_settlement_lag_days + {{ var('statement_grace_days') }}) DAY)`.

**Tests.** `unique` and `not_null` on `payment_id`; `not_null` on `booking_date`, `expected_accounting_date` and `due_date`. Unit test UT1.

**Contract.** No.

### `int_fx__usd_rates_daily`

**Purpose.** A rate for every calendar day, so reporting can convert any MID-day to USD.

**Grain.** One row per (`currency`, `day`).

**Materialization and config.** View, with the real label:
```sql
{{ config(labels={'data_origin': 'real'}) }}
```

**Inputs.** `ref('stg_fx__rates')`, `ref('stg_recon__as_of')`.

**Columns.**

| Column | Type | Description |
|---|---|---|
| `currency` | STRING | `KZT` from NBK rates, `USD` as identity rows |
| `day` | DATE | Calendar day |
| `provider` | STRING | `nbk` for KZT, `identity` for USD |
| `units_per_usd` | NUMERIC | Currency units per 1 USD on this day. 1 for USD |
| `rate_date` | DATE | The date of the rate actually used |
| `carry_days` | INT64 | `day` minus `rate_date`. 0 on a day with its own rate |

The description must say: "Weekend and holiday values are carried forward from the last published rate. This is a project convention, not NBK's official rate for that day."

**Logic.**
1. Take the rates with `provider = 'nbk'` and `base = 'USD'`. Their `quote` becomes `currency`. The provider filter is explicit, so a second provider added later (U7) can never be mixed in.
2. Per currency, build a spine of days from that currency's earliest `rate_date` to `as_of_date` with `GENERATE_DATE_ARRAY` and `UNNEST`.
3. `LEFT JOIN` the rates onto the spine on (`currency`, `day = rate_date`).
4. Carry forward: `LAST_VALUE(rate IGNORE NULLS)` and `LAST_VALUE(rate_date IGNORE NULLS)` over `PARTITION BY currency ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.
5. `carry_days = DATE_DIFF(day, rate_date, DAY)`.
6. `UNION ALL` the USD identity rows: one per day from the earliest `rate_date` of any currency to `as_of_date`, with `units_per_usd = NUMERIC '1'`, `rate_date = day`, `carry_days = 0`, `provider = 'identity'`.

**Tests.** `dbt_utils.unique_combination_of_columns` on (`currency`, `day`); `not_null` on `units_per_usd` and `rate_date`; `dbt_utils.accepted_range` on `carry_days` from 0 to `var('fx_max_carry_days')`. That last test is the staleness gate: a gap of more than 5 days fails the build. Repeated values on consecutive days (for example 451.05 on two days in a row) are not gaps.

**Contract.** No.

### `fct_recon_lines`

**Purpose.** The matcher. Every payment seen on either side gets exactly one status, its date flags, its fee check and one primary reason.

**Grain.** One row per `payment_id` seen in the ledger, the statement, or both.

**Materialization and config.**
```sql
{{ config(
    materialized='table',
    partition_by={'field': 'recon_date', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['mid']
) }}
```
`materialized='table'` repeats the folder default to make the file self-explaining. dbt rebuilds the table with `CREATE OR REPLACE TABLE ... PARTITION BY recon_date CLUSTER BY mid AS (...)`. If the partition or cluster spec ever changes, dbt drops the old table first, because BigQuery cannot replace a table with a differently partitioned one.

**Inputs.** `ref('int_ledger__captures')`, `ref('stg_psp__settlement_lines')`, `ref('stg_recon__as_of')`, `ref('mids')`.

**Columns.**

| Column | Type | Description |
|---|---|---|
| `payment_id` | STRING | PSP reference. Primary key. Taken from whichever side exists |
| `mid` | STRING | Merchant account, from whichever side exists |
| `currency` | STRING | Settlement currency. The same on both sides in v1.0 |
| `has_ledger` | BOOL | The ledger has a capture for this payment |
| `has_statement` | BOOL | A `SALE` statement line exists for this payment |
| `event_id` | STRING | Ledger side. NULL without a ledger side |
| `copies_received` | INT64 | Ledger side |
| `event_ts` | TIMESTAMP | Ledger side: capture time |
| `booking_date` | DATE | Ledger side: our revenue day |
| `ledger_amount_minor` | INT64 | Ledger side: booked amount |
| `expected_accounting_date` | DATE | Ledger side |
| `due_date` | DATE | Ledger side |
| `line_id` | STRING | Statement side. NULL without a statement side |
| `statement_id` | STRING | Statement side: the file |
| `captured_ts` | TIMESTAMP | Statement side: the PSP's capture time |
| `accounting_date` | DATE | Statement side: the PSP's day for the sale |
| `statement_arrival_date` | DATE | Statement side |
| `statement_gross_minor` | INT64 | Statement side |
| `statement_fee_minor` | INT64 | Statement side |
| `statement_net_minor` | INT64 | Statement side |
| `recon_date` | DATE | The line's own day: `COALESCE(booking_date, DATE(captured_ts))`. Never NULL. Partition column |
| `scope_start` | DATE | From `stg_recon__as_of` |
| `as_of_date` | DATE | From `stg_recon__as_of`. Every status is judged against it |
| `match_status` | STRING | Exactly one of `matched`, `before_scope`, `in_transit`, `missing_in_statement`, `missing_in_ledger` |
| `date_shift` | STRING | Matched lines: `none`, `timing_cutoff` or `date_mismatch`. NULL for one-sided lines |
| `amount_diff_minor` | INT64 | Matched lines: ledger amount minus statement gross. NULL otherwise |
| `is_amount_mismatch` | BOOL | Matched and `amount_diff_minor != 0`. Never NULL |
| `expected_fee_minor` | INT64 | Lines with a statement side: the contracted fee |
| `fee_tolerance_minor` | INT64 | Lines with a statement side: the allowed fee difference |
| `fee_variance_minor` | INT64 | Lines with a statement side: charged fee minus expected fee |
| `is_fee_mismatch` | BOOL | The fee is outside tolerance. Never NULL. Always false for `before_scope` lines |
| `primary_reason` | STRING | One reason code per line, by precedence |
| `is_exception` | BOOL | Any exception cause applies. Never NULL |

**Logic, as CTEs in this order.**
1. `as_of`: one row from `stg_recon__as_of`.
2. `ledger`: the columns of `int_ledger__captures`, with `amount_minor` renamed `ledger_amount_minor`.
3. `statement`: the columns of `stg_psp__settlement_lines` filtered to `record_type = 'SALE'`. The filter sits here, before the join. Applied after the join, it would also drop every ledger-only row, because their statement columns are NULL.
4. `joined`: `ledger as l FULL OUTER JOIN statement as s ON l.payment_id = s.payment_id`. Take `payment_id`, `mid` and `currency` with `COALESCE(l.x, s.x)`. Set `has_ledger = l.payment_id IS NOT NULL` and `has_statement = s.payment_id IS NOT NULL`.
5. `with_terms`: `LEFT JOIN` the `mids` seed on the coalesced `mid` (for the fee terms), and cross join `as_of`.
6. `classified`: add `recon_date`, `match_status`, `date_shift`, `amount_diff_minor` and `is_amount_mismatch` (rules below).
7. `fees`: add the four fee columns (rules below).
8. Final `SELECT`: add `primary_reason` and `is_exception`, then list the columns in the order of the table above.

Status, exactly one per line:
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
From the due date on (inclusive), a ledger-only line is missing. `as_of_date < due_date` is the line that mutation 2 changes.

Date shift, matched lines only:
- `none` if `accounting_date = booking_date`;
- else `timing_cutoff` if `accounting_date = expected_accounting_date` (the MID's cut-off explains it);
- else `date_mismatch` (an exception);
- NULL for one-sided lines.

Amount, matched lines only:
- `amount_diff_minor = ledger_amount_minor - statement_gross_minor`.
- `is_amount_mismatch = has_ledger AND has_statement AND amount_diff_minor != 0`. The same-currency gross tolerance is exactly 0.

Fee check, integer arithmetic only, on every line with a statement side:
```
expected_fee_minor  = DIV(statement_gross_minor * fee_bps + 5000, 10000) + fee_fixed_minor
fee_tolerance_minor = GREATEST(fee_tol_min_minor, DIV(statement_gross_minor * fee_tol_bps + 9999, 10000))
fee_variance_minor  = statement_fee_minor - expected_fee_minor
is_fee_mismatch     = has_statement AND match_status != 'before_scope'
                      AND ABS(fee_variance_minor) > fee_tolerance_minor
```
- `+ 5000` then `DIV` rounds half up for a positive gross. `+ 9999` then `DIV` is a ceiling. `DIV(INT64, INT64)` returns INT64.
- A variance equal to the tolerance is within it.
- The three fee numbers are NULL when there is no statement side.
- The flag is false for `before_scope` lines, so the exceptions queue and `is_exception` agree: neither includes out-of-scope lines.
- Worked example (KZT, gross 999000): expected fee = DIV(999000 x 250 + 5000, 10000) + 0 = DIV(249755000, 10000) = 24975. Tolerance = GREATEST(500, DIV(999000 x 10 + 9999, 10000)) = GREATEST(500, 999) = 999.
- Worked example (USD, gross 1999): expected fee = DIV(1999 x 290 + 5000, 10000) + 30 = DIV(584710, 10000) + 30 = 58 + 30 = 88. Tolerance = GREATEST(5, DIV(29989, 10000)) = GREATEST(5, 2) = 5.

Primary reason. The first true condition wins, in the precedence order of `reason_codes.csv`:
```
case
  when match_status = 'missing_in_statement' then 'missing_in_statement'   -- 10
  when match_status = 'missing_in_ledger'    then 'missing_in_ledger'      -- 20
  when is_amount_mismatch                    then 'amount_mismatch'        -- 30
  when is_fee_mismatch                       then 'fee_mismatch'           -- 40
  when date_shift = 'date_mismatch'          then 'date_mismatch'          -- 45
  when match_status = 'in_transit'           then 'in_transit'             -- 50
  when date_shift = 'timing_cutoff'          then 'timing_cutoff'          -- 60
  when match_status = 'before_scope'         then 'before_scope'           -- 80
  else                                            'matched'                -- 90
end
```
`timing_cutoff` only occurs on matched lines and `before_scope` only on one-sided lines, so their relative order never changes a result.

Exception flag:
```
is_exception = match_status in ('missing_in_statement', 'missing_in_ledger')
               or is_amount_mismatch
               or is_fee_mismatch
               or coalesce(date_shift = 'date_mismatch', false)
```
In BigQuery `FALSE OR NULL` is NULL. `date_shift` is NULL on one-sided lines, so the `coalesce` keeps `is_exception` true or false, never NULL. UT2 checks this.

Why the join must keep an equality: BigQuery rejects a `FULL OUTER JOIN` whose condition is not an equality between the two sides. An `OR` condition would also multiply rows. Later fuzzy passes (v1.x) run as a separate join over the leftovers.

**Tests.** `unique` and `not_null` on `payment_id` (no fan-out); `not_null` on `recon_date`, `match_status`, `primary_reason` and `as_of_date`; `accepted_values` on `match_status` with the five values; `relationships` from `primary_reason` to `ref('reason_codes')`, field `code`. Unit tests UT2 and UT4 (U1). Singular tests `assert_no_money_lost_between_layers` and, through `fct_recon_daily`, `assert_recon_decomposition_closes`.

**Contract.** No.

### `fct_recon_exceptions`

**Purpose.** The analyst work queue: one row per line and cause, with a signed amount, a date, an age, evidence ids and the next action.

**Grain.** One row per (`payment_id`, `cause`). A line with an amount difference and a fee overcharge gives two rows with two amounts.

**Materialization and config.**
```sql
{{ config(materialized='view') }}
```
A view stores nothing. It derives from the fingerprinted lines table.

**Inputs.** `ref('fct_recon_lines')`, `ref('reason_codes')`.

**Columns.**

| Column | Type | Description |
|---|---|---|
| `payment_id` | STRING | The line |
| `cause` | STRING | One of the five exception codes |
| `mid` | STRING | Merchant account |
| `currency` | STRING | Currency of `amount_minor` |
| `amount_minor` | INT64 | Signed. Positive means the ledger has more, or the PSP overcharged |
| `cause_date` | DATE | The day the cause is reported on |
| `recon_date` | DATE | The line's own day |
| `booking_date` | DATE | Ledger side |
| `accounting_date` | DATE | Statement side |
| `age_days` | INT64 | `DATE_DIFF(as_of_date, recon_date, DAY)` |
| `event_id` | STRING | Evidence: the webhook event |
| `line_id` | STRING | Evidence: the statement line |
| `statement_id` | STRING | Evidence: the statement file |
| `analyst_action` | STRING | From `reason_codes.csv` |
| `as_of_date` | DATE | As of which loaded day |

**Logic.**
1. Read `fct_recon_lines` with `match_status != 'before_scope'`. Out-of-scope lines never enter the queue.
2. Build one branch per cause and `UNION ALL` them:

| Cause | Lines | `amount_minor` | `cause_date` |
|---|---|---|---|
| `missing_in_statement` | `match_status = 'missing_in_statement'` | `+ledger_amount_minor` | `booking_date` |
| `missing_in_ledger` | `match_status = 'missing_in_ledger'` | `-statement_gross_minor` | `accounting_date` |
| `amount_mismatch` | `is_amount_mismatch` | `amount_diff_minor` | `accounting_date` |
| `fee_mismatch` | `is_fee_mismatch` | `fee_variance_minor` | `accounting_date` |
| `date_mismatch` | `date_shift = 'date_mismatch'` | `ledger_amount_minor` | `accounting_date` |

3. `LEFT JOIN` `reason_codes` on `code = cause` for `analyst_action`.
4. Add `age_days`, then list the columns in the order above.

**Tests.** `dbt_utils.unique_combination_of_columns` on (`payment_id`, `cause`); `not_null` on `amount_minor`; `relationships` from `cause` to `ref('reason_codes')`, field `code`.

**Contract.** No.

### `fct_recon_daily`

**Purpose.** The two-calendar bridge. For every MID and day it puts our booked gross next to the PSP's statement gross, splits the gap into dated reason components, and proves that nothing is left over.

**Grain.** One row per (`mid`, `currency`, `recon_date`). Here `recon_date` is a calendar day of the spine. It is our booking day for the ledger side and the PSP's accounting day for the statement side.

**Materialization and config.**
```sql
{{ config(
    materialized='table',
    partition_by={'field': 'recon_date', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['mid']
) }}
```
The enforced contract is configured in `_marts.yml` (below).

**Inputs.** `ref('stg_recon__as_of')`, `ref('mids')`, `ref('currencies')`, `ref('int_ledger__captures')`, `ref('stg_psp__settlement_lines')`, `ref('fct_recon_lines')`, `ref('fct_recon_exceptions')`, `ref('int_fx__usd_rates_daily')`.

**Columns (the contract, in this order).**

| # | Column | Type | Not null constraint | Definition |
|---|---|---|---|---|
| 1 | `mid` | string | yes | From the spine: every MID in `mids.csv` |
| 2 | `currency` | string | yes | The MID's currency, from `mids.csv` |
| 3 | `recon_date` | date | yes | Every day from the earliest to the latest date in the inputs. Days with no activity show zeros |
| 4 | `as_of_date` | date | yes | From `stg_recon__as_of` |
| 5 | `ledger_line_count` | int64 | | Top-down: captures with this `booking_date` |
| 6 | `statement_line_count` | int64 | | Top-down: `SALE` lines with this `accounting_date` |
| 7 | `ledger_gross_minor` | int64 | | Top-down: `SUM(amount_minor)` of `int_ledger__captures` by `booking_date` |
| 8 | `statement_gross_minor` | int64 | | Top-down: `SUM(gross_minor)` of `SALE` lines by `accounting_date` |
| 9 | `gap_minor` | int64 | | `ledger_gross_minor - statement_gross_minor` |
| 10 | `timing_cutoff_minor` | int64 | | Dated component (rules below) |
| 11 | `date_mismatch_minor` | int64 | | Dated component |
| 12 | `amount_mismatch_minor` | int64 | | Dated component |
| 13 | `in_transit_minor` | int64 | | Dated component |
| 14 | `missing_in_statement_minor` | int64 | | Dated component |
| 15 | `missing_in_ledger_minor` | int64 | | Dated component |
| 16 | `before_scope_minor` | int64 | | Dated component |
| 17 | `unexplained_minor` | int64 | yes | `gap_minor` minus the sum of columns 10 to 16. Must be 0 |
| 18 | `statement_fee_minor` | int64 | | Top-down: `SUM(fee_minor)` of `SALE` lines by `accounting_date` |
| 19 | `statement_net_minor` | int64 | | Top-down: `SUM(net_minor)` of `SALE` lines by `accounting_date` |
| 20 | `expected_fee_minor` | int64 | | `SUM(expected_fee_minor)` of `fct_recon_lines` with a statement side, by `accounting_date` |
| 21 | `fee_variance_minor` | int64 | | `SUM(fee_variance_minor)` of the same lines |
| 22 | `exception_count` | int64 | | Rows of `fct_recon_exceptions` by `cause_date`, all five causes |
| 23 | `exception_abs_minor` | int64 | | `SUM(ABS(amount_minor))` of `fct_recon_exceptions` by `cause_date`, over `missing_in_statement`, `missing_in_ledger`, `amount_mismatch` and `fee_mismatch`. Absolute values, so offsetting breaks cannot cancel. `date_mismatch` is counted in column 22 but not summed here: its amount is a whole payment on the wrong day, not money lost |
| 24 | `units_per_usd` | numeric | | Rate for `recon_date` and `currency`, from `int_fx__usd_rates_daily` |
| 25 | `fx_rate_date` | date | | The rate's own date |
| 26 | `fx_carry_days` | int64 | | Days the rate was carried forward |
| 27 | `ledger_gross_usd` | numeric | | `to_usd(ledger_gross_minor, minor_per_major, units_per_usd)` |
| 28 | `statement_gross_usd` | numeric | | `to_usd(statement_gross_minor, ...)` |
| 29 | `gap_usd` | numeric | | `to_usd(gap_minor, ...)`, converted once from `gap_minor` |

Column notes:
- Every INT64 column is wrapped in `COALESCE(..., 0)`, so a day without activity shows zeros and `unexplained_minor` is never NULL.
- `gap_usd` can differ by 0.01 from `ledger_gross_usd - statement_gross_usd`, because each value is rounded once on its own. That is expected and documented in the column description.
- The USD columns can be NULL on a spine day before the first fetched rate (possible in a short dev window). FX is for reporting only; the identity never uses it.

**Dated components.** Each line adds amounts in settlement-currency minor units. Let L be the ledger amount on booking date a, and S the statement gross on accounting date b.

| Line | Component rows it adds |
|---|---|
| matched, a = b | `amount_mismatch`: L - S on b |
| matched, a != b | `timing_cutoff` or `date_mismatch` (by `date_shift`): +L on a and -L on b; plus `amount_mismatch`: L - S on b |
| ledger-only | `in_transit`, `missing_in_statement` or `before_scope` (by `match_status`): +L on a |
| statement-only | `missing_in_ledger` or `before_scope` (by `match_status`): -S on b |

Worked example: L = 1000 booked on 10-20, S = 900 on accounting date 10-21. On 10-20 the gap is +1000, and the components are timing +1000. On 10-21 the gap is -900, and the components are timing -1000 plus amount_mismatch +100. Timing nets to zero across the two days, and the 100 difference appears exactly once.

Fees change net and payout, not gross. They have their own columns and never enter the gross identity.

**Logic, as CTEs.**
1. `as_of`: one row from `stg_recon__as_of`.
2. `ledger_daily`: `int_ledger__captures` grouped by `mid`, `currency`, `booking_date`: count and `SUM(amount_minor)`.
3. `statement_daily`: `stg_psp__settlement_lines` with `record_type = 'SALE'`, grouped by `mid`, `currency`, `accounting_date`: count and the sums of gross, fee and net.
4. `bounds`: `MIN(d)` and `MAX(d)` over one column built with `UNION ALL`: every `booking_date` of `int_ledger__captures` and every `accounting_date` of the `SALE` lines. Do not use `LEAST(MIN(...), MIN(...))`: in BigQuery `LEAST` and `GREATEST` return NULL when any argument is NULL, so a window with ledger rows but no statement lines yet would get an empty spine.
5. `spine`: `mids` (`mid`, `currency`) cross joined with `UNNEST(GENERATE_DATE_ARRAY(first_day, last_day))` as `recon_date`. On empty inputs the array is NULL and the spine has zero rows, which is fine.
6. `component_rows`: from `fct_recon_lines`, five branches joined with `UNION ALL`, each giving (`mid`, `currency`, `day`, `component`, `amount`):
   - every matched line: `'amount_mismatch'`, L - S, on `accounting_date`;
   - matched lines with `date_shift != 'none'`: `date_shift`, +L, on `booking_date`;
   - the same lines: `date_shift`, -L, on `accounting_date`;
   - ledger-only lines: `match_status`, +L, on `booking_date`;
   - statement-only lines: `match_status`, -S, on `accounting_date`.
7. `components_daily`: pivot with one `SUM(IF(component = '<name>', amount, 0))` per component, grouped by `mid`, `currency`, `day`.
8. `fees_daily`: `fct_recon_lines` with `has_statement`, grouped by `mid`, `currency`, `accounting_date`: sums of `expected_fee_minor` and `fee_variance_minor`.
9. `exceptions_daily`: `fct_recon_exceptions` grouped by `mid`, `currency`, `cause_date`: `COUNT(*)`, and `SUM(IF(cause != 'date_mismatch', ABS(amount_minor), 0))`.
10. Final: the spine `LEFT JOIN`s every daily CTE on (`mid`, `currency`, day), then `currencies` on `currency`, then `int_fx__usd_rates_daily` on (`currency`, `day = recon_date`). Compute `gap_minor`, `unexplained_minor` and the three `to_usd()` columns, and cross join `as_of` for `as_of_date`.

`unexplained_minor = gap_minor - (timing_cutoff_minor + date_mismatch_minor + amount_mismatch_minor + in_transit_minor + missing_in_statement_minor + missing_in_ledger_minor + before_scope_minor)`.

**Why the identity can fail.** The top-down totals (steps 2 and 3) come from `int_ledger__captures` and `stg_psp__settlement_lines`. They never pass through the matcher. The components (step 6) come only from `fct_recon_lines`. If the matcher loses a one-sided line, duplicates a line, puts money on the wrong day, flips a sign or forgets a component, one side changes and the other does not. Then `unexplained_minor` is not 0 and `assert_recon_decomposition_closes` fails. One bug it cannot see: a same-day matched line with equal amounts that the matcher drops adds 0 to the gap. `assert_no_money_lost_between_layers` catches that one. These are integrity checks on the matcher. They do not prove that the labels are right; unit tests and, from U1, the seeded self-test cover the labels.

**Contract (`_marts.yml`).** The pattern for the first five columns. The other 24 follow in the order of the table, each with `name`, `data_type` and a description; only `unexplained_minor` also gets the `not_null` constraint.
```yaml
models:
  - name: fct_recon_daily
    description: "One row per MID, currency and day: booked gross vs statement gross, the gap split into dated reason components, and unexplained_minor, which must be 0. Payments SYNTHETIC; USD columns use REAL NBK rates."
    config:
      contract:
        enforced: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [mid, currency, recon_date]
    columns:
      - name: mid
        data_type: string
        constraints:
          - type: not_null
      - name: currency
        data_type: string
        constraints:
          - type: not_null
      - name: recon_date
        data_type: date
        constraints:
          - type: not_null
      - name: as_of_date
        data_type: date
        constraints:
          - type: not_null
      - name: ledger_line_count
        data_type: int64
```

What the contract does on BigQuery:
1. Before building, dbt compares the model's output columns with the contract: names, types and number of columns. Any difference stops the build with a contract error.
2. dbt creates the table with an explicit column list: `create or replace table ... (mid string not null, ...) partition by recon_date cluster by mid as (select <columns in contract order> from (...))`.
3. BigQuery enforces only `not_null`. It does not support a `unique` constraint, so uniqueness stays a test.
4. Every `numeric` column makes dbt print: "Detected columns with numeric type and unspecified precision/scale, this can lead to unintended rounding". On BigQuery, NUMERIC always has 38 digits with 9 after the decimal point, so the warning does not apply. Keep plain `numeric`. BigQuery allows a sized type such as `NUMERIC(38, 9)` only in column definitions, while dbt's contract check also uses the type in a `CAST`, so a sized type is a risk for no gain.

**Tests.** `dbt_utils.unique_combination_of_columns` on (`mid`, `currency`, `recon_date`); the enforced contract; singular tests `assert_recon_decomposition_closes` and `warn_exception_share_7d`.

**Contract.** Yes, the only enforced contract in v1.0.

### What the cut order changes in dbt

The build plan's cut order removes floor items when time runs out. Three items touch dbt:

| Cut-order item | What changes in `dbt/` |
|---|---|
| 2: drop the two warn tests | Delete `warn_exception_share_7d.sql` and `warn_fx_restated.sql`. Nothing else |
| 5: `fct_recon_exceptions` becomes a saved query | Move its SQL to `dbt/analyses/exceptions_queue.sql` and delete its tests. An analysis cannot be referenced with `ref()`, so `fct_recon_daily` then computes `exception_count` and `exception_abs_minor` directly from `fct_recon_lines`, with the same five cause rules and the same `before_scope` exclusion |
| 7: drop the fee checks | Remove `expected_fee_minor`, `fee_tolerance_minor`, `fee_variance_minor` and `is_fee_mismatch` from `fct_recon_lines`; the `fee_mismatch` branch from `fct_recon_exceptions` and from `primary_reason`; columns 20 and 21 from `fct_recon_daily` and its contract; and the fee columns from UT2's `expect`. `statement_fee_minor` and `statement_net_minor` stay |

---

## Macro: `to_usd` (`dbt/macros/to_usd.sql`)

The only macro in v1.0. It converts minor units to USD for reporting, once per MID-day, after summing.

```sql
{% macro to_usd(minor_col, minor_per_major_col, units_per_usd_col) -%}
round(cast({{ minor_col }} as numeric) / {{ minor_per_major_col }} / {{ units_per_usd_col }}, 2)
{%- endmacro %}
```

How it keeps the money rules:
1. `CAST(... AS NUMERIC)` comes first, so every division is NUMERIC / INT64 or NUMERIC / NUMERIC, never INT64 / INT64.
2. `ROUND(..., 2)` is the only rounding stage. BigQuery rounds halfway cases away from zero.
3. A NULL rate gives a NULL result, never a wrong number.

Example: 999000 tiyn at 453.71 KZT per USD is ROUND(999000 / 100 / 453.71, 2) = ROUND(22.0184..., 2) = 22.02 USD.

The reconciliation itself never converts currency in v1.0. Both sides of every match are in the MID's settlement currency.

---

## Tests

### How the three kinds of tests fit together

| Kind | Where | Checks | Runs in |
|---|---|---|---|
| Generic data tests | `data_tests:` in the YAML files | Grain, keys, allowed values, links to seeds, simple row rules | `dbt build` everywhere (host and DAG) |
| Singular data tests | `dbt/tests/*.sql` | Rules across models: the identity, layer preservation, completeness, the business gate | `dbt build` everywhere |
| Unit tests | `dbt/models/_unit_tests.yml` | The logic of one model on hand-made input rows | host only |

How a data test works: it is a `SELECT` that returns the bad rows. Zero rows passes. Any row fails, at the test's severity.

Severity:
- `error` (the default) fails `dbt build`, and dbt skips every model downstream of the tested models.
- `warn` prints a warning and never fails the run or skips anything. The two `warn_*` tests are business gates: exceptions are the pipeline's output, not a pipeline failure.

What `dbt build` does, in lineage order, for each model: run its unit tests (host only), build it only if they pass, then run its data tests. A failure skips everything downstream. A failed unit test stops its model from being built, so the old table stays. A failed data test runs only after its model was rebuilt. For example, `assert_no_money_lost_between_layers` runs after `fct_recon_lines` is rebuilt, and `assert_recon_decomposition_closes` after `fct_recon_daily`. So a red build can leave a new mart with wrong numbers in place. Never read numbers after a red build.

### Generic tests: YAML syntax

In dbt-core 1.12.6, test inputs must sit under `arguments:`, and `where` and `severity` under `config:`. One example of each form:

```yaml
models:
  - name: stg_psp__settlement_lines
    description: "One row per settlement statement line that arrived on or before as_of_date. SYNTHETIC."
    data_tests:
      - dbt_utils.expression_is_true:
          arguments:
            expression: "net_minor = gross_minor - fee_minor"
    columns:
      - name: line_id
        description: "Statement line id, ln_<payment_id>. Primary key."
        data_tests:
          - unique
          - not_null
      - name: record_type
        data_tests:
          - accepted_values:
              arguments:
                values: ["SALE"]
      - name: mid
        data_tests:
          - relationships:
              arguments:
                to: ref('mids')
                field: mid

  - name: stg_fx__rates
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [provider, base, quote, rate_date]
    columns:
      - name: rate
        data_tests:
          - not_null
          - dbt_utils.accepted_range:
              arguments:
                min_value: 300
                max_value: 700
              config:
                where: "quote = 'KZT'"
```

A var inside an argument works: `max_value: "{{ var('fx_max_carry_days') }}"`. `accepted_range` is inclusive by default, which is what both range tests need.

### Generic tests: the complete list

| Model | Column or level | Test |
|---|---|---|
| `stg_recon__as_of` | `as_of_date` | `not_null` |
| `stg_recon__as_of` | `scope_start` | `not_null` |
| `stg_psp__payment_events` | `event_id` | `unique`, `not_null` |
| `stg_psp__payment_events` | `event_type` | `accepted_values` `['payment.captured']` |
| `stg_psp__payment_events` | `mid` | `relationships` to `ref('mids')`, field `mid` |
| `stg_psp__settlement_lines` | `line_id` | `unique`, `not_null` |
| `stg_psp__settlement_lines` | `payment_id` | `not_null` |
| `stg_psp__settlement_lines` | `record_type` | `accepted_values` `['SALE']` |
| `stg_psp__settlement_lines` | model | `dbt_utils.expression_is_true` `net_minor = gross_minor - fee_minor` |
| `stg_psp__settlement_lines` | `mid` | `relationships` to `ref('mids')`, field `mid` |
| `stg_fx__rates` | model | `dbt_utils.unique_combination_of_columns` `[provider, base, quote, rate_date]` |
| `stg_fx__rates` | `rate` | `not_null`; `dbt_utils.accepted_range` 300 to 700, `where: "quote = 'KZT'"` |
| `int_ledger__captures` | `payment_id` | `unique`, `not_null` |
| `int_ledger__captures` | `booking_date`, `expected_accounting_date`, `due_date` | `not_null` each |
| `int_fx__usd_rates_daily` | model | `dbt_utils.unique_combination_of_columns` `[currency, day]` |
| `int_fx__usd_rates_daily` | `units_per_usd`, `rate_date` | `not_null` each |
| `int_fx__usd_rates_daily` | `carry_days` | `dbt_utils.accepted_range` 0 to `var('fx_max_carry_days')` |
| `fct_recon_lines` | `payment_id` | `unique`, `not_null` |
| `fct_recon_lines` | `recon_date`, `match_status`, `primary_reason`, `as_of_date` | `not_null` each |
| `fct_recon_lines` | `match_status` | `accepted_values` `['matched', 'before_scope', 'in_transit', 'missing_in_statement', 'missing_in_ledger']` |
| `fct_recon_lines` | `primary_reason` | `relationships` to `ref('reason_codes')`, field `code` |
| `fct_recon_exceptions` | model | `dbt_utils.unique_combination_of_columns` `[payment_id, cause]` |
| `fct_recon_exceptions` | `amount_minor` | `not_null` |
| `fct_recon_exceptions` | `cause` | `relationships` to `ref('reason_codes')`, field `code` |
| `fct_recon_daily` | model | `dbt_utils.unique_combination_of_columns` `[mid, currency, recon_date]`, plus the contract |

### Singular tests (`dbt/tests/`)

A singular test whose name starts with `warn_` sets its severity in its first line:
```sql
{{ config(severity='warn') }}
```
The other four keep the default, `error`.

Names inside these queries: never use a BigQuery reserved word such as `window`, `range`, `rows` or `lookup` as a CTE name or alias.

**`assert_recon_decomposition_closes`** (error)
- Fails when: any `fct_recon_daily` row has `unexplained_minor != 0`.
- Logic: select `mid`, `currency`, `recon_date`, `gap_minor` and `unexplained_minor` from `fct_recon_daily` where `unexplained_minor != 0`.

**`assert_no_money_lost_between_layers`** (error)
- Fails when, for any MID: the count and `SUM(amount_minor)` of `int_ledger__captures` differ from the count and `SUM(ledger_amount_minor)` of `fct_recon_lines` rows with `has_ledger`; or the count, `SUM(gross_minor)` and `SUM(fee_minor)` of `stg_psp__settlement_lines` with `record_type = 'SALE'` differ from the count and sums of `fct_recon_lines` rows with `has_statement`.
- Logic: four CTEs grouped by `mid` (ledger in, ledger out, statement in, statement out), joined on `mid` with `FULL OUTER JOIN`. Return the rows where any pair differs, comparing with `IS DISTINCT FROM` so a missing MID on one side also counts. The `SALE` filter is the matcher's own filter, so the test stays right when later versions add other record types.

**`assert_redeliveries_identical`** (error)
- Fails when: two deliveries of one `event_id` in the raw source differ in `payment_id`, `mid`, `amount_minor`, `currency`, `event_ts` or `event_type`.
- Logic: from `source('psp', 'payment_events')`, group by `event_id` and keep groups where any of `COUNT(DISTINCT payment_id)`, `COUNT(DISTINCT mid)`, `COUNT(DISTINCT amount_minor)`, `COUNT(DISTINCT currency)`, `COUNT(DISTINCT event_ts)` or `COUNT(DISTINCT event_type)` is above 1. It reads all raw rows, not only those up to `as_of_date`, which is stricter.
- Why: dedup keeps the first delivery. That is only safe if every copy agrees. H4 (U4) plants a changed redelivery, and this test must catch it.

**`assert_arrival_days_complete`** (error)
- Fails when: a day in [`scope_start`, `as_of_date`] has no `payment_events` partition, or a MID has no statement lines on a day in (`scope_start`, `as_of_date`]. The first day is excluded for statements, because statements arrive 1 or 2 days after the accounting date.
- Logic:
  1. A spine of days from `scope_start` to `as_of_date` (`GENERATE_DATE_ARRAY`).
  2. Distinct `_arrival_date` from `source('psp', 'payment_events')`. Return spine days without a match, labelled `payment_events`.
  3. Distinct (`mid`, `_arrival_date`) from `source('psp', 'settlement_lines')`. Cross join the spine with `ref('mids')`, keep days after `scope_start`, and return (day, MID) pairs without a match, labelled `settlement_lines`.
- Why: a missing file is an incident that must fail the run. Without this test it would look like a pile of `missing_in_statement` lines. The v1.0 assumption is that every MID settles lines every day; U6 replaces it with statement headers.

**`warn_exception_share_7d`** (warn)
- Fails when, for a MID over the last `gate_window_days` days ending on `as_of_date`: `SUM(exception_abs_minor) / SUM(ledger_gross_minor)` is above `exception_share_warn`, and `SUM(exception_count)` is at least `exception_min_count`.
- Logic: read `fct_recon_daily` rows with `recon_date BETWEEN DATE_SUB(as_of_date, INTERVAL ({{ var('gate_window_days') }} - 1) DAY) AND as_of_date`, group by `mid`, and compute the share as `SAFE_DIVIDE(CAST(abs_sum AS NUMERIC), CAST(gross_sum AS NUMERIC))`. Compare it with `numeric '{{ var("exception_share_warn") }}'`. Return the MIDs over both limits. The parentheses around `gate_window_days - 1` are required.
- Why a minimum count: about 70 KZT payments a day make the daily share noisy. One break must not trip the gate.

**`warn_fx_restated`** (warn)
- Fails when: one (`provider`, `base`, `quote`, `rate_date`) has more than one `rate_text` across fetches in the raw source.
- Logic: from `source('fx', 'fx_rates')`, group by the four key columns and keep groups with `COUNT(DISTINCT rate_text) > 1`. Also return `STRING_AGG(DISTINCT rate_text)` so the warning shows the values.
- Why a warning: a restated rate is an observation about real data, not a pipeline failure. `stg_fx__rates` keeps the first value either way.

### Unit tests (`dbt/models/_unit_tests.yml`)

A unit test feeds hand-made rows to one model and compares its output with expected rows. It runs on the host only.

Rules for writing them:
1. Write the test first and see it fail before the logic exists. The model file must exist, so start with a stub that returns the right column names with the right types (for example `cast(null as date) as due_date`). The test then fails on the values, which is the "red" to record in `docs/failure_log.md`.
2. Mock every direct parent in `given`: every `ref()` and every `source()` the model reads, seeds included. A missing input gives a "node not found" error.
3. List only the columns the logic uses. dbt fills every other input column with a NULL of the right type.
4. Quote every date and timestamp: `"2026-10-20"`, `"2026-10-20 18:59:59"`. dbt casts each value with `SAFE_CAST`, so a typo becomes NULL, not an error. If a test fails strangely, check the fixture first.
5. Timestamps without a zone are UTC in BigQuery.
6. Give every `expect` row the same keys. dbt takes the list of compared columns from the first `expect` row; other model columns are not compared.
7. The model's direct parents must exist in `analytics_dev`, because dbt reads their column types from the warehouse. After `make dbt-build` they do. On a fresh dataset, see "Running dbt on the host".
8. Short readable ids (`pay_a`) are used on purpose. The generator's id format is not under test here.
9. To pin a var, use `overrides: vars:`.

The shape of one test, with its first rows:
```yaml
unit_tests:
  - name: ut_captures_cutoff_both_directions
    description: "Cut-off shifts in both directions and the inclusive due date (KZT UTC+5, USD UTC-5, lag 2, grace 1)."
    model: int_ledger__captures
    overrides:
      vars:
        statement_grace_days: 1
    given:
      - input: ref('stg_psp__payment_events')
        format: dict
        rows:
          - {event_id: evt_k1, event_type: payment.captured, payment_id: pay_k1, mid: mid_kzt_01, currency: KZT, amount_minor: 999000, event_ts: "2026-10-20 18:59:59"}
      - input: ref('mids')
        format: dict
        rows:
          - {mid: mid_usd_01, psp: psp_alpha, currency: USD, statement_utc_offset_hours: -5, max_settlement_lag_days: 2, fee_bps: 290, fee_fixed_minor: 30, fee_tol_bps: 10, fee_tol_min_minor: 5}
          - {mid: mid_kzt_01, psp: psp_alpha, currency: KZT, statement_utc_offset_hours: 5, max_settlement_lag_days: 2, fee_bps: 250, fee_fixed_minor: 0, fee_tol_bps: 10, fee_tol_min_minor: 500}
    expect:
      format: dict
      rows:
        - {payment_id: pay_k1, booking_date: "2026-10-20", expected_accounting_date: "2026-10-20", due_date: "2026-10-23"}
```
Every test below that mocks `mids` uses exactly these two rows.

#### UT1 `ut_captures_cutoff_both_directions` (v1.0, step S5.3)

Model: `int_ledger__captures`. Inputs: `ref('stg_psp__payment_events')`, `ref('mids')`. Override: `statement_grace_days: 1`.

Given, `stg_psp__payment_events` (all rows `event_type: payment.captured`):

| event_id | payment_id | mid | currency | amount_minor | event_ts (UTC) |
|---|---|---|---|---|---|
| evt_k1 | pay_k1 | mid_kzt_01 | KZT | 999000 | 2026-10-20 18:59:59 |
| evt_k2 | pay_k2 | mid_kzt_01 | KZT | 999000 | 2026-10-20 19:00:00 |
| evt_k3 | pay_k3 | mid_kzt_01 | KZT | 999000 | 2026-10-20 19:30:00 |
| evt_u1 | pay_u1 | mid_usd_01 | USD | 1999 | 2026-10-21 04:59:59 |
| evt_u2 | pay_u2 | mid_usd_01 | USD | 1999 | 2026-10-21 05:00:00 |
| evt_u3 | pay_u3 | mid_usd_01 | USD | 1999 | 2026-10-21 03:00:00 |

Expect:

| payment_id | booking_date | expected_accounting_date | due_date | Why |
|---|---|---|---|---|
| pay_k1 | 2026-10-20 | 2026-10-20 | 2026-10-23 | 18:59:59 + 5 h = 23:59:59 on 10-20; due 10-20 + 2 + 1 |
| pay_k2 | 2026-10-20 | 2026-10-21 | 2026-10-24 | 19:00:00 + 5 h = 00:00:00 on 10-21 |
| pay_k3 | 2026-10-20 | 2026-10-21 | 2026-10-24 | 19:30:00 + 5 h = 00:30:00 on 10-21 |
| pay_u1 | 2026-10-21 | 2026-10-20 | 2026-10-23 | 04:59:59 - 5 h = 23:59:59 on 10-20 |
| pay_u2 | 2026-10-21 | 2026-10-21 | 2026-10-24 | 05:00:00 - 5 h = 00:00:00 on 10-21 |
| pay_u3 | 2026-10-21 | 2026-10-20 | 2026-10-23 | 03:00:00 - 5 h = 22:00:00 on 10-20 |

#### UT2 `ut_lines_status_and_date_shift` (v1.0, step S5.5)

Model: `fct_recon_lines`. Inputs: `ref('stg_recon__as_of')`, `ref('mids')`, `ref('int_ledger__captures')`, `ref('stg_psp__settlement_lines')`.

Given, `stg_recon__as_of`: one row, `as_of_date: "2026-10-28"`, `scope_start: "2026-10-20"`.

Given, `int_ledger__captures` (a mocked parent: its date columns are given directly, not recomputed):

| payment_id | event_id | mid | currency | amount_minor | event_ts (UTC) | booking_date | expected_accounting_date | due_date |
|---|---|---|---|---|---|---|---|---|
| pay_a | evt_a | mid_kzt_01 | KZT | 999000 | 2026-10-26 10:00:00 | 2026-10-26 | 2026-10-26 | 2026-10-29 |
| pay_b | evt_b | mid_kzt_01 | KZT | 999000 | 2026-10-25 10:00:00 | 2026-10-25 | 2026-10-25 | 2026-10-28 |
| pay_c | evt_c | mid_kzt_01 | KZT | 999000 | 2026-10-26 20:00:00 | 2026-10-26 | 2026-10-27 | 2026-10-30 |
| pay_d | evt_d | mid_usd_01 | USD | 1999 | 2026-10-26 12:00:00 | 2026-10-26 | 2026-10-26 | 2026-10-29 |

Given, `stg_psp__settlement_lines` (all rows `record_type: SALE`):

| line_id | statement_id | payment_id | mid | currency | captured_ts (UTC) | accounting_date | gross_minor | fee_minor | net_minor | statement_arrival_date |
|---|---|---|---|---|---|---|---|---|---|---|
| ln_c | stmt_mid_kzt_01_20261028 | pay_c | mid_kzt_01 | KZT | 2026-10-26 20:00:00 | 2026-10-27 | 999000 | 24975 | 974025 | 2026-10-28 |
| ln_d | stmt_mid_usd_01_20261028 | pay_d | mid_usd_01 | USD | 2026-10-26 12:00:00 | 2026-10-27 | 1999 | 88 | 1911 | 2026-10-28 |
| ln_e | stmt_mid_kzt_01_20261027 | pay_e | mid_kzt_01 | KZT | 2026-10-26 10:00:00 | 2026-10-26 | 999000 | 24975 | 974025 | 2026-10-27 |
| ln_f | stmt_mid_usd_01_20261020 | pay_f | mid_usd_01 | USD | 2026-10-18 12:00:00 | 2026-10-18 | 1999 | 88 | 1911 | 2026-10-20 |

Expect:

| payment_id | recon_date | match_status | date_shift | is_amount_mismatch | expected_fee_minor | fee_tolerance_minor | is_fee_mismatch | primary_reason | is_exception |
|---|---|---|---|---|---|---|---|---|---|
| pay_a | 2026-10-26 | in_transit | null | false | null | null | false | in_transit | false |
| pay_b | 2026-10-25 | missing_in_statement | null | false | null | null | false | missing_in_statement | true |
| pay_c | 2026-10-26 | matched | timing_cutoff | false | 24975 | 999 | false | timing_cutoff | false |
| pay_d | 2026-10-26 | matched | date_mismatch | false | 88 | 5 | false | date_mismatch | true |
| pay_e | 2026-10-26 | missing_in_ledger | null | false | 24975 | 999 | false | missing_in_ledger | true |
| pay_f | 2026-10-18 | before_scope | null | false | 88 | 5 | false | before_scope | false |

Why each row:
- pay_a: ledger-only, `as_of_date` 10-28 < due 10-29, so it is waiting.
- pay_b: ledger-only, due 10-28 and `as_of_date` 10-28. The due date is inclusive, so it is missing. Mutation 2 flips exactly this row.
- pay_c: both sides; accounting 10-27 differs from booking 10-26 but equals the expected date (a KZT capture after 19:00 UTC). A benign cut-off shift.
- pay_d: both sides; the expected date is 10-26 (a USD capture at 12:00 UTC is 07:00 local), but the PSP booked 10-27. An exception.
- pay_e: statement-only, captured 10-26, inside scope. A lost webhook.
- pay_f: statement-only, captured 10-18, before `scope_start` 10-20. Out of scope, not an exception.
- Fees: every statement fee equals the expected fee (24975 for KZT gross 999000, 88 for USD gross 1999; see the worked examples under `fct_recon_lines`), so no fee flag fires.

#### UT3 `ut_events_dedup_first_delivery` (U1, step S11.1)

Model: `stg_psp__payment_events`. Inputs: `source('psp', 'payment_events')`, `ref('stg_recon__as_of')`.

Given, `stg_recon__as_of`: `as_of_date: "2026-10-21"`, `scope_start: "2026-10-20"`.

Given, the source (all rows `event_type: payment.captured`). The rows for `evt_y` are deliberately out of order:

| delivery_id | event_id | payment_id | mid | currency | amount_minor | event_ts | delivered_ts | _arrival_date |
|---|---|---|---|---|---|---|---|---|
| dlv_x_1 | evt_x | pay_x | mid_kzt_01 | KZT | 999000 | 2026-10-20 20:15:07 | 2026-10-20 20:15:30 | 2026-10-20 |
| dlv_x_2 | evt_x | pay_x | mid_kzt_01 | KZT | 999000 | 2026-10-20 20:15:07 | 2026-10-21 02:10:00 | 2026-10-21 |
| dlv_y_2 | evt_y | pay_y | mid_usd_01 | USD | 1999 | 2026-10-21 19:59:50 | 2026-10-21 20:00:00 | 2026-10-21 |
| dlv_y_1 | evt_y | pay_y | mid_usd_01 | USD | 1999 | 2026-10-21 19:59:50 | 2026-10-21 20:00:00 | 2026-10-21 |
| dlv_y_3 | evt_y | pay_y | mid_usd_01 | USD | 1999 | 2026-10-21 19:59:50 | 2026-10-22 01:00:00 | 2026-10-22 |

Expect:

| event_id | first_delivery_id | first_delivered_ts | first_arrival_date | copies_received |
|---|---|---|---|---|
| evt_x | dlv_x_1 | 2026-10-20 20:15:30 | 2026-10-20 | 2 |
| evt_y | dlv_y_1 | 2026-10-21 20:00:00 | 2026-10-21 | 2 |

What it pins: the earlier delivery wins (evt_x, across two arrival days); a tie on `delivered_ts` is broken by `delivery_id` (evt_y); a delivery after `as_of_date` is neither kept nor counted (`dlv_y_3`, so `copies_received` is 2, not 3).

#### UT4 `ut_lines_fee_boundary_and_two_causes` (U1, step S11.2)

Model: `fct_recon_lines`. Inputs: the same four as UT2, with the same `stg_recon__as_of` row (`as_of_date` 2026-10-28, `scope_start` 2026-10-20) and the same `mids` rows.

Given, `int_ledger__captures` (all `mid_kzt_01`, KZT, `event_ts` 2026-10-26 10:00:00, `booking_date` 2026-10-26, `expected_accounting_date` 2026-10-26, `due_date` 2026-10-29):

| payment_id | event_id | amount_minor |
|---|---|---|
| pay_g | evt_g | 999000 |
| pay_h | evt_h | 999000 |
| pay_i | evt_i | 999000 |
| pay_j | evt_j | 1020 |

Given, `stg_psp__settlement_lines` (all `mid_kzt_01`, KZT, `SALE`, `captured_ts` 2026-10-26 10:00:00, `accounting_date` 2026-10-26, `statement_arrival_date` 2026-10-27, `statement_id` stmt_mid_kzt_01_20261027):

| line_id | payment_id | gross_minor | fee_minor | net_minor |
|---|---|---|---|---|
| ln_g | pay_g | 999000 | 25974 | 973026 |
| ln_h | pay_h | 999000 | 25975 | 973025 |
| ln_i | pay_i | 998900 | 26973 | 971927 |
| ln_j | pay_j | 1020 | 26 | 994 |

Fee arithmetic, KZT terms (250 bps, fixed 0, tolerance 10 bps with a minimum of 500):

| Line | Expected fee | Tolerance | Variance |
|---|---|---|---|
| ln_g | DIV(999000 x 250 + 5000, 10000) = DIV(249755000, 10000) = 24975 | GREATEST(500, DIV(9990000 + 9999, 10000)) = 999 | 25974 - 24975 = 999 |
| ln_h | 24975 | 999 | 25975 - 24975 = 1000 |
| ln_i | DIV(998900 x 250 + 5000, 10000) = DIV(249730000, 10000) = 24973 | GREATEST(500, DIV(9989000 + 9999, 10000)) = 999 | 26973 - 24973 = 2000 |
| ln_j | DIV(1020 x 250 + 5000, 10000) = DIV(260000, 10000) = 26 (the exact fee is 25.5) | GREATEST(500, DIV(10200 + 9999, 10000)) = 500 | 26 - 26 = 0 |

Expect:

| payment_id | amount_diff_minor | is_amount_mismatch | expected_fee_minor | fee_tolerance_minor | fee_variance_minor | is_fee_mismatch | primary_reason | is_exception |
|---|---|---|---|---|---|---|---|---|
| pay_g | 0 | false | 24975 | 999 | 999 | false | matched | false |
| pay_h | 0 | false | 24975 | 999 | 1000 | true | fee_mismatch | true |
| pay_i | 100 | true | 24973 | 999 | 2000 | true | amount_mismatch | true |
| pay_j | 0 | false | 26 | 500 | 0 | false | matched | false |

What it pins:
- the inclusive boundary: 999 is within, 1000 is flagged;
- two causes on one line, with `amount_mismatch` winning `primary_reason` by precedence (30 before 40);
- half-up rounding, asserted directly on `expected_fee_minor`. Under mutation 5 (floor), ln_j's expected fee becomes DIV(255000, 10000) = 25 and ln_i's becomes DIV(249725000, 10000) = 24972, so UT4 goes red. The variance on ln_j would only move to 1, far inside the 500 tolerance, which is why the expected fee is asserted directly.

### Tests we do not write

- No tautological tests: no uniqueness test filtered by a `ROW_NUMBER` rank, and no identity computed from its own residual.
- No `not_null` tests on sources: BigQuery enforces the REQUIRED columns at load time.
- No tests on the seeds themselves: a duplicated seed row would fan out a join, and the downstream grain tests (`int_ledger__captures.payment_id`, `fct_recon_exceptions`, `fct_recon_daily`) catch that.
- No source freshness in v1.0 (see "Sources").

---

## Mutation check (step S7.5, and mutation 5 in S11.3)

A mutation is a deliberate one-line bug. If a test goes red, the test is real. Only after this check may the README or a slide say a test "fails when ...".

| # | Mutation | File | Expected red tests | When |
|---|---|---|---|---|
| 1 | `FULL OUTER JOIN` changed to `INNER JOIN` | `dbt/models/marts/fct_recon_lines.sql` | `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers` | S7.5 |
| 2 | `as_of_date < due_date` changed to `<=` | `dbt/models/marts/fct_recon_lines.sql` | UT2 | S7.5 |
| 3 | the `QUALIFY` line removed | `dbt/models/staging/stg_psp__payment_events.sql` | `unique` on `stg_psp__payment_events.event_id`, `unique` on `int_ledger__captures.payment_id` | S7.5 |
| 4 | the `record_type = 'SALE'` filter moved from the statement CTE to after the join | `dbt/models/marts/fct_recon_lines.sql` | `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers` | S7.5 |
| 5 | half-up fee rounding (`+ 5000`) changed to floor | `dbt/models/marts/fct_recon_lines.sql` | UT4 | S11.3 |

Run each mutation with `dbt run` followed by `dbt test`, not with `make dbt-build`. `dbt build` refuses to build a model whose unit test fails, and skips everything downstream of any failed test. Mutation 1, for example, would turn UT2 red, stop `fct_recon_lines` from being rebuilt, and report the two identity tests as skipped instead of red. `dbt run` builds every model; `dbt test` then runs every data test and unit test on its own.

Procedure:
1. Start from a green `make dbt-build` on the 7 dev days. Note the commit SHA.
2. `git switch -c mutation-check`. This branch is never pushed.
3. In a terminal:
   ```
   cd dbt
   export RAW_DATASET=raw_dev DBT_PROFILES_DIR="$PWD" DBT_KEYFILE="$(cd .. && pwd)/keys/sa.json"
   ```
4. For each mutation in the table:
   1. Apply the one change.
   2. `uv run dbt run --target dev`. If the SQL no longer compiles, the mutation is broken: fix the mutation, not the model.
   3. `uv run dbt test --target dev`.
   4. Copy every test that ended in FAIL or ERROR from the summary at the end of the output, or from `dbt/target/run_results.json` (entries with `"status": "fail"` or `"status": "error"`).
   5. Revert: `git checkout -- <file>`.
5. `git switch main` (or the working branch), `git branch -D mutation-check`, then `make dbt-build` to rebuild `analytics_dev` from the correct code.
6. Write the results in `docs/testing.md`.

Observed red tests can be more than the expected ones (mutation 1 also turns UT2 red). Record all of them. A mutation counts as caught when at least one expected test is red.

`docs/testing.md` template:

```markdown
# Testing

Three kinds of evidence, kept separate:
1. Integrity tests on the matcher (the identity and layer preservation).
2. Logic tests (dbt unit tests on hand-made rows).
3. Behaviour on planted data (the seeded self-test, from v1.1).

## Mutation check

Run on [date] on the dev datasets, starting from commit [sha].

| # | Mutation | File | Expected red | Observed red | Result |
|---|---|---|---|---|---|
| 1 | FULL OUTER JOIN changed to INNER JOIN | dbt/models/marts/fct_recon_lines.sql | assert_recon_decomposition_closes, assert_no_money_lost_between_layers | [names] | [caught or missed] |
| 2 | as_of_date < due_date changed to <= | dbt/models/marts/fct_recon_lines.sql | UT2 | [names] | [caught or missed] |
| 3 | QUALIFY removed | dbt/models/staging/stg_psp__payment_events.sql | unique event_id, unique payment_id | [names] | [caught or missed] |
| 4 | SALE filter moved after the join | dbt/models/marts/fct_recon_lines.sql | assert_recon_decomposition_closes, assert_no_money_lost_between_layers | [names] | [caught or missed] |

Caught: [K] of [K].
```

The number "[K] of [K]" in the slide and README comes only from this table.

---

## Incremental models: none in v1.0

### Why v1.0 has none

1. Every mart is a full rebuild (`CREATE OR REPLACE TABLE ... AS SELECT`) from all loaded raw partitions. At about 0.1 MB of raw data a day, a rebuild writes about 1 to 2 MB.
2. Idempotency belongs to the raw layer: each run replaces exactly one raw partition per table with one load job.
3. A full rebuild makes every mart a pure function of what is loaded. That is the property the rerun proof checks.
4. The course pattern `where date_col > (select max(date_col) from {{ this }})` depends on what the table already holds. It cannot reprocess an arbitrary old day, so it is not used.

### What the sandbox refuses

dbt-bigquery 1.12.1 turns these features into DML, which the sandbox rejects ("DML queries are not allowed in the free tier"):

| Feature | What dbt runs | Sandbox |
|---|---|---|
| `incremental` with the default strategy `merge` | `MERGE` | refused |
| `insert_overwrite` without `copy_partitions` (static or dynamic) | `DECLARE`, `SET`, then `MERGE` | refused |
| `microbatch` without `copy_partitions` | the same `insert_overwrite` path | refused |
| `time_ingestion_partitioning: true` | creates the table, then `INSERT` | refused, even on the first run |
| snapshots | `CREATE TABLE AS` on the first run, `MERGE` on every later run | refused from the second run |
| Elementary | `insert into ... values` | refused |

### The sandbox-safe pattern (U5 only, gated on probe P8)

dbt-bigquery 1.12.1 can replace partitions without DML when `copy_partitions` is on. For an incremental `insert_overwrite` model with dynamic partitions it runs:
1. the first time (or after the table is dropped): one `CREATE OR REPLACE TABLE ... PARTITION BY ... AS (...)`;
2. every later time: a temp table built with `CREATE OR REPLACE TABLE <model>__dbt_tmp` (with a 12-hour expiry), then `select distinct <partition>` from it, then one copy job per partition into `<model>$YYYYMMDD` with `WRITE_TRUNCATE`, then `drop table if exists` on the temp table.

There is no `MERGE` and no `INSERT` on that path. Copy jobs are a free operation, but the data is written twice (temp table, then copy), and a failed run leaves a temp table for 12 hours. Both count toward the lifetime storage quota.

U5's model `fct_recon_status_daily` uses exactly this config:
```sql
{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={'field': 'as_of_date', 'data_type': 'date', 'granularity': 'day', 'copy_partitions': true},
    on_schema_change='fail',
    full_refresh=false
) }}
```

Rules for it:
1. Dynamic partitions only. Never set a `partitions` list (the static copy path has a history of bugs).
2. The partition column must never be NULL, and it gets a `not_null` test. Open bug dbt-adapters #2086 crashes this path on a NULL partition value. The bug's suggested workaround, removing `copy_partitions`, falls back to `MERGE` and is not available here.
3. Never add `time_ingestion_partitioning`. The dbt docs' own `copy_partitions` example sets it. Do not copy that example.
4. `full_refresh=false` keeps `dbt build --full-refresh` from rebuilding the history. To reset it on purpose, drop the table in the BigQuery console (`DROP TABLE` is DDL, which the sandbox allows).
5. The model reads only arrivals up to `var('run_date')`, which the DAG passes. That changes the `dbt_build` command; `docs/specs/airflow_and_docker.md` owns that change when U5 starts.
6. Proof that it ran without DML (step S15.3): `logs/dbt.log` contains a line with "Copying table(s)", and a case-insensitive search for "merge into" or "insert into" in the same log finds 0 lines.

### Fallback

If probe P8 fails, or the copy path misbehaves, `fct_recon_status_daily` becomes a full-rebuild `table` model. ADR-0008 records the choice and the evidence. Probe P8 itself is described in `docs/specs/bigquery_sandbox_and_costs.md`. It needs a throwaway dbt project whose target dataset is `probe`, because this project has no custom schemas and only the targets `dev` and `airflow`.

---

## Selectors

v1.0 has no `selectors.yml`. Every command uses explicit flags, so there is one less file to explain. dbt 1.12 also warns when `--selector` is combined with `--select` or `--exclude`, and then ignores the latter two.

The selections used in this project:

| Purpose | Flags |
|---|---|
| The DAG: everything except unit tests | `dbt build --exclude-resource-type unit_test` |
| Host: only unit tests | `dbt test --select "test_type:unit"` |
| Host: one model and its tests | `dbt build --select fct_recon_lines` |
| Host: one model and everything downstream | `dbt build --select fct_recon_lines+` |
| Host: one saved query | `dbt show --select exceptions_queue` |

---

## Running dbt on the host

Every host command runs from `dbt/` with these variables set. The Makefile sets them for its targets. For a command without a make target, export them first:
```
cd dbt
export RAW_DATASET=raw_dev DBT_PROFILES_DIR="$PWD" DBT_KEYFILE="$(cd .. && pwd)/keys/sa.json"
```
`GCP_PROJECT` arrives from the root `.env` through dbt's own `.env` loading.

| Make target | The dbt command it runs (from `dbt/`) | When |
|---|---|---|
| `make setup` | `uv run dbt deps` (after `uv sync`) | first setup; after `dbt clean` |
| `make doctor` | `uv run dbt --version` (plus `which -a dbt`) | before anything else |
| `make dbt-build` | `uv run dbt build --target dev` | the normal host build: seeds, models, unit tests and data tests |
| `make dbt-unit` | `uv run dbt test --select "test_type:unit" --target dev` | fast logic checks while writing a model |

Commands without a make target:

| Goal | Command (from `dbt/`, variables exported) |
|---|---|
| Time travel to day X | `uv run dbt build --target dev --vars '{"as_of_date": "2026-10-28"}'`, then `uv run dbt build --target dev` |
| Mutation check | `uv run dbt run --target dev`, then `uv run dbt test --target dev` (see "Mutation check") |
| Parse only (also the clean-clone check S10.3 and CI in U2) | `uv run dbt parse`. It never connects to BigQuery and never opens the key file, but the profile is still read, so CI and the clean-clone check set the same dummy values: `GCP_PROJECT=ci-dummy RAW_DATASET=raw_dev DBT_KEYFILE=/nonexistent/sa.json` |
| Docs | see "Documentation" |
| Saved queries | see "Saved analyses" |

Unit tests on a fresh `analytics_dev` dataset. Unit tests need their models' direct parents to exist in the warehouse. If `make dbt-build` has never run:
1. `make bq-setup` (the raw tables in `raw_dev` exist).
2. `uv run dbt seed --target dev`.
3. `uv run dbt run --target dev --empty`. `--empty` builds every model with zero input rows: cheap, and enough for the column types.
4. `make dbt-unit`.
5. `make dbt-build`. This step matters: after step 3 the dev views are defined with "zero rows" built in, and only a normal build restores them.

Use `dbt run --empty` here, not `dbt build --empty`. Unit tests should run without `--empty`.

---

## How `dbt build` runs from Airflow

The task `dbt_build` in the DAG `recon_daily` (defined in `docs/specs/airflow_and_docker.md`) is a BashOperator with `pool="dbt_serial"`, `append_env=True` and `retries=0`. It runs after the three `load_raw` tasks. Its command, exactly:

```
cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt build --target airflow --exclude-resource-type unit_test --target-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/target --log-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/logs
```

| Part | Why |
|---|---|
| `cd /opt/airflow/dbt` | dbt finds `dbt_project.yml` and `dbt_packages/` here. No `.env` exists here or above it |
| `/opt/airflow/dbt_venv/bin/dbt` | The separate dbt venv. dbt cannot share Airflow's Python environment (dbt-bigquery needs google-cloud-storage below 3.2 and dbt-core needs pathspec below 1.1; Airflow 3.3.2 pins newer versions) |
| `build` | Seeds (3 load jobs), the 9 models, every data test, in lineage order |
| `--target airflow` | Builds `analytics` from `raw` |
| `--exclude-resource-type unit_test` | Unit tests check code, not data. They belong on the host |
| `--target-path`, `--log-path` | One folder per run date, so every run keeps its own `run_results.json`, `manifest.json`, compiled SQL and `dbt.log`. A reprocess of the same date overwrites that date's folder |
| `{{ data_interval_start \| ds }}` | The run date R. It names folders only. dbt's logic never sees it: `as_of_date` comes from the data |

Environment the command relies on, set in the compose file's `x-airflow-common` section: `GCP_PROJECT`, `RAW_DATASET=raw`, `DBT_PROFILES_DIR=/opt/airflow/dbt`, `DBT_KEYFILE=/opt/airflow/keys/sa.json`. `append_env=True` adds them to the task's environment without losing `PATH` and `HOME`.

What the task state means:

| dbt exit code | Meaning | Task |
|---|---|---|
| 0 | Everything passed. Warnings (the `warn_*` tests, the numeric warning) are allowed | success |
| 1 | A model failed, or an error-severity test failed | failed |
| 2 | dbt itself crashed (bad profile, missing env var, missing packages) | failed |

The BashOperator skips a task only on exit code 99, which dbt never uses.

Concurrency. The pool `dbt_serial` has one slot, so a scheduled run and a backfill run never build dbt at the same time. Two builds on one dataset would race on `CREATE OR REPLACE`. Inside one build, dbt runs up to 4 nodes at once (`threads: 4`).

Never add to this command in v1.0:
- `--vars`: the marts must not depend on Airflow parameters;
- `--warn-error`: the `warn_*` tests must stay warnings;
- `--full-refresh`: no effect on views and tables, and later it would wipe U5's history;
- `dbt deps`: packages come from the host through the mount.

---

## Reading a failed build

1. Open the `dbt_build` task log in the Airflow UI (http://localhost:8083). The summary near the end names each failing node.
2. Read `runs/dbt/<D>/logs/dbt.log`. It holds every SQL statement dbt sent, with BigQuery's error text.
3. Find the failing test's compiled SQL:
   - singular tests: `runs/dbt/<D>/target/compiled/ledger_vs_statement/tests/<test_name>.sql`;
   - generic tests: `runs/dbt/<D>/target/compiled/ledger_vs_statement/models/<folder>/<yml file>/<test_name>.sql`.
4. Paste that SQL into the BigQuery console. The rows it returns are the bad rows.
5. Fix the cause, write the entry in `docs/failure_log.md`, and rerun only dbt for that day: `airflow tasks clear recon_daily -s <D> -e <D> -t dbt_build -y` (inside the scheduler; see the "Operations runbook" heading in `docs/specs/airflow_and_docker.md`).

`runs/dbt/<D>/target/run_results.json` has one entry per node with `unique_id`, `status` and `adapter_response` (BigQuery's `bytes_processed`, `bytes_billed`, `slot_ms` and `job_id`). For example, `scripts/results.py` confirms the latest run's identity test passed by finding the entry whose `unique_id` is `test.ledger_vs_statement.assert_recon_decomposition_closes` and checking `"status": "pass"`.

Common failures:

| Message or symptom | Cause | Fix |
|---|---|---|
| `Env var required but not provided: 'DBT_KEYFILE'` | dbt run outside make, or the compose variable missing | export the variables, or fix the compose file |
| "Target dev must read RAW_DATASET=raw_dev" | the guard in `stg_recon__as_of` | run through make, or export `RAW_DATASET=raw_dev` |
| `dbt found 1 package(s) specified in packages.yml, but only 0 package(s) installed` | `dbt/dbt_packages/` is empty | `make setup` on the host |
| "This version of dbt is not supported" | the dbt v2 binary, or a dbt outside 1.12.x | use `uv run dbt` or the container venv path |
| "DML queries are not allowed in the free tier" | an incremental, snapshot or hook issued DML | change the materialization (see "Incremental models") |
| "This model has an enforced contract that failed" | `fct_recon_daily` returns a column whose name or type differs from `_marts.yml`, or a different number of columns | align the SQL and the contract |
| "Not able to get columns for unit test ... because the relation doesn't exist" | a unit test's parent was never built | `make dbt-build`, or the `--empty` steps in "Running dbt on the host" |
| `assert_arrival_days_complete` fails | a day or a MID file is missing in the window | load the missing day with a one-day backfill, then clear the latest `dbt_build` |

---

## Saved analyses (`dbt/analyses/`)

An analysis is a SQL file that dbt compiles (filling in `ref()`) but never builds. These two are the demo queries. Both are read-only.

`exceptions_queue.sql`
- Purpose: the analyst queue, oldest and largest first.
- Shape: select `cause`, `mid`, `currency`, `payment_id`, `amount_minor`, `cause_date`, `age_days`, `analyst_action`, `event_id`, `line_id` and `statement_id` from `ref('fct_recon_exceptions')`, ordered by `age_days` descending, then `ABS(amount_minor)` descending.
- If cut-order item 5 is taken, this file holds the exception logic itself, reading `ref('fct_recon_lines')`.

`one_mid_day_bridge.sql`
- Purpose: show one MID-day's bridge: the gap, each component, `unexplained_minor`, and the lines behind every non-zero component.
- Shape: a `params` CTE with two literals that I edit before the demo (`mid`, `day`); the matching row of `ref('fct_recon_daily')`; the rows of `ref('fct_recon_lines')` for that MID where `booking_date = day` or `accounting_date = day`, with their status, date shift and amounts.

How to run them:
```
uv run dbt show --select exceptions_queue --target dev --limit 50
uv run dbt compile --select one_mid_day_bridge --target airflow
```
`dbt show` prints at most 5 rows unless `--limit` is given. `dbt compile` writes the SQL to `dbt/target/compiled/ledger_vs_statement/analyses/one_mid_day_bridge.sql`, ready to paste into the BigQuery console. With `--target airflow`, the SQL reads the proof dataset `analytics`, which is read-only use of the host and is allowed.

---

## Documentation

Descriptions live in the YAML files: every model, seed and source table description starts with "One row per", and every column has a description. A source's own description says what its tables hold, because a source has no rows of its own. The FX models say that the carry-forward is a project convention. The payment models and sources say SYNTHETIC; the FX ones say REAL.

Generate and view the docs on the host:
```
uv run dbt docs generate --target dev --static
open target/static_index.html
```
1. `dbt docs generate` compiles the project and runs read-only catalog queries. It writes `target/index.html`, `target/manifest.json` and `target/catalog.json`.
2. `--static` also writes `target/static_index.html`, one file with the manifest and catalog inside. A browser opens it directly from disk, with no server. It is the file to use in a demo.
3. If the catalog queries ever fail in the sandbox, add `--empty-catalog`. The lineage graph and descriptions still work.
4. The local server also works: `uv run dbt docs serve --port 8090`. Never use the default port 8080: another local stack uses it, and 8082 and 8083 are taken by the Airflow stacks.

Not in v1.0:
- publishing on GitHub Pages (v1.x: copy `static_index.html` to a Pages folder as `index.html`);
- an exposure for the reconciliation report (v1.x);
- `persist_docs` to BigQuery (see "Project file").

The dbt docs pages online now describe dbt v2, where `docs generate` works differently. The flags above are the dbt-core 1.12.6 ones.

---

## Never in this project

Materializations and features:
- `merge` incrementals, and `insert_overwrite` or `microbatch` without `copy_partitions`;
- `time_ingestion_partitioning`, anywhere;
- snapshots;
- Python models;
- `hours_to_expiration` on any model, `partition_expiration_days` or `require_partition_filter`;
- `store_failures`, custom schemas, and a `generate_schema_name` override;
- `on-run-start` and `on-run-end` hooks;
- `INSERT`, `UPDATE`, `DELETE` or `MERGE` in any model, macro, test, hook or analysis.

SQL:
- `CURRENT_DATE()`, `CURRENT_TIMESTAMP()` or any other clock in a model;
- `POW()`, INT64 / INT64, `CEIL` on INT64, `ROUND(x * bps / 10000)`;
- FLOAT64 anywhere on the money path, including float literals in money math;
- `SELECT *` from a source in a mart;
- a `FULL OUTER JOIN` without an equality condition, or with `OR`.

Packages and tools:
- Elementary, calogica dbt-expectations, dbt_project_evaluator 2.x;
- the bare `dbt` command (`~/.local/bin/dbt`, dbt v2);
- `dbt freshness` (a dbt v2 command);
- `--target airflow` on the host for any command except `dbt compile` and `dbt show`;
- `--vars`, `--warn-error` or `--full-refresh` in the DAG's dbt command;
- `dbt deps` inside the container;
- a secret, key or path to a key in any file under `dbt/`.

---

## Facts checked for this specification

Checked on 2026-11-01. The official docs come first. Where a docs page now describes only dbt v2, the dbt v1 behaviour was read in the source code of the pinned packages: wheels downloaded from PyPI, sha256 matched against PyPI, read as text, never run.

Official docs:
- BigQuery configs (last updated 2026-10-20): `partition_by` keys, `cluster_by`, `labels` on tables and views (model labels replace project labels, no merge), `copy_partitions` works only with dynamic `insert_overwrite`, the docs' `copy_partitions` example also sets `time_ingestion_partitioning`, `merge` is the default strategy, `require_partition_filter`, `partition_expiration_days`, `hours_to_expiration`. https://docs.getdbt.com/reference/resource-configs/bigquery-configs
- Query comment with `job-label: true` (2025-06-12). https://docs.getdbt.com/reference/project-configs/query-comment
- Unit tests (2026-09-14): `given` and `expect`; list every `ref` and `source` as an input; only the relevant columns are needed; direct parents must exist in the warehouse, and `--empty` is the cheap way; `dbt test --select "test_type:unit"`; run unit tests only in dev or CI; tables must be aliased to unit-test join logic; every field of a BigQuery STRUCT is needed. https://docs.getdbt.com/docs/build/unit-tests
- Unit test properties (2026-09-14): `overrides` with `macros`, `vars` and `env_vars`. https://docs.getdbt.com/reference/resource-properties/unit-tests
- `--exclude-resource-type unit_test` for `dbt build` (2026-09-08). https://docs.getdbt.com/reference/global-configs/resource-type
- Upgrading to v1.12 (2026-10-16): `.env` is loaded from the working directory and shell variables win; `bigquery_use_standard_sql_for_partitions` now defaults to true; combining `--selector` with `--select` or `--exclude` warns. https://docs.getdbt.com/docs/dbt-versions/core-upgrade/upgrading-to-v1.12
- Behavior changes (2026-10-19): `require_generic_test_arguments_property` matured in 1.10.8, so `arguments:` is the default behaviour. https://docs.getdbt.com/reference/global-configs/behavior-changes
- Contracts (2026-09-08) and constraints (2026-10-27): every column needs a `data_type`; BigQuery enforces only `not_null`, cannot define `unique`; constraints apply to tables and incrementals. https://docs.getdbt.com/reference/resource-configs/contract and https://docs.getdbt.com/reference/resource-properties/constraints
- Source freshness (2026-10-12): `freshness` and `loaded_at_field` sit under `config:`; without `loaded_at_field`, dbt uses warehouse metadata. https://docs.getdbt.com/reference/resource-properties/freshness
- Seed `column_types` under `config:` (2026-07-18). https://docs.getdbt.com/reference/resource-configs/column_types
- Severity (2026-04-29): `{{ config(...) }}` at the top of a singular test; `warn` never errors. https://docs.getdbt.com/reference/resource-configs/severity
- `dbt build` (2026-09-16): a failed test skips downstream resources; unit tests, then the model, then its data tests; `--empty`; seeds are included. https://docs.getdbt.com/reference/commands/build
- dbt_utils 1.4.1 README: `arguments:` for `expression_is_true`, `accepted_range` (inclusive by default) and `unique_combination_of_columns`; `where` goes under `config:`. https://raw.githubusercontent.com/dbt-labs/dbt-utils/1.4.1/README.md
- BigQuery data types: NUMERIC has 38 digits with 9 after the decimal point; sized types such as `NUMERIC(P, S)` are allowed only for columns and script variables. https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/data-types
- The dbt BigQuery setup page (2026-10-07) and the docs command page (2026-10-23) now describe dbt v2 only. Their v1 equivalents were read in the source below. https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup and https://docs.getdbt.com/reference/commands/cmd-docs

Source code read:
- dbt-bigquery 1.12.1 (sha256 8f7e0eff7f4a5f8a...d745): `credentials.py` (methods `oauth` and `service-account`; `project` and `dataset` are aliases of `database` and `schema`; `job_retries` defaults to 1; `priority` is `interactive` or `batch`); `connections.py` (job labels parsed from the JSON query comment, cleaned to `[a-z0-9_-]` and 63 characters, plus a `dbt_invocation_id` label on every job); `relation_configs/_partition.py` (`data_type` defaults to `date`, `granularity` to `day`, `copy_partitions` to false); `materializations/incremental.sql` (default strategy `merge`; `copy_partitions` needs `insert_overwrite` or `microbatch`); `incremental_strategy/insert_overwrite.sql` (the dynamic copy path: temp CTAS, `select distinct`, copy jobs, `drop table`); `materializations/seed.sql` (drop, then a load job, then `alter table set options`); `materializations/table.sql` (drop first when partitioning or clustering changes); `utils/get_columns_spec_ddl.sql` (the contract column check).
- dbt-core 1.12.6 (sha256 a14fb6724a557dea...325e): `cli/main.py` (`load_dotenv(find_dotenv(usecwd=True), override=False)`; the commands include `source freshness` but no top-level `freshness`); `cli/params.py` (`--static`, `--empty-catalog`, `--port` default 8080, `--host` default 127.0.0.1, `dbt show --limit` default 5, `--target-path`, `--log-path`, `--exclude-resource-type`); `tracking.py` (`.user.yml` is written to the profiles folder only when usage stats are on); `contracts/project.py` (`send_anonymous_usage_stats` is a project flag; `require_generic_test_arguments_property` defaults to true); `task/debug.py` (`dbt debug` runs `git --help`); `node_types.py` (`dbt show` can select analyses); `utils/utils.py` (exit codes 0, 1, 2).
- dbt-adapters 1.24.5 (sha256 32345118b9211607...3411): `unit_test_sql/get_fixture_sql.sql` (missing input columns become `SAFE_CAST(null AS <type>)`; string values are quoted, then `SAFE_CAST`; an unknown column name is an error); `materializations/tests/unit.sql` (an empty temp table, then a comparison over the first `expect` row's keys); `adapters/columns.sql` (the numeric warning).
- dbt-common 1.39.0 (sha256 30d63490b9ef2aad...241f): `clients/agate_helper.py` (seeds treat only `null` and an empty field as NULL).
- apache/airflow 3.3.2 Dockerfile: `git` is in the runtime package list. https://raw.githubusercontent.com/apache/airflow/3.3.2/Dockerfile
