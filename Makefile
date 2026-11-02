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

.PHONY: doctor setup lint test check probe bq-setup day days up down smoke unpause pause backfill-dry backfill reprocess clear-day snapshot compare results storage fx-report dbt-build dbt-unit

doctor:
	which -a dbt
	@v="$$(uv run dbt --version)"; echo "$$v"; \
	echo "$$v" | grep -q -e '- installed: 1.12.6' && echo "$$v" | grep -q -e '- bigquery: 1.12.1' \
	  || { echo "doctor: need dbt-core 1.12.6 and dbt-bigquery 1.12.1 from the project venv" >&2; exit 1; }
	$(AIRFLOW) pools get dbt_serial

setup:
	uv sync
	mkdir -p keys landing runs logs config plugins
	test -f .env || cp .env.example .env
	cd dbt && uv run dbt deps

lint:
	uv run ruff check .

test:
	uv run pytest

check: lint test
	@test -z "$$(git ls-files keys .env)" || { echo "check: keys/ or .env is tracked by git" >&2; exit 1; }

probe:
	uv run python scripts/g0_probe.py $(ARGS)

bq-setup:
	uv run python -m recon.cli bq-setup

day:
	@test -n "$(DATE)" || { echo "day: set DATE=YYYY-MM-DD" >&2; exit 1; }
	uv run python -m recon.cli day --date $(DATE)

days:
	@test -n "$(FROM)" -a -n "$(TO)" || { echo "days: set FROM=YYYY-MM-DD TO=YYYY-MM-DD" >&2; exit 1; }
	uv run python -m recon.cli days --from $(FROM) --to $(TO)

up:
	docker compose up -d

down:
	docker compose down

smoke:
	$(AIRFLOW) dags unpause smoke_bigquery
	$(AIRFLOW) dags trigger smoke_bigquery

dbt-build:
	cd dbt && uv run dbt build --target dev

dbt-unit:
	cd dbt && uv run dbt test --select "test_type:unit" --target dev

unpause:
	$(AIRFLOW) dags unpause recon_daily

pause:
	$(AIRFLOW) dags pause recon_daily

backfill-dry:
	@test -n "$(FROM)" -a -n "$(TO)" || { echo "backfill-dry: set FROM=YYYY-MM-DD TO=YYYY-MM-DD" >&2; exit 1; }
	$(AIRFLOW) backfill create --dag-id recon_daily --from-date $(FROM) --to-date $(TO) --run-backwards --max-active-runs 1 --dry-run

backfill:
	@test -n "$(FROM)" -a -n "$(TO)" || { echo "backfill: set FROM=YYYY-MM-DD TO=YYYY-MM-DD" >&2; exit 1; }
	$(AIRFLOW) backfill create --dag-id recon_daily --from-date $(FROM) --to-date $(TO) --run-backwards --max-active-runs 1

reprocess:
	@test -n "$(FROM)" -a -n "$(TO)" || { echo "reprocess: set FROM=YYYY-MM-DD TO=YYYY-MM-DD" >&2; exit 1; }
	$(AIRFLOW) backfill create --dag-id recon_daily --from-date $(FROM) --to-date $(TO) --reprocess-behavior completed --max-active-runs 1

clear-day:
	@test -n "$(DAY)" || { echo "clear-day: set DAY=YYYY-MM-DD" >&2; exit 1; }
	$(AIRFLOW) tasks clear recon_daily -s $(DAY) -e $(DAY) -y

snapshot:
	@test -n "$(OUT)" -a -n "$(FROM)" -a -n "$(TO)" || { echo "snapshot: set OUT= FROM= TO=" >&2; exit 1; }
	uv run python scripts/prove_idempotency.py snapshot --out $(OUT) --from $(FROM) --to $(TO) --raw-dataset $(RAW_DS) --marts-dataset $(MARTS_DS)

compare:
	@test -n "$(BEFORE)" -a -n "$(AFTER)" || { echo "compare: set BEFORE= AFTER=" >&2; exit 1; }
	uv run python scripts/prove_idempotency.py compare --before $(BEFORE) --after $(AFTER) --out $(dir $(AFTER))compare.json

results:
	uv run python scripts/results.py --marts-dataset $(MARTS_DS) $(if $(RUN_RESULTS),--run-results $(RUN_RESULTS))

storage:
	uv run python scripts/storage.py $(if $(OUT),--out $(OUT))

fx-report:
	uv run python scripts/fx_report.py --marts-dataset $(MARTS_DS)
