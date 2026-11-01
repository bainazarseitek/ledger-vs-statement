Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0006: dbt runtime in Airflow

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** U1 (M11), step S11.5

## Context

1. dbt cannot share Airflow's environment: the 3.3.2 constraints for Python 3.13 pin `google-cloud-storage==3.14.1` and `pathspec==1.1.1`, but dbt-bigquery 1.12.1 needs `google-cloud-storage<3.2` and dbt-core 1.12.6 needs `pathspec<1.1`.
2. dbt-core 1.12.6 needs `dbt-core-experimental-parser`; version 2.0.8 downloads an aarch64 wheel from github.com while it installs.
3. With LocalExecutor, tasks run in the scheduler container (Python 3.13.15). The host's `~/.local/bin/dbt` is dbt v2 and must never run this project.
4. The project is small: 9 models, about 200 payments a day (design estimate).

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| BashOperator calling `/opt/airflow/dbt_venv/bin/dbt build` | one moving part; the host's command | one task for all models | **Chosen** |
| Cosmos `DbtTaskGroup` | a task per model | new under time pressure; only 1.14.0 to 1.15.0 confirmed on Airflow 3.3 | v1.x: 1.15.0, a 45-minute time box, never a 1.16 RC |
| dbt in Airflow's environment | no extra venv | the pin conflicts | Rejected |
| DockerOperator per run | isolation | Docker in Docker on a Mac | Rejected |
| dbt v2 (Rust engine) | dbt Labs' default for new projects | another engine and licence | Not now |

## Decision

1. The repo-root `Dockerfile` (`FROM apache/airflow:3.3.2`, image `ledger-vs-statement-airflow:3.3.2`) creates `/opt/airflow/dbt_venv` and installs `docker/requirements-dbt.txt` (`dbt-core==1.12.6`, `dbt-bigquery==1.12.1`, `dbt-core-experimental-parser==2.0.8`). Nothing goes into Airflow's environment, no key goes into the image, and `--only-binary` is never added.
2. `dbt_build` is a BashOperator with `pool="dbt_serial"`, `append_env=True` (a future `env` adds to the container's variables instead of replacing them) and `retries=0`. The command is inline, because a string ending in `.sh` is read as a template file:

```bash
cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt build --target airflow --exclude-resource-type unit_test --target-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/target --log-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/logs
```

3. Unit tests run only on the host (`make dbt-build`, `make dbt-unit`), never in the DAG.
4. Never a bare `dbt`: `uv run dbt` on the host, the venv path in the container. `make doctor` fails unless `uv run dbt --version` shows Core 1.12.6 and bigquery 1.12.1.
5. `dbt deps` runs on the host; `dbt/dbt_packages/` reaches the container through the `./dbt` mount. No dbt vars in v1.0 (U5 adds `run_date`, ADR-0008).

## Consequences

**Cost.** $0; the image grows by several hundred MB (dbt-bigquery pulls in AI Platform and Dataproc clients).

**Better.** One command on the host and in Airflow, with artifacts kept per run date under `runs/dbt/<run_date>/`; Airflow's pins stay untouched.

**Worse.** One failing test fails the whole task (fix it, then clear only `dbt_build`, as in "Operations runbook" in `docs/specs/airflow_and_docker.md`), and the grid shows one dbt box.

**Revisit when.** Builds get slow, per-model retries or lineage are needed (Cosmos, v1.x), an Airflow upgrade changes the constraints, or dbt v1 support ends.

## Sources (checked 2026-11-01)

Constraints https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.13.txt; requirements https://pypi.org/project/dbt-bigquery/1.12.1/, https://pypi.org/project/dbt-core/1.12.6/ and https://pypi.org/project/dbt-core-experimental-parser/2.0.8/; BashOperator https://github.com/apache/airflow/blob/providers-standard/1.19.0/providers/standard/src/airflow/providers/standard/operators/bash.py; dbt from Airflow https://www.astronomer.io/docs/learn/airflow-dbt; Cosmos https://astronomer.github.io/astronomer-cosmos/policy/compatibility-policy.html; dbt docs https://docs.getdbt.com/reference/global-configs/resource-type, https://docs.getdbt.com/docs/build/unit-tests, https://docs.getdbt.com/blog/comparing-dbt-and-dbt-oss and https://docs.getdbt.com/docs/dbt-versions/core.
