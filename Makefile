# Host values. Read .env first, then set host-only values that never go into .env.
-include .env
export GCP_PROJECT RECON_SEED RECON_WORLD_START
export RAW_DATASET := raw_dev
export RECON_LANDING_DIR := $(CURDIR)/landing
export DBT_PROFILES_DIR := $(CURDIR)/dbt
export DBT_KEYFILE := $(CURDIR)/keys/sa.json
export GOOGLE_APPLICATION_CREDENTIALS := $(CURDIR)/keys/sa.json
export PYTHONPATH := src
RAW_DS ?= raw
MARTS_DS ?= analytics
AIRFLOW := docker compose exec -T airflow-scheduler airflow

.PHONY: doctor setup lint check probe

doctor:
	which -a dbt
	@v="$$(uv run dbt --version)"; echo "$$v"; \
	echo "$$v" | grep -q -e '- installed: 1.12.6' && echo "$$v" | grep -q -e '- bigquery: 1.12.1' \
	  || { echo "doctor: need dbt-core 1.12.6 and dbt-bigquery 1.12.1 from the project venv" >&2; exit 1; }

setup:
	uv sync
	mkdir -p keys landing runs logs config plugins
	test -f .env || cp .env.example .env

lint:
	uv run ruff check .

check: lint
	@test -z "$$(git ls-files keys .env)" || { echo "check: keys/ or .env is tracked by git" >&2; exit 1; }

probe:
	uv run python scripts/g0_probe.py $(ARGS)
