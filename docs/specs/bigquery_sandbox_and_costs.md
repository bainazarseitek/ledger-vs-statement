Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# BigQuery sandbox and costs

This document covers everything on the BigQuery side of Two Ledgers:
- how to set up the free BigQuery sandbox, step by step;
- the G0 probes, which prove in the first hour which write path and which login method work;
- how raw tables are created and loaded without DML;
- partitioning and clustering;
- the rolling date window, the 60-day expiry, how the pipeline refuses to write dates that would vanish, and how to reset the datasets when the window moves;
- the storage guard, the query bytes cap, and how to measure bytes honestly;
- how to read data, and Data Studio as an option;
- Plan B, the GCP Free Trial, with its stop conditions.

The goal: a pipeline that costs $0, cannot be charged, and still behaves like a careful BigQuery project.

## At a glance

| Item | Value |
|---|---|
| Account | personal Google account (Gmail), "No organization" |
| Billing | none. No card, no billing account |
| Project | display name `ledger-vs-statement`; the id lives only in `.env` as `GCP_PROJECT` |
| Location | `US` (multi-region) for every dataset, client, connection and dbt target |
| Datasets | `raw`, `raw_dev`, `analytics`, `analytics_dev`, `probe` |
| Service account | `lvs-pipeline` with BigQuery Job User and BigQuery Data Editor |
| Key | `keys/sa.json`, gitignored, mode 600, mounted read-only |
| Query cap | `maximum_bytes_billed` = 1,000,000,000 bytes on every query |
| Storage caps | 1 GiB written (self-imposed, before U3); 8 GiB written (hard stop, from U3); 10 GiB for the life of the project (Google) |
| Proof window | 2026-10-04 to 2026-11-01 |
| Write guard | a run date must be on or after `RECON_WORLD_START`, before today (UTC), and at most 45 days old |
| G0 | about 1.5 hours; decisions written down by 12:00 Astana time on the first build day, hard stop 13:00 |

## How to read this document

- **You** marks a step I do myself in the browser or the terminal. AI agents never create Google Cloud resources, never sign up for anything, never click in the console, and never open, print or copy a key.
- **Agent may scaffold** marks code an agent may draft. I read every line, simplify it if it is over 60 lines, and can explain it before I run it.
- Text in `code` is an exact name: a dataset, table, file, command or variable. Use it as written.
- Each fact carries its source: **(Google docs)**; **(third-party report)** for public reports by other people that Google does not confirm; **(to be probed)** for something a G0 probe decides; **(design estimate)** for a planning number that is not a result.
- Results are placeholders such as `[N]` until my own run fills them.

Related documents:
- `docs/specs/data_and_generator.md`: the schema JSON files, the landing layout and the defect catalog.
- `docs/specs/dbt_project.md`: `dbt/profiles.yml`, the models and the tests.
- `docs/specs/airflow_and_docker.md`: the compose file, the DAGs and the "Operations runbook".
- `docs/build_plan.md`: clock times, gates, the cut order and kill switches.
- `docs/adr/0001-warehouse-bigquery-sandbox.md`: the warehouse decision and the probe results.
- `docs/adr/0002-raw-write-path-and-time-model.md` and `docs/adr/0009-window-and-expiry.md`.
- `docs/learning/concepts.md`: the glossary.

## Words used here

| Word | Meaning in this project |
|---|---|
| Sandbox | a BigQuery project with no billing account. Free, no card, with the limits listed below |
| Project | the Google Cloud container for everything |
| Dataset | a folder of tables and views. It has a location; all of ours are in `US` |
| Partition | one slice of a table. Here: one UTC day of the partition column |
| Partition decorator | a table name with `$YYYYMMDD` at the end, such as `raw.payment_events$20261025`. It points at one day's partition |
| Load job | a job that reads a file and writes rows into a table. Free, and not DML |
| WRITE_TRUNCATE | a load setting: replace what is at the destination. With a decorator, the destination is one partition |
| DML | statements that change rows in place: INSERT, UPDATE, DELETE, MERGE, TRUNCATE TABLE. The sandbox refuses them |
| DDL | statements that create or drop objects: CREATE TABLE, CREATE VIEW, DROP TABLE. Allowed |
| CTAS | `CREATE OR REPLACE TABLE ... AS SELECT`. A dbt table model is a CTAS. It is DDL, so it is allowed |
| Expiry | automatic deletion. In the sandbox: tables, views and partitions, after 60 days |
| Bytes processed | what a query reads |
| Bytes billed | bytes processed rounded up, with a minimum of 10 MB per table read and per query |
| Bytes written | what a load or a table rebuild adds to storage |
| Bytes stored | what the tables hold right now |
| Service account | a robot Google identity for the pipeline: `lvs-pipeline` |
| Key | a JSON file that proves to Google that a program is the service account. A secret |
| ADC | Application Default Credentials: Google's standard way for code to find credentials. The fallback uses my own user login through it |

## Rules the sandbox imposes

| Rule | Source | What it means here |
|---|---|---|
| No DML | Google docs | No dbt `merge` incrementals (the default on BigQuery), no `insert_overwrite` without `copy_partitions`, no snapshots (every run after the first is a MERGE), no `time_ingestion_partitioning` (it uses INSERT), no Elementary (INSERT), no INSERT-based logging. The refusal is a 403 containing "DML queries are not allowed in the free tier" |
| No streaming | Google docs | Never `insert_rows`, `insert_rows_json`, `BigQueryHook.insert_all` or the Storage Write API. Batch load jobs only |
| No Data Transfer Service | Google docs | No scheduled queries. Airflow does all the scheduling |
| No Cloud Storage | Google docs (the Cloud Storage free tier needs a billing account) | Local files are loaded straight into BigQuery. No GCS staging, no `GCSToBigQueryOperator`, no dbt Python models |
| Tables, views and partitions expire after 60 days | Google docs | Every business date stays inside a rolling window (see "Rolling window and expiry") |
| Expiry cannot be raised or removed | third-party report: "must be less than 60 days while in sandbox mode" | Never set an expiration option. Keep the defaults |
| A lifetime limit of 10 GiB of storage, "not refunded upon data deletion" | Google docs (wording since 2026-09-04) | How it is counted is not documented, and there is no counter to read. Assume every byte ever written counts (see "Storage guard") |
| 1 TiB of query processing per month | Google docs | The build should use under a quarter of it in November (design estimate, see "Query bytes guard") |
| At least 10 MB billed per table read and per query | Google pricing page; that the sandbox counts the same way is assumed | At this project's size, bytes billed mostly counts queries, not data. Bytes are never a headline result |
| The Storage Read API only for downloading query results | Google docs (sandbox sample code) | Read data through SELECT queries (see "Reading data from BigQuery") |
| "All BigQuery quotas and limits apply" | Google docs | For example 1,500 table modifications per table per day, and 10,000 partitions per table. This project uses a few dozen a day |
| Data Studio needs a billing account | Google docs; third-party reports say it works anyway | Optional, after v1.0 (see "Data Studio (optional)") |

What still works, because none of it is DML:
- Load jobs from local files with WRITE_TRUNCATE or WRITE_APPEND, including into one partition through a decorator (Google docs for loads; third-party reports for the sandbox; probe P3).
- Deleting one partition through the table API (Google docs; probe P5).
- `CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE TABLE ... AS SELECT`, `CREATE OR REPLACE VIEW` and `DROP TABLE` (Google docs; probe P1).
- Scripting with `DECLARE` and `SET` (third-party report).
- dbt `table` and `view` models, seeds (they are load jobs), generic and singular tests, unit tests and contracts (dbt-bigquery 1.12.1 source code).
- Copy jobs, which dbt uses for `insert_overwrite` with `copy_partitions: true` (dbt-bigquery 1.12.1 source code and third-party reports; optional probe P8).

### Never in this project (BigQuery side)

1. Any INSERT, UPDATE, DELETE, MERGE or TRUNCATE TABLE statement, in SQL files, dbt models, macros, hooks, packages or scripts.
2. dbt `merge` or default `insert_overwrite` incrementals, `insert_overwrite` or `microbatch` without `copy_partitions`, `time_ingestion_partitioning`, snapshots, Elementary, `hours_to_expiration` on partitioned models, Python models.
3. Streaming: `insert_rows`, `insert_rows_json`, `insert_all`, the Storage Write API.
4. Cloud Storage, GCS operators, external tables, the Data Transfer Service, scheduled queries.
5. Any expiration option: `expiration_timestamp`, `partition_expiration_days`, or a change to a dataset's default expirations.
6. `CREATE OR REPLACE TABLE` on a raw table. It would replace every partition at once.
7. Writing a partition dated more than 45 days before today (UTC), or dated today or later.
8. Reading tables through the Storage Read API.
9. A second sandbox project to reset a quota. The Google Cloud Terms forbid creating projects to get around usage limits or quotas. Plan B is the trial.
10. Clicking Upgrade or Activate anywhere in the console of the sandbox project.

## Setup step by step

### Before you start

1. Use a personal Google account (Gmail), never the university account. Google says managed accounts, such as academic ones, "must select an organization", and an organization can enforce a policy that blocks service-account keys.
2. Use a browser profile that is signed in only to that personal account, so the console never switches accounts.
3. No card is needed. If any screen in this setup asks for a card, a payment method or a billing account, you are on the Free Trial path, not the sandbox. Stop, and start again from the BigQuery link in S1.1 step 1.
4. The repo exists, and its first commit holds `.gitignore` with `keys/` and `.env` in it (step S0.1 in `docs/build_plan.md`).
5. Time: S1.1 and S1.2 take about 25 minutes together.

### S1.1 Create the sandbox project (You, about 12 minutes)

1. Open https://console.cloud.google.com/bigquery and sign in with the personal account.
   You should see: on a first visit, a welcome page that asks for a country and the Terms of Service.
