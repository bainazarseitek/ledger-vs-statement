Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# Airflow and Docker spec

This file is the reference for everything that runs Airflow in `ledger-vs-statement`:
1. **Docker packaging**: the image with dbt in its own virtual environment, the changes to the course `docker-compose.yaml`, the mounts, the read-only key, the environment variables and the Google Cloud connection.
2. **The DAGs**: `recon_daily` and `smoke_bigquery`, setting by setting and task by task, with code shapes.
3. **Operations runbook**: every day-to-day procedure, with exact Airflow 3.3.2 commands and UI clicks.
4. **Failure scenarios and what to do.**
5. **Later upgrade: Cosmos**, with exact pins.

Every CLI flag here was checked against the Airflow 3.3.2 CLI reference on 2026-11-01. Where the docs say nothing, the behaviour was read in the 3.3.2 source code. "Sources" at the end lists both.

Who writes what:
- You write `dags/recon_daily.py` and `dags/smoke_bigquery.py`. The code shapes below are skeletons: imports, decorators and wiring, with the logic in numbered comments. You turn the comments into code and can explain every line.
- An agent may scaffold the `Dockerfile`, `docker/requirements-dbt.txt`, the compose edits and the Makefile targets. You check each line against this file before the first build.

Other files:
- the generator, the landing files and the FX fetch: `docs/specs/data_and_generator.md`;
- datasets, raw tables, the load protocol and the G0 probes: `docs/specs/bigquery_sandbox_and_costs.md`;
- dbt models and tests: `docs/specs/dbt_project.md`;
- the hour-by-hour plan and step ids such as S2.1: `docs/build_plan.md`;
- the ideas behind this file (data interval, logical date, pools, backfill vs reprocess vs clear): `docs/learning/concepts.md`, "Part 3. Airflow 3".

## At a glance

| Item | Value |
|---|---|
| Base image | `apache/airflow:3.3.2` (Python 3.13.15 inside) |
| Custom image | `ledger-vs-statement-airflow:3.3.2`, built from the repo-root `Dockerfile` |
| dbt in the containers | `/opt/airflow/dbt_venv/bin/dbt`: dbt-core 1.12.6, dbt-bigquery 1.12.1, dbt-core-experimental-parser 2.0.8 |
| dbt on the host | `uv run dbt` with the same three pins (wrapped by `make`); never a bare `dbt` |
| Compose file | `docker-compose.yaml`, a copy of the course file with the changes in "docker-compose.yaml: the changes to the course file" |
| Executor | LocalExecutor: every task runs inside the `airflow-scheduler` container |
| UI and REST API | http://localhost:8083, user `airflow`, password `airflow` |
| DAGs | `recon_daily` (one run per UTC arrival day) and `smoke_bigquery` (manual only) |
| Timetable | `CronDataIntervalTimetable("0 0 * * *", timezone="UTC")` |
| Pool | `dbt_serial`, 1 slot, created by `airflow-init` |
| Connection | `google_cloud_default`, defined only by `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT` |
| Key | `keys/sa.json` on the host, `/opt/airflow/keys/sa.json` read-only in the containers |
| What the DAGs write | `recon_daily`: dataset `raw` (load jobs) and `analytics` (dbt target `airflow`). `smoke_bigquery`: dataset `probe` only |
| Where Airflow CLI commands run | `docker compose exec airflow-scheduler airflow ...`, from the repo root |

## Words used in this document

Short definitions. The full explanations are in `docs/learning/concepts.md`.
- **Data interval.** The time range a run is responsible for, `[data_interval_start, data_interval_end)`. Here it is always one UTC day.
- **Logical date.** The name of a run's day. For `recon_daily` it equals `data_interval_start`.
- **run_after.** The earliest moment a run may start. For `recon_daily` it is the end of the interval.
- **Run id.** The unique name of a run. In 3.3.2 it is the run type plus `run_after`, so it shows the day after the processed day: `backfill__2026-10-31T00:00:00+00:00` processes 2026-10-30.
- **Run D.** In this project, always the run whose logical date is D. It processes UTC day D.
- **Backfill.** Create runs for a range of logical dates.
- **Reprocess.** Rerun days that already finished: a backfill with `--reprocess-behavior completed`.
- **Clear.** Reset some or all task instances of an existing run so the scheduler runs them again.
- **Pool.** A named number of slots. A task assigned to a pool needs a free slot before it starts.
- **Mapped task.** One task definition that becomes several task instances at run time, one per input value, numbered by `map_index` (0, 1, 2).

## Docker packaging

### What runs where

The compose file starts these containers. Their names come from the folder name, for example `ledger-vs-statement-airflow-scheduler-1`.

| Service | Job |
|---|---|
| `postgres` | the Airflow metadata database (`postgres:18`). Its data lives in the volume `ledger-vs-statement_postgres-db-volume` |
| `airflow-init` | runs once at every `make up`: migrates the database, creates the `airflow` user, creates the mount folders, creates the pool `dbt_serial`, then exits with code 0 |
| `airflow-apiserver` | the UI, the REST API and the Execution API that running tasks report to |
| `airflow-scheduler` | creates runs, decides what starts, and **runs the tasks**: with LocalExecutor each task is a process inside this container |
| `airflow-dag-processor` | parses the files in `dags/` and stores the parsed DAGs in the database |
| `airflow-triggerer` | runs deferred tasks. This project has none; the service stays because the course file has it |
| `airflow-cli` | only under the `debug` profile; it does not start with `make up` |

Two consequences:
1. Every task runs in the scheduler container, so that container needs the dbt venv, the `src/` code, the dbt project, the landing folder, the runs folder and the key. All services share the same image, environment and mounts through the `x-airflow-common` block, so all of them have these.
2. The Python tasks (`check_window`, `ensure_tables`, `generate_day`, `fetch_fx`, `load_raw`) run in **Airflow's own Python environment**. Only `dbt_build` uses the dbt venv. So the `recon` package may import only the standard library and `google-cloud-bigquery` (3.45.0 in the image, from the constraints). Never give `recon` a dependency that Airflow's environment lacks: nothing is ever installed there.

### The Dockerfile

The image starts from the official one and adds exactly one thing: a separate Python virtual environment (venv) with dbt in it. The file at the repo root:

```dockerfile
FROM apache/airflow:3.3.2
# dbt gets its own venv: dbt-bigquery 1.12.1 needs google-cloud-storage<3.2 and dbt-core 1.12.6
# needs pathspec<1.1, while the Airflow 3.3.2 constraints pin google-cloud-storage 3.14.1 and pathspec 1.1.1.
COPY docker/requirements-dbt.txt /tmp/requirements-dbt.txt
RUN python -m venv /opt/airflow/dbt_venv \
 && /opt/airflow/dbt_venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt \
 && /opt/airflow/dbt_venv/bin/dbt --version
```

`docker/requirements-dbt.txt`:

```
dbt-core==1.12.6
dbt-bigquery==1.12.1
dbt-core-experimental-parser==2.0.8
```

Line by line:

| Line | What it does | Why |
|---|---|---|
| `FROM apache/airflow:3.3.2` | the official image your course uses. It already contains Airflow 3.3.2, the Google provider 22.5.0 and `google-cloud-bigquery` 3.45.0, all installed with the 3.3.2 constraints | no Airflow package is ever added, so the tested set stays intact. The default tag runs Python 3.13.15, so the matching constraints file is `constraints-3.13.txt` |
| `COPY docker/requirements-dbt.txt /tmp/requirements-dbt.txt` | copies only the pin list into the image | the build needs nothing else from the repo; `.dockerignore` keeps `keys/`, `.env`, `landing/`, `runs/`, `logs/`, `.venv/`, `dbt/target/`, `dbt/dbt_packages/` and `.git/` out of the build context |
| `python -m venv /opt/airflow/dbt_venv` | creates a new, empty venv | created without `--system-site-packages`, so it cannot see Airflow's packages and Airflow cannot see dbt's |
| `/opt/airflow/dbt_venv/bin/pip install --no-cache-dir -r ...` | installs the three pins and everything they need into the venv | the **full path** to the venv's `pip` matters: the image sets `VIRTUAL_ENV=/home/airflow/.local` and puts Airflow's environment first on `PATH`, so a bare `pip install` or `uv pip install` would install into Airflow's environment. `--no-cache-dir` keeps the image smaller |
| `/opt/airflow/dbt_venv/bin/dbt --version` | prints the versions at the end of the build | the build fails here if dbt did not install. Expect Core 1.12.6 and the bigquery plugin 1.12.1 |

Rules for the image:
1. The build runs as the base image's user `airflow`. Never add `USER root` for pip: the official image refuses pip as root.
2. The build needs internet access to PyPI and to github.com: `dbt-core-experimental-parser` 2.0.8 is published as a source package whose build step downloads a prebuilt aarch64 wheel from GitHub releases. Do not add `--only-binary`: that would refuse the source package.
3. Expect the image to grow by several hundred MB: dbt-bigquery pulls Google client libraries for AI Platform and Dataproc.
4. The key is never in the image, and neither is any project code. `dags/`, `src/` and `dbt/` arrive through mounts at run time, so editing them never needs a rebuild. Rebuild only after changing `Dockerfile` or `docker/requirements-dbt.txt`.
5. The image name is `ledger-vs-statement-airflow:3.3.2`. The compose file builds and tags it.

This is the pattern of the official docker-stack guide, "Example of adding a Python venv for ExternalPythonOperator": `python -m venv /opt/airflow/venv && /opt/airflow/venv/bin/pip install --no-cache-dir -r /requirements.txt`, which "leaves Airflow's own Python environment untouched".

### Why dbt has its own virtual environment

One Python environment can hold only one version of each package. Two packages that both Airflow and dbt need are pinned to versions that cannot coexist:

| Package | Airflow 3.3.2 constraints (Python 3.13) | What dbt needs |
|---|---|---|
| `google-cloud-storage` | 3.14.1 | below 3.2 (required by dbt-bigquery 1.12.1) |
| `pathspec` | 1.1.1 | below 1.1 (required by dbt-core 1.12.6) |

So there are two choices: downgrade packages inside Airflow's environment, which breaks the set of versions that Airflow 3.3.2 was tested with, or give dbt a second environment. This project takes the second. The Cosmos docs recommend the same ("isolating the installation of dbt from the Airflow installation").

How it is used:
- `dbt_build` and `smoke_bigquery`'s `dbt_debug` call `/opt/airflow/dbt_venv/bin/dbt` by its full path.
- The venv is not on `PATH`. In the containers, a bare `dbt` gives "command not found". That is on purpose: there is exactly one dbt in the containers, and it is called by path.
- On the host the same three pins live in the uv project, so `uv run dbt` and the container's dbt are the same versions.

Check the isolation once, after the first `make up`:

```bash
docker compose exec airflow-scheduler /opt/airflow/dbt_venv/bin/dbt --version
docker compose exec airflow-scheduler bash -c 'command -v dbt || echo "no dbt on PATH (expected)"'
docker compose exec airflow-scheduler python -c "from importlib.metadata import version as v; print('airflow env:', v('google-cloud-storage'), v('pathspec'))"
docker compose exec airflow-scheduler /opt/airflow/dbt_venv/bin/python -c "from importlib.metadata import version as v; print('dbt venv:', v('google-cloud-storage'), v('pathspec'))"
```

Expected: Core 1.12.6 and bigquery 1.12.1; "no dbt on PATH (expected)"; `airflow env: 3.14.1 1.1.1`; and for the dbt venv a `google-cloud-storage` version below 3.2 and a `pathspec` version below 1.1.

### Constraints files: what they are and where they apply

A constraints file lists one exact version for every package that an Airflow release was tested with. The one for this image is:

```
https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.13.txt
```

`3.3.2` is the Airflow version and `3.13` the Python version inside the image. The image also keeps the file it was built with at `/home/airflow/constraints.txt` (`${HOME}/constraints.txt` in the docker-stack docs).

Where it applies:
1. **Airflow's own environment in the image** was installed with it. That is where `google-cloud-storage` 3.14.1, `pathspec` 1.1.1, provider-google 22.5.0, `google-cloud-bigquery` 3.45.0 and provider-standard 1.19.0 come from. They are never upgraded.
2. **Anything ever installed into Airflow's environment** must use the constraints and name `apache-airflow==3.3.2` on the same command line, so pip fails loudly instead of quietly changing Airflow. In this project that is only Cosmos, later (see "Later upgrade: Cosmos").
3. **The dbt venv is installed without the constraints, on purpose.** The constraints would refuse dbt-bigquery 1.12.1 and dbt-core 1.12.6, which is the whole reason for the venv.
4. **The host uv project never gets `apache-airflow`.** It holds dbt, and Airflow's constraints conflict with dbt there exactly as in the image. The U2 DAG import test (`tests/test_dag.py`) needs `apache-airflow` 3.3.2 installed with `constraints-3.13.txt` in a separate environment in CI, not in `uv.lock`.
5. **`_PIP_ADDITIONAL_REQUIREMENTS` stays empty.** It installs packages at every container start, without a pinned, tested result.

To read a pin without installing anything:

```bash
docker compose exec airflow-scheduler grep -E "^(google-cloud-storage|pathspec|apache-airflow-providers-google|google-cloud-bigquery|apache-airflow-providers-standard)==" /home/airflow/constraints.txt
```