2. Country: Kazakhstan. Read the terms and tick the box if you agree. Click **Agree and continue**.
3. Click **Create project**.
4. Project name: `ledger-vs-statement`.
5. Project ID: the console proposes one based on the name. Keep it, or click **Edit**. The rules (Google docs): 6 to 30 characters; lowercase letters, digits and hyphens; starts with a letter; does not end with a hyphen; never used before by anyone; no restricted words such as `google`; permanent after creation. Put no personal data in it: no name, no email, no student number.
6. Organization (some screens call it **Location** or **Parent resource**): **No organization**. If the screen offers only an organization, you are signed in with a managed account. Stop and switch to the personal account.
7. Click **Create**. You return to the BigQuery page.
   You should see: the BigQuery sandbox notice on the BigQuery page (Google's docs call it "a BigQuery sandbox notice"; `docs/build_plan.md` calls it the SANDBOX badge). It offers an upgrade. Never click it. The Billing check in step 8 is the test that counts, because console layouts change.
8. Check billing. Pick the new project in the project picker at the top, open the **Navigation menu** and click **Billing**.
   You should see: "This project has no billing account". Do not click **Link a billing account**.
9. Copy the project id into your private notes. Step S1.3 writes it into `.env`. Committed files never contain the id: they use `your-sandbox-project-id` or `<project>`. `.env` is gitignored. Committed files never contain the id: they use `your-sandbox-project-id` or `<project>`.
10. Create the dataset `probe`. In BigQuery Studio, in the Explorer pane, open the actions menu next to the project and click **Create dataset**. Dataset ID: `probe`. Location type: **Multi-region**. Multi-region: **US**. Do not change any expiration field. Click **Create dataset**.
    You should see: `probe` under the project in the Explorer.

Done when: the sandbox notice shows, Billing says "This project has no billing account", the project id is in your private notes and in the banned-word list, and `probe` exists in `US`.

| If you see | Then |
|---|---|
| a request for a card or a payment method | stop. That is the trial sign-up. Go back to step 1 |
| only an organization to choose | stop. Use the personal account |
| a billing account linked to the project | stop. Never build in sandbox mode on a billed project. Write down what the screen shows and check **Billing**, **Account management** |
| no welcome page | fine. The account has used Google Cloud before. Continue with step 3 |

### S1.2 Service account and key (You, about 12 minutes)

1. In the project picker, select the sandbox project.
2. Open the **Navigation menu**, **IAM & Admin**, **Service accounts**. If the console asks you to enable the Identity and Access Management (IAM) API, click **Enable**. It is free.
3. Click **Create service account**.
   - Service account name: `lvs-pipeline`.
   - Service account ID: `lvs-pipeline` (filled in from the name; it cannot be changed later).
   - Description: `Loads raw tables and runs dbt for ledger-vs-statement`.
   - Click **Create and continue**.
4. Grant two roles on the project: **BigQuery Job User** and **BigQuery Data Editor**. Nothing else. Click **Continue**, then **Done**.
   You should see: `lvs-pipeline@<project id>.iam.gserviceaccount.com` in the list.
5. Before you download anything, prove that git will ignore the key:

   ```bash
   cd ~/Developer/ledger-vs-statement
   mkdir -p keys && chmod 700 keys
   git check-ignore keys/sa.json
   ```

   It must print `keys/sa.json`. If it prints nothing, stop and fix `.gitignore` first.
6. Click the service account's email, open the **Keys** tab, click **Add key**, then **Create new key**, choose **JSON**, and click **Create**. The browser downloads one JSON file. Google cannot show it again.
7. Move it into place and lock it down:

   ```bash
   mv ~/Downloads/<downloaded file name>.json keys/sa.json
   chmod 600 keys/sa.json
   ls -l keys/sa.json
   git status --short
   python3 -c "import json; d = json.load(open('keys/sa.json')); print(d['type'], d['client_email'].split('@')[0])"
   ```

   `ls -l` must show `-rw-------`. `git status --short` must not list anything under `keys/`. The last command must print `service_account lvs-pipeline`. It prints nothing secret.
8. Make sure no second copy is left in `~/Downloads`. Delete any duplicate download.

Done when: `keys/sa.json` exists with mode 600, `git check-ignore keys/sa.json` prints the path, and `git status` shows nothing under `keys/`.

Why these two roles (Google docs, BigQuery access control):

| Role | Gives | Needed for |
|---|---|---|
| BigQuery Job User (`roles/bigquery.jobUser`) | `bigquery.jobs.create` | running queries, load jobs and dbt |
| BigQuery Data Editor (`roles/bigquery.dataEditor`), on the project | `bigquery.datasets.create`, `bigquery.datasets.get`, `bigquery.tables.create`, `.get`, `.list`, `.getData`, `.update`, `.updateData`, `.delete` | creating datasets and tables (`make bq-setup`), loading and deleting partitions, reading data |

Not granted, on purpose:
- BigQuery Read Session User. It is for the Storage Read API, which this project does not use.
- BigQuery User. It adds `bigquery.jobs.list`, among other permissions. Without it, the service account cannot query the `INFORMATION_SCHEMA.JOBS` views; job history is read in the console as the project owner instead.
- Any admin or owner role.

Trade-off: the roles are on the whole project, so that `make bq-setup` can create datasets. Dataset-level roles would be tighter, but every dataset would then have to be created by hand first.

### Key handling rules

1. The key lives only at `keys/sa.json`. `keys/` was gitignored before the key existed. File mode 600, folder mode 700.
2. Never commit it, print it, open it in a shared or synced editor, paste it into a chat, an issue, an AI tool or a screenshot, or copy it into the Docker image. `.dockerignore` excludes `keys/`.
3. Only the path travels. dbt reads `DBT_KEYFILE`, host Python reads `GOOGLE_APPLICATION_CREDENTIALS`, and the Airflow connection reads `key_path`. All three hold a path, never the contents. `DBT_KEYFILE` and `GOOGLE_APPLICATION_CREDENTIALS` are never written into `.env`.
4. Containers see the key read-only at `/opt/airflow/keys/sa.json`, through the mount `./keys:/opt/airflow/keys:ro`. After `make up`, check that the container user can read it:

   ```bash
   docker compose exec airflow-scheduler test -r /opt/airflow/keys/sa.json && echo readable
   ```

5. `make check` fails if `git ls-files keys .env` prints anything.
6. What the key can do: read and write BigQuery data in this sandbox project only. There is no billing account, so it cannot spend money. Google's ADC docs say keys "create a security risk and are not recommended". This project accepts one least-privilege key for a local Docker stack, and ADR-0001 says so.
7. If the key leaks (pushed, pasted, shared, shown on screen):
   1. In **IAM & Admin**, **Service accounts**, `lvs-pipeline`, **Keys**, delete that key at once. Google cannot restore a deleted key.
   2. Create a new key as in S1.2 steps 5 to 8.
   3. If it was pushed, remove it from the git history before anything else is pushed.
   4. Write an entry in `docs/failure_log.md`.
8. When the project ends, delete the key in the **Keys** tab and delete `keys/sa.json` (see "Teardown").

### If key creation is blocked: ADC fallback (You, 20 to 40 minutes)

Use this only if S1.2 step 6 fails: there is no **Add key** button, or an error says key creation is disabled by the organization policy constraint `iam.disableServiceAccountKeyCreation`. With a personal account and **No organization** this should not happen, so first check that the project picker shows no organization.

What changes: the pipeline uses my own Google login through ADC instead of the service-account key. My user owns the project, so this is not least privilege. ADR-0001 records it.

1. Install the Google Cloud CLI: `brew install --cask gcloud-cli`. (Homebrew cask `gcloud-cli`, version 591.0.0 on 2026-11-01. It also installs `bq`; this project still does not use `bq`.)
2. Run `gcloud auth application-default login`. A browser opens. Sign in with the personal account and allow access. Google writes the credentials to `$HOME/.config/gcloud/application_default_credentials.json`. Google's docs: the file "contains your refresh token". Treat it like the key. If dbt later reports `invalid_scope`, run the longer form with `--scopes` given in `docs/specs/dbt_project.md`.
3. Run `chmod 600 ~/.config/gcloud/application_default_credentials.json`.
4. Only if a client later warns that there is no quota project (the warning is harmless): `gcloud auth application-default set-quota-project <GCP_PROJECT>`.
5. Host: the `Makefile` stops exporting `GOOGLE_APPLICATION_CREDENTIALS` and `DBT_KEYFILE` in this mode. Google's auth library reads `GOOGLE_APPLICATION_CREDENTIALS` first and fails if it points at a missing file. Without it, ADC finds the gcloud file at its default path (Google docs), so host clients built as `bigquery.Client(project=..., location="US")` pick it up.
6. dbt: in `dbt/profiles.yml`, in both targets, set `method: oauth` and delete the `keyfile:` line. Nothing else changes.
7. Docker: in `docker-compose.yaml`, inside `x-airflow-common` (the exact lines live in `docs/specs/airflow_and_docker.md`):
   - mount the file read-only where the auth library looks for it: `${HOME}/.config/gcloud/application_default_credentials.json:/home/airflow/.config/gcloud/application_default_credentials.json:ro` (`HOME` is `/home/airflow` in the image). This is outside the read-only `keys` mount;
   - set `GOOGLE_APPLICATION_CREDENTIALS: /home/airflow/.config/gcloud/application_default_credentials.json` too, so the lookup never depends on `HOME`;
   - in `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT`, delete `"key_path": "/opt/airflow/keys/sa.json"` from `extra`. Keep `project`, `location` and `use_legacy_sql`. With no key in the connection, the Google provider falls back to ADC.

   Check after `make up`:

   ```bash
   docker compose exec airflow-scheduler test -r /home/airflow/.config/gcloud/application_default_credentials.json && echo readable
   ```

8. Rerun S1.3 and `make probe`.
9. When the project ends: `gcloud auth application-default revoke`.

### S1.3 Host venv and dbt debug (You, about 18 minutes)

`dbt/profiles.yml` and a minimal `dbt/dbt_project.yml` are specified in `docs/specs/dbt_project.md` (agent may scaffold both). Then, by hand (the Makefile wraps the same commands later):

```bash
cd ~/Developer/ledger-vs-statement
which -a dbt
set -a; source .env; set +a
cd dbt
export RAW_DATASET=raw_dev DBT_PROFILES_DIR="$PWD" DBT_KEYFILE="$(cd .. && pwd)/keys/sa.json"
uv run dbt --version
uv run dbt debug --target dev
```

- `which -a dbt` may list `~/.local/bin/dbt`. That is dbt v2 (2.0.9). Never use it in this project.
- Pass: `uv run dbt --version` shows Core 1.12.6 and the bigquery plugin 1.12.1, and `dbt debug` ends with "All checks passed!".
- Fail: a credentials error means `DBT_KEYFILE` is wrong or the file is missing. A project or permission error means `GCP_PROJECT` does not match the console, or a role is missing. Never fix it by running bare `dbt`.

### Datasets

| Dataset | Created by | Holds | Written by |
|---|---|---|---|
| `probe` | You, in S1.1 (console) | throwaway KB tables: the G0 probes and `probe.smoke` | `scripts/g0_probe.py`, DAG `smoke_bigquery` |
| `raw` | `make bq-setup` (S2.3) | the 3 raw tables for the proof window | Airflow task `load_raw` |
| `raw_dev` | `make bq-setup` (S2.3) | the same 3 tables for development days | host CLI (`make day`) |
| `analytics` | dbt, on the first build of target `airflow` (location `US` from the profile) | the views and marts the DAG builds | dbt target `airflow` |
| `analytics_dev` | dbt, on the first build of target `dev` (location `US` from the profile) | host builds | dbt target `dev` |
| `raw_heldout`, `analytics_heldout` | U4 only | the held-out world | U4 host runs |

Rules:
1. Every dataset is in `US` (multi-region). The host client, the Airflow connection and the dbt profile also say `US`. A job in another location cannot see the data.
2. Never change a dataset's default expirations and never set one. The sandbox sets both to 60 days; probe P6 records them.
3. `make bq-setup` (`uv run python -m recon.cli bq-setup`) calls `ensure_tables(client, "raw")` and `ensure_tables(client, "raw_dev")`. `ensure_tables` first makes sure its dataset exists in `US`, then creates the tables (see "Creating partitioned tables before loads"). The dataset part (you write it, inside `ensure_tables`):

   ```python
   ds = bigquery.Dataset(f"{client.project}.{dataset}")
   ds.location = "US"
   ds = client.create_dataset(ds, exists_ok=True)       # returns the existing dataset if it is already there
   if ds.location != "US":
       raise RuntimeError(f"dataset {dataset} is in {ds.location}, expected US")
   ```

   Done when: `make bq-setup` succeeds twice in a row, and the second run changes nothing. Each table's **Details** tab in the console shows partitioning by DAY on `_arrival_date` and the clustering column.
4. dbt creates `analytics` and `analytics_dev` itself on the first build of each target, in the profile's location `US`. It needs no custom schema: the two targets write to these datasets directly.
5. Dropping a dataset or a table gives no storage back. Keep `probe`; its tables expire by themselves.

## G0 probes runbook

### What G0 decides

| Decision | Options | Decided by |
|---|---|---|
| Login method | the service-account key, or the ADC fallback | S1.2 |
| Raw write path | one WRITE_TRUNCATE load per day into `table$YYYYMMDD` (the design), daily shard tables (the fallback), or Plan B | P3, then the shard check |
| Empty-day rule | partition delete, or "never produce empty partitions" | P5 |
| Storage measurement | `__TABLES__`, `INFORMATION_SCHEMA.TABLE_STORAGE`, or the table API | P7 |
| FX fetch | the `fetch_fx` task, or a committed hand-fetched JSON | F1 |

Gate G0: the login method and the write path are chosen and written down by 12:00 Astana time. Hard stop 13:00. `docs/build_plan.md` has the clock.

### How to run the probes (S1.4)

```bash
cd ~/Developer/ledger-vs-statement
make probe                        # all probes
make probe ARGS="--only P3,P4"    # a subset
```

`make probe` runs `PYTHONPATH=src GOOGLE_APPLICATION_CREDENTIALS=$(CURDIR)/keys/sa.json uv run python scripts/g0_probe.py $(ARGS)`, with the `.env` values the Makefile loads.

How `scripts/g0_probe.py` behaves (agent may scaffold; you read every line before running it):
1. It is standalone. It imports only `google-cloud-bigquery` (installed with dbt-bigquery) and the standard library. `src/recon/bq.py` does not exist yet at G0.
2. It writes only into the dataset `probe`, a few KB, and makes one HTTP request to Frankfurter.
3. It prints one line per probe: `<id>  PASS|FAIL|SKIP  <short detail>`.
4. It writes `docs/evidence/<UTC date of the run>/g0_probe.json` with every result and every error text in full. Before writing, it replaces the service-account email with `<sa>` and the project id with `<project>`.
5. A FAIL is information, not a crash. The script goes on to the next probe. P4, P5 and P6 need the table P3 creates; they print SKIP if P3 could not create it.
6. Every probe starts from a clean state (it drops and re-creates its own tables), so the script can run again.
7. `--plan-b` flips the expected results of P2 and P6 for a billing-enabled project (see "Plan B: the GCP Free Trial").
8. Exit code 0 when every probe passed, 1 otherwise.

Dates used: `TODAY` is the current UTC date, `Y` is yesterday (UTC), and `Y1` is the day before yesterday. For a run on 2026-11-01 at 10:30 Astana time (05:30 UTC): `Y` = 2026-10-31 and `Y1` = 2026-10-30.

### Probe summary

| Id | Question | Pass | Fallback, decided now |
|---|---|---|---|
| S1.1 | Personal account, "No organization", new project, sandbox notice | notice shown; "This project has no billing account" | an organization is forced or billing is linked: stop, use the personal account, never build on a billed project |
| S1.2 | Service account `lvs-pipeline` and a JSON key at `keys/sa.json` | key downloaded; `git check-ignore keys/sa.json` prints the path | key creation blocked: the ADC fallback (20 to 40 minutes) |
| S1.3 | Host venv, `uv run dbt --version`, `uv run dbt debug` | Core 1.12.6, bigquery 1.12.1, "All checks passed!" | fix the environment variables or the profile; never bare `dbt` |
| P1 | Do CTAS and a view work? | both succeed | wrong project or credentials: fix the configuration |
| P2 | Is DML refused? | refused with "DML queries are not allowed in the free tier"; full text saved | if the INSERT succeeds, billing is on: stop and check Billing |
| P3 | Does a WRITE_TRUNCATE load into `t$<Y>` replace exactly that day? | `Y` holds only the second file's row; `Y1` untouched; timestamps loaded | the shard check; if it passes, daily shard tables (ADR-0002); if not, Plan B |
| P4 | Is a row for another day refused? | the load fails; the table is unchanged | none needed: the loader's own assertion is the guard |
| P5 | Does deleting one partition work? | `Y` is empty; `Y1` still has its row | the empty-day rule becomes "never produce empty partitions" |
| P6 | Which expirations does the sandbox set? | dataset defaults of 60 days (5184000000 ms); no table-level expiry on the partitioned table | note any table-level expiry; the 28-day window stays well inside 60 days |
| P7 | Can storage metadata be read? | `__TABLES__` or TABLE_STORAGE readable | the table API in `scripts/storage.py` |
| F1 | Does one Frankfurter request return NBK USD/KZT rows? | HTTP 200; a flat array of `{date, base, quote, rate}`; weekday dates only | a committed hand-fetched JSON in `landing/fx/`; cut the fetch task (cut-order item 6) |
| P8 | Does dbt `copy_partitions` avoid DML? (optional, 10 minutes, off the critical path) | "Copying table(s)" in the log; no `merge into` or `insert into` | U5 builds its snapshot as a full-rebuild model; ADR-0008 says why |

### Script skeleton

```python
"""G0 probes for the BigQuery sandbox. Writes a few KB into dataset `probe` only."""
import datetime as dt
import io
import json
import os
import re
import urllib.request

from google.api_core import exceptions as gexc
from google.cloud import bigquery

PROJECT = os.environ["GCP_PROJECT"]
CAP = 1_000_000_000                      # the maximum_bytes_billed used everywhere in the project
client = bigquery.Client(project=PROJECT, location="US")
TODAY = dt.datetime.now(dt.timezone.utc).date()
Y, Y1 = TODAY - dt.timedelta(days=1), TODAY - dt.timedelta(days=2)
T = f"{PROJECT}.probe.raw_pay"           # created by P3, used by P4 to P7
SA_EMAIL = re.compile(r"[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com")

def redact(text):
    """Remove the service-account email and the project id before anything is saved."""
    return SA_EMAIL.sub("<sa>", str(text)).replace(PROJECT, "<project>")

def q(sql, params=(), cap=CAP):
    """One query with the bytes cap and no cache. Returns (job, rows as dicts)."""
    config = bigquery.QueryJobConfig(maximum_bytes_billed=cap, use_query_cache=False,
                                     query_parameters=list(params))
    job = client.query(sql, job_config=config)
    return job, [dict(row.items()) for row in job.result()]

def load_rows(destination, rows, schema, create="CREATE_NEVER"):
    """One NDJSON load job with WRITE_TRUNCATE: the same settings as the real loader."""
    payload = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=create,
        max_bad_records=0,
    )
    job = client.load_table_from_file(io.BytesIO(payload), destination, job_config=config)
    job.result()
    return job

def row(day, x, hms):
    """A probe row. TIMESTAMP text in the raw format of this project: YYYY-MM-DD HH:MM:SS+00:00."""
    return {"d": day.isoformat(), "x": x, "ts": f"{day.isoformat()} {hms}+00:00"}

SCHEMA = [bigquery.SchemaField("d", "DATE", mode="REQUIRED"),
          bigquery.SchemaField("x", "INT64"),
          bigquery.SchemaField("ts", "TIMESTAMP")]
```

Each probe is one function that returns `{"id", "status", "detail", "evidence", "error_text"}`. `main()` runs them in the order P1, P2, P3, P4, P5, P6, P7, F1 (P8 runs by hand, outside the script), catches any exception as a FAIL, prints the summary lines, writes the JSON file with `json.dump(..., indent=2, default=str)`, and sets the exit code.

### P1: DDL works (CTAS and a view)

```python
q(f"CREATE OR REPLACE TABLE `{PROJECT}.probe.t` AS SELECT 1 AS x")
q(f"CREATE OR REPLACE VIEW `{PROJECT}.probe.v` AS SELECT x FROM `{PROJECT}.probe.t`")
_, rows = q(f"SELECT x FROM `{PROJECT}.probe.v`")
passed = rows == [{"x": 1}]
```

- Pass: both statements succeed, and the view returns one row with `x = 1`.
- If it fails: almost always the wrong project or the wrong credentials. Check `GCP_PROJECT`, the two roles and the key. Nothing else can start before P1 passes.
- It teaches: DDL is not DML. dbt table and view models are exactly these statements.

### P2: DML is refused

```python
try:
    q(f"INSERT INTO `{PROJECT}.probe.t` (x) VALUES (2)")
    passed, text = False, "the INSERT was accepted"
except gexc.GoogleAPICallError as e:
    text = redact(e)
    passed = "DML queries are not allowed in the free tier" in text
```

- Pass: refused, and the error contains "DML queries are not allowed in the free tier". The expected full text (third-party reports): "Billing has not been enabled for this project. Enable billing at https://console.cloud.google.com/billing. DML queries are not allowed in the free tier. Set up a billing account to remove this restriction." Save the text you actually get, word for word, for ADR-0001.
- If the INSERT succeeds: billing is on. Stop all work, open **Billing**, and do not build on this project.
- It teaches: why there is no MERGE, no snapshot and no default incremental anywhere in this project.

### P3: one decorator load replaces exactly one day

```python
client.delete_table(T, not_found_ok=True)                        # a clean start
table = bigquery.Table(T, schema=SCHEMA)
table.time_partitioning = bigquery.TimePartitioning(
    type_=bigquery.TimePartitioningType.DAY, field="d")
client.create_table(table)

load_rows(f"{T}${Y1:%Y%m%d}", [row(Y1, 7, "00:00:00")], SCHEMA)                       # the other day first
load_rows(f"{T}${Y:%Y%m%d}", [row(Y, 1, "10:00:00"), row(Y, 2, "23:59:59")], SCHEMA)  # file A: 2 rows
load_rows(f"{T}${Y:%Y%m%d}", [row(Y, 99, "12:00:00")], SCHEMA)                        # file B: 1 row
_, rows = q(f"SELECT d, COUNT(*) AS n, SUM(x) AS s, MIN(ts) AS ts FROM `{T}` GROUP BY d ORDER BY d")
```

- Pass: exactly two groups. `Y1`: n = 1, s = 7, so the two loads into `Y` did not touch it. `Y`: n = 1, s = 99, ts = `Y` 12:00:00 UTC, so file B replaced file A. The TIMESTAMP text loaded without an error.
- If it fails: run the shard check below. If the shard check passes, the write path becomes daily shard tables. If both fail: Plan B.
- It teaches: what WRITE_TRUNCATE on `t$YYYYMMDD` replaces, which is the whole basis of safe reruns.

Shard check (only if P3 failed):

```python
S = f"{PROJECT}.probe.raw_pay_{Y:%Y%m%d}"
client.delete_table(S, not_found_ok=True)
load_rows(S, [row(Y, 1, "10:00:00"), row(Y, 2, "23:59:59")], SCHEMA, create="CREATE_IF_NEEDED")
load_rows(S, [row(Y, 99, "12:00:00")], SCHEMA, create="CREATE_IF_NEEDED")
_, rows = q(f"SELECT COUNT(*) AS n, SUM(x) AS s FROM `{PROJECT}.probe.raw_pay_*` "
            f"WHERE _TABLE_SUFFIX = '{Y:%Y%m%d}'")
```

- Pass: n = 1 and s = 99.
- What the shard fallback changes (ADR-0002 records it): each raw table becomes one table per day, `raw.<table>_YYYYMMDD`, loaded as a whole with WRITE_TRUNCATE (each shard is created by its first load). dbt sources use the identifier `<table>_*` with constant `_TABLE_SUFFIX` filters and fixed schemas (`docs/specs/dbt_project.md`). An empty day deletes its shard. Shards are not partitioned, so each one expires 60 days after it was created; a reload probably does not reset that clock (third-party report).

### P4: a row for another day is refused

```python
try:
    load_rows(f"{T}${Y:%Y%m%d}", [row(Y1, 5, "01:00:00")], SCHEMA)   # a Y1 row into the Y partition
    passed, text = False, "the load was accepted"
except gexc.GoogleAPICallError as e:
    passed, text = True, redact(e)
_, after = q(f"SELECT d, COUNT(*) AS n, SUM(x) AS s FROM `{T}` GROUP BY d ORDER BY d")
```

- Pass: the job fails, and the table is unchanged: `Y1` n = 1, s = 7; `Y` n = 1, s = 99. Google docs: the partition in the decorator "must match the data being written. Otherwise, an error occurs."
- If the load is accepted: the design does not change. The loader already asserts that every row's `_arrival_date` equals the run date before any job runs. Record the result.

### P5: deleting one partition

```python
client.delete_table(f"{T}${Y:%Y%m%d}", not_found_ok=True)
client.delete_table(f"{T}${Y:%Y%m%d}", not_found_ok=True)        # a second delete must not fail
_, rows = q(f"SELECT d, COUNT(*) AS n FROM `{T}` GROUP BY d ORDER BY d")
```

- Pass: only `Y1` remains, with n = 1, and the second delete raised nothing. A partition delete is a table operation, not DML, and Google lists it as free.
- If it fails: the empty-day rule becomes "never produce empty partitions". That is already true for v1.0 data: every arrival day has rows in all three tables. One MID's file can be empty (`mid_kzt_01` on `RECON_WORLD_START`), but the table's partition for that day still has the other MID's rows. Write it into ADR-0002.

### P6: the expirations the sandbox sets

```python
ds = client.get_dataset(f"{PROJECT}.probe")
tb = client.get_table(T)
evidence = {
    "dataset_location": ds.location,
    "default_table_expiration_ms": ds.default_table_expiration_ms,
    "default_partition_expiration_ms": ds.default_partition_expiration_ms,
    "raw_pay_partition_expiration_ms": tb.time_partitioning.expiration_ms,
    "raw_pay_table_expires": tb.expires,                          # None means no table-level expiry
    "t_table_expires": client.get_table(f"{PROJECT}.probe.t").expires,
}
```

- Pass: location `US`; both dataset defaults are 5184000000 ms (60 days); `raw_pay` has a partition expiration of 5184000000 ms and no table-level expiry (`expires` is None). `probe.t`, which is not partitioned, shows an expiry about 60 days after its creation (information only).
- If a table-level expiry appears on `raw_pay`: write it down. The 28-day window stays well inside 60 days, and dbt re-creates its own tables on every build. Add the check to the follow-ups of ADR-0009.

### P7: storage metadata is readable

```python
sources = {
    "__TABLES__": f"SELECT table_id, row_count, size_bytes FROM `{PROJECT}.probe.__TABLES__`",
    "TABLE_STORAGE": "SELECT table_name, total_logical_bytes "
                     "FROM `region-us`.INFORMATION_SCHEMA.TABLE_STORAGE WHERE table_schema = 'probe'",
}
evidence = {}
for name, sql in sources.items():
    try:
        _, rows = q(sql)
        evidence[name] = {"readable": True, "rows": len(rows)}
    except gexc.GoogleAPICallError as e:
        evidence[name] = {"readable": False, "error": redact(e)}
passed = any(v["readable"] for v in evidence.values())
```

- Pass: at least one source is readable.
- Expected (to be probed): `__TABLES__` works. TABLE_STORAGE may fail with "INFORMATION_SCHEMA.TABLE_STORAGE hasn't been enabled for project <project>." Google's docs say the view may first need the project option `enable_info_schema_storage` (see "Storage guard").
- If both fail: `scripts/storage.py` uses the table API (`list_tables`, then `get_table(...).num_bytes`), which needs no query.

### F1: one Frankfurter request

```python
start, end = Y - dt.timedelta(days=6), Y                 # R-6..R with R = yesterday; never today or later
url = ("https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT"
       f"&from={start.isoformat()}&to={end.isoformat()}")
request = urllib.request.Request(url, headers={"User-Agent": "ledger-vs-statement (learning project)"})
with urllib.request.urlopen(request, timeout=10) as response:
    status, body = response.status, response.read()
rates = json.loads(body, parse_float=str)                 # rates stay exact text, never float
passed = (status == 200 and isinstance(rates, list) and len(rates) > 0
          and all(set(r) == {"date", "base", "quote", "rate"} for r in rates)
          and all(r["base"] == "USD" and r["quote"] == "KZT" for r in rates)
          and all(dt.date.fromisoformat(r["date"]).weekday() < 5 for r in rates))
```

- Pass: HTTP 200 and a flat JSON array of `{date, base, quote, rate}` objects for USD/KZT, with weekday dates only.
- The probe writes nothing into `landing/fx/`. Only the `fetch_fx` task lands FX files, once per run date.
- If it fails: commit a hand-fetched JSON into `landing/fx/` in the landing format of `docs/specs/data_and_generator.md`, and cut the fetch task (cut-order item 6 in `docs/build_plan.md`). FX stays real.

### P8 (optional): dbt `copy_partitions` avoids DML

Run it by hand, outside the repo, in about 10 minutes. It is off the critical path; U5 needs it, v1.0 does not.

1. Create a scratch dbt project:

   ```bash
   P8=/tmp/lvs_p8
   mkdir -p "$P8/models"
   cat > "$P8/dbt_project.yml" <<'EOF'
   name: p8_probe
   profile: p8_probe
   EOF
   cat > "$P8/profiles.yml" <<'EOF'
   p8_probe:
     target: probe
     outputs:
       probe:
         type: bigquery
         method: service-account
         keyfile: "{{ env_var('DBT_KEYFILE') }}"
         project: "{{ env_var('GCP_PROJECT') }}"
         dataset: probe
         location: US
         threads: 1
         maximum_bytes_billed: 1000000000
   EOF
   cat > "$P8/models/probe_copy.sql" <<'EOF'
   {{ config(
       materialized='incremental',
       incremental_strategy='insert_overwrite',
       partition_by={'field': 'd', 'data_type': 'date', 'granularity': 'day', 'copy_partitions': true}
   ) }}
   select date_sub(current_date(), interval 1 day) as d, 1 as x
   union all
   select date_sub(current_date(), interval 2 day) as d, 2 as x
   EOF
   ```

   The config sets no `time_ingestion_partitioning`: dbt's own `copy_partitions` example sets it, and it uses INSERT. The partition column is never NULL: an open dbt-adapters bug (#2086) breaks this path on NULL partition values.
2. Run it twice with the project's dbt, then read the log:

   ```bash
   cd ~/Developer/ledger-vs-statement
   set -a; source .env; set +a
   export DBT_KEYFILE="$PWD/keys/sa.json"
   for i in 1 2; do
     uv run dbt run --project-dir "$P8" --profiles-dir "$P8" --target-path "$P8/target" --log-path "$P8/logs" -s probe_copy
   done
   grep -c 'Copying table(s)' "$P8/logs/dbt.log"
   grep -ciE 'merge into|insert into' "$P8/logs/dbt.log"
   ```

- Pass: both runs succeed, the first `grep` prints 1 or more, and the second prints 0. The copy line is a debug line, so it is only in `dbt.log`, not on screen.
- If it fails: U5 builds its snapshot model as a full-rebuild table, and ADR-0008 records why.
- Clean up: `rm -rf /tmp/lvs_p8`. The tables in `probe` expire by themselves.

### Optional check: the bytes cap is enforced (2 minutes, not part of G0)

```python
try:
    q(f"SELECT x FROM `{PROJECT}.probe.t`", cap=1_000_000)        # below the 10 MB minimum, on purpose
    enforced, text = False, "the query ran"
except gexc.GoogleAPICallError as e:
    text = redact(e)
    enforced = "Query exceeded limit for bytes billed" in text
```

- Pass: the query is refused before it runs, with an error like Google's example "Query exceeded limit for bytes billed: 1000000. 10485760 or higher required." Google's pricing page: queries that return an error are not charged. So this check reads nothing and costs nothing. It shows that `maximum_bytes_billed` works in the sandbox.
- If the query runs: the sandbox ignores the cap. Keep the setting anyway (it matters on Plan B), and record the result.

### Not probed, on purpose

- Loading a partition dated 70 days back. Google documents that writing into a partition older than the partition expiration expires it at once, and third parties report that the job still succeeds. The 45-day guard prevents it.
- Reading tables through the Storage Read API. Never used (see "Reading data from BigQuery").
- Data Studio. Optional, after v1.0 (see "Data Studio (optional)").
- The lifetime storage counter. It cannot be read, and testing it would spend it.
- Whether a date-partitioned table survives past its own day 60. A follow-up check on or after 2026-12-31 (see "Rolling window and expiry").

### Recording the results (S1.5, You, about 18 minutes)

1. Read `docs/evidence/2026-11-01/g0_probe.json`. Check that it holds no project id, no email and nothing from the key. Commit it. (`docs/build_plan.md` also saves the console output with `tee`; the JSON file is the record to commit, because the script has already removed the project id from it.)
2. Copy the P2 error text word for word into the probe table of ADR-0001. Fill in the other result blanks there.
3. Write the decisions (login method, write path, empty-day rule, storage source, FX fetch) into the notes of ADR-0001 by 12:00.
4. Fill the README section "Platform constraints (G0 probes)" from the results. A suggested table, with placeholders until measured:

| Probe | Question | Google docs say | Result on [date] | Consequence |
|---|---|---|---|---|
| P2 | Is DML refused? | the sandbox does not support DML | [result and error text] | no MERGE, INSERT, UPDATE or DELETE anywhere |
| P3 | Does a WRITE_TRUNCATE load into `t$YYYYMMDD` replace only that day? | decorator loads are documented; the sandbox page says nothing about them | [result] | one load job per table per arrival day |
| P4 | Is a row for another day refused? | "an error occurs" | [result] | the loader's own assertion stays |
| P5 | Does a partition delete work? | yes, through `tables.delete` | [result] | the empty-day rule |
| P6 | Which expirations does the sandbox set? | tables, views and partitions expire after 60 days | [result] | a 28-day window and a 45-day write guard |
| P7 | Can storage metadata be read? | TABLE_STORAGE may need a project option | [result] | the source for `make storage` |
| F1 | Does the NBK series come back as expected? | not a Google service | [result] | a live fetch, or a committed JSON |
| P8 | Does `copy_partitions` avoid DML? | the dbt-bigquery source says so | [result, or "not run"] | the snapshot model in U5 |

### Decision rules at G0

| Outcome | Decision |
|---|---|
| the key is created and P1 passes | login method: the service-account key |
| key creation is blocked | login method: the ADC fallback (20 to 40 minutes) |
| P2 is refused | expected. Continue |
| P2 is accepted | billing is on. Stop and check Billing |
| P3 passes | write path: one WRITE_TRUNCATE load per (table, arrival day) into `table$YYYYMMDD` |
| P3 fails and the shard check passes | write path: daily shard tables; ADR-0002 records it |
| P3 and the shard check both fail | Plan B, or stop |
| P4 is accepted | no change; the loader's assertion is the guard |
| P5 fails | empty-day rule: never produce empty partitions |
| P7 | `make storage` uses `__TABLES__`, then TABLE_STORAGE if readable, then the table API |
| F1 fails | a committed hand-fetched FX JSON; cut the fetch task |

### Check yourself (the M1 explain check)

- Why can't dbt's default incremental run here? On BigQuery the default incremental strategy is `merge`, which sends a MERGE statement. MERGE is DML, and the sandbox refuses all DML.
- What did the DML refusal say? Quote the P2 text from `g0_probe.json`.
- What happens to a row dated 70 days ago? Its partition is already past the 60-day partition expiration, so writing it expires the partition at once. The job reports success and the row is gone. The 45-day guard never lets the pipeline write such a date.

## Creating partitioned tables before loads

### Why the table must exist first

- A decorator load writes into one partition of a table that already has a partition spec. The partition column (`_arrival_date`, by DAY) and the clustering column belong to the table, not to the load job.
- The load job uses `create_disposition=CREATE_NEVER`. Google's API reference: "The table must already exist. If it does not, a 'notFound' error is returned in the job result." So a load can never create a table of the wrong shape, for example one without partitions. A missing table fails loudly instead.
- `ensure_tables` creates the tables once. It runs in `make bq-setup`, and as a DAG task in every run, where it normally does nothing.

### The pattern: `ensure_tables` from the schema JSON (you write it)

One schema JSON file per raw table, `src/recon/schemas/<table>.json`, drives three things: the table creation below, `LoadJobConfig.schema`, and a pytest. Each file is one object: the table options (`table`, `description`, `labels`, `time_partitioning`, `clustering_fields`) plus a standard BigQuery `fields` list. The full files are in `docs/specs/data_and_generator.md`, heading "Schema JSON files". The options per table:

| Table | Partition column | Cluster by | Description starts with | Label `data_origin` |
|---|---|---|---|---|
| `payment_events` | `_arrival_date` (DAY) | `mid` | "SYNTHETIC: generated by src/recon/generator.py" | `synthetic` |
| `settlement_lines` | `_arrival_date` (DAY) | `mid` | "SYNTHETIC: generated by src/recon/generator.py" | `synthetic` |
| `fx_rates` | `_arrival_date` (DAY) | `provider` | "REAL: NBK rates via Frankfurter v2" | `real` |

Pseudocode:

```python
TABLES = ["payment_events", "settlement_lines", "fx_rates"]
STANDARD_NAMES = {"INTEGER": "INT64", "BOOLEAN": "BOOL", "FLOAT": "FLOAT64"}   # the API reports legacy type names

def ensure_tables(client, dataset):
    ensure_dataset_in_us(client, dataset)                 # the dataset part shown under "Datasets"
    for name in TABLES:
        doc = json.loads((SCHEMA_DIR / f"{name}.json").read_text())
        schema = [bigquery.SchemaField.from_api_repr(f) for f in doc["fields"]]   # not schema_from_json: it wants a bare list
        table = bigquery.Table(f"{client.project}.{dataset}.{doc['table']}", schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=doc["time_partitioning"]["type"], field=doc["time_partitioning"]["field"])
        table.clustering_fields = doc["clustering_fields"]
        table.description = doc["description"]
        table.labels = doc["labels"]
        client.create_table(table, exists_ok=True)       # creates it, or does nothing if it exists
        check_same_shape(client.get_table(table.reference), table)

def check_same_shape(actual, expected):
    """exists_ok=True never changes an existing table, so compare, and fail loudly on any difference."""
    same = (actual.time_partitioning is not None
            and actual.time_partitioning.field == expected.time_partitioning.field
            and actual.time_partitioning.type_ == expected.time_partitioning.type_
            and actual.clustering_fields == expected.clustering_fields
            and columns(actual) == columns(expected))
    if not same:
        raise RuntimeError(f"{actual.table_id} in {actual.dataset_id} exists with a different shape: "
                           "drop it, run make bq-setup, then reload the window")

def columns(table):
    return [(f.name, STANDARD_NAMES.get(f.field_type, f.field_type), f.mode) for f in table.schema]
```

Why the comparison: `create_table(exists_ok=True)` returns quietly when the table exists, even if its schema differs from the JSON. Without the check, a changed schema would show up later as a confusing load error. Why the name map: a table read back from the API reports `INTEGER` and `BOOLEAN`, while the JSON may say `INT64` and `BOOL`.

### The same table in SQL DDL

For reading, and for the console if a table is ever created by hand. This is DDL, so the sandbox allows it, and it processes 0 bytes.

```sql
CREATE TABLE IF NOT EXISTS `<project>.raw.payment_events` (
  delivery_id   STRING    NOT NULL,
  event_id      STRING    NOT NULL,
  event_type    STRING    NOT NULL,
  payment_id    STRING    NOT NULL,
  order_id      STRING    NOT NULL,
  mid           STRING    NOT NULL,
  plan_id       STRING    NOT NULL,
  amount_minor  INT64     NOT NULL,
  currency      STRING    NOT NULL,
  event_ts      TIMESTAMP NOT NULL,
  delivered_ts  TIMESTAMP NOT NULL,
  is_synthetic  BOOL      NOT NULL,
  _arrival_date DATE      NOT NULL,
  _source_file  STRING    NOT NULL
)
PARTITION BY _arrival_date
CLUSTER BY mid
OPTIONS (
  description = "SYNTHETIC: generated by src/recon/generator.py. One row per webhook delivery that arrived on _arrival_date (UTC).",
  labels = [("data_origin", "synthetic")]
);
```

`settlement_lines` and `fx_rates` follow the same pattern, with their own columns, cluster column, description and label.

### Rules for raw tables

1. Create them with `CREATE TABLE IF NOT EXISTS` or `create_table(exists_ok=True)` only. Never `CREATE OR REPLACE TABLE` on a raw table: it would replace every partition at once.
2. Never set `expiration_timestamp`, `partition_expiration_days` or `require_partition_filter`. The sandbox's 60-day partition expiry stays as it is, and dbt reads every partition.
3. Partition columns are REQUIRED. A NULL would land in the special `__NULL__` partition, which cannot be deleted.
4. A schema change after gate G1 means: drop the table, run `make bq-setup`, and reload the whole window. This is why the generator and the loader are frozen at G1.

## Load protocol

The same function, `load_day(client, dataset, table, run_date, landing_dir)` in `src/recon/load.py`, runs in the DAG and on the host. In the DAG the client comes from `BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")` and `hook.get_client(project_id=hook.project_id, location="US")`. On the host it comes from `src/recon/bq.py`. For each (table, run date R):

1. Read the exact expected landing files of that table for R (for statements, one file per MID from `mids.csv`; never a glob), and join their rows in memory. A missing expected file is an error, not an empty day; a 0-byte file is a file with no rows (`docs/specs/data_and_generator.md`, heading "Empty days and missing files").
2. Assert that every row has `_arrival_date == R`; for payment events, also `DATE(delivered_ts) == R`. A wrong row fails the task before any job runs.
3. If there are no rows, delete the partition: `client.delete_table(f"{project}.{dataset}.{table}${R:%Y%m%d}", not_found_ok=True)`. A partition delete is a table operation, not DML.
4. Otherwise run exactly one load job into `<table>$YYYYMMDD`:

   ```python
   job_config = bigquery.LoadJobConfig(
       source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
       schema=schema,                                    # from the same schema JSON as the table
       write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
       create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
       max_bad_records=0,                                # one bad row fails the whole job
   )
   job = client.load_table_from_file(io.BytesIO(payload), f"{project}.{dataset}.{table}${R:%Y%m%d}",
                                     job_config=job_config, location="US")
   job.result()
   ```

   Leave `ignore_unknown_values` off (the default), so a row with an unexpected field fails the job.
5. Assert `job.output_rows == len(rows)`. Return `{table, rows, action, output_bytes, job_id}`.

What WRITE_TRUNCATE on `t$20261025` replaces: only the rows of the 2026-10-25 partition of `t`. Other partitions are untouched. Google's API reference says truncation happens "as one atomic update upon job completion", so a reader sees the old day or the new day, never a mix. For a partition decorator, WRITE_TRUNCATE replaces that partition's rows but keeps the table schema. A different schema makes the job fail, unless `schema_update_options` allows the change. Google's API reference (`schemaUpdateOptions`) lists only two such changes, adding a NULLABLE column and relaxing a REQUIRED column to NULLABLE, and this project never sets the option. That is why the schema JSON and the table must be identical. A load into a whole table, such as a shard in the fallback below, works differently: WRITE_TRUNCATE always replaces that table's schema with the load job's schema.

Why exactly one job per partition: two WRITE_TRUNCATE jobs into the same partition would overwrite each other, and WRITE_APPEND would make every rerun add duplicate rows.

Queries in Python go through the client, which uses GoogleSQL by default. Never use the hook's own query methods: they default to legacy SQL.

Never used: `insert_rows`, `insert_rows_json`, `insert_all`, GCS, `GCSToBigQueryOperator`, and any INSERT, UPDATE, DELETE or MERGE.

Shard fallback (only if G0 chose it): the destination becomes `<table>_YYYYMMDD` with `create_disposition=CREATE_IF_NEEDED`, because each day's shard is created by its first load. An empty day deletes its shard with `delete_table(..., not_found_ok=True)`.

## Partitioning and clustering

| Object | Partition | Cluster | Why |
|---|---|---|---|
| `raw.payment_events` | `_arrival_date`, DAY | `mid` | one run owns one arrival day. The partition is the unit of replacement, which is what makes reruns safe |
| `raw.settlement_lines` | `_arrival_date`, DAY | `mid` | the same |
| `raw.fx_rates` | `_arrival_date`, DAY | `provider` | the same. One rate date appears in up to 9 fetch partitions |
| `analytics.fct_recon_lines` | `recon_date`, DAY | `mid` | readers ask for a day and a MID. `recon_date` is never NULL |
| `analytics.fct_recon_daily` | `recon_date`, DAY | `mid` | the same; it carries the enforced contract |
| staging and intermediate views, `fct_recon_exceptions` | none | none | views store nothing |
| seeds | none | none | a few rows each |
| `probe.raw_pay`, `probe.smoke` | `d`, DAY | none | probes |

Notes:
1. At this size, partitioning and clustering do not change bytes billed. Every query is billed at least 10 MB per table it reads, and our tables are a few MB. They are here because the write path needs partitions, and because they show how the design would hold with more data. Say exactly that if asked.
2. Partition pruning needs a filter on the partition column that BigQuery can evaluate before the query runs, such as a literal date. A filter whose value comes from a subquery, like the staging filter `_arrival_date <= as_of_date`, may not prune. That is fine at this size; with real volumes it would be the first thing to change.
3. The dbt shape for the two marts is `partition_by={'field': 'recon_date', 'data_type': 'date', 'granularity': 'day'}` and `cluster_by=['mid']` (`docs/specs/dbt_project.md`). Each build re-creates them with CTAS, and dbt repeats the PARTITION BY and CLUSTER BY every time. A plain `CREATE OR REPLACE TABLE t AS SELECT * FROM t` without them fails on a partitioned table (third-party report, consistent with Google's DDL docs).
4. Limits (Google docs): 10,000 partitions per table; 4,000 partitions per job; 1,500 table modifications per table per day (load, copy and query jobs that write); 30,000 partition modifications per day for a column-partitioned table. The overnight backfill writes 28 partitions per raw table, and the rerun proof about 8 more.

## Rolling window and expiry

### The expiry facts

1. A date partition expires 60 days after the end of its day in UTC. Google computes partition expiry "from the partition boundary in UTC". Its example: with a 6-hour expiry, a daily partition expires at 06:00 UTC the next day. So partition D lives until (D + 61 days) 00:00 UTC. Example: `$20261004` lives through 2026-12-03 and expires at 2026-12-04 00:00 UTC.
2. Writing into a partition that is already older than the expiry expires it at once. Google documents this for copies and inserts; third parties saw it with CTAS and load jobs. The job still reports success.
3. Google deletes expired partitions in a background process, which "can take several days". Never plan to read anything during that time.
4. Unpartitioned tables and views expire 60 days after they were created. `CREATE OR REPLACE` gives them a new 60-day clock. dbt re-creates views, seeds and mart tables on every build, so they renew whenever dbt runs. A WRITE_TRUNCATE load into a whole unpartitioned table probably does not renew the clock (third-party report).
5. A date-partitioned table created in a dataset with a default partition expiry gets no table-level expiry, only partition expiry (Google's REST reference for datasets; probe P6 checks it on `probe.raw_pay`). So `raw.payment_events` itself should never disappear while it keeps receiving recent days. Nobody has shown this past day 60 yet: see the follow-up check below.
6. A table-level expiry overrides partition expiry. That is why no table in this project ever gets one.

### The window

| Item | Value |
|---|---|
| `RECON_WORLD_START` | 2026-10-04. The business opens that day; there are no payments before it |
| History loaded overnight | 2026-10-04 to 2026-10-31 (28 run dates) |
| Proof window | 2026-10-04 to 2026-11-01 (29 days; the 00:00 UTC run on 2026-11-02 adds 2026-11-01) |
| Oldest mart partition | `fct_recon_daily` can hold `recon_date` 2026-10-03: a USD capture between 00:00 and 04:59 UTC on 2026-10-04 has accounting date 2026-10-03 |
| Write guard | a run date must be on or after `RECON_WORLD_START`, before today (UTC), and not older than today minus 45 days |

Why 28 days and a 45-day guard: the window must stay young enough that every rerun in the week of the proof writes partitions with weeks of life left. On 2026-11-02 the oldest partition is 29 days old and has 32 days to live. A partition written at the guard's limit still has at least 15 days to live. A longer world would buy little and make every later rerun riskier.

### How the pipeline refuses old dates

The check lives in one function that both the DAG and the host CLI call, so `make day` on the host is guarded too (you write it):

```python
# src/recon/load.py
MAX_RUN_AGE_DAYS = 45

def check_run_date(run_date: date, world_start: date, today_utc: date) -> None:
    if run_date < world_start:
        raise ValueError(f"run date {run_date} is before RECON_WORLD_START {world_start}: "
                         "no business existed yet")
    if run_date >= today_utc:
        raise ValueError(f"run date {run_date} has not ended in UTC (today is {today_utc}): "
                         "use yesterday or earlier")
    if run_date < today_utc - timedelta(days=MAX_RUN_AGE_DAYS):
        raise ValueError(f"run date {run_date} is more than {MAX_RUN_AGE_DAYS} days old: its partition "
                         "would expire too soon. Pick a date inside the window. This guard is never lifted")
```

- DAG: `check_window` reads the wall clock once (`datetime.now(timezone.utc).date()`), calls `check_run_date`, and turns a `ValueError` into `AirflowFailException`, so the task fails at once with no retry. Its other checks (an exact 1-day interval that starts at 00:00 UTC) are in `docs/specs/airflow_and_docker.md`. Every later task receives R from `check_window`, so no task can write a date the guard did not accept.
- Host: `src/recon/cli.py` calls `check_run_date` before it generates or loads a day.
- FX: each request covers R-6..R, so it never asks for today or a later date.
- dbt never writes a raw partition. Its tables are rebuilt from whatever raw still holds.

### Timeline (dates in UTC)

| Date | What happens |
|---|---|
| 2026-11-01 | G0 probes. The overnight backfill writes 2026-10-04 to 2026-10-31 |
| 2026-11-02, 00:00 | the scheduled run writes 2026-11-01. The rerun proof runs this day |
| 2026-11-18 | the last day `check_window` accepts 2026-10-04 (today minus 45 days is 2026-10-04) |
| 2026-11-19 | `check_window` refuses 2026-10-04. Each later day refuses one more old date |
| 2026-12-03, 00:00 | the 2026-10-03 partition of `fct_recon_daily` expires. Later builds drop that day silently |
| 2026-12-04, 00:00 | raw partition 2026-10-04 expires. From here, the live window loses one old day per day |
| 2026-12-31 | follow-up check: `raw.payment_events` still exists with no table-level expiry, 60 days after it was created |
| 2027-01-01, 00:00 | raw partition 2026-11-01 expires: the last day of the proof window is gone |

After the live data is gone, the numbers survive in `docs/evidence/`. A rebuild resets the datasets and moves `RECON_WORLD_START` forward: the steps are in "Reset the datasets (moving the window)" below, and `make demo` (v1.x) will automate them. The generator keys on `day_index`, so the synthetic data and the reconciliation numbers come out the same in the new window; only the real FX rates differ.

If the DAG keeps running after the proof, each scheduled run adds one new day, and the window keeps moving forward by itself.

The follow-up check, on or after 2026-12-31:

```python
t = client.get_table(f"{client.project}.raw.payment_events")
print(t.created, t.expires, t.time_partitioning.expiration_ms)
```

Expected: the table exists and `expires` is None. Record the result in ADR-0009.

### Reset the datasets (moving the window)

Use this to build a fresh window after the published one has aged out. From 2026-11-19 (UTC), `check_window` refuses 2026-10-04, so the old window can no longer be reloaded. Every step is **You**: it changes the proof datasets and Airflow state. `make demo` (v1.x) will automate these steps.

Why the old datasets must go: staging has no world-start filter, and `stg_recon__as_of` takes `scope_start` from the oldest loaded day. Old partitions that have not expired yet would mix the old world into the new marts, and any days between the two windows would have no data, which `assert_arrival_days_complete` fails. Deleting `analytics` as well means nobody reads an old mart before the first new build.

Before you start:
- Work out `new_start`: yesterday (UTC) minus 27 days, so the new history is 28 days ending yesterday. Example: on 2026-12-10 (UTC), yesterday is 2026-12-09, the day before yesterday is 2026-12-08, and `new_start` is 2026-11-12.
- Deleting `raw` also deletes the table that the follow-up check above watches. If that check is still open, the new tables restart its clock: run it 60 days after this reset instead.

Steps:
1. Stop all writes. If the stack is down, run `make up`. Wait until nothing runs: `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state running`, and the same with `--state queued`, list nothing. Then `make pause`. Do not run `make day`, `make days` or `make dbt-build` until step 10.
2. Look for runs on the new dates: `docker compose exec airflow-scheduler airflow dags list-runs recon_daily -s <new_start>`. If it lists nothing, keep the Airflow history. If it lists any run, those days already ran against the tables you are about to delete, and a backfill skips every day that already has a run, so the new window would have holes. Then save any evidence you still need, and reset the Airflow metadata: `docker compose down --volumes`, then `make up` ("Reset the Airflow metadata (rare)" in `docs/specs/airflow_and_docker.md`).
3. In `.env`, set `RECON_WORLD_START=<new_start>`, unless you already did. Keep `RECON_SEED=20261101`: the same seed gives the same synthetic days on the new dates.
4. In the BigQuery console, delete `raw` and `analytics`, and also `raw_dev` and `analytics_dev` if you used them for development days. For each one: in the **Explorer** pane, expand the project, click **Datasets**, click the dataset, click **Delete**, type `delete`, and click **Delete**. The tables and views inside it are deleted with it (Google docs). Keep `probe`.
   - Deleting gives no storage back. Google says the lifetime 10 GiB "is not refunded upon data deletion", and the reload writes the window again, so those bytes count too (see "Storage guard"). From U3 on, leave `runs/ledger/` as it is, so the ledger total never drops.
   - Never create a second sandbox project instead of a reset.
5. `make bq-setup`. It creates `raw` and `raw_dev` again, each with its 3 tables, in `US`. dbt creates `analytics` and `analytics_dev` again on the first build of each target. Check the tables as in "Datasets": each **Details** tab shows partitioning by DAY on `_arrival_date`.
6. Restart the stack so the containers read the new `.env`: `make down`, then `make up`. The DAG stays paused.
7. `make unpause`. The scheduler creates the run for yesterday (UTC) at once. Wait until it is `success` (`docker compose exec airflow-scheduler airflow dags list-runs recon_daily`).
8. Load the rest of the window newest first. Follow "Backfill a range" and "The overnight history load" in `docs/specs/airflow_and_docker.md` (Mac on power, lid open, `caffeinate -is`):
   - `make backfill-dry FROM=<new_start> TO=<day before yesterday>` lists 27 rows, the first `<day before yesterday>` and the last `<new_start>`. If it lists fewer, some of these days still have runs: reset the Airflow metadata as in step 2, then continue from step 7.
   - `make backfill FROM=<new_start> TO=<day before yesterday>`. In the example: `FROM=2026-11-12 TO=2026-12-08`.
9. Done when: `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state success -s <new_start> -e <yesterday>` lists 28 runs, and the same with `--state failed` lists nothing. Then finish with "A rerun months later" in `docs/specs/data_and_generator.md`: commit the new FX files, and write the new numbers into a new dated folder under `docs/evidence/`.
10. To develop on the host again, reload the dev days you need with `make days FROM= TO=`, inside the new window, then `make dbt-build`.

## Storage guard

### The facts

- Google: "You are granted a lifetime limit of 10 GiB of storage. This quota is not refunded upon data deletion." This wording appeared on 2026-09-04; before that, the page said 10 GB a month.
- Google does not say what counts (bytes written or bytes stored, logical or physical, with or without time travel), and there is no counter to read.
- A third-party sandbox project hit "Quota exceeded: Your project exceeded quota for free storage for projects" while its visible tables were almost empty. That suggests deleted and expired bytes still count.
- So this project assumes the strict reading: every byte ever written counts.

### Budget (design estimate, not a result)

| Item | Estimate |
|---|---|
| raw data per arrival day | about 0.1 MB |
| one full dbt build | about 1 to 2 MB written (2 mart tables and 3 seeds; views store nothing) |
| builds through 2026-11-02 | about 80 (28 overnight, about 10 on 2026-11-02, about 40 development builds) |
| total written through 2026-11-02 | under 0.25 GiB |
| self-imposed cap before U3 | 1 GiB written |
| hard stop from U3 on | 8 GiB in the bytes-written ledger, 2 GiB below the lifetime 10 GiB |

### Habits that keep writes small

1. Staging and intermediate models are views. Only `fct_recon_lines` and `fct_recon_daily` are tables.
2. Raw data stays at about 0.1 MB a day.
3. In development, build only what changed with a `--select` (the exact command is in `docs/specs/dbt_project.md`), or use `--empty` to check SQL and schemas without writing rows.
4. Reprocess the 7 days the proof needs, not the whole window. The full-window reprocess waits for U3, after the ledger exists.
5. Never create a second sandbox project to reset the quota.

### Measuring stored bytes: `scripts/storage.py` and `make storage` (v1.0)

`make storage` runs `uv run python scripts/storage.py`. By default the script writes `docs/evidence/<UTC date>/storage.json`. To choose the file, pass `OUT=`, which the Makefile hands to the script as `--out`: for example `make storage OUT=docs/evidence/2026-11-02/storage.json`. Agent may scaffold the IO; you write the queries.

For each of `raw`, `raw_dev`, `analytics`, `analytics_dev` and `probe`:
1. Read `__TABLES__`, one query per dataset:

   ```sql
   SELECT table_id, row_count, size_bytes,
          TIMESTAMP_MILLIS(creation_time)      AS created,
          TIMESTAMP_MILLIS(last_modified_time) AS last_modified
   FROM `<project>.<dataset>.__TABLES__`
   ```

   `__TABLES__` is a legacy metadata table. Google's current docs point to `INFORMATION_SCHEMA` instead, but `__TABLES__` still works in third-party reports and needs no project option (P7 confirms it). Views show size 0.
2. If `__TABLES__` fails, use the table API instead: `client.list_tables(dataset)`, then `client.get_table(item).num_bytes` and `.num_rows`. No query, no bytes processed.
3. Then try TABLE_STORAGE once for the whole project. If it is readable, record its totals per dataset, including deleted tables still held for time travel:

   ```sql
   SELECT table_schema,
          deleted,
          SUM(total_logical_bytes)        AS logical_bytes,
          SUM(total_physical_bytes)       AS physical_bytes,
          SUM(time_travel_physical_bytes) AS time_travel_bytes,
          SUM(fail_safe_physical_bytes)   AS fail_safe_bytes
   FROM `region-us`.INFORMATION_SCHEMA.TABLE_STORAGE
   WHERE table_schema IN ('raw', 'raw_dev', 'analytics', 'analytics_dev', 'probe')
   GROUP BY table_schema, deleted
   ```

   If it fails, record the error text and go on. Google says the view is usually a few seconds to a few minutes behind, and expiration changes can take up to a day to show.

`storage.json` fields (values come only from a run):

| Field | Meaning |
|---|---|
| `measured_at_utc` | when the script ran |
| `git_sha` | the commit the script ran from |
| `method` | `__TABLES__` or `api` |
| `datasets.<name>.tables`, `.views`, `.rows`, `.logical_bytes` | per dataset, from step 1 or step 2 |
| `total_logical_bytes` | the sum over all datasets |
| `table_storage` | the step 3 totals, or `{"readable": false, "error": "<text>"}` |
| `ledger_total_bytes` | from U3 on, the bytes-written ledger total; `null` before |
| `note` | "Bytes stored now. The lifetime quota may count every byte ever written, so this is a lower bound." |

The file holds no project id: the script uses the same `redact` as the probe script.

When to run it: after the overnight backfill, and after the rerun proof on 2026-11-02 (`make storage OUT=docs/evidence/2026-11-02/storage.json`).

Checking the 1 GiB self-cap before U3, by estimate: bytes written ≈ (raw stored bytes) x (1 + the number of times each day was reloaded) + (number of dbt builds) x (stored bytes of the analytics tables after one build). If this passes 1 GiB, stop and build the U3 ledger before writing more.

Optional, to make TABLE_STORAGE readable: as the project owner, in the BigQuery console, run Google's documented statement:

```sql
ALTER PROJECT `<project>`
SET OPTIONS (`region-us.enable_info_schema_storage` = TRUE);
```

It is DDL, not DML, but nobody has reported it in a sandbox (to be probed if you try it). Google says to allow about a day for the full history to appear. `__TABLES__` stays the default either way.

### The bytes-written ledger (U3, after v1.0)

What it counts, per write:
1. Load jobs: `job.output_bytes`, which `load_day` already returns.
2. dbt builds: the stored size (`num_bytes`) of every table and seed that the build created or replaced, read with `client.get_table(...)` after the build. Views count 0.
3. From U5: the temporary tables that `copy_partitions` writes (dbt writes that data twice).

What it misses (documented, and covered by the 2 GiB margin): the partial writes of failed builds (at most one build's tables, about 2 MB each), time-travel and fail-safe copies, and metadata.

Where it lives and how it is written:
1. One JSON file per record under `runs/ledger/`, named `<UTC timestamp to the microsecond>_<run date>_<dag or host>.json`, with the fields `recorded_at_utc`, `source`, `run_date`, `loads` (table, output_bytes, job_id), `dbt_tables` (table, num_bytes) and `bytes_written`.
2. Files are never overwritten and never deleted. A reprocessed day adds a new file, because its bytes were written again. One file per record means parallel tasks never race on one file.
3. Writers: `load_day` after each successful load job, the U3 `record_run` task after `dbt_build`, and `make dbt-build` on the host after dbt finishes.
4. A new environment variable gives the folder: `RECON_RUNS_DIR` (host `$(CURDIR)/runs`, container `/opt/airflow/runs`).
5. Baseline: when U3 starts, write one file `<timestamp>_baseline_host.json` with the estimate of everything written before the ledger existed (the formula above, rounded up).
6. `runs/` is gitignored, so the ledger exists only on this machine. `make storage` copies its total into `storage.json`, which is committed.

The stop: `check_window`, and the host commands that call `check_run_date`, sum `bytes_written` over `runs/ledger/*.json` and fail when the total reaches 8 GiB (8,589,934,592 bytes), with the message "Storage ledger at [X] GiB, at or above the 8 GiB stop: stop and decide in ADR-0001 (docs/adr/0001-warehouse-bigquery-sandbox.md)". Never raise the limit to make a run pass. The stop is not a Plan B trigger on its own (see "When to switch" under "Plan B: the GCP Free Trial").

U3 also adds `make no-dml`: it searches the compiled SQL and the dbt logs for `merge into`, `insert into`, `delete from` and `update ... set`, and must find 0 matches (`docs/build_plan.md`).

### If the storage quota error appears

"Quota exceeded: Your project exceeded quota for free storage for projects" (RESOURCE_EXHAUSTED; third-party report) on any load or build:
1. Stop all writes. Pause `recon_daily` (`airflow dags pause recon_daily`); if a backfill is running, cancel it first (see the "Operations runbook" in `docs/specs/airflow_and_docker.md`). Run nothing on the host.
2. Run `make storage` and keep the output.
3. Log it in `docs/failure_log.md`.
4. Switch to Plan B. Never create a second sandbox project.

## Query bytes guard

### Where the cap is set

- dbt: `maximum_bytes_billed: 1000000000` in both targets of `dbt/profiles.yml`. dbt sends it with every query. dbt's docs: queries "will fail if they exceed the configured maximum bytes threshold".
- Python: every query goes through `src/recon/bq.py`, which sets `QueryJobConfig(maximum_bytes_billed=1_000_000_000)`. The probe script sets the same value itself.
- Load jobs, copy jobs and partition deletes are not queries. They are free and process no bytes.

### How it behaves (Google docs)

- BigQuery estimates the bytes before the query runs. If the estimate is over the limit, "the query fails without incurring a charge".
- The error looks like Google's example: "Query exceeded limit for bytes billed: 1000000. 10485760 or higher required." The second number is what the query would bill.
- The value must be at least 10485760 (10 MB), because every query is billed at least 10 MB. A lower value makes every query fail.
- For clustered tables the estimate is an upper bound, so a query can fail even when it would have billed less.
- In the sandbox nothing can be charged, so here the cap protects the monthly 1 TiB and stops runaway queries. It matters for money only on Plan B. The optional check in the G0 runbook shows whether the sandbox enforces it.

### `src/recon/bq.py` (agent may scaffold; you read it)

```python
import logging
import os

from google.cloud import bigquery

MAX_BYTES_BILLED = 1_000_000_000
log = logging.getLogger(__name__)

def host_client() -> bigquery.Client:
    """Host only. Credentials come through ADC: GOOGLE_APPLICATION_CREDENTIALS (the key), or the gcloud file in the fallback."""
    return bigquery.Client(project=os.environ["GCP_PROJECT"], location="US")

def query(client, sql, params=(), *, dry_run=False, use_cache=True) -> bigquery.QueryJob:
    """Every Python query in the project goes through here, Airflow tasks included (client from the hook)."""
    config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        query_parameters=list(params),
        dry_run=dry_run,
        use_query_cache=use_cache and not dry_run,
    )
    job = client.query(sql, job_config=config, location="US")
    if not dry_run:
        job.result()
    log.info("query job=%s bytes_processed=%s bytes_billed=%s cache_hit=%s",
             job.job_id, job.total_bytes_processed, job.total_bytes_billed, job.cache_hit)
    return job

def rows(job) -> list[dict]:
    """Read a query result row by row. No pandas, no Storage Read API."""
    return [dict(row.items()) for row in job.result()]
```

### The monthly query budget (design estimate)

- One full `dbt build` sends about 50 to 100 queries (models and tests). At the 10 MB minimum per table read, it bills about 1 to 3 GB.
- About 80 builds through 2026-11-02 come to about 80 to 240 GB, under a quarter of November's 1 TiB. The fingerprints, the results script and the probes add a few GB.
- If the monthly allowance runs out, queries fail until the next month. Nothing is charged. Cut development builds first.

## Measuring bytes honestly

### Four different numbers

| Number | What it is | Where to read it |
|---|---|---|
| bytes processed | what a query reads | `job.total_bytes_processed`; a dry run gives an estimate |
| bytes billed | bytes processed, rounded up to at least 10 MB per table read and per query | `job.total_bytes_billed` |
| bytes written | what a load or a rebuild adds to storage | a load job's `output_bytes`; a rebuilt table's `num_bytes` |
| bytes stored | what the tables hold now | `make storage` |

### Where to read them

1. One Python query: `src/recon/bq.py` logs bytes processed, bytes billed and the cache hit for every job.
2. Before a query runs: a dry run (`query(client, sql, dry_run=True)`), or the console's query validator ("This query will process ... when run"). Both estimate and read nothing.
3. One dbt build: `run_results.json` holds `adapter_response.bytes_processed` and `bytes_billed` for each node. The DAG keeps one per run date in `runs/dbt/<run date>/target/`; host builds write `dbt/target/run_results.json`. To sum one build:

   ```bash
   uv run python - runs/dbt/2026-10-31/target/run_results.json <<'EOF'
   import json, sys
   results = json.load(open(sys.argv[1]))["results"]
   def total(key):
       return sum((r.get("adapter_response") or {}).get(key) or 0 for r in results)
   print(f"nodes={len(results)} bytes_processed={total('bytes_processed')} bytes_billed={total('bytes_billed')}")
   EOF
   ```

4. Job history: in the console as the project owner, or with a query on `` `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT `` run in the console. The service account cannot read job history (no `bigquery.jobs.list`), on purpose.
5. Stored bytes: `make storage`.

### Rules

1. Turn the cache off when you measure (`use_cache=False`). A cache hit processes 0 bytes and proves nothing.
2. Report bytes processed and bytes billed side by side, and say that billing rounds up to 10 MB per table and per query. At this size, bytes billed mostly counts queries.
3. Name the state you measured: the date, window, seed, git SHA and as_of, like every other number in `docs/evidence/`.
4. Say "MB processed", never dollars. The sandbox costs $0, so any price would be invented.
5. Never compare a "daily run" with a "full rebuild" in v1.0. Every build is a full rebuild of a few MB, so the two numbers would be about the same.
6. Count the tests too: dbt tests are queries.
7. Bytes are never a headline result. They belong in the README section "Cost and storage", with the measuring command next to them.

Suggested wording for the README section "Cost and storage" (fill it only from a run):

> Cost: $0 (BigQuery sandbox, no billing account). One full `dbt build` on [date] processed [P] MB and billed [B] MB (BigQuery bills at least 10 MB per table read and per query). Stored: [S] MB across 5 datasets (`make storage`, [date]).

## Reading data from BigQuery

Rule: read data only with SELECT query jobs.

1. Google's sandbox sample code says: "BigQuery Sandbox users can only use the BigQuery Storage API to download query results". Reading a table directly through the Storage Read API is not allowed there.
2. The service account has no BigQuery Read Session User role either, so the Storage Read API would be refused anyway.
3. In Python, read a query result row by row: `rows(query(client, sql))` from `src/recon/bq.py`. If pandas is ever used, call `job.to_dataframe(create_bqstorage_client=False)`, so the client never tries the Storage Read API.
4. Never call `client.list_rows(table).to_dataframe()` on a table.
5. In the console, the **Preview** tab of a table shows rows without writing a query. A `SELECT *` in the editor is a real query.
6. To see whether the Storage Read client is installed in the host venv: `uv pip show google-cloud-bigquery-storage`. The rule above holds either way.

## Data Studio (optional)

Status: Data Studio is the new name of Looker Studio (since April 2026). Google's connector doc says "you must provide a Google Cloud project that has an associated Google Cloud Billing account". Third parties report that it works on sandbox projects anyway (July to October 2026). So it is officially unsupported here, and it is not part of v1.0.

A 5-minute test, when the time comes:
1. Open Data Studio with the personal account. Create a report, and add a data source: **BigQuery**, **My projects**, the sandbox project, dataset `analytics`, table `fct_recon_daily`. Connect.
2. Add one table chart with `recon_date`, `mid` and `unexplained_minor`. Put "SYNTHETIC payments, REAL NBK rates. Learning project." in the report title.
3. Share it view-only by link, and open the link in a private browser window.

- Pass: the chart renders, and no screen asks for billing.
- Fail: use dated screenshots in `docs/img/` and the README tables instead.

Rules if it is used:
1. Keep the owner's credentials (the default). Report viewers then need no BigQuery access.
2. Connect marts in `analytics` only, never raw tables.
3. Every chart refresh is a query in the sandbox project. Google: "The selected project is used for both billing and data access." Each refresh bills at least 10 MB of the monthly 1 TiB.
4. The report breaks when its tables expire, or when dbt has not run for 60 days. Keep a dated screenshot in the README.
5. The README first screen never depends on it.

## Plan B: the GCP Free Trial

### When to switch (any one of these)

1. G0: P3 fails, and the shard check fails too.
2. The storage quota error appears on any load or build.

These two are the only triggers, as in ADR-0001. Two other events stop all writes but do not switch on their own: the U3 ledger reaching its 8 GiB stop, and a Google change to the sandbox that stops load jobs or DDL from working. For either one, stop and decide in ADR-0001 (its "Revisit when" list), because the trial can be used only once.

Not a reason: wanting MERGE or snapshots before v1.0 is green, wanting Data Studio, wanting a longer history, or a bug in our own code.

A later, separate use (v3): a time-boxed demo of MERGE and dbt snapshots, only after v1.x. The trial exists only once per person, so that demo would use up Plan B. Decide it on purpose and write the decision into ADR-0001.

### Facts (Google docs)

- $300 of credit for 90 days. "You will not be billed for any Google Cloud usage during your Free Trial."
- A card is required. Google places a temporary hold of $0.00 to $1.00, which is released later. It is not a charge.
- Eligibility: never a paying user of Google Cloud, Google Maps Platform or Firebase, and no earlier Free Trial. Confirmed: no earlier payment and no earlier trial (checked 2026-11-01).
- Cards: Visa or Mastercard, credit or debit. Prepaid cards are refused. Debit cards that need a one-time code for every online payment are refused. Virtual cards may be refused. The card must allow international and recurring payments, and the name and address must match the bank's records. Turn off any VPN.
- For some accounts, "certain types of payment methods require a one-time prepayment", which "differs by country and currency" (Google's payment-methods doc). Two forum users were asked for one at trial sign-up in late 2025 (third-party report).
- The trial cannot be paused or extended. At day 90, or when the credit is spent, billing is disabled and resources stop. After a 30-day grace period they are deleted. No page says the project falls back to sandbox mode, so treat the warehouse as gone after day 90.
- Upgrading is a manual click on **Activate**. Google: "Upgrading to a Paid billing account ends your Free Trial", and from then on the card can be charged automatically.
- The BigQuery free tier (1 TiB of queries and 10 GiB of storage a month) applies during the trial.
- In a project linked to the trial billing account: DML works, new datasets get no 60-day expiry, and storage is 10 GiB a month.

### Before you start (5 minutes)

1. Use your own Visa or Mastercard. Never anyone else's card or billing account.
2. VPN off. Use the personal Google account, the same one as the sandbox.
3. Write down today's date as trial day 1. Put day 80 (export the evidence) and day 90 (the end) into the calendar now.

### Sign-up (You, about 15 minutes)

1. Open https://cloud.google.com/free and click **Get started for free**. Sign in with the personal account.
2. Country: Kazakhstan. If Kazakhstan is not offered, stop: Plan B is not available.
3. Read the Free Trial terms. Accept only if you agree.
4. Account type: **Individual**. It cannot be changed later.
5. Payments profile: create a new one, with your name and address exactly as the bank has them.
6. Payment method: your card.
7. Stop here, without submitting, if any of these is true:
   - the page asks for a prepayment, or says an amount will be charged to activate the account (anything other than the temporary $0.00 to $1.00 hold);
   - the card is refused after you have checked the details once more;
   - the page asks for a bank verification you cannot complete;
   - the page says the account will be a paid account, or that charges are automatic.

   Write down exactly what the screen said, close the tab, and go back to the sandbox. If the sandbox cannot carry the build either, stop the build and record it in ADR-0001: this project uses no other warehouse.
8. Submit.
   You should see: a Free Trial billing account with $300 of credit. The sign-up may also create a project called "My First Project".
9. Check: **Billing**, **Overview**. The **Free credit** pane shows the credit and the days left. Never click **Activate**, there or on the **Welcome** page.

### Project and guardrails on day 1 (You, about 20 minutes)

1. Use a new project linked to the trial billing account. Either use "My First Project" if the sign-up created it (rename its display name to `ledger-vs-statement-trial`), or create a new project named `ledger-vs-statement-trial`, with **No organization** and the trial billing account. Never link the sandbox project: it stays a sandbox.
2. Check **Billing**, **Account management**: only the trial project is linked.
3. Budget alert: **Billing**, **Budgets & alerts**, **Create budget**.
   - Type: alerts only. Name: `lvs-trial-1-usd`.
   - Scope: Projects: the trial project. Services: all. Under **Savings**, clear **Promotional credits** (the trial credit is one) and keep **Free tier credits** selected. The budget then tracks what I would pay without the trial credit, which should stay at $0.
   - Amount: specified amount, $1.
   - Actions: thresholds at 50%, 90% and 100% of actual spend; email alerts to billing admins and users.
   - Google: a budget "doesn't automatically cap" usage or spending. It only alerts.
4. `maximum_bytes_billed` stays at 1,000,000,000 in `dbt/profiles.yml` and `src/recon/bq.py`. Check it: `grep -n maximum_bytes_billed dbt/profiles.yml src/recon/bq.py`.
5. Optional: a custom quota for **Query usage per day** on the BigQuery API (**IAM & Admin**, **Quotas**), for example 25 GiB a day. Google calls custom quotas approximate, and whether the trial console accepts a value this low is not verified. Skip it if it is refused.
6. Use nothing else: no BigQuery Studio notebooks, no Spark procedures, no Cloud Storage buckets, no other APIs.

### Moving the code (You, about 1 hour)

1. In the trial project, create the service account `lvs-pipeline` with the same two roles, and a new JSON key (as in S1.2). Put it at `keys/sa.json`. Delete the old key in the sandbox project's **Keys** tab, so only one key is live.
2. In `.env`, set `GCP_PROJECT` to the trial project id.
3. Create the dataset `probe` in `US` in the console (as in S1.1 step 10). Then run `make bq-setup`: it creates `raw` and `raw_dev` and their tables fresh in `US`. dbt creates `analytics` and `analytics_dev` on its first build.
4. Check that no dataset has a default expiration. As the owner, in the console:

   ```sql
   SELECT schema_name, option_name, option_value
   FROM `region-us`.INFORMATION_SCHEMA.SCHEMATA_OPTIONS
   ORDER BY schema_name, option_name;
   ```

   It must show no `default_table_expiration_days` and no `default_partition_expiration_days`. Run it again after the first dbt build, so the two analytics datasets are checked too.
5. Run `make probe ARGS="--plan-b"`. With `--plan-b`, P2 passes when the INSERT is accepted (billing is linked), and P6 passes when there are no default expirations. Record the results in ADR-0001.
6. Restart the stack so the containers read the new `.env`: `make down`, then `make up`.
7. Reload the window with the backfill and reprocess commands of the "Operations runbook" (`docs/specs/airflow_and_docker.md`): the existing DAG runs belong to the old project, so they need `--reprocess-behavior completed`. Then run the pipeline exactly as planned. The code stays DML-free, and the 45-day guard stays. Nothing else changes.
8. ADR-0001: write "Plan B in use since [date] because [trigger]".

### During the trial

1. Once a week: **Billing**, **Overview**. The credit used should stay near $0. If more than $1 of credit is used, or a budget email arrives, stop all runs and read **Billing**, **Reports**, grouped by SKU.
2. Never click **Activate** or **Upgrade**.
3. Day 80: export the evidence: `docs/evidence/`, screenshots, and small CSV exports of the marts made with SELECT queries.
4. Day 90: the trial ends. Do nothing. Never upgrade.
5. After day 90 the warehouse is gone. The repo and the committed evidence stay.

### Stop conditions in one place

| When | Stop if | Then |
|---|---|---|
| sign-up | a prepayment is asked; the card is refused; a bank verification is impossible; "paid account" or automatic charges | close the tab; record it; go back to the sandbox, or stop the build |
| day 1 | the sandbox project shows a billing account | remove the link at once, and check that nothing ran there with billing |
| any time | a budget email; more than $1 of credit used | stop all runs; read **Reports**; log it |
| any time | any Activate or Upgrade prompt | never click it |
| day 90 | the trial ends | let it end |

## BigQuery failure modes

Exact error texts are quoted only where a source shows them. The other rows describe the symptom.

| Symptom | Likely cause | What to do |
|---|---|---|
| a 403 containing "DML queries are not allowed in the free tier" | a DML statement: a `merge` incremental, a snapshot, an INSERT in a script | change the materialization or the script; U3's `make no-dml` checks the logs |
| "Quota exceeded: Your project exceeded quota for free storage for projects" | the lifetime storage quota | see "If the storage quota error appears" |
| a quota error on queries late in the month | the monthly 1 TiB | wait for the next month and cut development builds. Nothing is charged |
| "Query exceeded limit for bytes billed: 1000000000. [N] or higher required." | a query would bill more than 1 GB | read the query: a missing filter, or a join that multiplies rows. Never raise the cap to make it pass |
| a load fails with notFound for the table | the table was never created (`CREATE_NEVER`) | run `make bq-setup`, or let `ensure_tables` run first |
| a dataset is "not found in location" | the job ran in another location | `location="US"` in the client, the connection and the profile |
| Access Denied, or a permission such as `bigquery.jobs.create` denied | a wrong `GCP_PROJECT`, a missing role, or a key from another project | compare `.env` with the console; check the two roles in IAM |
| access denied on `INFORMATION_SCHEMA.JOBS` views from a script | the service account has no `bigquery.jobs.list`, on purpose | read job history in the console as the owner |
| a load fails because rows do not belong to the decorator's partition | a generator or loader bug | the loader's assertion should catch it first; fix it, then clear `load_raw` |
| a load fails on a TIMESTAMP or DATE value | the text format | write `YYYY-MM-DD HH:MM:SS+00:00` and `YYYY-MM-DD` (P3 proves the format) |
| a load fails on an unknown field or a missing REQUIRED field | the landing rows and the schema JSON disagree | fix the generator or the JSON. Never turn on `ignore_unknown_values` |
| `ensure_tables` says a table "exists with a different shape" | the schema JSON changed after the table was created | drop the table, run `make bq-setup`, reload the window |
| "INFORMATION_SCHEMA.TABLE_STORAGE hasn't been enabled for project <project>." | the view needs a project option | use `__TABLES__`, or enable the option as the owner |
| old days show 0 rows, with no error | their partitions passed 60 days | expected from 2026-12-03; the numbers live in `docs/evidence/` |
| a view, seed or mart table is missing | it passed 60 days since dbt last created it | `make dbt-build` re-creates it |
| `DefaultCredentialsError` on the host | `GOOGLE_APPLICATION_CREDENTIALS` points at a missing file | check the path; in the ADC fallback, the Makefile must not export it at all |
| a permission error about read sessions | something used the Storage Read API | read through a query; `to_dataframe(create_bqstorage_client=False)` |
| the key file is not readable inside a container | the file owner or mode does not match `AIRFLOW_UID` | check `AIRFLOW_UID` in `.env` (your `id -u`) and `ls -l keys/sa.json` |

## Teardown

When the project is finished, or before anyone else uses the machine:
1. Delete the service-account key: **IAM & Admin**, **Service accounts**, `lvs-pipeline`, **Keys**, delete. Then run `rm keys/sa.json`.
2. If the ADC fallback was used: `gcloud auth application-default revoke`.
3. The datasets: deleting them is optional, and it gives no storage back. Their data expires by itself (see "The expiry facts"), but the datasets themselves stay until you delete them. If you may rebuild later, you can leave them: "Reset the datasets (moving the window)" deletes the ones a rebuild needs. For a clean console, delete `raw`, `raw_dev`, `analytics`, `analytics_dev` and `probe` with the console steps in that procedure. The README's "Teardown" gives the same advice to readers who ran their own copy.
4. Keep the sandbox project. It costs nothing, and `make demo` (v1.x) can rebuild a fresh window in it later.
5. On Plan B: let the trial end. Never upgrade.

## Sources

Read on 2026-11-01. The date after each Google page is its "Last updated" line; many pages show dates in late October 2026, which says that a page is current, not when a rule changed.

Google Cloud and BigQuery:
- BigQuery sandbox (2026-10-27): https://docs.cloud.google.com/bigquery/docs/sandbox
- Managing partitioned tables (2026-10-27): https://docs.cloud.google.com/bigquery/docs/managing-partitioned-tables
- Loading data into partitioned tables (2026-10-27): https://docs.cloud.google.com/bigquery/docs/load-data-partitioned-tables
- REST reference, Job resource: load `writeDisposition`, `createDisposition`, `schemaUpdateOptions`, `outputBytes`, `outputRows` (API discovery revision 20261009): https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/Job
- REST reference, datasets (`defaultPartitionExpirationMs`): https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/datasets
- Managing datasets, deleting a dataset in the console (its tables and views go with it): https://docs.cloud.google.com/bigquery/docs/managing-datasets
- TABLE_STORAGE view (2026-10-28): https://docs.cloud.google.com/bigquery/docs/information-schema-table-storage
- Access control, predefined roles and permissions: https://docs.cloud.google.com/bigquery/docs/access-control
- Quotas and limits (2026-10-29): https://docs.cloud.google.com/bigquery/quotas
- Cost best practices, maximum bytes billed: https://docs.cloud.google.com/bigquery/docs/best-practices-costs
- Pricing (the 10 MB minimum, no charge for errors and cache hits, free operations): https://cloud.google.com/bigquery/pricing
- Error messages (2026-10-27): https://docs.cloud.google.com/bigquery/docs/error-messages
- Sandbox sample, Storage API only for query results: https://docs.cloud.google.com/bigquery/docs/samples/bigquery-pandas-public-data-sandbox
- Creating and managing projects, project ID rules (2026-10-26): https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects
- Verify that billing is enabled (2026-10-26): https://docs.cloud.google.com/billing/docs/how-to/verify-billing-enabled
- Create service accounts (2026-10-29): https://docs.cloud.google.com/iam/docs/service-accounts-create
- Create and delete service account keys (2026-10-29): https://docs.cloud.google.com/iam/docs/keys-create-delete
- Secure-by-default organizations (2026-10-26): https://docs.cloud.google.com/resource-manager/docs/secure-by-default-organizations
- How Application Default Credentials works (2026-10-29): https://docs.cloud.google.com/docs/authentication/application-default-credentials
- Set up ADC for a local development environment (2026-10-29): https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment
- Free Trial and Free Tier (2026-10-27): https://docs.cloud.google.com/free/docs/free-cloud-features
- Free Trial terms: https://cloud.google.com/terms/free-trial
- Payment methods (2026-10-26): https://docs.cloud.google.com/billing/docs/how-to/payment-methods
- Create a billing account (2026-10-26): https://docs.cloud.google.com/billing/docs/how-to/create-billing-account
- Budgets and budget alerts (2026-10-26): https://docs.cloud.google.com/billing/docs/how-to/budgets
- Custom quotas (2026-10-27): https://docs.cloud.google.com/bigquery/docs/custom-quotas
- Google Cloud Terms (last modified 2026-10-12): https://cloud.google.com/terms
- Data Studio BigQuery connector (2026-10-26): https://docs.cloud.google.com/data-studio/connect-to-google-bigquery

dbt and tools:
- Connect BigQuery to dbt Core (`maximum_bytes_billed`, OAuth via gcloud; the dbt v1 part of the page source): https://docs.getdbt.com/docs/local/connect-data-platform/bigquery-setup
- dbt BigQuery configs (`copy_partitions`): https://docs.getdbt.com/reference/resource-configs/bigquery-configs
- dbt-bigquery 1.12.1: https://pypi.org/project/dbt-bigquery/1.12.1/
- dbt-adapters issue 2086 (NULL partition values with `copy_partitions`): https://github.com/dbt-labs/dbt-adapters/issues/2086
- Homebrew cask `gcloud-cli` (591.0.0): https://formulae.brew.sh/cask/gcloud-cli
- Frankfurter: https://frankfurter.dev/

Third-party reports (self-reported; used to design the probes, never as proof):
- Decorator loads and `copy_partitions` in a sandbox: https://github.com/HabilMB/indonesia-haze-monitor/pull/1 and https://github.com/HabilMB/indonesia-haze-monitor/pull/2
- Sandbox platform notes (expiry caps, TABLE_STORAGE): https://github.com/ayush-ranjan-official/people-analytics-warehouse/blob/main/docs/platform-notes.md
- Expiry errors and silent row loss after a CTAS: https://github.com/Ardiyanto24/nirwana-database/blob/main/milestones/2.3-layer-intermediate-mart-cleaned/logs.md
- The free-storage quota error: https://github.com/MakerParsDev/android-multi-app-framework/issues/401
- The DML error text (forum, 2024): https://discuss.google.dev/t/bigquery-on-90-day-free-trial-cannot-do-dml/162474
- A prepayment request at trial sign-up (forum, 2025): https://discuss.google.dev/t/google-cloud-free-trial/284530