### docker-compose.yaml: the changes to the course file

Start from your working course file:

```bash
cp ~/Developer/learning/courses/airflow/docker-compose.yaml ~/Developer/ledger-vs-statement/docker-compose.yaml
```

Then make exactly these five changes. Everything else stays as it is.

**Change 1: build the custom image.** In `x-airflow-common`:

Before:
```yaml
  image: ${AIRFLOW_IMAGE_NAME:-apache/airflow:3.3.2}
  # build: .
```
After:
```yaml
  image: ${AIRFLOW_IMAGE_NAME:-ledger-vs-statement-airflow:3.3.2}
  build: .
```
Why: with both `image:` and `build:`, Compose builds the repo-root `Dockerfile` and tags the result with the image name. Every service in `x-airflow-common` then runs the custom image, including the scheduler, where LocalExecutor runs the tasks. Never set `AIRFLOW_IMAGE_NAME` in `.env`: it would replace the custom image.

**Change 2: the API server port.** In `airflow-apiserver`:

Before:
```yaml
      - "8082:8080"  # host 8080 is taken by kafka-ui
```
After:
```yaml
      - "127.0.0.1:8083:8080"  # 8080 is kafka-ui, 8082 is the course stack; localhost only
```
Why: 8080 and 8082 are taken on your Mac. `127.0.0.1` keeps the UI on your machine only. Without it, Docker Desktop publishes the port on every network interface, and the login is the well-known `airflow` / `airflow`. Inside the Docker network the API server still listens on 8080, so `AIRFLOW__CORE__EXECUTION_API_SERVER_URL: 'http://airflow-apiserver:8080/execution/'` stays unchanged.

**Change 3: environment variables for every Airflow service.** Add these lines under `environment: &airflow-common-env`, after the `AIRFLOW_CONFIG` line:

```yaml
    # ledger-vs-statement: seen by the scheduler, dag-processor, triggerer, api-server and init
    PYTHONPATH: /opt/airflow/src
    GCP_PROJECT: ${GCP_PROJECT}
    RAW_DATASET: raw
    RECON_SEED: "${RECON_SEED}"
    RECON_WORLD_START: "${RECON_WORLD_START}"
    RECON_LANDING_DIR: /opt/airflow/landing
    DBT_PROFILES_DIR: /opt/airflow/dbt
    DBT_KEYFILE: /opt/airflow/keys/sa.json
    AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT: '{"conn_type": "google_cloud_platform", "extra": {"key_path": "/opt/airflow/keys/sa.json", "project": "${GCP_PROJECT}", "location": "US", "use_legacy_sql": false}}'
```
Why: `x-airflow-common` is merged into every Airflow service, so the scheduler (where tasks run), the dag-processor and `airflow-init` all see the same values. Each variable is explained in "Environment variables". The quotes keep the seed and the date as plain strings. `DBT_KEYFILE` is a literal path here and never comes from `.env`. dbt's usage tracking needs no variable here: `flags: send_anonymous_usage_stats: false` in `dbt/dbt_project.yml` already turns it off (heading "Project file" in `docs/specs/dbt_project.md`).

**Change 4: mounts.** Keep the four course mounts and add five, in `x-airflow-common`:

```yaml
  volumes:
    - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
    - ${AIRFLOW_PROJ_DIR:-.}/logs:/opt/airflow/logs
    - ${AIRFLOW_PROJ_DIR:-.}/config:/opt/airflow/config
    - ${AIRFLOW_PROJ_DIR:-.}/plugins:/opt/airflow/plugins
    - ./src:/opt/airflow/src
    - ./dbt:/opt/airflow/dbt
    - ./landing:/opt/airflow/landing
    - ./runs:/opt/airflow/runs
    - ./keys:/opt/airflow/keys:ro
```
Why: see "Mounts". `:ro` makes the key folder read-only inside every container.

**Change 5: `airflow-init` creates the new folders and the pool.** In the `airflow-init` command block:

Before:
```bash
        mkdir -v -p /opt/airflow/{logs,dags,plugins,config}
        /entrypoint airflow version
        /entrypoint airflow config list >/dev/null
        chown -R "${AIRFLOW_UID:-50000}:0" /opt/airflow/{logs,dags,plugins,config}
```
After:
```bash
        mkdir -v -p /opt/airflow/{logs,dags,plugins,config,landing,runs}
        /entrypoint airflow version
        /entrypoint airflow config list >/dev/null
        /entrypoint airflow pools set dbt_serial 1 "one dbt build at a time"
        chown -R "${AIRFLOW_UID:-50000}:0" /opt/airflow/{logs,dags,plugins,config,landing,runs}
```
Why:
1. `landing` and `runs` are written by tasks, so they must exist and belong to your user id.
2. Each `/entrypoint airflow ...` call first migrates the database (because `airflow-init` sets `_AIRFLOW_DB_MIGRATE: 'true'`), so the pool line always runs on a ready database. `airflow pools set` creates the pool, or resets it to 1 slot if it exists, so it is safe on every `make up`.
3. A task in a pool that does not exist is never scheduled. `make doctor` therefore runs `airflow pools get dbt_serial`.
4. Never add `keys` to the `mkdir` or `chown` lines. The key mount is read-only, `chown` would fail, `airflow-init` would exit non-zero, and no other Airflow service would start.

Optional and harmless: the course file's header comment still says "CeleryExecutor with Redis". You may correct it to LocalExecutor; it is only a comment.

**What stays exactly as in the course file, and why:**
- `AIRFLOW__CORE__EXECUTOR: LocalExecutor` and the commented-out Redis and Celery worker: one machine, no queue needed.
- `AIRFLOW__CORE__AUTH_MANAGER` (FAB), the database URL, `AIRFLOW__API_AUTH__JWT_SECRET: 'test-key'` and `AIRFLOW__API_AUTH__JWT_ISSUER`: fine for a stack that only your machine can reach.
- `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'`: a new DAG starts paused, so nothing runs until you unpause it on purpose.
- `AIRFLOW__CORE__LOAD_EXAMPLES: 'false'`, `_PIP_ADDITIONAL_REQUIREMENTS` empty, `AIRFLOW_CONFIG`, the health checks, `restart: always`, the `depends_on` rules, `postgres:18` with its volume at `/var/lib/postgresql`, and `user: "${AIRFLOW_UID:-50000}:0"`.
- The service names. Every command in this file uses `airflow-scheduler`.

Names do not clash with the course stack: Compose takes the project name from the folder, so this project is `ledger-vs-statement` and the course stack is `airflow`. Their containers and volumes are separate. Stop the course stack anyway, for memory.

Validate after editing:

```bash
docker compose config --quiet   # prints nothing and exits 0 when the file is valid
```

`docker compose config` without `--quiet` prints the resolved file, including your project id. Do not paste that output anywhere public.

### Mounts

| Host path | Container path | Mode | Written by | Purpose |
|---|---|---|---|---|
| `./dags` | `/opt/airflow/dags` | read-write | you, on the host | the two DAG files, parsed by the dag-processor |
| `./logs` | `/opt/airflow/logs` | read-write | Airflow | task logs, one file per try (gitignored) |
| `./config` | `/opt/airflow/config` | read-write | `airflow-init` writes `airflow.cfg` | Airflow config folder from the course file (`config/airflow.cfg` is gitignored) |
| `./plugins` | `/opt/airflow/plugins` | read-write | nobody | empty (`.gitkeep`) |
| `./src` | `/opt/airflow/src` | read-write | you, on the host | the `recon` package, importable because `PYTHONPATH=/opt/airflow/src` |
| `./dbt` | `/opt/airflow/dbt` | read-write | you; `dbt debug` writes `dbt/logs/` | the dbt project, `profiles.yml`, and `dbt_packages/` installed on the host by `uv run dbt deps` |
| `./landing` | `/opt/airflow/landing` | read-write | `generate_day`, `fetch_fx` | landing files. `landing/fx/` is committed; the rest is gitignored |
| `./runs` | `/opt/airflow/runs` | read-write | `dbt_build` | per-run dbt artifacts in `runs/dbt/<run_date>/` (gitignored) |
| `./keys` | `/opt/airflow/keys` | **read-only** | you, on the host | `sa.json` |

Notes:
1. Everything that tasks read and write is a mount, so the files are on your Mac and survive `make down`.
2. Create `keys/sa.json` before the first `make up`. If `keys/` is missing, Docker may create it as an empty folder, and every BigQuery task then fails with a file-not-found error.
3. Files that tasks create, for example `landing/fx/...json`, belong to your user on the Mac, because the containers run as your user id. You can `git add` them directly.
4. `PYTHONPATH=/opt/airflow/src` also reaches the dbt venv's Python. Never create a top-level folder in `src/` named like a library (`src/google/`, `src/dbt/`): it would shadow the real package in both environments.

### The service-account key: read-only and readable

1. On the host the key is `keys/sa.json`, created in step S1.2, with `chmod 600` (only you can read it). `keys/` is gitignored before the key exists. Never print the key (`cat keys/sa.json`), and never paste it anywhere.
2. In every container it is `/opt/airflow/keys/sa.json`, through `./keys:/opt/airflow/keys:ro`. Read-only means no task, and no mistake in a task, can change or delete it.
3. It is readable because the containers run as `AIRFLOW_UID`, your own user id (`id -u`, usually 501 on a Mac), with group 0. The owner-only permission is therefore enough. `AIRFLOW_UID` must never be 0.
4. It is in no image (`.dockerignore` excludes `keys/`) and in no environment variable. The environment holds only its path.
5. Two readers use it: the BigQuery hook (through `key_path` in the connection) and dbt (through `DBT_KEYFILE` in `dbt/profiles.yml`).

Checks:

```bash
ls -l keys/sa.json                 # -rw------- and your user name
git check-ignore keys/sa.json      # prints keys/sa.json
docker compose exec airflow-scheduler bash -c 'test -r /opt/airflow/keys/sa.json && echo "key readable"'
docker compose exec airflow-scheduler bash -c 'touch /opt/airflow/keys/write_test 2>&1 || true'   # must say: Read-only file system
```

If the key ever leaks, follow "Key leaked" under "Failure scenarios and what to do".

### Environment variables

| Variable | Value in the containers | Comes from | Used by | Notes |
|---|---|---|---|---|
| `AIRFLOW_UID` | your `id -u` | `.env` | `user:` in the compose file | containers run as this user with group 0; never 0 |
| `GCP_PROJECT` | your sandbox project id | `.env`, through `${GCP_PROJECT}` | dbt profile `project`; the connection's `project` extra | the only place the project id lives |
| `RAW_DATASET` | `raw` | a literal in the compose file | dbt sources (`env_var('RAW_DATASET', 'raw')`); `ensure_tables` checks that it equals `raw` | the host Makefile sets `raw_dev` |
| `RECON_SEED` | `20261101` | `.env` | `recon.config` | the seed of the published run |
| `RECON_WORLD_START` | `2026-10-04` | `.env` | `recon.config`, `check_window` | first business day of the synthetic world |
| `RECON_LANDING_DIR` | `/opt/airflow/landing` | a literal in the compose file | `recon.config` | the host uses `$(CURDIR)/landing` |
| `DBT_PROFILES_DIR` | `/opt/airflow/dbt` | a literal in the compose file | dbt finds `profiles.yml` here | |
| `DBT_KEYFILE` | `/opt/airflow/keys/sa.json` | a literal in the compose file | `keyfile: "{{ env_var('DBT_KEYFILE') }}"` in the profile | **never in `.env`**: dbt 1.12 also reads `.env` from its working directory, and a wrong path there would win in a manual run |
| `PYTHONPATH` | `/opt/airflow/src` | a literal in the compose file | tasks import `recon` | the host uses `src` |
| `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT` | the JSON in Change 3 | the compose file, with `${GCP_PROJECT}` filled in | the BigQuery hook | see "The Google Cloud connection" |
| `GOOGLE_APPLICATION_CREDENTIALS` | not set | | | the hook uses `key_path`, dbt uses `DBT_KEYFILE`; never in `.env` |

`.env` holds exactly four lines (`.env.example` is committed, `.env` is not):

```
AIRFLOW_UID=501
GCP_PROJECT=your-sandbox-project-id
RECON_SEED=20261101
RECON_WORLD_START=2026-10-04
```

Containers read their environment only when they are created. After any change to `.env`, run `make down`, then `make up`.

### The Google Cloud connection

The connection `google_cloud_default` exists only as the environment variable `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT`. Airflow reads a variable named `AIRFLOW_CONN_<CONN_ID>` as a connection, here in JSON form:

| Field | Value | Meaning |
|---|---|---|
| `conn_type` | `google_cloud_platform` | the Google provider's connection type |
| `extra.key_path` | `/opt/airflow/keys/sa.json` | the service-account key file |
| `extra.project` | your project id | the default project; `hook.project_id` returns it |
| `extra.location` | `US` | the location of all datasets |
| `extra.use_legacy_sql` | `false` | GoogleSQL, not legacy SQL |

How tasks use it:

```python
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook  # inside the task function

hook = BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")
client = hook.get_client(project_id=hook.project_id, location="US")
```

- `use_legacy_sql=False` is passed even though the connection also sets it. The provider still defaults to legacy SQL when nothing sets it (with a deprecation warning), and the explicit argument makes the choice visible in the code.
- `project_id=hook.project_id` is needed: in provider 22.5.0, `get_client` builds the client with exactly the project it is given and does not read it from the connection by itself.
- The client then runs load jobs and queries. Never `insert_all` or `insert_rows_json`: they are streaming inserts, which the sandbox refuses.

Things to know:
1. Connections defined by environment variables "are not displayed in the Airflow UI or listed using airflow connections list" (3.3.2 docs). An empty Connections page is normal. The real test is the `smoke_bigquery` DAG.
2. Never create `google_cloud_default` in the UI or the database. One definition, in one file, is easier to reason about.
3. If S1.2 fell back to Application Default Credentials (the ADC fallback in `docs/specs/bigquery_sandbox_and_costs.md`): remove `key_path` from the extras, mount `~/.config/gcloud/application_default_credentials.json` read-only, and switch the dbt profile to `method: oauth`.

### Ports and login

| Host address | Container | What |
|---|---|---|
| `127.0.0.1:8083` | `airflow-apiserver:8080` | UI, REST API (`/api/v2/...`) and the token endpoint `/auth/token` |

Nothing else is published: Postgres stays inside the Docker network. Log in with `airflow` / `airflow` (the course file's defaults for `_AIRFLOW_WWW_USER_USERNAME` and `_AIRFLOW_WWW_USER_PASSWORD`).

## The DAGs

### Why CronDataIntervalTimetable (and never "@daily")

In Airflow 3, the config option `create_cron_data_intervals` defaults to `False`. Every cron string, including the preset `"@daily"`, then becomes a `CronTriggerTimetable`. The 3.3.2 docs: "A trigger timetable does not include data interval. This means that the value of data_interval_start and data_interval_end are the same; the time when a Dag run is triggered."

Compare the run that starts at 2026-10-21 00:00 UTC:

| | `schedule="@daily"` in Airflow 3 (CronTriggerTimetable) | `CronDataIntervalTimetable("0 0 * * *", timezone="UTC")` |
|---|---|---|
| `data_interval_start` | 2026-10-21 00:00 | 2026-10-20 00:00 |
| `data_interval_end` | 2026-10-21 00:00 | 2026-10-21 00:00 |
| `logical_date` | 2026-10-21 00:00 | 2026-10-20 00:00 |
| `{{ data_interval_start \| ds }}` | `2026-10-21`: today, an interval of zero length | `2026-10-20`: the day that just ended |
| `check_window` | fails: the interval is not one day | passes and returns `2026-10-20` |

A course DAG with `schedule="@daily"` works for "do something every day". It is wrong for "process yesterday's partition". So `recon_daily` imports the timetable from `airflow.sdk` and states it explicitly. `timezone="UTC"` makes midnight mean UTC midnight, the boundary of the arrival days.

### One run, one UTC day

For R = 2026-10-20:

| Property | Value |
|---|---|
| Data interval | [2026-10-20 00:00, 2026-10-21 00:00) UTC: everything that arrived during UTC day 2026-10-20 |
| Logical date | 2026-10-20T00:00:00+00:00 |
| run_after (earliest start) | 2026-10-21 00:00 UTC, which is 05:00 Astana |
| Run id if scheduled | `scheduled__2026-10-21T00:00:00+00:00` |
| Run id if created by a backfill | `backfill__2026-10-21T00:00:00+00:00` |
| `check_window` returns | `"2026-10-20"` |
| `{{ data_interval_start \| ds }}` | `2026-10-20` |
| dbt artifacts | `runs/dbt/2026-10-20/target/` and `runs/dbt/2026-10-20/logs/` |
| Task logs | `logs/dag_id=recon_daily/run_id=backfill__2026-10-21T00:00:00+00:00/task_id=<task>/attempt=<n>.log` |
| Raw partitions written | `raw.payment_events$20261020`, `raw.settlement_lines$20261020`, `raw.fx_rates$20261020` |

The trap in that table: **the run id shows the interval end**, one day after the processed day. In 3.3.2 a run id is the run type plus `run_after`. Always name a run by its logical date. The CLI accepts a plain date wherever it asks for `logical_date_or_run_id`, for example `airflow tasks states-for-dag-run recon_daily 2026-10-20`.

What unpausing does: with `catchup=False`, the scheduler creates one run for the **latest complete** interval. Unpausing at 2026-11-01 16:30 UTC creates the run for [2026-10-31, 2026-11-01), so R = 2026-10-31. (3.3.2 source, `CronDataIntervalTimetable._skip_to_latest`: "the current time is AFTER the period end".) After that, one run starts each day just after 00:00 UTC, for the day that just ended.

### recon_daily settings

| Setting | Value | Why |
|---|---|---|
| `dag_id` | `"recon_daily"` | |
| `schedule` | `CronDataIntervalTimetable("0 0 * * *", timezone="UTC")` | one UTC day per run (previous heading) |
| `start_date` | `pendulum.datetime(2026, 10, 1, tz="UTC")` | on or before `RECON_WORLD_START` (2026-10-04), so backfills can reach the first day. Dates before world start are refused by `check_window` |
| `catchup` | `False` | history is loaded only by explicit backfills, newest first, after a dry run |
| `max_active_runs` | `1` | at most one scheduled or manual run at a time. Backfill runs are limited separately by the backfill's own `--max-active-runs` |
| `default_args` | `{"retries": 0, "retry_delay": timedelta(seconds=30), "on_failure_callback": log_failure}` | retries are set per task (next heading) |
| `tags` | `["portfolio", "reconciliation"]` | filters on the Dags page |
| `doc_md` | `__doc__` (the module docstring) | the interval rules, shown on the DAG page |

The module docstring is yours to write, in about 10 lines. It must say:
1. One run owns one UTC arrival day R; its data interval is [R 00:00, R+1 00:00) UTC.
2. The scheduled run for R starts just after R+1 00:00 UTC (05:00 Astana).
3. The logical date is R; the run id shows R+1.
4. An exact day runs only through a one-day backfill, after a dry run.
5. dbt rebuilds the marts from all loaded days, as of the latest loaded arrival day, so rerunning an old day never rolls the marts back.

Imports (exact; no Airflow 2 paths such as `airflow.decorators`, `airflow.operators.bash`, `schedule_interval` or `execution_date`):

```python
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import CronDataIntervalTimetable, chain, dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException
```

`log_failure(context)` writes exactly one log line when a task fails for the last time: dag id, run id, task id, try number and run date. Airflow calls `on_failure_callback` only after the final try. A try that will be retried calls `on_retry_callback` instead, which this DAG does not set. The line appears at the end of the failed try's log.

Heavy imports (`google.cloud.bigquery`, the provider hook, the `recon` package) go inside the task functions. The dag-processor parses the file about every 30 seconds, and only the task needs those modules. XCom carries only small dicts and short strings.

### recon_daily tasks

| Task | Kind | Retries | Input | XCom output | Side effects | Safe to rerun because |
|---|---|---|---|---|---|---|
| `check_window` | `@task` | 0 | the run's data interval | `"YYYY-MM-DD"` (R) | none | a pure check |
| `ensure_tables` | `@task` | 2, every 30 s | none | small dict | creates dataset `raw` and the 3 raw tables if missing | create-if-missing through the API (`exists_ok=True`) |
| `generate_day` | `@task` | 0 | R | counts dict | writes the synthetic files that arrive on R, and the local answer key | a pure function of (seed, world start, R): byte-identical files |
| `fetch_fx` | `@task` | 3, backoff 2.0, at most 10 min apart | R | `{"action": ...}` | lands the NBK response for R-6..R once | a landed day is never fetched again |
| `load_raw` | `@task`, mapped 3 times | 2, every 30 s | R and one table | load result dict | replaces `raw.<table>$YYYYMMDD` with one load job, or deletes it on an empty day | the whole partition is replaced, never appended |
| `dbt_build` | `BashOperator`, pool `dbt_serial` | 0 | `{{ data_interval_start \| ds }}` | none | rebuilds `analytics` and writes `runs/dbt/R/` | a full rebuild of views and small tables from raw; `as_of_date` comes from the data |

Order: `check_window` first; then `ensure_tables`; then `generate_day` and `fetch_fx` side by side; then the three loads side by side; then `dbt_build`.

R travels through XCom as the string `YYYY-MM-DD`. Each Python task converts it once with `date.fromisoformat(run_date)` before calling `recon`.

#### check_window

The guard. It turns the data interval into R and refuses every run that could write in the wrong place. The interval checks (steps 1 to 3) live in this task, because only an Airflow run has a data interval. The date rules live in one function, `recon.load.check_run_date`, which the host CLI calls too, so the DAG and `make day` can never disagree about the window.
1. Read `data_interval_start` and `data_interval_end` from `get_current_context()`. Use `.get()`: a run without a logical date has no interval, and reading the key directly raises `KeyError`.
2. If either is missing or `None`: raise `AirflowFailException("No data interval: create exact days with a one-day backfill")`.
3. Convert both to UTC. If `end - start` is not exactly one day, or `start` is not 00:00:00: raise `AirflowFailException` and print both values.
4. R = the date of `start`. `today` = `datetime.now(timezone.utc).date()`, the same call as in "How the pipeline refuses old dates" in `docs/specs/bigquery_sandbox_and_costs.md`. This is the only wall-clock read in the whole DAG, and it only checks; it never shapes data.
5. Read `RECON_WORLD_START` through `recon.config` (imported inside the function).
6. Call `recon.load.check_run_date(R, world_start, today)` and turn its `ValueError` into `AirflowFailException` with the same message (`raise AirflowFailException(str(err)) from err`). You write the function in S4.1, from "How the pipeline refuses old dates". It refuses:
   - `R < RECON_WORLD_START`: before the synthetic business opened;
   - `R >= today`: the day has not ended (a backfill never creates such a run, but a manual run with a typed interval could);
   - `R < today - 45 days`: inside the zone where the sandbox's 60-day partition expiry would silently drop rows.

   Never copy these three rules into the DAG. A second copy of the 45-day guard could drift from the first.
7. Log `run_date=R` (`log.info("run_date=%s", R.isoformat())`) and return `R.isoformat()`.

`AirflowFailException` fails the task at once and never retries, whatever `retries` says.

U3 (after v1.0) adds one more refusal to this task: the 8 GiB stop of the bytes-written ledger, described under "The bytes-written ledger (U3, after v1.0)" in `docs/specs/bigquery_sandbox_and_costs.md`. The host commands that call `check_run_date` get the same stop.

#### ensure_tables

1. If `os.environ["RAW_DATASET"]` is not `"raw"`: raise `AirflowFailException`. dbt's sources read `RAW_DATASET`, so the loader and dbt must never point at different datasets.
2. Build the client (see "The Google Cloud connection") and call `recon.load.ensure_tables(client, "raw")`. It creates the dataset and the three tables from the schema JSON files if they are missing. Normally it changes nothing.
3. Return `{"dataset": "raw"}`.

#### generate_day

1. Load the config with `recon.config` (seed, world start and landing folder from the environment).
2. Return `recon.generator.emit(seed, world_start, R, landing_dir)`. It writes the events file, one statement file per MID and the answer-key file, and returns the small counts dict defined in `docs/specs/data_and_generator.md` (heading "`emit(seed, world_start, run_date, landing_dir) -> dict of counts`").

No retries: the generator is deterministic, so a failure is a bug or a wrong date.

#### fetch_fx

1. Call `recon.fx.fetch_nbk(R, landing_dir)` (steps in `docs/specs/data_and_generator.md`, heading "Landing (immutable)").
2. It returns `{"action": "skipped"}` when the day is already landed, or `{"action": "fetched", "rows": n}`.
3. Retries: `retries=3`, `retry_delay=timedelta(seconds=30)`, `retry_exponential_backoff=2.0`, `max_retry_delay=timedelta(minutes=10)`. In Task SDK 1.3.2, `retry_exponential_backoff` is a float multiplier. Write the explicit float 2.0, never `True` (the project rule). `True` still works: Airflow maps it to 2.0 for backward compatibility, per the 3.2.0 release notes. But the explicit multiplier is what those release notes recommend, and it makes the backoff visible in the code. The waits are in "What a retry looks like".

#### load_raw (mapped)

1. Defined once as `load_raw(table: str, run_date: str)` and used as `load_raw.partial(run_date=rd).expand(table=TABLES)` with `TABLES = ["payment_events", "settlement_lines", "fx_rates"]`. Airflow creates three task instances: `map_index` 0 is `payment_events`, 1 is `settlement_lines`, 2 is `fx_rates`.
2. Each calls `recon.load.load_day(client, "raw", table, R, landing_dir)`: it asserts that every row belongs to R, then runs exactly one `WRITE_TRUNCATE` load job into `<table>$YYYYMMDD` (or deletes that partition if the day has no rows), and checks `job.output_rows` against the rows landed. Details: the load protocol in `docs/specs/bigquery_sandbox_and_costs.md`.
3. It returns `{table, rows, action, output_bytes, job_id}`.
4. The three loads write three different tables, so they may run at the same time.

#### dbt_build

A `BashOperator`:

```python
dbt_build = BashOperator(
    task_id="dbt_build",
    bash_command=DBT_BUILD_CMD,   # the exact command under the next heading
    pool="dbt_serial",
    append_env=True,
    retries=0,
)
```

- `append_env=True`: the command inherits the container's environment (`DBT_PROFILES_DIR`, `DBT_KEYFILE`, `GCP_PROJECT`, `RAW_DATASET`, `PATH`, `HOME`). Without an `env` mapping it inherits anyway. With `True`, it still inherits if someone later adds an `env=` mapping. With `append_env=False` and an `env` mapping, only that mapping would exist, and dbt would lose `PATH`, `HOME` and the key path.
- `skip_on_exit_code` keeps its default, 99: the BashOperator marks a task **skipped**, not failed, only when the command exits with code 99. dbt never uses that code (it exits 0, 1 or 2; see "How `dbt build` runs from Airflow" in `docs/specs/dbt_project.md`), so every dbt failure fails the task.
- `retries=0`: a failing dbt test fails the same way every time. Short BigQuery hiccups are retried inside dbt (`job_retries: 1` in the profile).
- `pool="dbt_serial"`: see "The pool dbt_serial".

### The dbt_build command, piece by piece

```
cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt build --target airflow --exclude-resource-type unit_test --target-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/target --log-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/logs
```

| Piece | Why |
|---|---|
| `cd /opt/airflow/dbt &&` | the BashOperator starts in a temporary folder; dbt looks for `dbt_project.yml` in the current folder. dbt 1.12 also loads `.env` from its working folder, and `dbt/` has none (the repo's `.env` is at the root and is not mounted) |
| `/opt/airflow/dbt_venv/bin/dbt` | the only dbt in the containers, called by path |
| `build` | seeds, models and data tests, in dependency order |
| `--target airflow` | writes to dataset `analytics`. The profile's default target is `dev` (`analytics_dev`) for the host, so this flag must never be dropped |
| `--exclude-resource-type unit_test` | unit tests run on the host (`make dbt-build`, `make dbt-unit`), never in the DAG |
| `--target-path /opt/airflow/runs/dbt/{{ data_interval_start \| ds }}/target` | keeps `run_results.json`, `manifest.json` and the compiled SQL of every run date in its own folder |
| `--log-path /opt/airflow/runs/dbt/{{ data_interval_start \| ds }}/logs` | keeps each run date's `dbt.log` |

Rules:
1. The command stays inline in the DAG file. A `bash_command` string ending in `.sh` or `.bash` is treated as a template file to load, not as a command.
2. Airflow renders `{{ data_interval_start | ds }}` before bash runs. To see the result, open the task instance's "Rendered Templates" tab, or run `docker compose exec airflow-scheduler airflow tasks render recon_daily dbt_build 2026-10-20`.
3. A rerun of day D replaces `runs/dbt/D/`. Each folder holds the latest run of that day.
4. dbt exits 0 when everything passed, including warn-level tests, and non-zero when an error-level test failed or a model broke. Any non-zero exit fails `dbt_build`.

### Templates: where a business date may come from

1. Python tasks get R only from `check_window`, through XCom.
2. The BashOperator uses only `{{ data_interval_start | ds }}`.
3. Never `{{ ds }}`. It is the logical date, which the docs describe as "simply a value for identification", and it does not exist on runs without a logical date.
4. Never `datetime.now()` or `pendulum.now()` for a business date. The only wall-clock read is the window check in `check_window`.
5. No dbt vars come from Airflow in v1.0. dbt's `as_of_date` comes from the data (the latest loaded arrival date). U5 adds one var, `run_date`, for its snapshot model only.

### The pool dbt_serial

A pool is a counter of slots. `dbt_serial` has 1 slot, and only `dbt_build` uses it.

Why it is needed: two runs of `recon_daily` can be active at the same moment. `max_active_runs=1` limits scheduled and manual runs. A backfill is limited only by its own `--max-active-runs`, and the 3.3.2 docs say it "is applied independently" of the DAG setting. So when the 00:00 UTC scheduled run starts while a backfill runs, without the pool both could rebuild the same marts at once and overwrite each other's tables halfway. With the pool, the second `dbt_build` waits in state "scheduled" until the slot is free.

What the pool does not do: it does not stop the other run's `load_raw` from landing a **new** day while a dbt build is running. A build that sees raw data change in the middle can fail its identity or preservation test. That failure is loud and the fix is simple (see "Two runs overlapped and dbt_build failed"). The prevention is a rule: plan backfills so they finish before the next 00:00 UTC (05:00 Astana). Reloading an existing day is harmless here, because it writes identical rows.

Check the pool: `docker compose exec airflow-scheduler airflow pools get dbt_serial` shows `dbt_serial` with 1 slot.

### recon_daily code shape

```python
"""recon_daily: one run per UTC arrival day.

<You write about 10 lines here: the five points listed under "recon_daily settings".>
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import CronDataIntervalTimetable, chain, dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException

log = logging.getLogger(__name__)

TABLES = ["payment_events", "settlement_lines", "fx_rates"]  # map_index 0, 1, 2

DBT_BUILD_CMD = (
    "cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt build --target airflow "
    "--exclude-resource-type unit_test "
    "--target-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/target "
    "--log-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/logs"
)


def log_failure(context) -> None:
    """One line per final failure."""
    # 1. ti = context["ti"]; start = context.get("data_interval_start")
    # 2. run_date = the UTC date of start as YYYY-MM-DD, or "none" when there is no interval
    # 3. log.error("task failed dag_id=%s run_id=%s task_id=%s try_number=%s run_date=%s", ...)


def _bq_client():
    """BigQuery client from the connection google_cloud_default."""
    # 1. from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook   (heavy import, here only)
    # 2. hook = BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")
    # 3. return hook.get_client(project_id=hook.project_id, location="US")


@dag(
    dag_id="recon_daily",
    schedule=CronDataIntervalTimetable("0 0 * * *", timezone="UTC"),
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 0,
        "retry_delay": timedelta(seconds=30),
        "on_failure_callback": log_failure,
    },
    tags=["portfolio", "reconciliation"],
    doc_md=__doc__,
)
def recon_daily():
    @task(retries=0)
    def check_window() -> str:
        # the 7 steps under "check_window":
        # 1-3. read the interval with .get(); refuse a missing interval or one that is not one UTC day
        # 4. R = the UTC date of start; today = datetime.now(timezone.utc).date()   (the only wall-clock read)
        # 5. world_start from recon.config
        # 6. from recon.load import check_run_date   (the date rules, shared with the host CLI)
        #    try: check_run_date(R, world_start, today)
        #    except ValueError as err: raise AirflowFailException(str(err)) from err
        # 7. log.info("run_date=%s", R.isoformat()); return R.isoformat()
        ...

    @task(retries=2, retry_delay=timedelta(seconds=30))
    def ensure_tables() -> dict:
        # 1. RAW_DATASET must be "raw", else AirflowFailException
        # 2. from recon.load import ensure_tables as create_raw_tables; create_raw_tables(_bq_client(), "raw")
        # 3. return {"dataset": "raw"}
        ...

    @task(retries=0)
    def generate_day(run_date: str) -> dict:
        # R = date.fromisoformat(run_date); config from recon.config
        # return recon.generator.emit(seed, world_start, R, landing_dir)
        ...

    @task(
        retries=3,
        retry_delay=timedelta(seconds=30),
        retry_exponential_backoff=2.0,
        max_retry_delay=timedelta(minutes=10),
    )
    def fetch_fx(run_date: str) -> dict:
        # R = date.fromisoformat(run_date); return recon.fx.fetch_nbk(R, landing_dir)
        ...

    @task(retries=2, retry_delay=timedelta(seconds=30))
    def load_raw(table: str, run_date: str) -> dict:
        # R = date.fromisoformat(run_date)
        # return recon.load.load_day(_bq_client(), "raw", table, R, landing_dir)
        ...

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=DBT_BUILD_CMD,
        pool="dbt_serial",
        append_env=True,
        retries=0,
    )

    rd = check_window()
    chain(
        rd,
        ensure_tables(),
        [generate_day(rd), fetch_fx(rd)],
        load_raw.partial(run_date=rd).expand(table=TABLES),
        dbt_build,
    )


recon_daily()
```

How `chain` reads: `rd` runs before `ensure_tables`; `ensure_tables` runs before both `generate_day` and `fetch_fx`; both run before all three `load_raw` instances; all three run before `dbt_build`. `generate_day(rd)` and `fetch_fx(rd)` also receive R through XCom, which is a dependency of its own.

Check after writing the file:

```bash
uv run ruff check dags/ --select AIR301,AIR302               # no Airflow 2 imports or removed names
docker compose exec airflow-scheduler airflow dags list-import-errors
docker compose exec airflow-scheduler airflow tasks list recon_daily
```

`tasks list` must show exactly six task ids: `check_window`, `dbt_build`, `ensure_tables`, `fetch_fx`, `generate_day`, `load_raw`.

### Manual-run semantics

Each way of creating a run gets a different data interval. Checked in the 3.3.2 source (`api/common/trigger_dag.py`, `api_fastapi/core_api/datamodels/dag_run.py`, `models/backfill.py`, `timetables/interval.py`).

| How the run is created | Data interval it gets | Use it? |
|---|---|---|
| Scheduled run, starting at 2026-11-01 00:00 UTC | [2026-10-31, 2026-11-01): processes 2026-10-31 | yes |
| Unpausing with catchup off, at any time during UTC day 2026-11-01 | the latest complete interval: [2026-10-31, 2026-11-01) | yes: "run yesterday" |
| `airflow backfill create --dag-id recon_daily --from-date D --to-date D` | [D, D+1): processes D. The range is inclusive, and only intervals that have already ended get a run | **yes: the only way to run an exact day** |
| UI "Trigger", "Single Run", data interval "Inferred from Logical Date and Timetable", logical date L (REST works the same) | the last complete interval before L. For a midnight L that is [L-1, L) | only as "run yesterday now" |
| UI "Single Run" with "Specify Manually", or REST with `data_interval_start` and `data_interval_end` | the interval you type | not used: one rule (one-day backfills) leaves less room for mistakes |
| `airflow dags trigger recon_daily -l L` | inferred from the trigger time (now), **not** from L: yesterday relative to now, while the run records logical date L | **never** for exact days |
| `airflow dags trigger recon_daily` without `-l` | no logical date and no interval | `check_window` fails: "No data interval..." |
| `airflow dags test recon_daily D`, or `airflow tasks test recon_daily <task> D` when no run for D exists | [D-1, D): processes D-1 | debugging only. It writes real data to `raw` and `analytics` and ignores the pool, so never while anything else runs |
| `airflow tasks test` on an existing run | that run's interval | debugging only, same warning |
| REST API or Asset event without a logical date | none | `check_window` fails |

The rule: an exact day runs only through a one-day backfill, with `--dry-run` first. Debugging logic happens on the host (`make day DATE=...`, `make dbt-build`); debugging Airflow behaviour happens with a one-day backfill.

### smoke_bigquery

The walking skeleton (milestone M2, gate G-skel) and the health check you can run any time. It proves, inside Docker, that the key, the connection, a partition-decorator load job and dbt all work. It never touches `raw` or `analytics` and never creates scheduled runs.

| Setting | Value |
|---|---|
| `dag_id` | `"smoke_bigquery"` |
| `schedule` | `None` (manual only) |
| `start_date` | `pendulum.datetime(2026, 10, 1, tz="UTC")` |
| `catchup`, `max_active_runs` | `False`, `1` |
| `tags` | `["portfolio", "smoke"]` |

| Task | Kind | Does | Done when |
|---|---|---|---|
| `bq_load_one_row` | `@task`, retries 0 | creates `probe.smoke (d DATE NOT NULL, x INT64) PARTITION BY d` if missing; runs one `WRITE_TRUNCATE` load job of 1 row into `probe.smoke$<yesterday UTC>`; counts that partition with a `SELECT` | the log shows 1 row in that partition |
| `dbt_debug` | `BashOperator` | `cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt debug --target airflow` | the log ends with "All checks passed!" |

"Yesterday" here comes from the wall clock. That is allowed only in this DAG, because it never writes business data. Running it twice on one day still leaves exactly 1 row, because `WRITE_TRUNCATE` replaces the partition: a small idempotency check of its own. `dbt debug` writes its log to `dbt/logs/` (gitignored).

#### smoke_bigquery code shape

```python
"""smoke_bigquery: manual health check. Writes only to dataset probe."""

from __future__ import annotations

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task


@dag(
    dag_id="smoke_bigquery",
    schedule=None,
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["portfolio", "smoke"],
    doc_md=__doc__,
)
def smoke_bigquery():
    @task(retries=0)
    def bq_load_one_row() -> dict:
        # 1. client exactly as in recon_daily (hook, use_legacy_sql=False, location "US", project_id=hook.project_id)
        # 2. yesterday = wall-clock UTC date minus 1 day (allowed only in this DAG)
        # 3. create table probe.smoke if missing: d DATE REQUIRED, x INT64, DAY partitioning on d, exists_ok=True
        # 4. one load job: [{"d": "<yesterday>", "x": 1}] into probe.smoke$YYYYMMDD,
        #    NEWLINE_DELIMITED_JSON, explicit schema, WRITE_TRUNCATE, location US
        # 5. assert job.output_rows == 1
        # 6. SELECT COUNT(*) for d = yesterday, with QueryJobConfig(maximum_bytes_billed=1_000_000_000); assert 1
        # 7. return {"partition": "YYYYMMDD", "rows": 1, "job_id": job.job_id}
        ...

    dbt_debug = BashOperator(
        task_id="dbt_debug",
        bash_command="cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt debug --target airflow",
        append_env=True,
    )

    bq_load_one_row() >> dbt_debug


smoke_bigquery()
```

## Operations runbook

### Conventions for every command

1. Run every command from the repo root, `~/Developer/ledger-vs-statement`.
2. Airflow CLI commands run inside the scheduler container: `docker compose exec airflow-scheduler airflow <command>`. The Makefile wraps the common ones and always adds `-T` (see the table below). If a command you type by hand in a non-interactive shell (a script, an AI agent) prints "the input device is not a TTY", add `-T` right after `exec`.
3. `D`, `D1` and `D2` are UTC calendar dates written `YYYY-MM-DD`. The CLI reads a plain date as midnight UTC.
4. "Run D" always means the run whose logical date is D. Its run id shows D+1.
5. Before you read or pick any time in the UI, set the UI timezone to UTC ("Open the UI and set its timezone to UTC").
6. Who may run what (agent, ask first, owner only) is in `AGENTS.md`, heading "Commands". Everything that changes Airflow state or the datasets `raw` and `analytics` is for you, the owner.

What each Airflow-related Make target runs:

| Target | Runs |
|---|---|
| `make up` | `docker compose up -d` (builds the image first if it does not exist) |
| `make down` | `docker compose down` |
| `make smoke` | `docker compose exec -T airflow-scheduler airflow dags unpause smoke_bigquery`, then `docker compose exec -T airflow-scheduler airflow dags trigger smoke_bigquery` |
| `make unpause` | `docker compose exec -T airflow-scheduler airflow dags unpause recon_daily` |
| `make pause` | `docker compose exec -T airflow-scheduler airflow dags pause recon_daily` |
| `make backfill-dry FROM=D1 TO=D2` | `docker compose exec -T airflow-scheduler airflow backfill create --dag-id recon_daily --from-date D1 --to-date D2 --run-backwards --max-active-runs 1 --dry-run` |
| `make backfill FROM=D1 TO=D2` | the same command without `--dry-run` |
| `make reprocess FROM=D1 TO=D2` | `docker compose exec -T airflow-scheduler airflow backfill create --dag-id recon_daily --from-date D1 --to-date D2 --reprocess-behavior completed --max-active-runs 1` |
| `make clear-day DAY=D` | `docker compose exec -T airflow-scheduler airflow tasks clear recon_daily -s D -e D -y` |
| `make doctor` (its Airflow part) | `docker compose exec -T airflow-scheduler airflow pools get dbt_serial` |

Each target that takes `FROM`, `TO` or `DAY` stops with an error when the value is empty, before calling Airflow.

Every Airflow target has `-T` because the Makefile keeps the prefix in one variable, `AIRFLOW := docker compose exec -T airflow-scheduler airflow` (`docs/build_plan.md`, heading "Make targets: what each runs, and the step that adds it"). `-T` tells `docker compose exec` not to set up a terminal (TTY) for the command. The targets then also run where there is no terminal, for example in a script or an agent's shell. The commands you type by hand in this file leave `-T` out. If one fails without a terminal, see "the input device is not a TTY".

### Pre-flight checks

Before the first `make up` of a session:
1. Docker Desktop runs: `open -a Docker`, wait, then `docker info --format '{{.ServerVersion}}'` prints a version.
2. Docker has at least 6 GB of memory: `docker info --format '{{.MemTotal}}'` prints at least about 5.5 GiB (`5905580032` bytes). Docker reports a little less than the value set in Settings, Resources. The number comes from the Linux kernel inside Docker's VM, which keeps some memory for itself, so a correct 6 GB setting prints less than `6442450944`. To see the setting itself, read the Memory slider in Docker Desktop, Settings, Resources. If it is below 6 GB: set Memory to 6 GB or more, then "Apply & restart". The compose file warns below 4 GB.
3. At least 10 GB of disk is free: `df -h ~` (column "Avail").
4. The course stack is stopped: `(cd ~/Developer/learning/courses/airflow && docker compose down)`. Then `docker ps --format '{{.Names}}'` lists no container from that stack.
5. Port 8083 is free: `lsof -nP -iTCP:8083 -sTCP:LISTEN` prints nothing.
6. `.env` holds the four values: `grep -c -E '^(AIRFLOW_UID|GCP_PROJECT|RECON_SEED|RECON_WORLD_START)=.+' .env` prints `4`; `grep -c -E '^(DBT_KEYFILE|GOOGLE_APPLICATION_CREDENTIALS)=' .env` prints `0`; and `id -u` prints the same number as `AIRFLOW_UID`.
7. The key exists and is private: `ls -l keys/sa.json` shows `-rw-------`.
8. The dbt package is installed on the host: `ls dbt/dbt_packages` lists `dbt_utils`. If not, run `make setup`.
9. The local folders exist: `ls -d landing runs logs config plugins`. `make setup` creates them.
10. The compose file is valid: `docker compose config --quiet` prints nothing.

### Build the image

Step S2.1. Needs internet access to PyPI and github.com.
1. `docker compose build`. The first build takes several minutes. Start it in a second terminal and keep working on S2.2.
2. Check the result: `docker image ls ledger-vs-statement-airflow` shows the tag `3.3.2`.
3. Check dbt in the image without starting the stack: `docker run --rm --entrypoint /opt/airflow/dbt_venv/bin/dbt ledger-vs-statement-airflow:3.3.2 --version` shows Core 1.12.6 and bigquery 1.12.1.
4. Rebuild only after a change to `Dockerfile` or `docker/requirements-dbt.txt`: `docker compose build`, then `make up`, which recreates the containers that use the new image.

### Start the stack

Step S2.5, then at the start of every session.
1. Do the pre-flight checks.
2. `make up`.
3. Wait one to two minutes. `docker compose ps` shows `(healthy)` for `airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor`, `airflow-triggerer` and `postgres`.
4. `docker compose ps -a airflow-init` shows `Exited (0)`. Its log: `docker compose logs airflow-init | tail -n 30`.
5. `docker compose exec airflow-scheduler airflow pools get dbt_serial` shows the pool with 1 slot.
6. `docker compose exec airflow-scheduler airflow dags list-import-errors` reports no errors.
7. `docker compose exec airflow-scheduler airflow dags list` lists the DAG files that exist so far. A new DAG shows `is_paused` True.
8. The first time only: run the four isolation checks in "Why dbt has its own virtual environment" and the key checks in "The service-account key: read-only and readable".
9. Open the UI (next procedures).

If `recon_daily` was left unpaused, the scheduler may start the run for the latest day right after `make up`. That is expected.

### Stop the stack

1. Check that nothing runs: `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state running` and the same with `--state queued` list no runs. Never stop the stack during a backfill or the rerun proof.
2. `make down`. Runs, the pool and the user stay in the Postgres volume, and all files stay in the mounted folders.
3. Never add `--volumes` (or `-v`) unless you mean to delete the Airflow history ("Reset the Airflow metadata (rare)").
4. A task that was running when the stack stopped may show "Failed" or "Up For Retry" a few minutes after the next `make up` (its heartbeat stopped). Clear it ("Clear and rerun a day").

### Open the UI and set its timezone to UTC

1. Open http://localhost:8083 and log in with `airflow` / `airflow`.
2. In the left navigation bar, click the clock button. It is labelled with the current offset, `+05:00` on your Mac. The "Select Timezone" window opens.
3. Choose "UTC (Coordinated Universal Time)". The button now shows `+00:00`.
4. Why: by default the 3.3.2 UI shows and reads times in the browser's timezone (it stores your choice in the browser). In Astana time, midnight UTC is 05:00, so a date typed into the backfill form in local time selects the wrong logical dates.
5. The setting belongs to the browser. Repeat it in another browser or a private window.

### After you add or change a DAG file

1. Save the file in `dags/`.
2. The dag-processor re-parses known files every 30 seconds and looks for new files every 300 seconds (3.3.2 defaults). To parse at once: `docker compose exec airflow-scheduler airflow dags reserialize`.
3. Check for errors: `docker compose exec airflow-scheduler airflow dags list-import-errors`. In the UI an import error appears as a red banner on the Dags page.
4. Check the tasks: `docker compose exec airflow-scheduler airflow tasks list recon_daily`.
5. The next task that starts uses the new file. With a local dags folder there is no older version to go back to: the 3.3.2 docs say local bundles "do not support versioning ... tasks always run using the latest code". The same is true for `src/` and `dbt/`, which are mounted live. That is why the generator and loader freeze at tag `g1-freeze` and dbt after S7.6, and why you never edit code during a backfill or the proof.

### Run the smoke test

Step S2.5, gate G-skel.
1. `make smoke`. In the UI instead: Dags, `smoke_bigquery`, switch its toggle on, "Trigger", "Single Run", "Trigger".
2. Watch: `docker compose exec airflow-scheduler airflow dags list-runs smoke_bigquery`.
3. Done when the run is `success`, the `bq_load_one_row` log shows 1 row in `probe.smoke$<yesterday>`, and the `dbt_debug` log ends with "All checks passed!".
4. An unpaused DAG with `schedule=None` never creates runs by itself, so `smoke_bigquery` can stay unpaused.
5. If it fails, see "BigQuery tasks fail with a key or permission error" and "dbt debug fails in the container".

### Unpause and pause recon_daily

Unpause:
1. `make unpause`. In the UI: Dags page, the toggle on the `recon_daily` row, or the toggle on the DAG page.
2. The CLI prints the old value. "No paused DAGs were found" means it was already unpaused.
3. What follows: the scheduler creates the run for the latest complete UTC day at once (if it does not exist yet), then one run a day just after 00:00 UTC, and queued backfill runs may start.

Pause:
1. `make pause`, or the same toggle.
2. What follows: nothing new starts. That includes queued backfill runs and the next task of a run that is already in progress. Tasks that are already running finish.
3. Pause only when nothing runs. Never pause during a backfill or the proof: the backfill stalls, and when you unpause after a 00:00 UTC boundary, the scheduler creates the missed scheduled run at once, which can overlap the backfill.

Check the state: `docker compose exec airflow-scheduler airflow dags list` (column `is_paused`).

### Run the latest complete day

Step S6.2, gate G1.
1. `make unpause`. The scheduler creates the run for yesterday (UTC). If that run already exists, nothing new happens; use "Run one exact logical date" with reprocessing instead.
2. Find it: `docker compose exec airflow-scheduler airflow dags list-runs recon_daily`. Run type `scheduled`, logical date yesterday.
3. Read the `check_window` log ("Read logs and dbt artifacts"): it must say `run_date=<yesterday>`.
4. Measure the wall time from the `start_date` and `end_date` columns of `list-runs`. S6.2 records it as [T] minutes.

### Run one exact logical date

The rule: an exact day runs only through a one-day backfill, after a dry run.

With the CLI:
1. Dry run: `make backfill-dry FROM=D TO=D`. It prints "Performing dry run of backfill.", the parameters, then "Runs to be attempted:" with one row for D at 00:00 UTC.
2. If the table is empty, either a run for D already exists (go to step 4) or D has not ended yet (D must be yesterday or earlier).
3. Create it: `make backfill FROM=D TO=D`. (`--run-backwards` makes no difference for one day.)
4. If a run for D exists and has finished (`success` or `failed`): `docker compose exec airflow-scheduler airflow backfill create --dag-id recon_daily --from-date D --to-date D --reprocess-behavior completed --max-active-runs 1 --dry-run`, check the one row, then `make reprocess FROM=D TO=D`.
5. Watch it ("Watch runs"). The `check_window` log must say `run_date=D`.

With the UI:
1. Timezone set to UTC.
2. Dags, `recon_daily`, then "Trigger" in the DAG page header. The "Trigger Dag" window opens.
3. Choose "Backfill" ("Run this Dag for a range of dates").
4. "Date Range": From D 00:00, To D 00:00.
5. "Reprocess Behavior": "Missing Runs" for a day that never ran, "All Runs" for a day that already ran.
6. "Max Active Runs": 1 (the field starts at 10).
7. Check the line under the form: "1 run will be triggered." "No runs matching selected criteria." means the day already has a run (switch to "All Runs") or has not ended.
8. "Run Backfill". A message "Backfill generated" appears.

Conditions in both cases: D is at or after `RECON_WORLD_START`, at most 45 days old, and yesterday (UTC) or earlier; the DAG is unpaused; no other backfill of `recon_daily` is running.

Never use `airflow dags trigger recon_daily -l D` for this (see "Manual-run semantics").

### Watch runs

In the UI (DAG page of `recon_daily`):
- Grid: one column per run, one row per task. Hover a square to see its state (Success, Failed, Running, Queued, Scheduled, Up For Retry, Upstream Failed). The mapped `load_raw` row holds three instances.
- "Runs" tab: run type (Scheduled, Backfill, Manual), logical date, state, duration.
- "Backfills" tab: each backfill with its date range and whether it has completed. While one runs, a banner "Backfill in progress" sits on the DAG page.
- The dropdown above the grid sets how many runs it shows ("last 25 runs" and similar). Raise it to see a whole backfill.

With the CLI:

```bash
docker compose exec airflow-scheduler airflow dags list-runs recon_daily                      # all runs
docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state failed       # or queued, running, success
docker compose exec airflow-scheduler airflow dags list-runs recon_daily -s 2026-10-26 -e 2026-11-01   # a logical-date range
docker compose exec airflow-scheduler airflow tasks states-for-dag-run recon_daily 2026-10-20  # every task of run 2026-10-20
docker compose exec airflow-scheduler airflow tasks failed-deps recon_daily dbt_build 2026-10-20 # why a task is not starting
docker compose exec airflow-scheduler airflow dags next-execution recon_daily --field data_interval.start   # the day the next scheduled run processes
docker compose logs --tail 100 airflow-scheduler                                               # what the scheduler is doing
```

During a backfill, the number of `--state queued` runs falls by one per finished day, and `--state failed` must stay empty.

### Read logs and dbt artifacts

Task logs in the UI:
1. In the grid, click the square of the task and run.
2. The "Logs" tab opens by default. For a task that ran more than once, pick the try in the "Try Number" selector.
3. Use "Search logs..." to find a line, for example `run_date=`.
4. The "XCom" tab shows the returned values (R from `check_window`, the counts dicts). The "Rendered Templates" tab shows the rendered dbt command.

Task logs on disk (the default 3.3.2 log path):
- `logs/dag_id=recon_daily/run_id=<run id>/task_id=<task id>/attempt=<try>.log`
- mapped loads: `logs/dag_id=recon_daily/run_id=<run id>/task_id=load_raw/map_index=<0, 1 or 2>/attempt=<try>.log`, with 0 = `payment_events`, 1 = `settlement_lines`, 2 = `fx_rates`.
- Remember that the run id shows the interval end. Run 2026-10-30 from the overnight backfill lives in `run_id=backfill__2026-10-31T00:00:00+00:00`. Copy the run id from `list-runs` instead of typing it.
- Example: `grep -h "run_date=" "logs/dag_id=recon_daily/run_id=backfill__2026-10-31T00:00:00+00:00/task_id=check_window/"attempt=*.log` prints a line with `run_date=2026-10-30`. The lines may be JSON objects rather than plain text; `grep` finds the text either way.

dbt artifacts of run D:
- `runs/dbt/D/logs/dbt.log`: dbt's full log for that run.
- `runs/dbt/D/target/run_results.json`: the status of every model and test.
- `runs/dbt/D/target/compiled/ledger_vs_statement/...`: the compiled SQL. A failing singular test is at `runs/dbt/D/target/compiled/ledger_vs_statement/tests/<test name>.sql`. It is a `SELECT`; paste it into the BigQuery console to see the failing rows.
- List everything that did not pass:

```bash
uv run python -c "import json, sys; r = json.load(open(sys.argv[1])); [print(x['status'], x['unique_id']) for x in r['results'] if x['status'] not in ('success', 'pass')]" runs/dbt/2026-10-20/target/run_results.json
```

Warn-level tests print as `warn`; failed error-level tests as `fail` or `error`.

Container logs: `docker compose logs --tail 100 airflow-scheduler`, `docker compose logs --tail 100 airflow-dag-processor` (parse errors), `docker compose logs airflow-init` (start-up).

### What a retry looks like

Example: `fetch_fx` when the FX API is slow.
1. Try 1 fails, for example after the 10-second HTTP timeout. The square turns "Up For Retry". `log_failure` does not run yet.
2. Airflow waits, then starts try 2. With `retry_delay` 30 s and `retry_exponential_backoff=2.0`, 3.3.2 waits between 30 and 59 seconds before try 2, between 60 and 119 seconds before try 3, and between 120 and 239 seconds before try 4. The exact value inside each range is fixed per task, day and try. `max_retry_delay` caps every wait at 10 minutes.
3. There are at most 4 tries (1 plus `retries=3`). Each try has its own log: the "Try Number" selector in the UI, and `attempt=1.log` to `attempt=4.log` on disk.
4. If try 4 fails, the task is "Failed", `log_failure` writes its one line at the end of the try 4 log, the three `load_raw` instances and `dbt_build` become "Upstream Failed", and the run fails.
5. `ensure_tables` and `load_raw` retry twice, about 30 seconds after the failed try (no backoff, so no random part; the scheduler starts the retry on its next loop).
6. `check_window`, `generate_day` and `dbt_build` have no retries, so a failure shows at once. An `AirflowFailException` never retries.
7. After you fix the cause, clear the failed task together with everything after it ("Clear and rerun a day"). The try counter keeps counting, so the next log is `attempt=5.log`.

### Mark a task or a run failed or success

Marking changes a state without running anything. Use it rarely.

Allowed:
1. Mark a run **failed** to stop it. Its running tasks are told to stop, and its other tasks will not start.
2. Mark a task **failed** when it hangs in "Running" after a restart, so that you can clear it.
3. Mark a run **failed** when it sits in "Queued" and belongs to a cancelled backfill, so that a new one-day backfill can take it over ("A cleared run stays queued").

Never mark a `recon_daily` task or run **success**. A green square must mean that the partitions and marts were really built: the rerun proof and the evidence depend on it.

In the UI:
- A task: in the grid, click the task square, then "Mark Task Instance as...", then "Failed". Read the list of affected tasks, leave "Past", "Future", "Upstream" and "Downstream" off, then "Confirm". Keyboard: select the square, press Shift+F.
- A run: in the grid, click the bar at the top of the run's column (or click the run in the "Runs" tab), then "Mark Dag Run as...", then "Failed", then "Confirm".

The 3.3.2 CLI has no command to mark states. The REST API can: `PATCH /api/v2/dags/recon_daily/dagRuns/<run id>` with the body `{"state": "failed"}`, using a token as in "Stop, pause or resume a running backfill". The run id must be URL-encoded (`+` becomes `%2B`).

### Clear and rerun a day

Clearing resets task instances of an existing run, so the scheduler runs them again with the same data interval. The run goes back to queued and obeys the pool and the run limits like any other run.

With the CLI:
1. Every task of day D: `make clear-day DAY=D`, which runs `docker compose exec -T airflow-scheduler airflow tasks clear recon_daily -s D -e D -y`.
2. Only dbt for day D: `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s D -e D -t dbt_build -y`.
3. A failed task and every task after it: `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s D -e D -t <task id> -d -y`.
4. Only the failed tasks of day D: `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s D -e D -f -y`.

How the flags work:
- `-s` and `-e` select runs by logical date, both ends included, so `-s D -e D` is exactly run D.
- `-t` is a regular expression on task ids. `-t load_raw` clears all three mapped loads. `-t dbt_build` matches only `dbt_build` in this DAG.
- `-d` adds the downstream tasks. Without it, the tasks after the cleared one keep their old state: clearing only `fetch_fx` lands the file again but does not reload BigQuery or rebuild dbt.
- Without `-y` the CLI lists the task instances and asks "Are you sure? [y/n]". The question says "delete"; it means clear. Nothing is deleted.
- The DAG must be unpaused for cleared tasks to run.
- Never clear a run that belongs to a cancelled backfill ("A cleared run stays queued").

With the UI:
- The whole run: click the bar at the top of the run's column, then "Clear Dag Run", keep "Clear existing tasks", then "Confirm".
- One task: click its square, then "Clear Task Instance", tick "Downstream" if the later tasks must rerun too, then "Confirm". Keyboard: Shift+C.
- The mapped loads: "Clear All Mapped Tasks" clears all three; clearing a single instance clears one table.
- Keep "Prevent rerun if task is running" ticked. "Run with latest bundle version" is always on with a local dags folder.

### Backfill a range

Rules for every backfill:
1. The DAG is unpaused. The 3.3.2 scheduler starts queued runs only for unpaused DAGs.
2. Only one backfill of `recon_daily` runs at a time.
3. Always `--max-active-runs 1` on the CLI, and 1 in the UI form, whose "Max Active Runs" field starts at 10 (the REST API default). Never rely on a default here: several days running at once break the newest-first order and let loads land during dbt builds.
4. `TO` is yesterday (UTC) or earlier. A backfill creates runs only for intervals that have ended, and refuses a range that lies entirely in the future.
5. `FROM` is at or after `RECON_WORLD_START` and at most 45 days old.
6. Dry run first, every time.
7. History loads newest first (`--run-backwards`): every run then sees a contiguous history from its own day to the latest loaded day, even after the scheduled latest run exists.

With the CLI:
1. `make backfill-dry FROM=D1 TO=D2`. "Runs to be attempted:" lists one row per logical date, newest first. The 3.3.2 dry run already leaves out days that would not get a run (with the default reprocess behavior, days that already have one). Check the first date, the last date and the count.
2. `make backfill FROM=D1 TO=D2`.
3. All runs of the backfill appear at once as queued, and run one at a time, newest first. The banner "Backfill in progress" appears.
4. Watch it ("Watch runs"). Done when `--state queued` and `--state failed` both list nothing for the range.

With the UI:
1. Timezone set to UTC.
2. Dags, `recon_daily`, "Trigger", then "Backfill".
3. "Date Range": From D1 00:00, To D2 00:00.
4. "Reprocess Behavior": "Missing Runs".
5. "Max Active Runs": 1 (the field starts at 10).
6. "Run Backwards": on.
7. Leave "Advanced Options" (the run conf) empty.
8. Check the line "N runs will be triggered." against your own count.
9. If the window shows "Unpause recon_daily on trigger", the DAG is paused. The runs cannot start while it stays paused. Tick it only if you mean to unpause now, which also creates the latest scheduled run.
10. "Run Backfill".

The UI's three choices match the CLI's `--reprocess-behavior`: "Missing Runs" is `none`, "Missing and Errored Runs" is `failed`, "All Runs" is `completed`. The UI also notes that backfill runs are ordered after other runs in each scheduler cycle, so a scheduled run starts first when both are waiting.

### The overnight history load

Step S6.3. Preconditions: gate G1 passed (one `recon_daily` run green end to end), tag `g1-freeze` exists, and you know the wall time [T] of one run.
1. Choose the range. 27 runs (2026-10-04 to 2026-10-30) take about 27 times [T]. If that is more than about 4 hours, use `FROM=2026-10-18`. The backfill should finish before 00:00 UTC (05:00 Astana), when the scheduled run for 2026-11-01 starts.
2. Keep the Mac on power with the lid open. Closing the lid sleeps the Mac whatever else you do.
3. In a second terminal, run `caffeinate -is` and leave it running. `-i` stops idle sleep; `-s` stops system sleep while on power.
4. Keep Docker Desktop open.
5. `make backfill-dry FROM=2026-10-04 TO=2026-10-30`: 27 rows, the first 2026-10-30 and the last 2026-10-04.
6. `make backfill FROM=2026-10-04 TO=2026-10-30`.
7. Watch the first run until `load_raw` is green and `dbt_build` has started, so you know the chain works before you sleep.

In the morning (step S7.1):
1. `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state failed` lists nothing.
2. `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state success -s 2026-10-04 -e 2026-11-01` lists 29 runs: the 27 backfill days, 2026-10-31 (from the unpause) and 2026-11-01 (the 00:00 UTC scheduled run). With `FROM=2026-10-18` it lists 15.
3. Each day has its FX files: `ls landing/fx/provider=nbk/*.meta.json | wc -l` prints the same count. Commit `landing/fx/`: it is real data, landed once, never fetched again.
4. Stop `caffeinate` with Ctrl+C.
5. If a run failed, read its logs and use "Failure scenarios and what to do".

### Reprocess finished days

Reprocessing reruns days that already have a finished run. The backfill clears each existing run and queues it again as part of the new backfill; the run keeps its run id, and its run type becomes backfill.
1. Dry run: `docker compose exec airflow-scheduler airflow backfill create --dag-id recon_daily --from-date D1 --to-date D2 --reprocess-behavior completed --max-active-runs 1 --dry-run`. Every finished day in the range is listed.
2. `make reprocess FROM=D1 TO=D2`.
3. Watch until the range is green.

The three behaviours: `none` (the default) skips days that already have a run; `failed` reruns only days whose run failed; `completed` reruns every finished day, successful or failed. A day whose run is still queued or running is never rerun, whatever you choose. In the UI it is the backfill form with "Reprocess Behavior" set to "All Runs".

### Stop, pause or resume a running backfill

The 3.3.2 CLI can only create backfills. Stopping one happens in the UI or through the REST API.

Three tools:
1. **Pause the backfill** (banner "Backfill in progress", "Pause backfill"). Its queued runs wait; the run in progress finishes. "Unpause backfill" continues where it stopped. Scheduled runs are not affected. Use this when the Mac has to sleep.
2. **Cancel the backfill** (same banner, "Cancel backfill"). In 3.3.2 this pauses the backfill, sets every queued run of it to failed, and marks the backfill completed. The run in progress finishes. Afterwards the days that never started show as red, failed runs: that is expected, not a data problem. To finish them later, create a new backfill over the same range with `--reprocess-behavior failed` (dry run first). Do not use `tasks clear` on runs of a cancelled backfill.
3. **Pause the DAG.** Avoid during a backfill ("Unpause and pause recon_daily").

If the UI is not reachable, use the REST API:

```bash
TOKEN=$(curl -s -X POST http://localhost:8083/auth/token -H "Content-Type: application/json" -d '{"username": "airflow", "password": "airflow"}' | uv run python -c "import json, sys; print(json.load(sys.stdin)['access_token'])")
curl -s "http://localhost:8083/api/v2/backfills?dag_id=recon_daily" -H "Authorization: Bearer $TOKEN"
curl -s -X PUT "http://localhost:8083/api/v2/backfills/<id>/cancel" -H "Authorization: Bearer $TOKEN"
```

1. The first line gets a token (the UI can also make one: User menu, "Generate Token").
2. The second lists the backfills. The running one has `"completed_at": null`; note its `id`.
3. The third cancels it. Replace `cancel` with `pause` or `unpause` for the other two actions.
4. Never paste the token anywhere public or commit it.

### The idempotency proof

Steps M8 and S8.2. It measures N1. Do all of it inside one UTC day (after 05:00 Astana on Monday and long before 05:00 on Tuesday): a new day landing at 00:00 UTC would change `as_of_date` and every mart row, and the comparison would report changes for a trivial reason.

Preconditions:
1. The code is frozen: generator and loader since `g1-freeze`, dbt since S7.6.
2. S7.6 is done: the latest marts were built by the final dbt code (`docker compose exec airflow-scheduler airflow tasks clear recon_daily -s 2026-11-01 -e 2026-11-01 -t dbt_build -y`, then green).
3. Nothing runs, and the DAG stays unpaused throughout.

Steps:
1. Confirm the scheduled run for 2026-11-01 finished: `docker compose exec airflow-scheduler airflow dags list-runs recon_daily -s 2026-11-01 -e 2026-11-01` shows `success`. Confirm that `--state running` and `--state queued` list nothing.
2. `make snapshot OUT=docs/evidence/2026-11-02/fp_before.json FROM=2026-10-03 TO=2026-11-01`.
3. Dry run the reprocess: `docker compose exec airflow-scheduler airflow backfill create --dag-id recon_daily --from-date 2026-10-26 --to-date 2026-11-01 --reprocess-behavior completed --max-active-runs 1 --dry-run` lists 7 dates.
4. `make reprocess FROM=2026-10-26 TO=2026-11-01`. Write `scripts/results.py` while it runs.
5. When all 7 runs are `success` (`list-runs -s 2026-10-26 -e 2026-11-01`): `make clear-day DAY=2026-10-14`, one older day, out of order. Wait until run 2026-10-14 is `success`. If it stays queued for more than 5 minutes, see "A cleared run stays queued".
6. `make snapshot OUT=docs/evidence/2026-11-02/fp_after.json FROM=2026-10-03 TO=2026-11-01`.
7. `make compare BEFORE=docs/evidence/2026-11-02/fp_before.json AFTER=docs/evidence/2026-11-02/fp_after.json`. It writes `docs/evidence/2026-11-02/compare.json` and prints "[P] of [P] (table, partition) groups identical, [R] rows, as_of [A] in both". It exits non-zero on any changed group or a changed `as_of_date`.

Why `FROM=2026-10-03`: USD accounting dates can fall one day before world start, so the mart partitions start a day earlier than the raw ones.

A non-zero result is a finding. Write it in `docs/failure_log.md`, fix the cause, and run the proof again. Never hide it. U3 later adds the full-window reprocess, a negative control (one day reloaded with another seed must show changes) and the host-versus-Airflow comparison.

### Reset the Airflow metadata (rare)

`docker compose down --volumes` deletes the Postgres volume: every run, every backfill record, the user and the pool. Log files in `logs/` and all data in BigQuery stay. The next `make up` creates the user and the pool again, and every DAG starts paused with no history.

Use it only when the metadata is broken or for a clean rehearsal, and never before the evidence and the grid screenshot are saved.

## Failure scenarios and what to do

Each entry: how it shows, the usual cause, and what to do. After any real bug, add an entry to `docs/failure_log.md` (heading "Entry format").

### The image build fails while installing dbt

- **Shows as:** `docker compose build` stops in the `pip install` step, often at `dbt-core-experimental-parser`.
- **Cause:** no access to github.com (the parser downloads its wheel from GitHub releases) or to PyPI.
- **Do:** 1. Check your connection and any VPN. 2. Run `docker compose build` again. 3. Never add `--only-binary` and never install dbt into Airflow's environment as a workaround.

### airflow-init exits with an error and nothing else starts

- **Shows as:** `docker compose ps -a airflow-init` shows `Exited (1)`; the other Airflow services wait or restart.
- **Cause:** usually `keys` added to the `chown` line (read-only mount), a YAML mistake in the command block, or a database that was not ready.
- **Do:** 1. `docker compose logs airflow-init | tail -n 50`. 2. Fix the compose file (compare it with "docker-compose.yaml: the changes to the course file"). 3. `docker compose config --quiet`. 4. `make up`.

### A service is not healthy, or port 8083 is taken

- **Shows as:** `docker compose ps` lacks `(healthy)`, or the UI does not open. When the API server is down, tasks cannot start either: they report to its Execution API.
- **Do:** 1. Port: `lsof -nP -iTCP:8083 -sTCP:LISTEN` shows who holds it; stop that program or stack. 2. Memory: check Docker's memory (pre-flight check 2). 3. `docker compose logs --tail 100 <service>`. 4. `make down`, then `make up`.

### The DAG does not appear, or shows an import error

- **Shows as:** the DAG is missing from `airflow dags list`, or the Dags page has a red import-error banner.
- **Cause:** a syntax or import error, or a new file that the dag-processor has not found yet (it looks every 300 seconds).
- **Do:** 1. `docker compose exec airflow-scheduler airflow dags list-import-errors`. 2. Fix the file; `uv run ruff check dags/ --select AIR301,AIR302` finds Airflow 2 imports. 3. `docker compose exec airflow-scheduler airflow dags reserialize`.

### BigQuery tasks fail with a key or permission error

- **Shows as:** "No such file or directory: '/opt/airflow/keys/sa.json'", "Permission denied", a 403 or 404 from BigQuery, or a client with an empty project.
- **Cause:** the key was missing at `make up`; `AIRFLOW_UID` differs from `id -u`; `GCP_PROJECT` is empty or wrong in `.env`; the service account lacks BigQuery Job User or BigQuery Data Editor; the dataset `probe` does not exist (for `smoke_bigquery`).
- **Do:** 1. Pre-flight checks 6 and 7. 2. The key checks in "The service-account key: read-only and readable". 3. Check the roles in the console. 4. After fixing `.env`: `make down`, then `make up`. 5. `make smoke`.

### dbt debug fails in the container

- **Shows as:** `dbt_debug` in `smoke_bigquery` fails; its log names the failing check.
- **Do:** 1. "profiles.yml" problems: `DBT_PROFILES_DIR`, `DBT_KEYFILE` and `GCP_PROJECT` must be set (`docker compose exec airflow-scheduler bash -c 'echo $DBT_PROFILES_DIR $DBT_KEYFILE $GCP_PROJECT'`). 2. Connection problems: as in the previous entry. 3. "dbt_project.yml" problems: fix the project file; the host `uv run dbt debug` should fail the same way.

### The host runs the wrong dbt

- **Shows as:** `make doctor` fails, or `dbt --version` shows 2.x.
- **Cause:** a bare `dbt` reached `~/.local/bin/dbt` (dbt v2, another program).
- **Do:** Use `uv run dbt` or `make`. In the containers only `/opt/airflow/dbt_venv/bin/dbt` exists.

### dbt packages are missing in the container

- **Shows as:** `dbt_build` fails with a message that the packages in `packages.yml` are not installed and that you should run "dbt deps".
- **Do:** 1. On the host: `make setup` (it runs `uv run dbt deps` into `dbt/dbt_packages/`, which the container sees through the mount). 2. Clear `dbt_build` for that day.

### check_window fails

- **Shows as:** the run fails at its first task. The log names the rule.
- **Cause and do:**
  1. "No data interval": the run was made with `airflow dags trigger` without `-l`, or through the REST API without a logical date. Leave that failed manual run as it is and use a one-day backfill.
  2. "not one UTC day": a manual run with a typed interval. Use a one-day backfill.
  3. Before `RECON_WORLD_START`, today or later, or older than 45 days: pick a date inside the window. Never lift the guard. After the window has moved past the published dates, follow the window rule under the heading "Setup" in `README.md`.

### The FX API is slow or down

- **Shows as:** `fetch_fx` goes "Up For Retry", then fails after try 4; the loads and dbt are "Upstream Failed".
- **Do:** 1. Wait and clear `fetch_fx` with downstream: `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s D -e D -t fetch_fx -d -y`. 2. If it stays down: land a hand-fetched response at the same path, with its meta file, in the format `docs/specs/data_and_generator.md` describes (this is cut-order item 6 in `docs/build_plan.md`), then clear with downstream. The FX stays real.

### load_raw fails

- **Shows as:** one or more `load_raw` instances fail before or inside the load job.
- **Cause:** a row whose `_arrival_date` is not R, a schema mismatch with the schema JSON, `output_rows` different from the rows landed, or a missing landing file.
- **Do:** 1. Read the instance's log (`map_index` tells the table). 2. Fix the generator or the schema JSON. Remember the freeze: after `g1-freeze`, any change means reprocessing the whole window before the proof. 3. Clear `load_raw` with downstream: `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s D -e D -t load_raw -d -y`.

### A dbt error-level test fails

- **Shows as:** `dbt_build` fails; `run_results.json` lists a `fail` or `error`.
- **Do:** 1. Find it with the `run_results.json` command in "Read logs and dbt artifacts". 2. Open its compiled SQL and run it in the BigQuery console to see the failing rows. 3. Fix the cause (on the host first: `make day`, `make dbt-build`). 4. Clear only `dbt_build`: `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s D -e D -t dbt_build -y`. 5. Write the failure log entry.

### A statement file is missing

- **Shows as:** `assert_arrival_days_complete` fails.
- **Do:** 1. Load the missing day with a one-day backfill (or reprocess it if a run exists). 2. Then clear `dbt_build` of the latest day.

### DML slipped in

- **Shows as:** HTTP 403 with "DML queries are not allowed in the free tier".
- **Do:** Change the materialization or the code back to a sandbox-safe pattern (see the never-list in `AGENTS.md`). U3 adds the `make no-dml` check.

### The storage quota is exhausted

- **Shows as:** RESOURCE_EXHAUSTED on a load job or a table build.
- **Do:** Stop all writes (pause the DAG once nothing runs). Follow Plan B in `docs/specs/bigquery_sandbox_and_costs.md`. Never create a second sandbox project to reset the quota.

### A backfill never starts

- **Shows as:** its runs stay "Queued".
- **Cause:** the DAG is paused; the backfill itself is paused (banner shows "Unpause backfill"); or a non-backfill run is ahead in the queue.
- **Do:** 1. `make unpause` (or "Unpause backfill" in the banner). 2. `docker compose exec airflow-scheduler airflow pools get dbt_serial`. 3. `docker compose logs --tail 100 airflow-scheduler`.

### dbt_build waits in "Scheduled"

- **Shows as:** every task of the run is done except `dbt_build`, which does not start.
- **Cause:** another run's `dbt_build` holds the only slot (normal, it waits), or the pool does not exist.
- **Do:** 1. `docker compose exec airflow-scheduler airflow tasks failed-deps recon_daily dbt_build D` names the reason. 2. If the pool is missing: `docker compose exec airflow-scheduler airflow pools set dbt_serial 1 "one dbt build at a time"`, and check why `airflow-init` did not create it.

### "Another backfill is running"

- **Shows as:** `backfill create` fails with "Another backfill is running for Dag recon_daily. There can be only one running backfill per Dag."
- **Do:** Wait until it finishes, or pause or cancel it ("Stop, pause or resume a running backfill").

### A backfill would create no runs

- **Shows as:** the dry run lists no rows, or the CLI warns "No runs to create for Dag recon_daily in the range ...".
- **Cause:** every day in the range already has a run (default behaviour `none`), or the range has not ended yet.
- **Do:** Use `--reprocess-behavior completed` (or `failed`) for days that already ran; keep `TO` at yesterday or earlier.

### The UI backfill picked the wrong days

- **Shows as:** the runs' logical dates are off by one day, or the form says "No runs matching selected criteria." for a range that should work.
- **Cause:** the UI timezone was not UTC.
- **Do:** 1. Cancel the backfill if it is running. 2. Set the timezone to UTC. 3. Repeat. Days created by mistake are harmless: every run is idempotent, and its `check_window` refuses dates outside the window.

### A backfill was started without --max-active-runs 1

- **Shows as:** several backfill runs are running at the same time.
- **Do:** 1. Cancel it. 2. Wait until no run is running. 3. Clear `dbt_build` of the latest day. 4. Finish the cancelled days with a new backfill (`--reprocess-behavior failed --max-active-runs 1`). The pool kept dbt builds apart, but loads may have landed during builds.

### Two runs overlapped and dbt_build failed

- **Shows as:** while a backfill and the scheduled run were both active, one run's `dbt_build` failed `assert_recon_decomposition_closes` or `assert_no_money_lost_between_layers`.
- **Cause:** the pool keeps dbt builds apart, but another run landed a new day in the middle of this build, so the build's tables saw two states of raw.
- **Do:** 1. Wait until nothing runs. 2. Clear the failed run's `dbt_build`; it rebuilds everything from the complete raw tables. 3. If it passes, this was the overlap and not a matcher bug; note it in the failure log. 4. Next time, plan the backfill to end before 00:00 UTC.

### A cleared run stays queued

- **Shows as:** after `tasks clear` (or `make clear-day`), the run stays "Queued" for more than 5 minutes while nothing else runs.
- **Cause:** the run belongs to a cancelled backfill. In 3.3.2 a cancelled backfill stays paused, and queued runs of a paused backfill never start. A new backfill also skips the day, because the run counts as in progress.
- **Do:** 1. Mark the run failed ("Mark a task or a run failed or success"). 2. `docker compose exec airflow-scheduler airflow backfill create --dag-id recon_daily --from-date D --to-date D --reprocess-behavior failed --max-active-runs 1 --dry-run`, check the one row, then run it without `--dry-run`. The new backfill takes the run over and queues it.

### A task hangs in "Running" after a restart or a sleep

- **Shows as:** a task shows "Running" for much longer than usual, and nothing happens in its log.
- **Do:** 1. Wait 5 minutes: the scheduler fails tasks whose heartbeat stopped (default timeout 300 seconds), and a task with retries then retries. 2. If it still shows "Running", mark the task failed, then clear it with downstream.

### The Mac slept during runs

- **Shows as:** runs stalled overnight; after waking, some tasks may fail because their heartbeat stopped.
- **Do:** 1. Wake the Mac; the scheduler continues by itself. 2. Clear or reprocess the days that failed. 3. Next time: power on, lid open, `caffeinate -is`.

### Code changed during a backfill

- **Shows as:** days built by different code (tasks always run the latest files in `dags/`, `src/` and `dbt/`).
- **Do:** Finish or cancel the backfill, then reprocess the whole window with the final code before the proof. The freeze rules exist to avoid this.

### Key leaked

- **Do at once:** 1. In the Google Cloud console, IAM, Service accounts, `lvs-pipeline`, Keys: delete the leaked key. 2. Create a new key and save it as `keys/sa.json` with `chmod 600`. 3. If it was pushed, rewrite the git history and force-push, then check `git log --all -- keys .env` is empty. 4. `make down`, then `make up`.

### "the input device is not a TTY"

- **Shows as:** a `docker compose exec` command fails in a script or an agent's shell.
- **Do:** Add `-T` after `exec`. The Make targets already pass it. The commands in this file never wait for input, because they all use `-y` where Airflow would ask.

## Later upgrade: Cosmos

Cosmos turns every dbt model into its own Airflow task, with per-model retries and the dbt lineage visible in the grid. It is a v1.x item in `docs/roadmap.md`, time-boxed to 45 minutes, and `docs/adr/0006-dbt-runtime-in-airflow.md` records why v1.0 uses the BashOperator.

### Pins

| Package | Pin | Why |
|---|---|---|
| `astronomer-cosmos` | `1.15.0` | the Cosmos compatibility page lists 1.14.0, 1.14.1, 1.14.2 and 1.15.0 as "Confirmed working" on Airflow 3.2 and 3.3, and lists versions from 1.5.1 to 1.13.1 as confirmed failing there. 1.15.1 is newer but is not on that list. Never a 1.16 release candidate |
| Airflow | `apache-airflow==3.3.2`, unchanged | named on the install line so pip refuses to change it |
| dbt | the existing venv, unchanged | Cosmos calls it by path |

### Install

Cosmos is the only package that may ever go into Airflow's environment, and it goes in with the constraints. Add one line to the `Dockerfile`, after the dbt venv:

```dockerfile
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" "astronomer-cosmos==1.15.0" \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.13.txt"
```

`AIRFLOW_VERSION` is set to `3.3.2` inside the image. This is the docker-stack guide's pattern for adding a package with constraints. If pip reports a conflict, stop: the time box ends there, and the failure log records why.

### Code shape

The task group replaces only `dbt_build`; everything before it stays.

```python
from cosmos import (
    DbtTaskGroup, ExecutionConfig, ExecutionMode, LoadMode,
    ProfileConfig, ProjectConfig, RenderConfig, TestBehavior,
)

DBT = "/opt/airflow/dbt_venv/bin/dbt"

dbt = DbtTaskGroup(
    group_id="dbt",
    project_config=ProjectConfig(dbt_project_path="/opt/airflow/dbt", install_dbt_deps=False),
    profile_config=ProfileConfig(
        profile_name="ledger_vs_statement",
        target_name="airflow",
        profiles_yml_filepath="/opt/airflow/dbt/profiles.yml",
    ),
    execution_config=ExecutionConfig(execution_mode=ExecutionMode.LOCAL, dbt_executable_path=DBT),
    render_config=RenderConfig(
        load_method=LoadMode.DBT_LS,
        dbt_executable_path=DBT,
        test_behavior=TestBehavior.BUILD,
        exclude=["resource_type:unit_test"],
    ),
    operator_args={"pool": "dbt_serial"},
)
```

What each part does:
- `ProjectConfig`: the mounted project; `install_dbt_deps=False` because `dbt deps` runs on the host.
- `ProfileConfig` with `profiles_yml_filepath`: Cosmos uses the committed `profiles.yml` and target `airflow`, so threads, `maximum_bytes_billed` and the key path stay the same as today.
- `ExecutionConfig` and `RenderConfig` both get `dbt_executable_path`: the Cosmos docs' answer to the dependency conflict.
- `LoadMode.DBT_LS`: the dag-processor runs `dbt ls` from the venv to learn the models. All services share the image and environment, so it works there too.
- `TestBehavior.BUILD`: one `dbt build` per model, with the model's tests attached.
- `exclude=["resource_type:unit_test"]`: unit tests stay on the host; Cosmos passes the exclusion to the test commands too.
- `operator_args={"pool": "dbt_serial"}`: every model task uses the 1-slot pool.

Trade-offs to know before you start:
1. With one task per model in a 1-slot pool, models of two overlapping runs could interleave. The rule "never let a backfill overlap the 00:00 UTC run" becomes strict. Cosmos's `ExecutionMode.WATCHER` (stable since 1.15.0) runs one `dbt build` in a producer task and watches each model from sensor tasks; its producer takes Airflow arguments through `ExecutionConfig(setup_operator_args={"pool": "dbt_serial"})`. Try it only if LOCAL works first.
2. The per-run folder `runs/dbt/<run_date>/` is not automatic under Cosmos. Check where `run_results.json` ends up before you rely on it.
3. Parsing runs `dbt ls`, which makes each DAG parse slower.

### Verify, then decide

1. Work on a branch. Keep the BashOperator version on `main` until Cosmos passes.
2. One one-day backfill green, every model task green.
3. The fingerprints of that day's partitions match the BashOperator version (`make snapshot` before and after, then `make compare`).
4. `make no-dml` finds nothing.
5. If checks 2 to 4 hold within 45 minutes: merge and update `docs/adr/0006-dbt-runtime-in-airflow.md`. If not: leave the branch, write the failure log entry, keep the BashOperator.

## Check yourself

Answer aloud, without notes (milestones M2 and M6). Model answers are in `docs/learning/concepts.md`, heading "Explain checks with model answers", and in this file.
1. Why does dbt have its own venv, and why is it installed without Airflow's constraints?
2. How does the key reach the container, and why can no task change it?
3. Why does `smoke_bigquery` never touch `raw`?
4. Which interval does run 2026-10-25 process, and what date does its run id show?
5. Why `CronDataIntervalTimetable` and not `"@daily"`?
6. What does `airflow dags trigger recon_daily -l 2026-10-25` process?
7. Why load history newest first?
8. What does the pool `dbt_serial` protect, and what does it not protect?
9. What happens to the days of a cancelled backfill, and how do you finish them?
10. Why is `TO` always yesterday or earlier?

## Sources (checked 2026-11-01)

Airflow 3.3.2 documentation:
- CLI reference (every command and flag in this file): https://airflow.apache.org/docs/apache-airflow/3.3.2/cli-and-env-variables-ref.html
- Backfill (reprocess behaviours, "applied independently", UI steps): https://airflow.apache.org/docs/apache-airflow/3.3.2/core-concepts/backfill.html
- Timetables (trigger vs data interval): https://airflow.apache.org/docs/apache-airflow/3.3.2/authoring-and-scheduling/timetable.html
- Configuration reference (`create_cron_data_intervals`, `log_filename_template`, `refresh_interval`, `min_file_process_interval`, `task_instance_heartbeat_timeout`): https://airflow.apache.org/docs/apache-airflow/3.3.2/configurations-ref.html
- Templates reference (`ds` filter, `logical_date`): https://airflow.apache.org/docs/apache-airflow/3.3.2/templates-ref.html
- Connections (environment-variable JSON, not shown in the UI): https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/connection.html
- DAG bundles (local bundles run the latest code): https://airflow.apache.org/docs/apache-airflow/3.3.2/administration-and-deployment/dag-bundles.html
- Task logging (log file layout): https://airflow.apache.org/docs/apache-airflow/3.3.2/administration-and-deployment/logging-monitoring/logging-tasks.html
- UI overview: https://airflow.apache.org/docs/apache-airflow/3.3.2/ui.html
- Public API authentication (`POST /auth/token`): https://airflow.apache.org/docs/apache-airflow/3.3.2/security/api.html
- REST API spec (backfill cancel, pause, unpause; dag run patch): https://airflow.apache.org/docs/apache-airflow/3.3.2/stable-rest-api-ref.html
- FAB auth manager token: https://airflow.apache.org/docs/apache-airflow-providers-fab/stable/auth-manager/token.html
- Docker stack, extending the image (venv example, constraints example): https://airflow.apache.org/docs/docker-stack/build.html
- Release notes, 3.2.0, "Support numeric multiplier values for retry_exponential_backoff parameter" (`True` is converted to 2.0; explicit numbers recommended): https://airflow.apache.org/docs/apache-airflow/3.3.2/release_notes.html

Airflow 3.3.2 source (tag `3.3.2` on github.com/apache/airflow):
- `Dockerfile` (`VIRTUAL_ENV=/home/airflow/.local`, constraints copy, `git` in the runtime packages) and `scripts/docker/entrypoint_prod.sh` (migration on every call with `_AIRFLOW_DB_MIGRATE`)
- `airflow-core/src/airflow/timetables/interval.py` (`_skip_to_latest`, `infer_manual_data_interval`) and `timetables/base.py` (`DagRunInfo.interval`: `run_after` is the interval end; run ids from `run_after`)
- `airflow-core/src/airflow/models/backfill.py` (inclusive range, only ended intervals, future ranges refused, one active backfill per DAG, dry run filtered by reprocess behaviour, re-adoption of existing runs) and `cli/cli_config.py` (`--max-active-runs` has no CLI default; the REST body defaults to 10)
- `airflow-core/src/airflow/api_fastapi/core_api/routes/public/backfills.py` (cancel: pause, queued runs to failed, completed)
- `airflow-core/src/airflow/models/dagrun.py` (queued runs start only for unpaused DAGs and unpaused backfills)
- `airflow-core/src/airflow/models/taskinstance.py` (`next_retry_datetime`: backoff, jitter, cap)
- `airflow-core/src/airflow/serialization/serialized_objects.py` (`populate_operator`: in the scheduler's copy of a task, a boolean `retry_exponential_backoff` becomes 2.0 or 0)
- `airflow-core/src/airflow/api/common/trigger_dag.py` and `api_fastapi/core_api/datamodels/dag_run.py` (CLI vs UI and REST interval inference)
- `airflow-core/src/airflow/cli/commands/task_command.py` and `dag_command.py` (logical date or run id, clear date filter, pause output)
- `airflow-core/src/airflow/ui/src/context/timezone/TimezoneProvider.tsx` (the UI defaults to the browser's timezone) and `ui/public/i18n/locales/en/*.json` (UI labels)
- Task SDK 1.3.2 `airflow/sdk/__init__.py`, `bases/operator.py` (`retry_exponential_backoff` float) and `exceptions.py`; providers-standard 1.19.0 `operators/bash.py` (`env`, `append_env`, `cwd`, `skip_on_exit_code`, `.sh` templates)
- providers-google 22.5.0 `hooks/bigquery.py` and `common/hooks/base_google.py` (legacy SQL default, extras, `get_client`)

Docker:
- `docker info` memory: the daemon reads `MemTotal` from `/proc/meminfo` inside Docker's Linux VM (`daemon/info.go` and `pkg/meminfo/meminfo_linux.go` on github.com/moby/moby). The kernel defines it as "Total usable RAM (i.e. physical RAM minus a few reserved bits and the kernel binary code)": https://docs.kernel.org/filesystems/proc.html

dbt and Cosmos:
- dbt exit codes (only 0, 1 and 2 are documented): https://docs.getdbt.com/reference/exit-codes
- dbt 1.12 upgrade guide (`.env` loaded from the working directory): https://docs.getdbt.com/docs/dbt-versions/core-upgrade/upgrading-to-v1.12
- Cosmos compatibility policy: https://astronomer.github.io/astronomer-cosmos/policy/compatibility-policy.html
- Cosmos 1.15.0 source and docs (tag `astronomer-cosmos-v1.15.0`): `cosmos/config.py`, `docs/guides/dbt_setup/execution-modes-local-conflicts.rst`, `docs/guides/translate_dbt_to_airflow/selecting-excluding.rst`, `docs/guides/run_dbt/airflow-worker/watcher-execution-mode.rst`
