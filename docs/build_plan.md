Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# Build plan: Two Ledgers (`ledger-vs-statement`)

This is the order of work for the whole project. It goes from an empty folder to the call-ready checkpoint on Monday 2 Nov at 15:00, then through the upgrades after the call. Every step says what to learn, what to do, who writes it, how you know it is done, and what usually goes wrong.

This plan does not repeat the designs. It points to them by file and by heading, table or model name:

| File | What it holds |
|---|---|
| `docs/design.md` | Goals, non-goals, sources, the architecture diagram, the three dates, the window, the cost ceiling, top risks |
| `docs/specs/data_and_generator.md` | The simulated business, the seeds, the `world.toml` keys, the RNG rules, the "Defect catalog", the ground truth and its scoring, the three raw schema JSON files, the landing layout, the Frankfurter and NBK RSS formats |
| `docs/specs/dbt_project.md` | Profile and project YAML, seeds, sources, every model, every test and unit-test fixture, the contract, vars, the macro, the mutation check and the `docs/testing.md` template |
| `docs/specs/airflow_and_docker.md` | The Dockerfile, the compose change list, env vars, the connection, both DAGs, the manual-run semantics table, the "Operations runbook", the idempotency proof, failure modes |
| `docs/specs/bigquery_sandbox_and_costs.md` | Console setup, the service account and key, datasets, raw tables, the load protocol, the G0 probe table, expiry facts, storage and bytes guards, Plan B |
| `docs/learning/concepts.md` | Concepts and a glossary. Each step names one or two of its headings |
| `docs/adr/` | Decisions. ADR-0001 to 0003 are accepted in M10, the others after the call |
| `docs/failure_log.md` | Real bugs, written when they happen |
| `docs/roadmap.md` | Work after the 25 hours |

Concept links name a heading in `docs/learning/concepts.md` exactly, for example "Idempotency". Spec links name the spec's heading in quotes, for example "Defect catalog".

## Contents

- How to use this plan
- Rules: who writes what
- Timeline
- Conventions for every step
- The floor: M0 to M10, then BUF and FREEZE
- Gates and kill switches
- Cut order and the slip rule
- G0 fallbacks
- G1 host-run fallback
- Plan B: the GCP Free Trial
- Call-ready checklist (Monday 15:00)
- After the call: R0 (optional), then the upgrades M11 to M17

---

## How to use this plan

> **Build mode (owner decision, 2026-11-02).** An AI agent builds this plan end to end, as `AGENTS.md`, heading "Build mode", describes. Where a step says "You write", "you run", "your words" or names the owner, the agent does it, except the owner-only actions listed there. This overrides "Rules: who writes what", the tutor workflow and items 2, 3, 6 and 13 of "Rules for agents that follow this plan". The clock, the time boxes and the slip rule do not apply. The agent records every step in `docs/build_journal.md` and writes `docs/walkthrough.md` at the end.

Before each milestone, read the cards listed for it in `docs/learning/concepts.md`, heading "Learn before each milestone". Card reading is not in the clock. For Sunday, read the M0 to M2 cards, `docs/design.md` and the "Defect catalog" before you start; read the M3 to M6 cards in the breaks.

### Starting a session

- The planning pack is the private folder `~/Developer/ledger-vs-statement-plan/`. Until step S0.3 copies the documents into the repo, read the plan there: this file, `AGENTS.md` and the spec the step names.
- Do S0.1 sub-steps 1 to 3 yourself in a terminal (they are short), then start the agent in the new repo folder `~/Developer/ledger-vs-statement`, never in the planning pack. Give it plan files by full path. The pack also holds private files: an agent opens only the files listed in S0.3 sub-step 5 and the files you name.
- From S0.3 on, read the repo copies. If a repo copy and the pack differ, the repo copy wins.

A first prompt you can paste before S0.3:

> Start the build. Read ~/Developer/ledger-vs-statement-plan/AGENTS.md fully and follow it, in particular "Build mode". Then read ~/Developer/ledger-vs-statement-plan/docs/build_plan.md and build from step S0.1 sub-step 4 to the end of M10. Open no other file in that folder unless the plan or I name it. Stop only for owner-only actions and "Stop and ask" cases.

### With a tutor agent

1. Open the step. Read **Goal** and **Why it matters**.
2. Ask the tutor to explain the named concept from `docs/learning/concepts.md` and the **Learn first** links. Ask "why" until you could explain it to someone else.
3. Do the **You write** part yourself, or ask the agent to write it. If you write it yourself, try for 20-30 minutes before asking for help.
4. When you are stuck on your own code, ask for a hint, a question, a doc link or a review. If you would rather have the agent write it, say so.
5. When the agent writes code, it first says exactly what it will write and why, and afterwards walks you through every line. Explain the file back in 2 minutes.
6. Run the **Done when** commands. Compare the output with the expected output.
7. Before you close a milestone, ask the tutor to examine you with its **Explain check**. Answer aloud, without notes.
8. Commit with the suggested message.

A prompt you can paste:

> I am on step S3.2 in docs/build_plan.md. Explain "Minor units and integer fee arithmetic" from docs/learning/concepts.md in plain English, then ask me three questions. Do not write project code.

### Alone

Use the same order. Use the official links under **Learn first**. When something fails, read the whole error and the docs before you search or ask anyone (debug yourself first).

### Rules for agents that follow this plan

1. Work only on the step you were asked about. Never start the next step on your own.
2. The agent may write any code the person asks for, including core logic, as long as it first explains exactly what it will write and why, and afterwards walks the person through every line. **You write** marks core logic: by default explain, ask questions and review the person's code, and write it only when asked.
3. Deliver at most 60 lines at a time, each part explained before and walked through after.
4. Never run bare `dbt`. On the host use `make` or `uv run dbt`. In the containers use `/opt/airflow/dbt_venv/bin/dbt`.
5. Never open, print, copy, move or paste `keys/sa.json` or `.env`.
6. Who may run each command is set in `AGENTS.md`, heading "Commands": Agent, Ask or Owner. Never run an Owner command, even when a step lists it: show the exact command and let the person run it. Owner commands change `recon_daily` (its runs, tasks or pause state), write data into `raw` or `analytics`, or write `docs/evidence/` or `landing/fx/`. The person runs them in his own terminal, even when he asks you to.
7. Never pause `recon_daily` while a backfill or the rerun proof is running.
8. Never edit `dags/`, `src/` or `dbt/` while an Airflow run is active. These folders are mounted into the containers, so a running task would read half-edited code. Check first: `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state running` and the same with `--state queued` must both show no runs. A backfill creates all its runs as queued at once, so a running-only check can miss it between two runs.
9. Never change a pinned version. Never use anything on the sandbox never-list in `AGENTS.md`.
10. Never touch `docs/evidence/`, `landing/fx/` or `uv.lock` unless the step says so.
11. Never write a number into the README or the docs as a result unless it comes from a file in `docs/evidence/`. Until then use a placeholder such as `[N]`.
12. Never write a word from the private banned-word list, and do not ask what is on it.
13. From S1.3 on, run `make check` before proposing a commit. The person makes the commit.
14. If a gate fails, or a **Done when** check does not match, stop and report what you saw. Do not invent a new design.

---

## Rules: who writes what

The agent may write any code you asks for, including core logic, as long as it first explains exactly what it will write and why, and afterwards walks you through every line. You must be able to explain every line you commit, whoever wrote it. In each step, **You write** marks the core logic (write it yourself or ask the agent) and **Agent may scaffold** marks boilerplate.

| Core logic: you write it, or ask the agent to | Boilerplate: the agent may draft it when you ask |
|---|---|
| The generator's world and defect logic, the loader and FX logic, every SQL model and test, both DAGs, the fingerprint SQL and the comparison, the queries in `results.py` and `fx_report.py`, the scoring rules (U1), every README sentence, every ADR and every failure-log entry | `.gitignore`, `.dockerignore`, `Dockerfile`, `docker/requirements-dbt.txt`, the compose edits, the Makefile, `.env.example`, `dbt/profiles.yml` and the first `dbt/dbt_project.yml`, YAML column lists, the schema JSON files, `src/recon/bq.py`, the loading code in `src/recon/config.py`, argparse and file IO wrappers, `LoadJobConfig`, urllib boilerplate, `scripts/g0_probe.py`, the LICENSE text, the CI YAML (U2) |

- **At most 60 lines at a time.** Agent-written code arrives in parts of at most 60 lines, each explained before and walked through after. Exception: `scripts/g0_probe.py`, delivered in parts and kept as specified. Then you add a comment to each block in your own words and explain the file back in 2 minutes.
- **Mark AI-written work.** A commit that contains agent-written code ends with the line `written with AI` (see "Commit messages").
- **Try first.** For logic you choose to write yourself, spend 20-30 minutes on your own before asking. For plumbing blockers (Dockerfile, compose, IAM, auth), spend about 15 minutes, then ask, because the clock matters more there.
- **The line budget for v1.0.** About 900-1,000 lines of logic you must explain: generator about 220, config about 60, loader and FX about 130, DAGs about 120, SQL about 350, scripts about 150. On top of that, about 400 lines of YAML and config. If a file grows far past its share, stop and simplify.
- **The AI rules from your master plan apply throughout:** try first, ask "why" and not "do it", debug yourself first, use AI as an examiner, and do not trust the feeling of speed. See `docs/learning/concepts.md`, "Rules for learning with AI".

---

## Timeline

These hours overlap other interview preparation in your week plan for Sunday and Monday, some of it marked never cut. You chose to spend them here. This plan does not schedule that preparation.

- **Budget:** about 25 focused hours, 25.5 as planned. The floor is 16.75 hours: 14.75 hours of steps (M0 to M10), a protected 1.5-hour buffer and the 0.5-hour FREEZE. The upgrades after the call (M11 to M17) are 8.75 hours.
- **T0:** Sunday 1 Nov, 10:00 Astana. If you start later, apply the slip rule (see "Cut order and the slip rule").
- **Call-ready checkpoint:** Monday 2 Nov, 15:00 Astana. Every item on the "Call-ready checklist (Monday 15:00)" must be true. Monday 15:00-18:00 is outside the 25 hours and outside this repo.
- **After the call:** R0 (optional reading, outside the 25 hours), then M11 to M17 in a fixed order. Each upgrade ends with a tag, from `v1.1` to `v1.7`.

**Time zones.** Astana is UTC+5 all year. Every date in Airflow and BigQuery in this project is a UTC date. 05:00 in Astana is 00:00 UTC: at that moment the scheduled run for the previous UTC day starts.

### Clock, Sunday 1 Nov (Astana time; UTC is 5 hours earlier)

| Astana | Block | Steps start at |
|---|---|---|
| 10:00-10:30 | M0 Design-first repo | S0.1 10:00, S0.2 10:06, S0.3 10:12 |
| 10:30-12:00 | M1 G0 sandbox probes. **Gate G0 at 12:00, hard stop 13:00** | S1.1 10:30, S1.2 10:42, S1.3 10:54, S1.4 11:12, S1.5 11:42 |
| 12:00-12:45 | Lunch (after G0 if G0 runs late) | |
| 12:45-14:15 | M2 Walking skeleton. **Gate G-skel at 14:15, hard stop 16:00** | S2.1 12:45, S2.2 12:57, S2.3 13:15, S2.4 13:39, S2.5 13:57 |
| 14:15-16:30 | M3 Generator | S3.1 14:15, S3.2 14:30, S3.3 15:15, S3.4 15:45, S3.5 16:15 |
| 16:30-16:45 | Break | |
| 16:45-17:30 | M4 Loader and FX | S4.1 16:45, S4.2 17:03, S4.3 17:15 |
| 17:30-18:15 | Dinner | |
| 18:15-21:30 | M5 dbt core | S5.1 18:15, S5.2 18:39, S5.3 19:15, S5.4 19:45, S5.5 20:06, S5.6 20:54 |
| 21:30-22:15 | M6 DAG end to end. **Gate G1 at 22:15, hard stop 23:00** | S6.1 21:30, S6.2 21:51, S6.3 22:03 |
| Night | The backfill runs. At 05:00 Astana (00:00 UTC) the scheduler starts the run for 2026-11-01 | Sleep |

Sunday focused hours: 10.5.

### Clock, Monday 2 Nov (Astana time)

| Astana | Block | Steps start at |
|---|---|---|
| 08:00-09:15 | M7 dbt complete and the mutation check | S7.1 08:00, S7.2 08:09, S7.3 08:27, S7.4 08:36, S7.5 08:51, S7.6 09:09 |
| 09:15-10:00 | M8 Rerun proof (the reprocess runs in the background) | S8.1 09:15, S8.2 09:33 (write S9.1 while the reprocess runs) |
| 10:00-10:45 | M9 Results and the real-data number | S9.1 10:00, S9.2 10:15 |
| 10:45-11:00 | Break | |
| 11:00-12:30 | M10 Publish. **Gate G2 at 12:30** | S10.1 11:00, S10.2 11:36, S10.3 11:54, S10.4 12:09 |
| 12:30-13:00 | Lunch | |
| 13:00-14:30 | BUF Protected buffer | Debugging first, README polish second |
| 14:30-15:00 | FREEZE Read the first screen as a stranger. **Code freeze 15:00** | |

Monday focused hours: 6.25, including the buffer and FREEZE.

---

## Conventions for every step

### Where commands run

- All commands run from the repo root, `~/Developer/ledger-vs-statement`, unless the step says otherwise.
- Airflow commands run inside the scheduler container: `docker compose exec airflow-scheduler airflow <command>`. The `make` targets wrap the common ones.
- Ad-hoc BigQuery checks run in the BigQuery console query editor, with your sandbox project selected. The console resolves `raw.payment_events` to your project. Each check query is billed at least 10 MB from the free 1 TiB a month, which is nothing at this size.
- `$TMPDIR` is your macOS temporary folder. Scratch files go there, never into the repo.

### The dev shell

For an ad-hoc command outside `make` (for example one dbt command), open a terminal at the repo root and run these three lines once. They give the shell the same environment the Makefile gives its commands:

```sh
set -a; . ./.env; set +a
export RAW_DATASET=raw_dev RECON_LANDING_DIR="$PWD/landing" PYTHONPATH=src
export DBT_PROFILES_DIR="$PWD/dbt" DBT_KEYFILE="$PWD/keys/sa.json" GOOGLE_APPLICATION_CREDENTIALS="$PWD/keys/sa.json"
```

dbt commands then run as `(cd dbt && uv run dbt <command> --target dev)`. An agent may use the dev shell, but never prints the environment in it: no `env`, `printenv`, `set` or `set -x`.

### Make targets: what each runs, and the step that adds it

The target names are fixed. The Makefile grows step by step; add a target only in its step.

| Target | Runs | Added in |
|---|---|---|
| `doctor` | `which -a dbt`; fails unless `uv run dbt --version` shows `installed: 1.12.6` and `bigquery: 1.12.1`. From S2.5 it also runs `airflow pools get dbt_serial` in the scheduler, so it then needs the stack up | S1.3, S2.5 |
| `setup` | `uv sync`; creates `keys landing runs logs config plugins`; copies `.env.example` to `.env` if `.env` is missing. From S5.1 it also runs `cd dbt && uv run dbt deps` | S1.3, S5.1 |
| `lint` | `uv run ruff check .` | S1.3 |
| `check` | `lint`, then fails if `git ls-files keys .env` prints anything. From S3.4 it also runs `test` | S1.3, S3.4 |
| `probe` | `uv run python scripts/g0_probe.py $(ARGS)` (for example `ARGS="--only P3,P4"`) | S1.4 |
| `bq-setup` | `uv run python -m recon.cli bq-setup`: makes sure `raw` and `raw_dev` and their 3 tables exist | S2.3 |
| `up`, `down` | `docker compose up -d`, `docker compose down` | S2.5 |
| `smoke` | unpauses, then triggers `smoke_bigquery` in the scheduler | S2.5 |
| `day DATE=` | M3: `uv run python -m recon.cli generate --date $(DATE)`. From S4.3: `recon.cli day --date $(DATE)`, which generates, fetches FX and loads the 3 tables into `raw_dev` | S3.5, S4.3 |
| `days FROM= TO=` | `recon.cli days --from $(FROM) --to $(TO)`: every date in the range, oldest first (the loop is in Python, not in shell) | S4.3 |
| `test` | `uv run pytest` | S3.4 |
| `dbt-build` | `cd dbt && uv run dbt build --target dev` | S5.1 |
| `dbt-unit` | `cd dbt && uv run dbt test --select "test_type:unit" --target dev` | S5.3 |
| `unpause`, `pause` | `airflow dags unpause recon_daily`, `airflow dags pause recon_daily` | S6.2 |
| `backfill-dry FROM= TO=`, `backfill FROM= TO=` | `airflow backfill create --dag-id recon_daily --from-date $(FROM) --to-date $(TO) --run-backwards --max-active-runs 1`, with `--dry-run` added for `backfill-dry` | S6.3 |
| `reprocess FROM= TO=` | `airflow backfill create --dag-id recon_daily --from-date $(FROM) --to-date $(TO) --reprocess-behavior completed --max-active-runs 1` | S8.1 |
| `clear-day DAY=` | `airflow tasks clear recon_daily -s $(DAY) -e $(DAY) -y` | S8.1 |
| `snapshot OUT= FROM= TO=` | `uv run python scripts/prove_idempotency.py snapshot --out $(OUT) --from $(FROM) --to $(TO) --raw-dataset $(RAW_DS) --marts-dataset $(MARTS_DS)` | S8.1 |
| `compare BEFORE= AFTER=` | `uv run python scripts/prove_idempotency.py compare --before $(BEFORE) --after $(AFTER) --out $(dir $(AFTER))compare.json` | S8.1 |
| `results` | `uv run python scripts/results.py --marts-dataset $(MARTS_DS) $(if $(RUN_RESULTS),--run-results $(RUN_RESULTS))` | S9.1 |
| `storage` | `uv run python scripts/storage.py $(if $(OUT),--out $(OUT))` | S9.1 |
| `fx-report` | `uv run python scripts/fx_report.py --marts-dataset $(MARTS_DS)` | S9.2 |
| `eval` | `uv run python scripts/eval.py` | S11.4 |
| `no-dml` | the grep of compiled SQL and dbt logs | S13.5 |

Each target that takes `FROM`, `TO`, `DAY` or `DATE` stops with an error when the value is empty, before it calls anything. The Airflow targets run inside the scheduler with `docker compose exec -T` (the `-T` lets them run without a terminal, for example from an agent). `RAW_DS` and `MARTS_DS` default to `raw` and `analytics`, the datasets the DAG writes. Only the G1 host-run fallback and the U3 checks override them. Two more values are optional. `RUN_RESULTS` is empty by default, so `results.py` reads the most recently written `runs/dbt/*/target/run_results.json` (the DAG build that made the current marts); only the G1 host-run fallback sets it, to `dbt/target/run_results.json`. Without `OUT`, `storage.py` writes `docs/evidence/<UTC date>/storage.json`.

The Makefile header is the part that is easy to get wrong:

```make
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
```

Recipe lines in a Makefile start with a tab, never with spaces.

### Commit messages

The format is the one in `AGENTS.md`, heading "Commit style":

- Subject: `<type>(<area>): <what changed, in the imperative> (<step id>)`, at most 72 characters. Types: `feat`, `fix` (its body names the failure-log entry), `test`, `docs`, `build` (Dockerfile, compose, `pyproject.toml`, Makefile), `ci`, `refactor`, `chore`. Areas: `generator`, `load`, `fx`, `cli`, `dbt`, `dag`, `docker`, `scripts`, `tests`, `docs`, `adr`, `ci`, `repo`.
- Body: why, in one to three short lines.
- Last line `written with AI`, only when an agent drafted part of the change and you reviewed it.
- At least one commit per step, never squashed: the order of commits is evidence. Push at the end of every milestone; the pre-push hook runs on every push. Never amend, rebase or force-push a commit that is already pushed.

### Failure log

Write an entry in `docs/failure_log.md` when a real bug happens, not at the end. Each takes about 5 minutes: the date and step, the symptom (the exact error line), the root cause, the fix, how you found it, and the time lost. Use the entry format in that file (heading "Entry format"), and put the entry id (for example `F-003`) in the message of the commit that fixes it.

Planned failures are not bugs. A unit test seen red before its logic exists (UT1 and UT2 in M5, UT3 and UT4 in M11), the U3 negative control and the U6 late batch each get a row in the "Planned red runs (not bugs)" table of `docs/failure_log.md`, not an entry. If a planned red run fails for a reason you did not plan, that is a bug: write an entry. Nothing is written for show.

### Evidence and placeholders

- Results live only in `docs/evidence/<date>/`, written by a `make` target. For the call, that folder is `docs/evidence/2026-11-02/`.
- Until a number is measured, the docs use placeholders such as `[N]`. A README row with no measured value is deleted, never left with a placeholder.
- Before the README goes public, this check must print nothing: `grep -nE '<!--|\[WRITE|\[[A-Za-z]{1,8}\]([^(]|$)' README.md`. It is the check in the first FILL comment of the README skeleton. It finds every FILL comment, every `[WRITE: ...]` marker and every placeholder, such as `[N]`, `[date]`, `[s]` or `[sha]`, while a Markdown link such as `[CI](...)` passes. Run it in S10.1 and again in S10.4.
- The GCP project id lives only in `.env`. Never commit it. Scrub it from saved outputs (write `<project>` instead) and crop it out of screenshots. S1.1 adds it to your private banned-word list, so the pre-push hook blocks it too.

---

## The floor: M0 to M10

Every step has the same fields: **Clock**, **Goal**, **Why it matters**, **Learn first**, **Do**, **You write** and **Agent may scaffold** (core logic and boilerplate, see "Rules: who writes what"), **Files** (the files the step creates or changes), **Done when**, **Traps**, **Commit**, **Failure log**. Each milestone ends with its **Explain check**. Model answers are in `docs/learning/concepts.md`, "Explain checks with model answers".

## M0. Design-first repo

Sunday 10:00-10:30, 0.5 h. **Done when:** the first commits hold only `.gitignore`, then `docs/design.md` and `docs/specs/data_and_generator.md`, and the pre-push hook blocks a test word.

### S0.1 Start clean: Docker, the folder, git, `.gitignore`

- **Clock:** Sun 10:00-10:06 (0.1 h).
- **Goal:** an empty repo whose first commit is the `.gitignore`, made before any key or `.env` exists.
- **Why it matters:** if `keys/` is ignored before the key exists, the key can never be committed by accident. Concept: "Service accounts, roles and keys"; the secrets rules are in `AGENTS.md`.
- **Learn first:** [git check-ignore](https://git-scm.com/docs/git-check-ignore); [Docker Desktop settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/) (Resources).
- **Do:**
  1. Start Docker Desktop. In Settings, Resources, set Memory to at least 6 GB. Check that at least 10 GB of disk is free: `df -h ~`.
  2. Stop your Airflow course stack: `cd ~/Developer/learning/courses/airflow && docker compose down`.
  3. `mkdir ~/Developer/ledger-vs-statement && cd ~/Developer/ledger-vs-statement && git init -b main`
  4. Check the email your commits will carry: `git config user.email`. It becomes public with the repo. To hide it, set the GitHub noreply address shown in GitHub Settings, Emails: `git config user.email "<your noreply address>"` ([GitHub docs](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address)).
  5. Create `.gitignore` with exactly these lines:
     ```
     keys/
     .env
     landing/*
     !landing/fx/
     runs/
     logs/
     config/airflow.cfg
     dbt/target/
     dbt/dbt_packages/
     dbt/logs/
     dbt/.user.yml
     .venv/
     __pycache__/
     .pytest_cache/
     .ruff_cache/
     ```
  6. `git add .gitignore && git commit -m "chore(repo): ignore keys, .env and generated data first (S0.1)"`
- **You write:** the commands. **Agent may scaffold:** `.gitignore` (the lines above).
- **Files:** `.gitignore`.
- **Done when:** `git check-ignore keys/sa.json .env landing/_truth/x` prints all three paths. `git check-ignore landing/fx/provider=nbk/arrival_date=2026-10-20.json` prints nothing (the FX files must stay tracked). `git log --oneline` shows one commit.
- **Traps:** write `landing/*` plus `!landing/fx/`, never `landing/`: git cannot re-include a child of a directory that is itself ignored. Below 4 GB of Docker memory the compose warns and containers die. Running the course stack and this stack together doubles the memory use (names and ports do not clash: the projects and ports differ).
- **Commit:** `chore(repo): ignore keys, .env and generated data first (S0.1)`
- **Failure log:** nothing expected. If Docker Desktop will not start, log it.

### S0.2 The private banned-word list and the pre-push hook

- **Clock:** Sun 10:06-10:12 (0.1 h).
- **Goal:** on your machine, a push that contains a banned word is blocked.
- **Why it matters:** the repo must never name the target company, its products, the payment providers its postings name, or any employer. A local hook catches mistakes before they become public history. Concept: "Words I use and words I never use"; the naming rules are in `AGENTS.md`.
- **Learn first:** [githooks, pre-push](https://git-scm.com/docs/githooks); [git grep](https://git-scm.com/docs/git-grep).
- **Do:**
  1. `mkdir -p ~/.config/lvs && chmod 700 ~/.config/lvs`
  2. Write `~/.config/lvs/banned_words.txt`: one word per line, lower case, copied from your private notes outside this repo. Never type these words into a repo file, a commit message or an agent chat. Then `chmod 600 ~/.config/lvs/banned_words.txt`.
  3. Create `.git/hooks/pre-push` with exactly the text below, then `chmod +x .git/hooks/pre-push`.
  4. Test it with a made-up canary word (the commands after the hook text).
- **The hook text:**
  ```sh
  #!/bin/sh
  # Local pre-push hook for ledger-vs-statement. Lives in .git/hooks/, never committed.
  # Blocks the push when a word from the private banned-word list (one word per line,
  # any case) appears in an outgoing commit's files, file paths or message, in the
  # pushed branch or tag name, or in an annotated tag's message. Only letters and digits
  # count as part of a word, so "_", "-", "." and "/" separate words: a word inside
  # a snake_case name, a file name or a branch name is caught too.
  words_file="${LVS_BANNED_WORDS:-$HOME/.config/lvs/banned_words.txt}"
  patterns=$(mktemp) || exit 1
  words=$(mktemp) || exit 1
  trap 'rm -f "$patterns" "$words"' EXIT
  # Trim spaces at both ends, drop blank lines and comments (an empty pattern would
  # match every line), then wrap each word as (^|[^[:alnum:]])word([^[:alnum:]]|$).
  sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$words_file" 2>/dev/null |
    grep -v -e '^$' -e '^#' > "$words"
  if [ ! -s "$words" ]; then
    echo "pre-push: word list missing or empty ($words_file). Push blocked." >&2
    exit 1
  fi
  # Every line must be a plain word (letters, digits, hyphens), never a pattern.
  if grep -q -v -E '^[[:alnum:]-]+$' "$words"; then
    echo "pre-push: a line in $words_file is not a plain word. Push blocked." >&2
    exit 1
  fi
  sed -e 's/.*/(^|[^[:alnum:]])&([^[:alnum:]]|$)/' "$words" > "$patterns"
  zero=$(git hash-object --stdin </dev/null | tr '[0-9a-f]' '0')
  status=0
  while read -r local_ref local_sha remote_ref remote_sha; do
    [ "$local_sha" = "$zero" ] && continue        # deleting a remote branch: nothing to scan
    if printf '%s\n%s\n' "$local_ref" "$remote_ref" | grep -n -i -E -f "$patterns" >&2; then
      echo "pre-push: banned word in the branch or tag name $remote_ref" >&2; status=1
    fi
    if [ "$remote_sha" = "$zero" ]; then
      range="$local_sha --not --remotes"          # new branch: every commit not yet on the remote
    else
      range="$remote_sha..$local_sha"
    fi
    commits=$(git rev-list $range) || { echo "pre-push: cannot list commits for $local_ref. Push blocked." >&2; exit 1; }
    for c in $commits; do
      if git grep -n -I -i -E -f "$patterns" "$c" >&2; then
        echo "pre-push: banned word in the files of commit $c" >&2; status=1
      fi
      if git ls-tree -r --name-only "$c" | grep -n -i -E -f "$patterns" >&2; then
        echo "pre-push: banned word in a file path of commit $c" >&2; status=1
      fi
      if git log -1 --format=%B "$c" | grep -n -i -E -f "$patterns" >&2; then
        echo "pre-push: banned word in the message of commit $c" >&2; status=1
      fi
    done
    if [ "$(git cat-file -t "$local_sha")" = "tag" ] &&
       git cat-file -p "$local_sha" | grep -n -i -E -f "$patterns" >&2; then
      echo "pre-push: banned word in tag $local_ref" >&2; status=1
    fi
  done
  if [ "$status" -ne 0 ]; then
    echo "pre-push: push blocked. Remove the word, fix the commit (amend or rebase), push again." >&2
  fi
  exit "$status"
  ```
  For every outgoing commit, the hook scans the full file tree, the file paths and the message. It also scans the pushed branch or tag name and the message of an annotated tag. It contains no banned word itself: it reads them from your list.
- **The test** (there is no remote yet, so you feed the hook what git would feed it):
  ```sh
  printf 'zqxwcanary\n' > "$TMPDIR/lvs_test_words.txt"
  git switch -c hook-test
  echo "zqxwcanary" > hook_test.txt && git add hook_test.txt && git commit -m "test: hook canary"
  echo "refs/heads/hook-test $(git rev-parse HEAD) refs/heads/hook-test 0000000000000000000000000000000000000000" | LVS_BANNED_WORDS="$TMPDIR/lvs_test_words.txt" .git/hooks/pre-push origin test; echo "exit=$?"
  git switch main && git branch -D hook-test && rm "$TMPDIR/lvs_test_words.txt"
  echo "refs/heads/main $(git rev-parse main) refs/heads/main 0000000000000000000000000000000000000000" | .git/hooks/pre-push origin test; echo "exit=$?"
  ```
- **You write:** the word list. **Hook text:** copied exactly from this step.
- **Files:** `~/.config/lvs/banned_words.txt` and `.git/hooks/pre-push`, both outside the tracked tree.
- **Done when:** the canary run prints a line ending in `hook_test.txt:1:zqxwcanary`, then `pre-push: banned word in the files of commit ...` and `exit=1`. The run on `main` with your real list prints `exit=0`.
- **Traps:**
  - An empty line in a pattern file matches every line. The hook drops blank lines and comments; keep that part.
  - Only letters and digits count as part of a word. `_`, `-`, `.` and `/` separate words, so a banned word inside a snake_case name, a file name such as `word_notes.md` or a branch name such as `word-wip` is caught, while a longer word that merely contains it is not. Keep the list to plain words (letters, digits and hyphens), one per line, with no "- " bullet. Spaces at either end are trimmed. Any other line (a bullet, two words, a dot, a bracket) blocks every push until you fix it.
  - The hook runs only on push. A banned word can sit in a local commit until you push. Fix it before pushing: `git commit --amend` for the last commit, a rebase in your own terminal for older ones.
  - The hook checks every outgoing commit, so a word added and later removed still blocks the push. That is intended: history becomes public.
  - `.git/hooks/` is not copied by `git clone`. A fresh clone has no hook until you install it again.
  - `LVS_BANNED_WORDS` exists only for this test.
- **Commit:** none. Nothing in the repo changes.
- **Failure log:** whenever the hook blocks a real word later, log it: which word class, where, and how it got there.

### S0.3 Design first: your words, the defect catalog, the private GitHub repo

- **Clock:** Sun 10:12-10:30 (0.3 h).
- **Goal:** the first content commit is the design and the pre-registered defect catalog, dated before any code. The repo exists on GitHub as private.
- **Why it matters:** committing the defect catalog before any matcher SQL is evidence that the tests were not tuned to the answers. The commit order is part of the evidence. Concept: "The seeded self-test, and why it is not accuracy".
- **Learn first:** read `docs/design.md` and the "Defect catalog" in `docs/specs/data_and_generator.md`; [gh repo create](https://cli.github.com/manual/gh_repo_create).
- **Do:**
  1. Copy the design and the defect catalog from the planning pack:
     ```sh
     PACK=~/Developer/ledger-vs-statement-plan
     mkdir -p docs/specs
     cp "$PACK/docs/design.md" docs/design.md
     cp "$PACK/docs/specs/data_and_generator.md" docs/specs/data_and_generator.md
     ```
  2. First pass on `docs/design.md`, at most 8 minutes: fix anything wrong or unclear to you (it stays at most 2 pages). The full own-words rewrite happens in BUF, after the README polish, or after the call.
  3. Read the "Defect catalog". Change anything you disagree with now. After this commit, any change needs its own commit that says why.
  4. `git add docs/design.md docs/specs/data_and_generator.md && git commit -m "docs(repo): add the design and the pre-registered defect catalog (S0.3)"`
  5. Copy the other repo documents by name, and nothing else. Every other file in the planning pack is private and never enters the repo:
     ```sh
     PACK=~/Developer/ledger-vs-statement-plan
     mkdir -p docs/adr docs/learning docs/specs
     cp "$PACK/README.md" "$PACK/AGENTS.md" "$PACK/CLAUDE.md" .
     cp "$PACK/docs/build_plan.md" "$PACK/docs/roadmap.md" "$PACK/docs/failure_log.md" docs/
     cp "$PACK/docs/learning/concepts.md" docs/learning/
     cp "$PACK/docs/specs/dbt_project.md" "$PACK/docs/specs/airflow_and_docker.md" "$PACK/docs/specs/bigquery_sandbox_and_costs.md" docs/specs/
     cp "$PACK/docs/adr/README.md" "$PACK"/docs/adr/00*.md docs/adr/
     ls docs/adr/00*.md | wc -l    # prints 10
     git status --short            # only these files (and LICENSE, once added)
     ```
     Then add `LICENSE`: the MIT text from [choosealicense.com](https://choosealicense.com/licenses/mit/) with `Copyright (c) 2026 Bainazar Seitek`.
  6. Scan what you staged, file contents and file paths, with the same rules the hook uses:
     ```sh
     git add -A
     sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' ~/.config/lvs/banned_words.txt | grep -v -e '^$' -e '^#' |
       sed -e 's/.*/(^|[^[:alnum:]])&([^[:alnum:]]|$)/' > "$TMPDIR/lvs_words.re"
     git grep -n -I -i -E -f "$TMPDIR/lvs_words.re" --cached; echo "exit=$?"
     git ls-files | grep -n -i -E -f "$TMPDIR/lvs_words.re"; echo "exit=$?"
     rm "$TMPDIR/lvs_words.re"
     ```
  7. `git commit -m "docs(repo): add the planning documents (S0.3)" -m "Drafted with AI assistance before the build and reviewed by me." -m "written with AI"`
  8. `gh auth status` (log in with `gh auth login` if needed), then `gh repo create ledger-vs-statement --private --source=. --remote=origin --push`. The hook runs on this first push.
  9. Add one row to the table in `~/Developer/learning/projects/README.md` (Folder `~/Developer/ledger-vs-statement/` (own repo), Plan weeks `1-2 Nov 2026, side project`, What `Two Ledgers: daily revenue vs settlement-statement reconciliation per merchant account on the BigQuery sandbox, with Airflow 3 and dbt; synthetic payments, real NBK FX`, Status `In progress`). That folder is its own git repo: `git -C ~/Developer/learning add projects/README.md && git -C ~/Developer/learning commit -m "projects: add ledger-vs-statement"`.
- **You write:** your version of `docs/design.md`, any change to the defect catalog, the portfolio row. **Agent may scaffold:** the LICENSE text.
- **Files:** `docs/design.md`, `docs/specs/data_and_generator.md`, the planning-pack files in sub-step 5, `LICENSE`; outside the repo `~/Developer/learning/projects/README.md`.
- **Done when:** both scans in sub-step 6 print `exit=1` (no match). `git log --reverse --format='%h %ad %s' --date=iso` lists, oldest first, the `.gitignore` commit, the design commit and the planning commit, and no code. `gh repo view --json visibility -q .visibility` prints `PRIVATE`.
- **Traps:** copy only with the commands in sub-steps 1 and 5, never the whole folder: the planning pack holds private files. If `git status --short` lists any other file, delete it before sub-step 6. Eighteen minutes is tight: do a first pass of the design now and improve the wording in BUF or after the call. Do not make the repo public until G2.
- **Commit:** the two commits in sub-steps 4 and 7.
- **Failure log:** if the scan or the hook finds a word, log where it was and how it got there.

### Explain check M0

Why is the defect catalog committed before any matcher SQL?

---

## M1. G0 sandbox probes

Sunday 10:30-12:00, 1.5 h. **Done when:** the probe table is filled, the write path and the auth method are chosen, and the DML error text is saved. **Gate G0:** decided and recorded by 12:00; hard stop 13:00 (see "Gates and kill switches").

### S1.1 Personal Google account, sandbox project, `probe` dataset

- **Clock:** Sun 10:30-10:42 (0.2 h).
- **Goal:** a BigQuery sandbox project with no billing account, and a dataset `probe` in the US multi-region.
- **Why it matters:** the sandbox costs $0 because nothing can be billed. It also refuses DML, and that rule shapes the whole design. Concepts: "The BigQuery sandbox and its limits", "DDL and DML, and why this project has no DML".
- **Learn first:** [BigQuery sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox); "S1.1 Create the sandbox project (You, about 12 minutes)" under "Setup step by step" in `docs/specs/bigquery_sandbox_and_costs.md`.
- **Do:**
  1. Open https://console.cloud.google.com/bigquery (Google's sandbox entry point) signed in with your personal Gmail, never the university account.
  2. Create a project: name `ledger-vs-statement`, location "No organization". Keep a project id that differs from the repo name, for example the suggested id with a number at the end. If the console proposes exactly `ledger-vs-statement`, click **Edit** and add a suffix: the id is permanent. If BigQuery shows an **Enable** button for its API, click it (it is free) and wait a minute.
  3. Open BigQuery. Check the SANDBOX badge at the top. Check the Billing page: the project has no billing account. If a screen offers a free trial, billing, "Activate" or "Upgrade", close it.
  4. Create the dataset `probe`: location type Multi-region, `US`.
  5. Add the project id as one more line in `~/.config/lvs/banned_words.txt`. From now on the hook also blocks it.
- **You write:** all of it (console clicks).
- **Files:** none in the repo; `~/.config/lvs/banned_words.txt` (one more line).
- **Done when:** the console shows the SANDBOX badge and the dataset `probe` (US). The Billing page shows no billing account linked to the project.
- **Traps:**
  - If the account must pick an organization, it is the wrong account. Stop and use the personal one.
  - A project id equal to the repo name would make the hook block the repo name everywhere. Keep the suffixed id.
  - Never create a second sandbox project to reset quotas. The Google Cloud Terms forbid it.
- **Commit:** none.
- **Failure log:** if an organization is forced or billing shows up, log it and stop (G0 rule).

### S1.2 Service account `lvs-pipeline` and its key

- **Clock:** Sun 10:42-10:54 (0.2 h).
- **Goal:** a key file that lets the host and Airflow act as `lvs-pipeline`, with two roles.
- **Why it matters:** least privilege. The pipeline can run jobs and edit data, and nothing else. Concept: "Service accounts, roles and keys"; the secrets rules are in `AGENTS.md`.
- **Learn first:** [create service accounts](https://docs.cloud.google.com/iam/docs/service-accounts-create); [create and delete keys](https://docs.cloud.google.com/iam/docs/keys-create-delete); [BigQuery roles](https://docs.cloud.google.com/bigquery/docs/access-control); "S1.2 Service account and key (You, about 12 minutes)" and "Key handling rules" in `docs/specs/bigquery_sandbox_and_costs.md` (follow its click path step by step).
- **Do:**
  1. IAM and Admin, Service Accounts, Create: `lvs-pipeline`.
  2. Grant two roles at project level: BigQuery Job User and BigQuery Data Editor.
  3. Click the service account's email, open the **Keys** tab, **Add key**, **Create new key**, **JSON**, **Create**. The browser saves it to `~/Downloads`.
  4. `mkdir -p keys && mv ~/Downloads/<the downloaded file>.json keys/sa.json && chmod 600 keys/sa.json`
- **You write:** all of it.
- **Files:** `keys/sa.json` (ignored, never committed).
- **Done when:** `git check-ignore keys/sa.json` prints `keys/sa.json`. `git status --short` shows nothing under `keys/`. `ls ~/Downloads/*.json` no longer lists the key (if no JSON file is left, zsh prints `no matches found`: that is the pass).
- **Traps:** never open the key in an app that syncs files, and never show its content to an agent. If key creation is blocked by an organization policy, switch to the ADC fallback (see "G0 fallbacks").
- **Commit:** none.
- **Failure log:** a blocked key is a real event: log it with the exact message.

### S1.3 Host venv, dbt profile and project, `dbt debug`

- **Clock:** Sun 10:54-11:12 (0.3 h).
- **Goal:** dbt-core 1.12.6 with dbt-bigquery 1.12.1 runs from the project venv on your Mac and connects to the sandbox.
- **Why it matters:** two dbt programs exist on your Mac. `~/.local/bin/dbt` is dbt v2 (2.0.9), a different engine. Calling only the project's pinned dbt prevents silent version drift. Concept: "Profiles and targets"; the tool rules are in `AGENTS.md`.
- **Learn first:** [dbt BigQuery setup](https://docs.getdbt.com/docs/local/connect-data-platform/bigquery-setup); [dbt debug](https://docs.getdbt.com/reference/commands/debug); [uv init](https://docs.astral.sh/uv/concepts/projects/init/); [dbt 1.12 upgrade notes](https://docs.getdbt.com/docs/dbt-versions/dbt-upgrade/upgrading-to-v1.12) (`.env` loading).
- **Do:**
  1. `uv init --bare --python 3.13`. `--bare` writes only `pyproject.toml`: no package build system, no README, no `main.py`, no new git repo. The design keeps this repo "not a package".
  2. `uv python pin 3.13` (writes `.python-version`).
  3. `uv add dbt-core==1.12.6 dbt-bigquery==1.12.1 dbt-core-experimental-parser==2.0.8`
  4. `uv add --dev pytest "ruff>=0.13"`
  5. Add to `pyproject.toml`: a `[tool.pytest.ini_options]` table with `pythonpath = ["src"]`.
  6. Create `.env.example` with the four `.env` lines from "Environment variables" in `docs/specs/airflow_and_docker.md` (`AIRFLOW_UID`, `GCP_PROJECT`, `RECON_SEED=20261101`, `RECON_WORLD_START=2026-10-04`). Then `cp -n .env.example .env` (never overwrites an existing `.env`) and fill in your project id and the output of `id -u`.
  7. Create `dbt/profiles.yml` (profile `ledger_vs_statement`, targets `dev` and `airflow`, every setting from the profile in `docs/specs/dbt_project.md`) and a minimal `dbt/dbt_project.yml`: name and profile `ledger_vs_statement`, plus the `flags:` block with `send_anonymous_usage_stats: false`, as in the project file in that spec. S5.1 completes the project file.
  8. Create the Makefile: the header from "Conventions for every step" and the targets `doctor`, `setup`, `lint`, `check`.
  9. `make doctor`
  10. Open the dev shell, then `(cd dbt && uv run dbt debug --target dev)`.
- **You write:** the `.env` values; you read every scaffolded line. **Agent may scaffold:** `dbt/profiles.yml`, the minimal `dbt/dbt_project.yml`, the Makefile header and its four targets, `.env.example`.
- **Files:** `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `.env` (ignored), `dbt/profiles.yml`, `dbt/dbt_project.yml`, `Makefile`.
- **Done when:** `make doctor` prints the `which -a dbt` list, then `installed: 1.12.6` and `bigquery: 1.12.1`, and exits 0. `dbt debug` ends with `All checks passed!`. `git check-ignore .env` prints `.env`. `make check` exits 0.
- **Traps:**
  - `which -a dbt` lists `~/.local/bin/dbt`. Never run it here.
  - In current uv, `uv init --app` without `--bare` creates a packaged project (a `src/` package and a build system). This repo is not a package.
  - dbt 1.12 loads `.env` from its working directory, and shell values win. That is why `DBT_KEYFILE` never goes into `.env`.
  - With usage stats on, the first dbt command writes a user-id file, `.user.yml`, into the profiles folder, which here is `dbt/`. The `flags:` block stops that from the first `dbt debug`, and `.gitignore` ignores `dbt/.user.yml` in case it ever appears.
  - The first `uv add` downloads the parser's native wheel from github.com, so it needs the network.
  - Both targets set `maximum_bytes_billed: 1000000000`. Do not drop it.
- **Commit:** `build(repo): add the uv project with pinned dbt and the profile (S1.3)`, ending with the line `written with AI`.
- **Failure log:** any `dbt debug` error with its fix.

### S1.4 Run the G0 probes

- **Clock:** Sun 11:12-11:42 (0.5 h).
- **Goal:** PASS or FAIL for each probe P1 to P7 and F1 (P8 is optional).
- **Why it matters:** the write path, the DML refusal and the expiry rules decide the design. Test them with a few KB before writing any pipeline code. Concepts: "DDL and DML, and why this project has no DML", "Partition decorators", "Expiry and the rolling date window".
- **Learn first:** "Probe summary", "Script skeleton" and the probe sections P1 to P8 and F1 under "G0 probes runbook" in `docs/specs/bigquery_sandbox_and_costs.md`; [loading partitioned tables](https://docs.cloud.google.com/bigquery/docs/load-data-partitioned-tables); [managing partitioned tables](https://docs.cloud.google.com/bigquery/docs/managing-partitioned-tables) (expiry).
- **Do:**
  1. An agent scaffolds `scripts/g0_probe.py` from "Script skeleton" and the probe sections of that spec: one function per probe, each prints `<id> PASS <detail>` or `<id> FAIL <detail>`, and every query sets `maximum_bytes_billed=1_000_000_000`. The agent delivers it in parts of at most 60 lines (the skeleton, then the probes in two or three parts), as `AGENTS.md` says. It is a throwaway probe script, so the simplify-below-60 rule does not apply. Read each probe next to its spec section.
  2. Read every line. Ask "why" about anything unclear. Explain the script back in 2 minutes.
  3. Add `make probe`.
  4. `make probe 2>&1 | tee "$TMPDIR/g0_probe.txt"` (the `tee` copy is for your eyes only). The script also writes `docs/evidence/<UTC date>/g0_probe.json` with every result and every error text in full, the project id and the service-account email already replaced by `<project>` and `<sa>`.
  5. `make probe ARGS="--only P3,P4"` reruns a subset.
  6. Run P8 only if you are ahead of the clock. It is off the critical path.
- **You write:** the interpretation of each result. You run the script. **Agent may scaffold:** `scripts/g0_probe.py`.
- **Files:** `scripts/g0_probe.py`, `Makefile`, `docs/evidence/2026-11-01/g0_probe.json` (written by the script).
- **Done when:** one line per probe: PASS, FAIL or SKIP (P4 to P6 print SKIP if P3 could not create its table), and `docs/evidence/2026-11-01/g0_probe.json` exists. P2 PASS means the INSERT was refused with "DML queries are not allowed in the free tier".
- **Traps:**
  - If P2 shows that the INSERT succeeded, billing is on. Stop and check the Billing page. Never build on a billed project.
  - "Yesterday" in the probes is the UTC date.
  - BigQuery error messages contain the request URL, and the URL contains your project id.
  - P3 must show 1 row for yesterday (the second file replaced the first) and the other day untouched.
- **Commit:** `test(scripts): add the G0 sandbox capability probes (S1.4)`, ending with the line `written with AI`.
- **Failure log:** every FAIL is a finding. Log it with the exact message.

### S1.5 Choose the write path and the auth method; record G0

- **Clock:** Sun 11:42-12:00 (0.3 h).
- **Goal:** a written decision by 12:00: decorator loads or shard tables, and key or ADC.
- **Why it matters:** a decision written down at noon is not re-decided at midnight. Concept: "DDL and DML, and why this project has no DML".
- **Learn first:** `docs/adr/0001-warehouse-bigquery-sandbox.md` and `docs/adr/0002-raw-write-path-and-time-model.md` as drafted.
- **Do:**
  1. Read `docs/evidence/2026-11-01/g0_probe.json`. It must hold no project id, no email and nothing from the key. Commit it.
  2. Fill the blanks under the heading "G0 results" in ADR-0001: a result per probe, the P2 error text word for word, the write path, the authentication and the time of the run. Keep the status Proposed; you accept it in S10.2.
  3. Write the other G0 decisions into ADR-0001's notes: the empty-day rule (P5), the storage source (P7) and the FX fetch (F1). The rules are in "Decision rules at G0" in `docs/specs/bigquery_sandbox_and_costs.md`.
  4. Fill the README section "Platform constraints (G0 probes)" from the results. Keep a placeholder where a value is not measured yet.
  5. If P3 failed, switch to shard tables and note it in ADR-0002. If the key was blocked, switch to ADC (see "G0 fallbacks").
- **You write:** all of it.
- **Files:** `docs/evidence/2026-11-01/g0_probe.json`, `docs/adr/0001-warehouse-bigquery-sandbox.md`, `README.md` ("Platform constraints (G0 probes)"); `docs/adr/0002-raw-write-path-and-time-model.md` only if a fallback was chosen.
- **Done when:** "G0 results" in ADR-0001 has a result for every probe, the P2 text, the write path and the authentication, and `git show --stat HEAD` lists the committed `g0_probe.json`.
- **Traps:** do not polish the ADR wording now (that is S10.2). Do not continue past G0 if P2 succeeded.
- **Commit:** `docs(adr): record the G0 results and the chosen write path (S1.5)`
- **Failure log:** if you chose a fallback, one entry that says why.

### Explain check M1

Why can't dbt's default incremental strategy run here? What did the DML refusal say? What happens to a row dated 70 days ago?

---

## M2. Walking skeleton

Sunday 12:45-14:15, 1.5 h. **Done when (gate G-skel):** `smoke_bigquery` is green inside Docker. G-skel at 14:15; hard stop 16:00.

### S2.1 Dockerfile and the dbt requirements; start the image build

- **Clock:** Sun 12:45-12:57 (0.2 h).
- **Goal:** the image `ledger-vs-statement-airflow:3.3.2` is building.
- **Why it matters:** the Airflow 3.3.2 constraints pin package versions that dbt-bigquery 1.12.1 and dbt-core 1.12.6 refuse, so dbt gets its own venv inside the image. Concept: "Docker images, containers and virtual environments".
- **Learn first:** [building a custom Airflow image](https://airflow.apache.org/docs/docker-stack/build.html); "The Dockerfile" and "Why dbt has its own virtual environment" in `docs/specs/airflow_and_docker.md`.
- **Do:**
  1. An agent scaffolds `Dockerfile`, `docker/requirements-dbt.txt` (the three pins) and `.dockerignore`, exactly as in the spec. You read each line.
  2. In a second terminal, from the repo root: `docker build -t ledger-vs-statement-airflow:3.3.2 .`. Let it run while you do S2.2. (The compose file arrives in S2.2. This command builds the same image that `docker compose build` would build, with the same name.)
- **You write:** nothing new; you check the scaffold. **Agent may scaffold:** the three files.
- **Files:** `Dockerfile`, `.dockerignore`, `docker/requirements-dbt.txt`.
- **Done when:** near the end of the build, the `dbt --version` line inside the build prints Core 1.12.6 and bigquery 1.12.1, `docker image ls ledger-vs-statement-airflow` lists the tag `3.3.2`, and `docker run --rm --entrypoint /opt/airflow/dbt_venv/bin/dbt ledger-vs-statement-airflow:3.3.2 --version` shows Core 1.12.6 and bigquery 1.12.1.
- **Traps:**
  - Create `.dockerignore` before the first build. It keeps `keys/` and `.env` out of the build context.
  - The build needs github.com, because the parser downloads its arm64 wheel during install. Do not add `--only-binary`.
  - Expect several hundred MB more than the base image.
  - Never install anything into Airflow's own environment. Never copy the key into the image.
  - Do not set `AIRFLOW_IMAGE_NAME` in your shell; compose would use it instead of this image.
- **Commit:** `build(docker): give dbt its own venv in the Airflow image (S2.1)`, ending with the line `written with AI`.
- **Failure log:** a failed build (network, disk space) with its fix.

### S2.2 `docker-compose.yaml` from your course file

- **Clock:** Sun 12:57-13:15 (0.3 h).
- **Goal:** a compose file that runs your image with the project's mounts, environment and pool.
- **Why it matters:** you reuse a stack you already know and change only what this project needs. Concepts: "Connections", "Scheduler, dag-processor, API server, triggerer and executor".
- **Learn first:** [Airflow docker-compose](https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/docker-compose/index.html); [connections from environment variables](https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/connection.html); "docker-compose.yaml: the changes to the course file" in `docs/specs/airflow_and_docker.md`.
- **Do:**
  1. `cp ~/Developer/learning/courses/airflow/docker-compose.yaml .`
  2. An agent applies the changes listed under "docker-compose.yaml: the changes to the course file" in the spec: the image name with `build: .`, the port `127.0.0.1:8083:8080` (localhost only), the environment block in `x-airflow-common`, the volumes, and the `airflow-init` lines (`landing` and `runs` in `mkdir` and `chown`, then the `dbt_serial` pool).
  3. You check each change against the list, one at a time.
  4. `mkdir -p dags logs config plugins landing runs && touch config/.gitkeep plugins/.gitkeep`
  5. `docker compose config --quiet && echo VALID`
- **You write:** the check of each change. **Agent may scaffold:** the compose edits.
- **Files:** `docker-compose.yaml`, `config/.gitkeep`, `plugins/.gitkeep`.
- **Done when:** `VALID` is printed. `grep -n '127.0.0.1:8083:8080' docker-compose.yaml` shows the localhost-only port. `grep -n 'keys:/opt/airflow/keys:ro' docker-compose.yaml` shows the read-only key mount. Grep the file itself, not the `docker compose config` output: that output rewrites each service's ports and volumes in long form (`host_ip: 127.0.0.1`, `published: "8083"`, `read_only: true`). So the port string never appears in it, and the key-mount string appears only in the `x-airflow-common` block, which it repeats word for word. That proves nothing about the services.
- **Traps:**
  - `DBT_KEYFILE` is a literal path in the compose file, never read from `.env`.
  - `AIRFLOW_UID` in `.env` must be your `id -u`, so the container user can read the `chmod 600` key.
  - The environment goes into `x-airflow-common`, so the scheduler, the dag-processor and the triggerer all see it.
  - The pool line goes after `airflow config list` in `airflow-init`; the metadata database exists by then.
  - `docker compose config` prints your project id. Do not paste its output anywhere public.
- **Commit:** `build(docker): add docker-compose from the course file (S2.2)`, ending with the line `written with AI`.
- **Failure log:** any compose error that took more than a few minutes.

### S2.3 The raw schema contract, the BigQuery helper, `ensure_tables`, `make bq-setup`

- **Clock:** Sun 13:15-13:39 (0.4 h).
- **Goal:** the three raw tables exist in `raw` and in `raw_dev`, partitioned by `_arrival_date`, clustered, and created from one JSON schema file per table.
- **Why it matters:** one schema file drives the table, every load job and a test, so the three can never disagree. Concepts: "Partitions and partition pruning", "Clustering".
- **Learn first:** [creating partitioned tables](https://docs.cloud.google.com/bigquery/docs/creating-partitioned-tables); [clustered tables](https://docs.cloud.google.com/bigquery/docs/clustered-tables); the [Python `Client`](https://docs.cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.client.Client) (`create_dataset`, `create_table`) and [`SchemaField.from_api_repr`](https://docs.cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.schema.SchemaField); "Raw tables" and "Schema JSON files" in `docs/specs/data_and_generator.md`; "The pattern: `ensure_tables` from the schema JSON" in `docs/specs/bigquery_sandbox_and_costs.md`.
- **Do:**
  1. An agent scaffolds `src/recon/schemas/payment_events.json`, `settlement_lines.json` and `fx_rates.json` from the spec. You compare every column, type and mode with the spec.
  2. An agent scaffolds `src/recon/__init__.py` and `src/recon/bq.py` (the host client from the key file, and a query helper that always sets `maximum_bytes_billed`).
  3. You write `ensure_tables(client, dataset)` in `src/recon/load.py`. It creates the dataset in US if it is missing. For each table it creates the table from its schema JSON with partitioning on `_arrival_date`, clustering (`mid` for the payment tables, `provider` for FX), the description and the `data_origin` label, and `exists_ok=True`. Each schema file is one object: the table options plus a `fields` list. So the schema comes from `doc["fields"]`, and every option comes from the same file. The client syntax that is easy to get wrong:
     ```python
     ds = bigquery.Dataset(f"{project}.{dataset}"); ds.location = "US"
     client.create_dataset(ds, exists_ok=True)
     doc = json.loads(Path(path).read_text())           # src/recon/schemas/<table>.json
     schema = [bigquery.SchemaField.from_api_repr(f) for f in doc["fields"]]
     table = bigquery.Table(f"{project}.{dataset}.{doc['table']}", schema=schema)
     table.time_partitioning = bigquery.TimePartitioning(
         type_=doc["time_partitioning"]["type"], field=doc["time_partitioning"]["field"])   # note: type_
     table.clustering_fields = doc["clustering_fields"]  # ["mid"], or ["provider"] for fx_rates
     table.labels = doc["labels"]                        # data_origin: synthetic, or real for fx_rates
     table.description = doc["description"]              # starts with "SYNTHETIC:" or "REAL:"
     client.create_table(table, exists_ok=True)
     ```
  4. An agent scaffolds `src/recon/cli.py` with one subcommand, `bq-setup`, that calls your `ensure_tables` for `raw` and `raw_dev`. Add `make bq-setup`.
  5. `make bq-setup`, then `make bq-setup` again (the second run must change nothing).
- **You write:** `ensure_tables`. **Agent may scaffold:** the schema JSON files, `bq.py`, the `cli.py` skeleton.
- **Files:** `src/recon/__init__.py`, `src/recon/bq.py`, `src/recon/load.py`, `src/recon/cli.py`, `src/recon/schemas/payment_events.json`, `src/recon/schemas/settlement_lines.json`, `src/recon/schemas/fx_rates.json`, `Makefile`.
- **Done when:** in the console, `SELECT table_name, ddl FROM raw.INFORMATION_SCHEMA.TABLES ORDER BY table_name` returns 3 rows whose `ddl` contains `PARTITION BY _arrival_date` and `CLUSTER BY`; the same for `raw_dev`. Each table's Details tab shows no table expiration and the `data_origin` label.
- **Traps:**
  - Never call `client.schema_from_json` on these files. It expects a file that holds only a list of fields, and each file here is one object, so it fails.
  - Never set a table expiration on a partitioned table; it overrides the partition expiry.
  - Leave `partition_expiration_days` alone; the sandbox default of 60 days stays.
  - The `fx_rates` table is labelled `real` and its description starts with "REAL: NBK rates via Frankfurter v2".
  - Location `US` everywhere. Set the client's project explicitly.
- **Commit:** `feat(load): add the raw schema contract and ensure_tables (S2.3)`, ending with the line `written with AI`.
- **Failure log:** a schema mismatch found here is cheap. Log it if it came from a real misunderstanding.

### S2.4 `dags/smoke_bigquery.py`

- **Clock:** Sun 13:39-13:57 (0.3 h).
- **Goal:** a manual DAG that proves the container can load into BigQuery and run dbt.
- **Why it matters:** a walking skeleton surfaces image, key-mount and connection problems while there is still time to fix them. It never touches `raw` and never creates scheduled runs. Concepts: "DAG", "Task and operator", "Timetables: CronTriggerTimetable vs CronDataIntervalTimetable" (`schedule=None` means manual only).
- **Learn first:** [TaskFlow](https://airflow.apache.org/docs/apache-airflow/3.3.2/tutorial/taskflow.html); [BashOperator](https://airflow.apache.org/docs/apache-airflow-providers-standard/stable/operators/bash.html); [the Google Cloud connection](https://airflow.apache.org/docs/apache-airflow-providers-google/stable/connections/gcp.html); `smoke_bigquery` in `docs/specs/airflow_and_docker.md`.
- **Do:**
  1. Write the DAG as specified: `schedule=None`; create `probe.smoke (d DATE NOT NULL, x INT64) PARTITION BY d` if it is missing; load 1 row into `probe.smoke$<yesterday, UTC>` with WRITE_TRUNCATE through the hook's client; then a BashOperator `cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt debug --target airflow`.
  2. Quick parse check before the stack is up (needs the image from S2.1):
     `docker run --rm --entrypoint python -v "$PWD/dags:/opt/airflow/dags:ro" ledger-vs-statement-airflow:3.3.2 /opt/airflow/dags/smoke_bigquery.py && echo PARSE_OK`
- **You write:** the DAG.
- **Files:** `dags/smoke_bigquery.py`.
- **Done when:** `PARSE_OK` is printed.
- **Traps:**
  - Import from `airflow.sdk`. No Airflow 2 idioms.
  - Build the client with `BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")` and `hook.get_client(project_id=hook.project_id, location="US")`. The hook defaults to legacy SQL otherwise.
  - Put heavy imports (the Google provider, google-cloud-bigquery) inside the task function, because the dag-processor parses the file often.
  - Never `insert_rows_json` or `insert_all`: they are streaming inserts and the sandbox refuses them.
- **Commit:** `feat(dag): add the manual smoke_bigquery DAG (S2.4)`
- **Failure log:** an import error that took more than a few minutes.

### S2.5 Start the stack and run the smoke DAG (G-skel)

- **Clock:** Sun 13:57-14:15 (0.3 h).
- **Goal:** `smoke_bigquery` is green inside Docker.
- **Why it matters:** it proves the image, the key mount, the connection, the pool and the container's dbt in one run. Concept: "Pools".
- **Learn first:** [pools](https://airflow.apache.org/docs/apache-airflow/3.3.2/administration-and-deployment/pools.html); "Start the stack" and "Run the smoke test" in the "Operations runbook" of `docs/specs/airflow_and_docker.md`.
- **Do:**
  1. Add the `up`, `down` and `smoke` targets.
  2. `make up`. Wait until `docker compose ps` shows the services healthy (a minute or two).
  3. `docker compose exec airflow-scheduler airflow pools get dbt_serial`
  4. Add that pool check to `make doctor`.
  5. `make smoke`
  6. Watch the run at http://localhost:8083 (user `airflow`, password `airflow`). Set the UI timezone to UTC first (runbook heading "Open the UI and set its timezone to UTC").
- **You write:** the run and the checks. **Agent may scaffold:** the three Makefile targets.
- **Files:** `Makefile`.
- **Done when:** the pool line shows `dbt_serial` with 1 slot. The smoke run is green. The dbt task's log ends with `All checks passed!`. In the console, `SELECT COUNT(*) AS n FROM probe.smoke WHERE d = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)` returns `n = 1` (`CURRENT_DATE()` in the console is the UTC date; this is a check, never a model).
- **Traps:**
  - If the container's `dbt debug` fails, check its environment: `docker compose exec airflow-scheduler env | grep -E '^(DBT_|GCP_PROJECT|RAW_DATASET)'`.
  - A permission error on the key means `AIRFLOW_UID` does not match the owner of `keys/sa.json`.
  - If the course stack is still running, the two stacks compete for Docker memory. Stop it first.
  - After a change to `Dockerfile` or `docker/requirements-dbt.txt`: `docker compose build && make up`.
- **Commit:** `build(repo): add the up, down and smoke targets (S2.5)`, ending with the line `written with AI`.
- **Failure log:** every plumbing bug here is a real entry, about 5 minutes each.

### Explain check M2

Why does dbt have its own venv? How does the key reach the container? Why does `smoke_bigquery` not touch `raw`?

**Gate G-skel** (14:15, hard stop 16:00): if it is not green by 16:00, stop Docker work. Build M3 to M5 on the host as planned, and take one more 1-hour Docker slot before G1.

---

## M3. Generator

Sunday 14:15-16:30, 2.25 h. **Done when:** pytest is green, and `make day DATE=2026-10-30` run twice gives the same sha256 for every file.

### S3.1 `world.toml`, `config.py` and `mids.csv`

- **Clock:** Sun 14:15-14:30 (0.25 h).
- **Goal:** every synthetic design parameter in one TOML file with a comment per value, loaded with the environment and the merchant-account terms into frozen dataclasses.
- **Why it matters:** what finance knows (the contract terms in `mids.csv`) is shared with dbt. What finance does not know (noise, defects, PSP mistakes) stays in `world.toml`, hidden from dbt. That split is what makes the self-test fair. Concept: "The seeded self-test, and why it is not accuracy".
- **Learn first:** [tomllib](https://docs.python.org/3.13/library/tomllib.html); the `world.toml` keys and `mids.csv` in `docs/specs/data_and_generator.md`.
- **Do:**
  1. Create `dbt/seeds/mids.csv` exactly as in the spec. The generator reads it, so it exists now; S5.1 adds the other seeds and the column types.
  2. Write `src/recon/world.toml` yourself: every key from the spec, every value, and a one-line comment that says what it means.
  3. An agent scaffolds `src/recon/config.py`: read the env vars (`RECON_SEED`, `RECON_WORLD_START`, `RECON_LANDING_DIR`), `world.toml` and `mids.csv` into frozen dataclasses.
- **You write:** `world.toml`, every value and comment. **Agent may scaffold:** the loading code in `config.py`.
- **Files:** `dbt/seeds/mids.csv`, `src/recon/world.toml`, `src/recon/config.py`.
- **Done when:** in `PYTHONPATH=src uv run python` (with the dev shell open), loading the config shows `mid_usd_01` and `mid_kzt_01` with their fee terms and offsets, the seed `20261101` and the world start `2026-10-04`.
- **Traps:** every value is an integer or a string, as in the data spec: plan weights in percent (`weight_pct = [30, 50, 20]`), rates in basis points (`*_bp`), delays in seconds (`*_delay_s`). Fees and tolerances live in `mids.csv`, also as integers. Read the seed the same way everywhere, because it becomes part of every random-stream key.
- **Commit:** `feat(generator): add world parameters and contract terms (S3.1)`, ending with the line `written with AI`.
- **Failure log:** a value you had to change because the spec and the TOML disagreed.

### S3.2 `payments_for_day`

- **Clock:** Sun 14:30-15:15 (0.75 h).
- **Goal:** a pure function that returns the payments booked on one UTC day for one MID, with the planted defects and the benign noise.
- **Why it matters:** the same inputs must always give the same payments, on any machine and any Python 3.13. Money is integers end to end. Concepts: "Deterministic replay: the seeded generator", "Minor units and integer fee arithmetic", "Gross, fee, net and basis points".
- **Learn first:** [random](https://docs.python.org/3.13/library/random.html) (the reproducibility notes); the generator pseudocode, the RNG rules and the "Defect catalog" in `docs/specs/data_and_generator.md`; optional, 5 minutes: the [Adyen settlement details report](https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report/) columns.
- **Do (you write all of it):**
  1. One random stream per purpose: `random.Random(f"{seed}|{day_index}|{mid}|{purpose}")` for day-level draws, and the same key with the payment number `n` for per-payment draws. The purposes are listed in the spec.
  2. Two helpers built only on `rng.random()`: `draw_int(rng, lo, hi)` and `draw_weighted(rng, weights)`.
  3. Volume, plan, capture time (the UTC hour comes from the MID's local-hour weights rotated by its offset), first delivery, D1 redeliveries, settlement lag.
  4. One draw on the `money` stream picks D2, D3, D4 or none. Then the D4 amount delta, the D4 plus D5 combination, the D5 overcharge and the B3 fee noise, each on its own stream.
  5. Expected fees and tolerances with the integer formulas from the spec (Python `//` gives the same result as SQL `DIV` for positive values).
  6. Readable ids as in the spec. No payment before `RECON_WORLD_START`.
- **You write:** the whole function. **Agent may scaffold:** nothing here.
- **Files:** `src/recon/generator.py`.
- **Done when:** in a Python shell, the same (seed, world start, day, MID) twice returns equal lists, a different seed returns a different list, and every amount and fee is an `int`.
- **Traps:**
  - Never `hash()`: it changes between processes. String seeds in `random.Random` are stable.
  - Never `randint`, `choices`, `uniform` or the module-level `random.seed()`. Only `Random.random()` is guaranteed to stay the same across Python versions.
  - Never a float on the money path. Never the wall clock.
  - A new defect class gets a new purpose, so it never reshuffles existing rows.
  - D1 cannot apply to D3 (no deliveries). D4 and D5 cannot apply to D2 (no statement line).
- **Commit:** `feat(generator): generate payments with planted defects (S3.2)`
- **Failure log:** a determinism or money-type bug, with how you saw it.

### S3.3 `arrivals`, `emit` and the answer key

- **Clock:** Sun 15:15-15:45 (0.5 h).
- **Goal:** `emit(seed, world_start, run_date, landing_dir)` writes exactly what arrived during UTC day `run_date`, byte for byte the same on every rerun, plus the answer key for the payments booked that day.
- **Why it matters:** one Airflow run owns one arrival day. The arrival date, the booking date and the accounting date are three different dates (see the three dates in `docs/design.md`). Byte-identical files are the first half of idempotency. Concepts: "Idempotency", "Three dates and as_of_date", "Cut-off times, time zones and the accounting date".
- **Learn first:** [json](https://docs.python.org/3.13/library/json.html) (`sort_keys`, `separators`); [os.replace](https://docs.python.org/3.13/library/os.html) (atomic rename); the timing table, `emit` and lookback, the file formats and the landing layout in `docs/specs/data_and_generator.md`.
- **Do:**
  1. You write `arrivals`: recompute the payments booked on R-5 to R (the 5-day lookback), then keep webhook deliveries with `DATE(delivered_ts) = R` and statement lines whose arrival date (accounting date plus lag) is R.
  2. You write the answer-key rows for the payments booked on R.
  3. An agent scaffolds the writing: NDJSON with sorted keys and compact separators, rows sorted by key, a trailing newline, timestamps as `YYYY-MM-DD HH:MM:SS+00:00`, each file written to a temporary name and renamed atomically.
  4. `emit` returns a small dict of counts.
- **You write:** the selection logic and the answer-key rows. **Agent may scaffold:** the atomic file writing and serialization.
- **Files:** `src/recon/generator.py`.
- **Done when:** running `emit` twice for one date leaves the same sha256 for every file, and the files sit at the landing paths from the spec.
- **Traps:** a capture at 23:59:50 UTC is delivered the next day. Redeliveries up to 6 hours later cross midnight. A USD accounting date can be one day before the world start. The answer key goes to `landing/_truth/`, which is gitignored and never loaded.
- **Commit:** `feat(generator): emit arrival-day files and the answer key (S3.3)`, ending with the line `written with AI`.
- **Failure log:** an off-by-one-day bug in arrival selection is the classic one. Log it if it happens.

### S3.4 Generator tests

- **Clock:** Sun 15:45-16:15 (0.5 h).
- **Goal:** tests that catch non-determinism, wrong arrival dates, lost or duplicated statement lines, and schema drift.
- **Why it matters:** the golden hash turns "it looked the same" into a check that fails when anything changes. Concepts: "Idempotency", "Deterministic replay: the seeded generator".
- **Learn first:** [pytest configuration](https://docs.pytest.org/en/stable/reference/customize.html) (`pythonpath`); [hashlib](https://docs.python.org/3.13/library/hashlib.html).
- **Do:**
  1. An agent scaffolds the harness in `tests/test_generator.py` (fixtures with `tmp_path`).
  2. You write the assertions: a golden sha256 of one emitted day, committed in the test; another seed gives different files; every event row has `_arrival_date = R` and `DATE(delivered_ts) = R`; over 10 days every settled payment appears in exactly one statement file; every row matches its schema JSON (names, required fields, types); the class counts over 7 days stay within loose bounds.
  3. Add `make test` and add `test` to `make check`.
- **You write:** the assertions. **Agent may scaffold:** the harness.
- **Files:** `tests/test_generator.py`, `pyproject.toml` (only if the pytest settings change), `Makefile`.
- **Done when:** `make test` ends with `passed` and no failures. `make check` exits 0.
- **Traps:** compute the golden hash only when the generator is final for M3. Before G1 you may update it on purpose (say why in the commit). After G1, only together with a `generator_version` bump (as in U6 and U7), with the reason in the commit. Set the class bounds with the rule under "Generator tests" in `docs/specs/data_and_generator.md`: each count lies between 0.25 and 3 times its expected value, and the expected value is the rate times the real base count. For example D3 is 0.4% of payments: about 1,400 payments over 7 days give an expected 5.6, so the bounds are about 1.4 to 16.8. D1 at 4% of events gets much higher bounds. If a bound fails for the pinned seed, widen it and log why; never change the seed to make a test pass. The generator is deterministic, so a bound either always passes or always fails: it never flickers.
- **Commit:** `test(generator): add determinism and golden-hash tests (S3.4)`, ending with the line `written with AI`.
- **Failure log:** a test that found a real generator bug is a good entry.

### S3.5 `make day` twice: the same bytes

- **Clock:** Sun 16:15-16:30 (0.25 h).
- **Goal:** the host command for one day, proven byte-identical.
- **Why it matters:** this is the first visible proof of idempotency. Concept: "Idempotency".
- **Learn first:** [argparse](https://docs.python.org/3.13/library/argparse.html).
- **Do:**
  1. An agent adds a `generate --date` subcommand to `src/recon/cli.py`. `make day DATE=` runs it. In M3, `make day` only generates; S4.3 adds the fetch and the load.
  2. Run:
     ```sh
     make day DATE=2026-10-30
     find landing -type f -path '*2026-10-30*' | sort | xargs shasum -a 256 > "$TMPDIR/day_run1.txt"
     make day DATE=2026-10-30
     find landing -type f -path '*2026-10-30*' | sort | xargs shasum -a 256 > "$TMPDIR/day_run2.txt"
     diff "$TMPDIR/day_run1.txt" "$TMPDIR/day_run2.txt" && echo IDENTICAL
     ```
- **You write:** the run and the check. **Agent may scaffold:** the argparse code.
- **Files:** `src/recon/cli.py`, `Makefile`.
- **Done when:** `IDENTICAL` is printed, and `git status --short` shows no files under `landing/` (they are gitignored).
- **Traps:** the host writes the same `landing/` folder that the containers mount. That is safe only because the files are identical for the same inputs.
- **Commit:** `feat(cli): add make day for one generated day (S3.5)`, ending with the line `written with AI`.
- **Failure log:** if the hashes differ, that is a real bug: log the cause.

### Explain check M3

Why is the generator a pure function of (seed, day_index, MID)? Why only `random()`? Which defect can cross midnight, and what does that do to the arrival files?

---

## M4. Loader and FX

Sunday 16:45-17:30, 0.75 h. **Done when:** 7 development days are in `raw_dev`, a reloaded day is identical, and the FX files were landed once and committed.

### S4.1 `load_partition` and `load_day`

- **Clock:** Sun 16:45-17:03 (0.3 h).
- **Goal:** for each table and arrival day, exactly one WRITE_TRUNCATE load job into one partition, or a partition delete on an empty day.
- **Why it matters:** the sandbox has no DML, so idempotency lives in the loader: rerunning a day replaces that day and nothing else. Concepts: "Load jobs and write dispositions", "Partition decorators", "DDL and DML, and why this project has no DML", "Idempotency".
- **Learn first:** [loading partitioned tables](https://docs.cloud.google.com/bigquery/docs/load-data-partitioned-tables); [LoadJobConfig](https://docs.cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.job.LoadJobConfig); "Load protocol" in `docs/specs/bigquery_sandbox_and_costs.md`.
- **Do:**
  1. You write two functions in `src/recon/load.py`. `load_day(client, dataset, table, run_date, landing_dir)` reads every landing file of that table for R (both MID files for statements), concatenates the rows, asserts every row's `_arrival_date == R` (and for events also `DATE(delivered_ts) == R`) before any job runs, then calls `load_partition`. `load_partition` does the one write for that table and day (sub-steps 2 and 3).
  2. With no rows: `client.delete_table("<project>.<dataset>.<table>$YYYYMMDD", not_found_ok=True)`. That is a table operation, not DML.
  3. Otherwise exactly one load job, then assert `job.output_rows == len(rows)` and return `{table, rows, action, output_bytes, job_id}`.
  4. For `fx_rates`, build the rows from the landed JSON parsed with `json.loads(body, parse_float=str)`; take `provider` from the request and `fetched_at` from the meta file.
  5. The job syntax that is easy to get wrong (an agent may scaffold it):
     ```python
     doc = json.loads(Path(schema_path).read_text())          # src/recon/schemas/<table>.json, one object
     job_config = bigquery.LoadJobConfig(
         source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
         schema=[bigquery.SchemaField.from_api_repr(f) for f in doc["fields"]],   # the same list as the table
         write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
         create_disposition=bigquery.CreateDisposition.CREATE_NEVER,   # a missing table fails loudly
         max_bad_records=0,
     )
     dest = f"{project}.{dataset}.{table}${run_date:%Y%m%d}"  # one partition, no dashes
     job = client.load_table_from_file(ndjson_bytes, dest, job_config=job_config, location="US")
     job.result()                                             # waits, raises on error
     ```
  6. You write `check_run_date(run_date, world_start, today_utc)` in the same file, from "How the pipeline refuses old dates" in `docs/specs/bigquery_sandbox_and_costs.md`: it refuses a date before the world start, a date that has not ended in UTC, and a date more than 45 days old. The host CLI (S4.3) and the DAG's `check_window` (S6.1) both call it.
- **You write:** the reading, the assertions, the delete-or-load choice, the row-count check, `check_run_date`. **Agent may scaffold:** the `LoadJobConfig` block above.
- **Files:** `src/recon/load.py`.
- **Done when:** loading one day twice into `raw_dev` gives the same counts. Copy one landing file, change one row's `_arrival_date` by hand, load it: the task fails before any job runs. Restore the file (regenerate the day).
- **Traps:**
  - Two WRITE_TRUNCATE jobs into one partition overwrite each other, so concatenate first.
  - WRITE_APPEND would make reruns add duplicates.
  - `CREATE_NEVER` means a load never creates a table. A missing table fails the job loudly, instead of appearing without its partitions (see "Load protocol").
  - Never `insert_all` or `insert_rows_json` (streaming), never GCS, never any INSERT, UPDATE, DELETE or MERGE.
  - `ndjson_bytes` is a binary file object (for example `io.BytesIO`), opened at position 0.
- **Commit:** `feat(load): one WRITE_TRUNCATE load job per table and day (S4.1)`, ending with the line `written with AI`.
- **Failure log:** a partition mismatch or a row-count mismatch, with the cause.

### S4.2 `recon.fx.fetch_nbk`

- **Clock:** Sun 17:03-17:15 (0.2 h).
- **Goal:** real NBK USD/KZT rates, fetched once per run date into an immutable landed file.
- **Why it matters:** the rates are real data, and real data can be restated. Landing the response once and never fetching it again keeps every rerun identical. Concept: "FX rates, direction, cross rates and the carry-forward".
- **Learn first:** [Frankfurter](https://frankfurter.dev/); [urllib.request](https://docs.python.org/3.13/library/urllib.request.html); the Frankfurter request and response examples in `docs/specs/data_and_generator.md`.
- **Do:**
  1. You write `fetch_nbk(run_date, landing_dir)` in `src/recon/fx.py`. If `landing/fx/provider=nbk/arrival_date=R.json` exists, skip and log "already landed".
  2. Otherwise request R-6 to R: `https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT&from=<R-6>&to=<R>`, with a 10-second timeout and the User-Agent `ledger-vs-statement (learning project)`.
  3. Write the body byte for byte, and a meta file (`url`, `fetched_at`, `http_status`, `sha256`), both atomically.
  4. Refuse any R on or after today (UTC).
- **You write:** the skip rule, the window, the files. **Agent may scaffold:** the urllib request code.
- **Files:** `src/recon/fx.py`.
- **Done when:** the first call for a date writes the two files. The second call for the same date makes no HTTP request and logs "already landed".
- **Traps:** when R-6 has no rate (R is a Friday or a Saturday, or R-6 is a holiday), the answer starts with the last published row before R-6. The check allows exactly that one earlier row. Test with R = 2026-10-31: the answer starts with 2026-10-23. Seven days always contain weekdays, which is why the window is R-6 to R. Always pass `base` and `quotes`. Never use blended rates. Never parse a rate as a float.
- **Commit:** `feat(fx): fetch NBK rates once into immutable landing (S4.2)`, ending with the line `written with AI`.
- **Failure log:** an HTTP or parsing surprise from the real API is a good entry.

### S4.3 The host CLI for full development days

- **Clock:** Sun 17:15-17:30 (0.25 h).
- **Goal:** 7 development days (2026-10-25 to 2026-10-31) in `raw_dev`, one of them reloaded and unchanged.
- **Why it matters:** the host runs the same functions as the DAG. Debugging logic on the host is fast, and the Airflow datasets stay clean. Concept: "Idempotency".
- **Learn first:** nothing new.
- **Do:**
  1. An agent adds `fetch --date`, `load --date`, `day --date` (generate, then fetch, then load the 3 tables into `$RAW_DATASET`) and `days --from --to` to `src/recon/cli.py`. Update `make day` and add `make days` (see "Make targets: what each runs, and the step that adds it").
  2. `make days FROM=2026-10-25 TO=2026-10-31`
  3. Run this in the console and note the result:
     ```sql
     select 'payment_events' as t, count(*) as n, sum(amount_minor) as s
     from raw_dev.payment_events where _arrival_date = '2026-10-28'
     union all
     select 'settlement_lines', count(*), sum(gross_minor)
     from raw_dev.settlement_lines where _arrival_date = '2026-10-28'
     ```
  4. `make day DATE=2026-10-28`, then run the query again.
  5. `git add landing/fx && git commit -m "chore(fx): land real NBK rates for 2026-10-25 to 2026-10-31 (S4.3)"`
- **You write:** the runs and the checks. **Agent may scaffold:** the argparse code.
- **Files:** `src/recon/cli.py`, `Makefile`, `landing/fx/provider=nbk/*.json` (committed).
- **Done when:** each raw table in `raw_dev` has 7 partitions. The query returns the same two rows before and after the reload. `git ls-files landing/fx | head` lists the committed FX files. `git check-ignore landing/payment_events` prints the path.
- **Traps:** the CLI calls `check_run_date` before it generates or loads a day, so a day older than 45 days, or on or after today (UTC), is refused on the host too. (In M3, `make day` only generated files and had no guard yet.) Landed FX files are committed and immutable: never edit or refetch them.
- **Commit:** `feat(cli): load full development days into raw_dev (S4.3)`, ending with the line `written with AI`. Then the FX commit in sub-step 5.
- **Failure log:** anything that differed between the two queries.

### Explain check M4

Why one load job per table per day? What exactly does WRITE_TRUNCATE on `t$20261025` replace? What happens on an empty day?

---

## M5. dbt core (host, target `dev`)

Sunday 18:15-21:30, 3.25 h. **Done when:** `make dbt-build` is green over the 7 development days, `unexplained_minor` is 0 on every MID-day, and UT1 and UT2 were seen red first (each recorded in "Planned red runs (not bugs)" in `docs/failure_log.md`).

Every SQL model and test in this milestone is yours. The shapes, columns, grains and fixtures are in `docs/specs/dbt_project.md`. Write each model from its row there.

### S5.1 Project config, packages, seeds, sources

- **Clock:** Sun 18:15-18:39 (0.4 h).
- **Goal:** a complete `dbt_project.yml`, `dbt_utils` installed, three seeds loaded with explicit types, and the two sources declared.
- **Why it matters:** an inferred seed type can turn money into FLOAT64. Typing every column stops that at the door. Concepts: "Seeds", "Sources", "Packages", "Data types for money: INT64, NUMERIC and FLOAT64".
- **Learn first:** [seeds](https://docs.getdbt.com/docs/build/seeds); [column_types](https://docs.getdbt.com/reference/resource-configs/column_types); [sources](https://docs.getdbt.com/docs/build/sources); [packages](https://docs.getdbt.com/docs/build/packages); [env_var](https://docs.getdbt.com/reference/dbt-jinja-functions/env_var); [query-comment](https://docs.getdbt.com/reference/project-configs/query-comment).
- **Do:**
  1. You complete `dbt/dbt_project.yml` from the spec (materializations per folder, vars, `query-comment` with `job-label: true`).
  2. You write `dbt/packages.yml` (`dbt-labs/dbt_utils` 1.4.1), `dbt/seeds/currencies.csv`, `dbt/seeds/reason_codes.csv`, `dbt/seeds/_seeds.yml` (a type for every seed column) and `dbt/models/staging/_sources.yml`.
  3. Open the dev shell. `(cd dbt && uv run dbt deps)`. Add `dbt deps` to `make setup`, and add `make dbt-build`.
  4. `(cd dbt && uv run dbt seed --target dev)`
- **You write:** all YAML and CSV. **Agent may scaffold:** the YAML column lists, which you check against the spec.
- **Files:** `dbt/dbt_project.yml`, `dbt/packages.yml`, `dbt/package-lock.yml`, `dbt/seeds/currencies.csv`, `dbt/seeds/reason_codes.csv`, `dbt/seeds/_seeds.yml`, `dbt/models/staging/_sources.yml`, `Makefile`.
- **Done when:** the seed command ends with a line that starts `Done. PASS=3` and shows `ERROR=0`. `dbt/package-lock.yml` exists and is committed.
- **Traps:**
  - Write data tests as `data_tests:` with `arguments:`, as in your dbt course project.
  - If BigQuery rejects a job label on the first build, remove `job-label` and log it.
  - The source schema is `{{ env_var('RAW_DATASET', 'raw') }}`; the dev shell and the Makefile set `raw_dev`.
  - No custom schemas, so no `generate_schema_name` override. `dbt/dbt_packages/` is gitignored; the containers see it through the `./dbt` mount.
- **Commit:** `feat(dbt): add project config, typed seeds and sources (S5.1)`. Add the line `written with AI` if an agent drafted the column lists.
- **Failure log:** a seed type or YAML error that took more than a few minutes.

### S5.2 The four staging models and their generic tests

- **Clock:** Sun 18:39-19:15 (0.6 h).
- **Goal:** `stg_recon__as_of`, `stg_psp__payment_events` (deduplicated), `stg_psp__settlement_lines` and `stg_fx__rates`, with their tests in `_staging.yml`.
- **Why it matters:** dedup sits right after the as-of filter. One model per source keeps the layers easy to reason about. Concepts: "Deduplication with QUALIFY", "Materializations".
- **Learn first:** [QUALIFY in the query syntax](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax); [data tests](https://docs.getdbt.com/docs/build/data-tests); [dbt_utils](https://hub.getdbt.com/dbt-labs/dbt_utils/latest/); the four staging models in the spec.
- **Do:**
  1. You write the four models and `_staging.yml` from the spec.
  2. `(cd dbt && uv run dbt build --select staging --target dev)`
- **You write:** all of it.
- **Files:** `dbt/models/staging/stg_recon__as_of.sql`, `stg_psp__payment_events.sql`, `stg_psp__settlement_lines.sql`, `stg_fx__rates.sql`, `_staging.yml` (all in `dbt/models/staging/`).
- **Done when:** that build ends with `ERROR=0`.
- **Traps:**
  - Break ties in the dedup order with `delivery_id` after `delivered_ts`.
  - `COUNT(*) OVER (PARTITION BY event_id)` is computed before QUALIFY filters rows, so it counts every copy.
  - Filter `_arrival_date <= as_of_date` before deduplicating.
  - Never `CURRENT_DATE()` in a model.
  - `rate = CAST(rate_text AS NUMERIC)`.
  - If BigQuery asks for a WHERE clause next to QUALIFY, add `where true`.
- **Commit:** `feat(dbt): add the staging models with dedup and tests (S5.2)`
- **Failure log:** a test that caught a real problem in the data or the SQL.

### S5.3 UT1 first, then `int_ledger__captures`

- **Clock:** Sun 19:15-19:45 (0.5 h).
- **Goal:** the cut-off rule pinned by a unit test that you saw fail before the logic existed.
- **Why it matters:** a unit test checks logic on fixed rows you choose. A data test checks the data you have. The cut-off rule is the first thing a reviewer probes. Concepts: "Unit tests versus data tests", "Cut-off times, time zones and the accounting date".
- **Learn first:** [dbt unit tests](https://docs.getdbt.com/docs/build/unit-tests); UT1 and `int_ledger__captures` in the spec.
- **Do:**
  1. Write UT1 `ut_captures_cutoff_both_directions` in `dbt/models/_unit_tests.yml` from the spec. Mock every direct parent in `given`, the seed `mids` included.
  2. Write a first version of the model with the naive rule `expected_accounting_date = DATE(event_ts)`.
  3. Add `make dbt-unit`. Run it. UT1 is red: the KZT rows from 19:00 UTC and the USD rows before 05:00 UTC differ. Record the red run as a row in "Planned red runs (not bugs)" in `docs/failure_log.md` (date, commit, first failure line).
  4. Write the real logic. `make dbt-unit` is green. Then `make dbt-build`.
- **You write:** the test and the model.
- **Files:** `dbt/models/_unit_tests.yml`, `dbt/models/intermediate/int_ledger__captures.sql`, `dbt/models/intermediate/_intermediate.yml`, `Makefile`, `docs/failure_log.md`.
- **Done when:** UT1 was red, then green, and `make dbt-build` ends with `ERROR=0`.
- **Traps:** a unit test needs its model's direct parents to exist in the warehouse. They exist after S5.2. On a fresh dataset, build them empty first: `(cd dbt && uv run dbt seed --target dev && uv run dbt run --select staging --empty --target dev)`. Mock every input, or compilation fails with "node not found". `TIMESTAMP_ADD(event_ts, INTERVAL statement_utc_offset_hours HOUR)` accepts an INT64 column.
- **Commit:** `test(dbt): add UT1 cut-off cases before the captures model (S5.3)`, then `feat(dbt): add int_ledger__captures (S5.3)`.
- **Failure log:** the red run goes in its "Planned red runs (not bugs)" row. Write a real entry only if UT1 failed for a reason you did not plan, for example a broken fixture.

### S5.4 `int_fx__usd_rates_daily` and the `to_usd` macro

- **Clock:** Sun 19:45-20:06 (0.35 h).
- **Goal:** one rate per currency per day from the earliest fetched rate date to the as-of date, with the carry-forward and its age, and one rounding macro.
- **Why it matters:** NBK publishes on weekdays, so a weekend day carries Friday's rate forward. The project labels that as its own convention, and a staleness test fails if the carry gets too long. Concepts: "As-of joins, date spines and carry-forward", "FX rates, direction, cross rates and the carry-forward".
- **Learn first:** [GENERATE_DATE_ARRAY](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/array_functions); [LAST_VALUE](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/navigation_functions) with `IGNORE NULLS`; [NUMERIC](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/data-types); [macros](https://docs.getdbt.com/docs/build/jinja-macros); the model and the macro in the spec.
- **Do:**
  1. You write the model and its tests in `_intermediate.yml`.
  2. You write `dbt/macros/to_usd.sql`.
  3. `(cd dbt && uv run dbt build --select int_fx__usd_rates_daily --target dev)`
- **You write:** all of it.
- **Files:** `dbt/models/intermediate/int_fx__usd_rates_daily.sql`, `dbt/models/intermediate/_intermediate.yml`, `dbt/macros/to_usd.sql`.
- **Done when:** the build ends with `ERROR=0`. Spot check in the console: a Saturday KZT row has Friday's `rate_date` and `carry_days = 1`, and USD rows have `units_per_usd = 1` and `carry_days = 0`.
- **Traps:** never `POW()` (it returns FLOAT64). INT64 divided by INT64 is FLOAT64, so cast to NUMERIC before dividing. The `carry_days` bound comes from `var('fx_max_carry_days')`.
- **Commit:** `feat(dbt): add the daily USD rate spine and to_usd (S5.4)`
- **Failure log:** a type error or a wrong carry, with the cause.

### S5.5 UT2 first, then `fct_recon_lines`

- **Clock:** Sun 20:06-20:54 (0.8 h).
- **Goal:** the matcher: one row per payment seen on either side, exactly one status per line, flags, dated reason codes and the integer fee check.
- **Why it matters:** a FULL OUTER JOIN keeps one-sided lines, and they are the interesting ones. Every status is judged against the data's as-of date, never the wall clock. Concepts: "FULL OUTER JOIN matching", "Line statuses, due dates and scope", "Minor units and integer fee arithmetic".
- **Learn first:** [FULL OUTER JOIN in the query syntax](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax); [mathematical functions](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/mathematical_functions) (`DIV`, `GREATEST`, `ABS`); `fct_recon_lines`, the status CASE, the flags and UT2 in the spec.
- **Do:**
  1. Write UT2 `ut_lines_status_and_date_shift` from the spec. Mock every direct parent, including `stg_recon__as_of` and the seed `mids`.
  2. Write a first version that labels every line `matched`. `make dbt-unit`: UT2 is red. Record the red run in "Planned red runs (not bugs)".
  3. Write the real matcher. `make dbt-unit` is green. Then `make dbt-build`.
- **You write:** the test and the model.
- **Files:** `dbt/models/_unit_tests.yml`, `dbt/models/marts/fct_recon_lines.sql`, `dbt/models/marts/_marts.yml`, `docs/failure_log.md`.
- **Done when:** UT2 was red, then green, and `make dbt-build` ends with `ERROR=0`.
- **Traps:**
  - The join key is `payment_id` with equality only. BigQuery rejects a FULL OUTER JOIN without an equality condition, and OR conditions are wrong here.
  - Filter `record_type = 'SALE'` in a CTE before the join. A filter after the join drops the ledger-only lines.
  - The due date is inclusive: from the due date on, a ledger-only line is missing.
  - Fees use `DIV`, never `ROUND(x * bps / 10000)`. `CEIL` on INT64 returns FLOAT64.
  - `recon_date` is never NULL. The grain is one row per `payment_id`.
- **Commit:** `test(dbt): add UT2 status and date-shift cases (S5.5)`, then `feat(dbt): add the fct_recon_lines matcher (S5.5)`.
- **Failure log:** the red run in its "Planned red runs (not bugs)" row; a real entry for any real matcher bug.

### S5.6 `fct_recon_daily` and the three integrity tests

- **Clock:** Sun 20:54-21:30 (0.6 h).
- **Goal:** the two-calendar bridge per (MID, currency, day), with `unexplained_minor`, and three error-level tests that can actually fail.
- **Why it matters:** the gap is computed top-down from the input models, and the components bottom-up from the matcher. If the two disagree by even one minor unit, the matcher lost, duplicated or misdated money. A residual-defined "unexplained" would be a tautology. Concept: "The two-calendar bridge and the identity (and why it is not a tautology)".
- **Learn first:** `fct_recon_daily`, the dated components and the three singular tests in the spec; [data tests](https://docs.getdbt.com/docs/build/data-tests) (singular tests).
- **Do:**
  1. You write `fct_recon_daily`: a spine of every MID times every day, top-down totals from `int_ledger__captures` and `stg_psp__settlement_lines`, dated components from `fct_recon_lines`, fees and the USD reporting columns. Leave out `exception_count` and `exception_abs_minor` for now: they come from `fct_recon_exceptions`, which S7.2 builds, and S7.2 adds them.
  2. You write `dbt/tests/assert_recon_decomposition_closes.sql`, `assert_no_money_lost_between_layers.sql` and `assert_redeliveries_identical.sql`.
  3. `make dbt-build`
  4. In the console:
     ```sql
     select countif(unexplained_minor != 0) as days_not_closing,
            sum(abs(unexplained_minor)) as abs_unexplained_minor
     from analytics_dev.fct_recon_daily
     ```
- **You write:** all of it.
- **Files:** `dbt/models/marts/fct_recon_daily.sql`, `dbt/models/marts/_marts.yml`, `dbt/tests/assert_recon_decomposition_closes.sql`, `dbt/tests/assert_no_money_lost_between_layers.sql`, `dbt/tests/assert_redeliveries_identical.sql`.
- **Done when:** `make dbt-build` ends with `ERROR=0`, and the query returns `0` and `0`.
- **Traps:** the top-down totals must not read `fct_recon_lines`. The spine includes days with no activity. A timing component is +L on the booking date and -L on the accounting date. Fees never enter the gross identity.
- **Commit:** `feat(dbt): add fct_recon_daily and the integrity tests (S5.6)`
- **Failure log:** every time the identity did not close, the cause. These are your best interview stories.

### Explain check M5

Why a tie-break in QUALIFY? Why must the FULL OUTER JOIN keep an equality? Why can the identity test fail? Why is there no `CURRENT_DATE()` in any model?

---

## M6. DAG end to end (gate G1)

Sunday 21:30-22:15, 0.75 h. **Done when (gate G1):** one `recon_daily` run is green end to end, and the history backfill has started. G1 at 22:15; hard stop 23:00.

### S6.1 `dags/recon_daily.py`

- **Clock:** Sun 21:30-21:51 (0.35 h).
- **Goal:** the pipeline DAG, complete: `check_window`, `ensure_tables`, `generate_day` and `fetch_fx`, the mapped `load_raw`, and `dbt_build` in the `dbt_serial` pool.
- **Why it matters:** one run owns one UTC arrival day, given by its data interval. In Airflow 3 a cron string or `"@daily"` gives an empty interval, so the timetable must be explicit. Concepts: "Timetables: CronTriggerTimetable vs CronDataIntervalTimetable", "Data interval", "Dynamic task mapping", "The guard task check_window".
- **Learn first:** [timetables](https://airflow.apache.org/docs/apache-airflow/3.3.2/authoring-and-scheduling/timetable.html); [DAG runs and data intervals](https://airflow.apache.org/docs/apache-airflow/3.3.2/core-concepts/dag-run.html); [dynamic task mapping](https://airflow.apache.org/docs/apache-airflow/3.3.2/authoring-and-scheduling/dynamic-task-mapping.html); [templates reference](https://airflow.apache.org/docs/apache-airflow/3.3.2/templates-ref.html); [upgrading to Airflow 3](https://airflow.apache.org/docs/apache-airflow/3.3.2/installation/upgrading_to_airflow3.html); "recon_daily settings", "recon_daily tasks" and "The dbt_build command, piece by piece" in `docs/specs/airflow_and_docker.md`.
- **Do:**
  1. You write the DAG from the spec: settings, `default_args` with `log_failure`, the six tasks, the exact `dbt_build` command, and the `chain(...)` of dependencies. `check_window` calls `check_run_date` from S4.1 and turns its `ValueError` into `AirflowFailException`.
  2. The syntax that is easy to get wrong (shape only; your file follows the spec):
     ```python
     import pendulum
     from datetime import timedelta
     from airflow.sdk import dag, task, CronDataIntervalTimetable

     @dag(schedule=CronDataIntervalTimetable("0 0 * * *", timezone="UTC"),  # never "@daily"
          start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
          catchup=False, max_active_runs=1)
     def recon_daily():
         @task(retries=3, retry_delay=timedelta(seconds=30),
               retry_exponential_backoff=2.0,                    # a float multiplier, never True
               max_retry_delay=timedelta(minutes=10))
         def fetch_fx(run_date: str) -> dict: ...
         # mapped: load_raw.partial(run_date=rd).expand(table=["payment_events", "settlement_lines", "fx_rates"])
     recon_daily()
     ```
  3. Check that it parses: `docker compose exec airflow-scheduler airflow dags list-import-errors`, then `docker compose exec airflow-scheduler airflow tasks list recon_daily`.
- **You write:** the whole DAG.
- **Files:** `dags/recon_daily.py`.
- **Done when:** `list-import-errors` reports no errors, and `tasks list recon_daily` prints `check_window`, `ensure_tables`, `generate_day`, `fetch_fx`, `load_raw` and `dbt_build`.
- **Traps:**
  - No Airflow 2 idioms: no `schedule_interval`, `execution_date`, `airflow.decorators` or SLAs.
  - `append_env=True` on the BashOperator. Without it, `env=` would wipe `PATH` and `HOME`.
  - Keep the dbt command inline. A command string ending in `.sh` is read as a template file name.
  - The only template is `{{ data_interval_start | ds }}`, and only in the BashOperator. Python tasks receive R from `check_window`.
  - `check_window` is the only place that reads the wall clock, and only for the guard.
  - Heavy imports go inside task functions. Only small dicts go through XCom.
- **Commit:** `feat(dag): add the recon_daily DAG (S6.1)`
- **Failure log:** any import or parse error, with the fix.

### S6.2 The first real run: unpause, read the interval, time it

- **Clock:** Sun 21:51-22:03 (0.2 h).
- **Goal:** the latest complete day (2026-10-31) runs end to end through Airflow, and you know how long one run takes.
- **Why it matters:** with catchup off, unpausing creates exactly one run: the latest complete interval. Reading the logged `run_date` proves you understand which day a run processes. Concepts: "Data interval", "Logical date", "Catchup".
- **Learn first:** "Manual-run semantics" in `docs/specs/airflow_and_docker.md`.
- **Do:**
  1. Add `make unpause` and `make pause`.
  2. `make unpause`. The scheduler creates the run for the interval [2026-10-31 00:00, 2026-11-01 00:00) UTC.
  3. Watch the Grid view at http://localhost:8083.
  4. Open the `check_window` log and find `run_date=2026-10-31`.
  5. `docker compose exec airflow-scheduler airflow dags list-runs recon_daily`. Write down the run's duration (end minus start, or the duration in the UI) as [T] minutes.
- **You write:** the run and the checks.
- **Files:** `Makefile`.
- **Done when:** one run with logical date `2026-10-31T00:00:00+00:00` and state `success`; the log line `run_date=2026-10-31`; [T] is written down.
- **Traps:**
  - Never `airflow dags trigger -l` for an exact day: a CLI trigger processes "yesterday relative to now".
  - If a task fails: read its log, fix, then `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s 2026-10-31 -e 2026-10-31 -t <task> -d -y`.
  - The dags folder is read live: a fixed file is used by the next try.
- **Commit:** none, unless you fixed something: then `fix(<area>): <what> (S6.2)`, its body naming the failure-log entry.
- **Failure log:** every failure in this first run is a real entry.

### S6.3 Freeze, then start the overnight backfill (G1)

- **Clock:** Sun 22:03-22:15 (0.2 h).
- **Goal:** the generator and the loader frozen under a tag, and the history loading newest first while you sleep.
- **Why it matters:** newest first means every run sees a contiguous history from its own date to the latest loaded day. Oldest first, after the run for 2026-10-31 exists, would leave a gap that `assert_arrival_days_complete` correctly fails. Concept: "Backfill, reprocess and clear (the three verbs)".
- **Learn first:** [backfill](https://airflow.apache.org/docs/apache-airflow/3.3.2/core-concepts/backfill.html); "The overnight history load" in the "Operations runbook".
- **Do:**
  1. `git status --short` is empty. Then `git tag -a g1-freeze -m "G1: generator and loader frozen"` and `git push origin main g1-freeze`.
  2. Choose the history. The plan is 2026-10-04 to 2026-10-30 (27 runs). If [T] times 27 is more than about 4 hours ([T] above about 9 minutes), use FROM=2026-10-18 instead (cut-order item 4).
  3. Add `make backfill-dry` and `make backfill`.
  4. `make backfill-dry FROM=2026-10-04 TO=2026-10-30`. It lists the 27 logical dates and creates nothing.
  5. `make backfill FROM=2026-10-04 TO=2026-10-30`
  6. In a second terminal: `caffeinate -is`. Keep the Mac on power with the lid open, and Docker Desktop running.
  7. Watch the first backfill run (2026-10-30) start. Then sleep.
- **You write:** the commands. **Agent may scaffold:** the two Makefile targets.
- **Files:** `Makefile`; the tag `g1-freeze`.
- **Done when:** the UI shows the backfill running, and the 2026-10-30 run is running or green.
- **Traps:**
  - A backfill runs only on an unpaused DAG (it is unpaused since S6.2).
  - There is one backfill per DAG at a time. Never pause the DAG during it.
  - Never edit `dags/`, `src/` or `dbt/` while it runs.
  - `caffeinate -is` stops idle and system sleep on power. It does not stop sleep when the lid closes.
  - At 05:00 Astana (00:00 UTC Monday) the scheduler starts the run for 2026-11-01. The backfill must finish before then. The 4-hour rule in sub-step 2 ensures it when you start on time; after a late start, choose the shorter history. If the backfill overlaps the run for 2026-11-01, a `dbt_build` can fail its identity test: the `dbt_serial` pool keeps two dbt builds apart, but not a load that lands a new day during a build (see "Two runs overlapped and dbt_build failed" in `docs/specs/airflow_and_docker.md`).
  - From now on, a change to the generator or the loader means a full re-backfill before the proof.
- **Commit:** the tag `g1-freeze`.
- **Failure log:** none expected. Check in the morning (S7.1).

### Explain check M6

Which interval does the run for 2026-10-25 process? Why CronDataIntervalTimetable? What does a CLI trigger process? Why newest first?

**Gate G1** (22:15, hard stop 23:00): if no run is green by 23:00, stop and sleep. See "Gates and kill switches" for Monday's one-hour Airflow fix slot and the host-run fallback.

---

## M7. dbt complete and the mutation check

Monday 08:00-09:15, 1.25 h. **Done when:** all tests are green on the host and in the latest Airflow run, `docs/testing.md` is filled, and the dbt code is frozen.

### S7.1 Check the overnight backfill

- **Clock:** Mon 08:00-08:09 (0.15 h).
- **Goal:** every run from the night is green, and the counts look plausible.
- **Why it matters:** you prove the history is complete before you build on it. Concept: "Backfill, reprocess and clear (the three verbs)".
- **Learn first:** "Watch runs" in the "Operations runbook".
- **Do:**
  1. `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state failed`, then the same with `--state running`.
  2. `docker compose exec airflow-scheduler airflow dags list-runs recon_daily`
  3. In the console: `select _arrival_date, count(*) as n from raw.payment_events group by 1 order by 1`, and the same for `raw.settlement_lines` and `raw.fx_rates`.
  4. When every run is green, commit the FX files the night landed. They are real data, landed once and never fetched again, and a fresh clone needs them to rebuild the window with the same rates. `ls landing/fx/provider=nbk/*.meta.json | wc -l` prints 29 (15 with FROM=2026-10-18). Then `git add landing/fx && git commit -m "chore(fx): land real NBK rates for the backfilled window (S7.1)"`.
- **You write:** the checks.
- **Files:** `landing/fx/provider=nbk/*` (the files landed overnight, committed).
- **Done when:** no failed and no running runs. Every date from 2026-10-04 to 2026-11-01 is `success` (29 runs; 15 runs from 2026-10-18 if you shortened the history). Each raw table has one partition per loaded day, and no day has zero rows. After the FX commit, `git status --short landing/fx` prints nothing.
- **Traps:**
  - If a run failed for an outside reason (network), clear that day: `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s <D> -e <D> -y`.
  - If it failed because of a bug in the frozen code, log it, fix it, tag the fixed commit `g1-freeze-2` (never move or force-push a tag), push it, and re-backfill. That costs the buffer. The proof's frozen-code check then uses `g1-freeze-2`.
  - Start S7.2 only when no run is active.
- **Commit:** `chore(fx): land real NBK rates for the backfilled window (S7.1)`.
- **Failure log:** any failed run, with its cause.

### S7.2 `fct_recon_exceptions`, and its two columns in the daily mart

- **Clock:** Mon 08:09-08:27 (0.3 h).
- **Goal:** the analyst work queue as a view, one row per (line, cause), with no `before_scope` lines; and `exception_count` and `exception_abs_minor` in `fct_recon_daily`.
- **Why it matters:** one line can have two causes, for example an amount difference and a fee overcharge, so the queue has one row per cause with its own signed amount. A view stores nothing. Concepts: "Materializations", "Line statuses, due dates and scope".
- **Learn first:** [materializations](https://docs.getdbt.com/docs/build/materializations); `fct_recon_exceptions` and the exception columns of `fct_recon_daily` in the spec.
- **Do:**
  1. You write `dbt/models/marts/fct_recon_exceptions.sql` (materialized as a view) and its tests in `_marts.yml`.
  2. You add `exception_count` and `exception_abs_minor` to `fct_recon_daily`, from the new view by `cause_date`, with absolute amounts, so offsetting breaks cannot cancel.
  3. `make dbt-build`
- **You write:** all of it.
- **Files:** `dbt/models/marts/fct_recon_exceptions.sql`, `dbt/models/marts/fct_recon_daily.sql`, `dbt/models/marts/_marts.yml`.
- **Done when:** `make dbt-build` ends with `ERROR=0`. In the console, `select cause, count(*) from analytics_dev.fct_recon_exceptions group by 1` shows only exception causes (never `before_scope`, `matched`, `in_transit` or `timing_cutoff`).
- **Traps:** a positive amount means the ledger has more, or the PSP overcharged. Each cause has its own cause date (see the spec). Use `DATE_DIFF` for `age_days`. The key (`payment_id`, `cause`) is unique.
- **Commit:** `feat(dbt): add the fct_recon_exceptions work queue (S7.2)`
- **Failure log:** a sign or date error you found.

### S7.3 Enforce the `fct_recon_daily` contract

- **Clock:** Mon 08:27-08:36 (0.15 h).
- **Goal:** the daily mart has an enforced contract: a `data_type` for every column, and `not_null` on `mid`, `currency`, `recon_date`, `as_of_date` and `unexplained_minor`.
- **Why it matters:** the build fails if the mart's shape drifts. BigQuery enforces only `not_null`, so uniqueness stays a data test. Concept: "Contracts".
- **Learn first:** [model contracts](https://docs.getdbt.com/docs/mesh/govern/model-contracts); [constraints](https://docs.getdbt.com/reference/resource-properties/constraints); the contract column list in the spec.
- **Do:**
  1. An agent scaffolds the column list in `_marts.yml` from the spec. You check every type.
  2. The YAML shape that is easy to get wrong:
     ```yaml
     models:
       - name: fct_recon_daily
         config:
           contract:
             enforced: true
         columns:
           - name: unexplained_minor
             data_type: int64
             constraints:
               - type: not_null
     ```
  3. `make dbt-build`
  4. Commit the contract now, before you break it on purpose: `git add dbt/models/marts/_marts.yml && git commit -m "feat(dbt): enforce the fct_recon_daily contract (S7.3)" -m "written with AI"`.
  5. Prove the contract can fail: change one `data_type` (for example `unexplained_minor` to `string`), run `make dbt-build`, see the contract error, then undo only that file with `git restore dbt/models/marts/_marts.yml` (or edit the one line back).
- **You write:** the check of every type, and the failure test. **Agent may scaffold:** the column list.
- **Files:** `dbt/models/marts/_marts.yml`.
- **Done when:** `make dbt-build` ends with `ERROR=0` with the contract, you saw the deliberate type change fail, and after the undo `git status --short dbt/` prints nothing.
- **Traps:** `NUMERIC` is not `BIGNUMERIC`. Counts are `INT64`. A contract compiles into `create or replace table ... (columns) as select ...`: still DDL, still no DML. Never run `git restore dbt/` while work is uncommitted: it throws away every uncommitted change under `dbt/`, including a contract you have not committed yet.
- **Commit:** `feat(dbt): enforce the fct_recon_daily contract (S7.3)`, ending with the line `written with AI`, made in sub-step 4, before the failure test.
- **Failure log:** a type mismatch the contract caught.

### S7.4 The completeness error test and the two warning gates

- **Clock:** Mon 08:36-08:51 (0.25 h).
- **Goal:** a missing statement file fails the run; a high exception share or a restated FX rate only warns.
- **Why it matters:** missing data is an incident that must stop the run. Many exceptions are business output for an analyst, not a pipeline failure. Concepts: "Data quality checks: integrity gates and business gates", "Data tests: generic, singular and severity".
- **Learn first:** [data tests](https://docs.getdbt.com/docs/build/data-tests) (singular tests and `severity`); the three tests in the spec.
- **Do:**
  1. You write `dbt/tests/assert_arrival_days_complete.sql` (error), `warn_exception_share_7d.sql` and `warn_fx_restated.sql`. Each warning test starts with `{{ config(severity='warn') }}`.
  2. `make dbt-build`
- **You write:** all three.
- **Files:** `dbt/tests/assert_arrival_days_complete.sql`, `dbt/tests/warn_exception_share_7d.sql`, `dbt/tests/warn_fx_restated.sql`.
- **Done when:** `make dbt-build` ends with `ERROR=0`, and each warning test shows PASS or WARN, never ERROR.
- **Traps:** payment events must exist on every day in [scope_start, as_of]; statement lines on every day in (scope_start, as_of]. The statement interval is open at the start because on the first loaded day a MID can rightly have no statement lines: the sales they would settle are older than the loaded history. The share needs the minimum count, so one break on about 70 KZT payments cannot trip it. If you are late, cut-order item 2 drops the two warning tests.
- **Commit:** `test(dbt): add the completeness test and two warning gates (S7.4)`
- **Failure log:** a gate that fired for a reason you did not expect.

### S7.5 The mutation check, mutations 1 to 4

- **Clock:** Mon 08:51-09:09 (0.3 h).
- **Goal:** proof that the key tests can fail: each deliberate code mutation turns at least one named test red.
- **Why it matters:** a test that never fails proves nothing. Only after this step may the README say a test "fails when...". Concept: "The mutation check".
- **Learn first:** the mutation-check procedure and the `docs/testing.md` template in the spec; [dbt build](https://docs.getdbt.com/reference/commands/build) (a model is built only if its unit tests pass) and [dbt run](https://docs.getdbt.com/reference/commands/run) (models only, no tests).
- **Do:**
  1. `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state running` and the same with `--state queued` must both show no runs (the `dbt/` folder is mounted into the containers, and `git switch` rewrites it).
  2. `git switch -c mutation-check`
  3. Open the dev shell. For each mutation 1 to 4 from the spec: make the one edit, run `(cd dbt && uv run dbt run --target dev)`, then `(cd dbt && uv run dbt test --target dev)`. If the SQL no longer compiles, the mutation is broken: fix the mutation, not the model. Write down every test that ends in FAIL or ERROR, from the summary at the end of the output or from `dbt/target/run_results.json`. Then revert with `git checkout -- <file>`.
  4. `git switch main && git branch -D mutation-check`
  5. On `main`, write `docs/testing.md` from the template: mutation, file, expected red, observed red, result.
  6. `make dbt-build` once more on `main`. It is green, and `analytics_dev` is clean again.
- **You write:** the mutations, the observations and `docs/testing.md`.
- **Files:** `docs/testing.md` on `main`; the mutations touch `dbt/` only on the scratch branch and are never committed.
- **Done when:** `docs/testing.md` has 4 rows, each with at least one of its expected red tests observed red, and `main` is green.
- **Traps:**
  - Never run a mutation with `make dbt-build`. `dbt build` does not materialize a model whose unit test fails, so a mutation that also breaks UT2 (mutations 1 and 4 do) would leave the old tables in place, and the identity tests would pass on them. `dbt run` skips unit tests and builds the mutated model.
  - Never commit a mutation.
  - Record what you observed, not what you expected. If a mutation stays green, that is a finding: log it and add the missing test.
  - Observed red tests can be more than the expected ones (mutation 1 also turns UT2 red): record all of them. A mutation counts as caught only when at least one of its expected tests is red (the rule under "Mutation check" in `docs/specs/dbt_project.md`), and N2's [K] of [K] counts caught mutations.
- **Commit:** `docs(docs): record mutation checks 1 to 4 (S7.5)`
- **Failure log:** a mutation that stayed green.

### S7.6 Rebuild the latest marts with the final dbt code

- **Clock:** Mon 09:09-09:15 (0.1 h).
- **Goal:** the marts in `analytics` built by the final dbt code.
- **Why it matters:** the overnight runs used Sunday's dbt code. The proof must compare the outputs of one frozen code version. Clearing a task reruns it inside an existing run. Concepts: "Backfill, reprocess and clear (the three verbs)", "Clear and rerun".
- **Learn first:** "Clear and rerun a day" in the "Operations runbook".
- **Do:** `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s 2026-11-01 -e 2026-11-01 -t dbt_build -y`, then wait for it to finish.
- **You write:** the command.
- **Files:** none.
- **Done when:** `dbt_build` for 2026-11-01 is green again in the UI, and `ls -l runs/dbt/2026-11-01/target/run_results.json` shows a fresh time.
- **Traps:** from here until the proof ends, the dbt code is frozen.
- **Commit:** none.
- **Failure log:** a test that passed on the host but failed in Airflow. That points to a difference between the two datasets.

### Explain check M7

What does each mutation prove? Why is the exception share a warning and the identity an error?

---

## M8. Rerun proof

Monday 09:15-10:00, 0.75 h. **Done when:** `compare.json` shows every group identical, or a real bug was logged and fixed and the proof run again.

### S8.1 `scripts/prove_idempotency.py`

- **Clock:** Mon 09:15-09:33 (0.3 h).
- **Goal:** a script that fingerprints every (table, partition) group in the raw tables and the mart tables, and compares two snapshots.
- **Why it matters:** "rerunning changes nothing" becomes a measured fact, checked by row hashes. Concepts: "Idempotency", "The fingerprint proof".
- **Learn first:** [FARM_FINGERPRINT](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/hash_functions); [TO_JSON_STRING](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/json_functions); [BIT_XOR](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/aggregate_functions); [BIGNUMERIC](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/data-types); "The idempotency proof" in the "Operations runbook" of `docs/specs/airflow_and_docker.md`.
- **Do:**
  1. You write the fingerprint query (the query shape in the spec: COUNT, BIT_XOR and the BIGNUMERIC SUM per partition) and the comparison logic.
  2. An agent scaffolds argparse and JSON IO: `snapshot --out --from --to` and `compare --before --after --out`, plus the options `--raw-dataset` (default `raw`) and `--marts-dataset` (default `analytics`).
  3. `snapshot` also records `as_of_date` from `<marts>.stg_recon__as_of`. `compare` prints one summary line and exits non-zero on any changed group or a changed `as_of`.
  4. Add `make snapshot`, `make compare`, `make reprocess` and `make clear-day`.
  5. Test it: two snapshots of a short range one after the other, written to `$TMPDIR`, then `compare`.
- **You write:** the SQL and the comparison. **Agent may scaffold:** argparse and JSON IO.
- **Files:** `scripts/prove_idempotency.py`, `Makefile`.
- **Done when:** the test compare says identical and `echo $?` prints `0`.
- **Traps:**
  - BIT_XOR alone cancels identical pairs of rows; that is why COUNT and the SUM are kept too.
  - Every query sets `maximum_bytes_billed`.
  - The JSON never contains the project id.
  - The script reads `raw` and `analytics` by default, even though the Makefile sets `RAW_DATASET=raw_dev` for development commands.
  - Test snapshots go to `$TMPDIR`, never into `docs/evidence/`.
- **Commit:** `feat(scripts): add the fingerprint snapshot and compare (S8.1)`, ending with the line `written with AI`.
- **Failure log:** a fingerprint that differed for a reason you did not expect.

### S8.2 Run the proof

- **Clock:** Mon 09:33-10:00 (0.45 h). Write S9.1 while the reprocess runs.
- **Goal:** N1 measured: reprocessing finished days, and re-running one older day out of order, changes nothing.
- **Why it matters:** "reprocess" reruns finished days, "clear" reruns the tasks of one existing run, and both must leave every partition byte-identical. Concepts: "The fingerprint proof", "Backfill, reprocess and clear (the three verbs)".
- **Learn first:** the procedure in "The idempotency proof" in the "Operations runbook".
- **Do (all inside one UTC day; Monday morning is safe, because the next UTC day starts at 05:00 Tuesday Astana):**
  1. Frozen code: `git status --short` is empty, and `git diff --stat <the latest freeze tag, normally g1-freeze> -- src/recon/generator.py src/recon/config.py src/recon/world.toml src/recon/load.py src/recon/fx.py src/recon/schemas dbt/seeds/mids.csv` prints nothing.
  2. Nothing running: `docker compose exec airflow-scheduler airflow dags list-runs recon_daily --state running` and the same with `--state queued` show no runs, and the run for 2026-11-01 is `success`. The DAG stays unpaused.
  3. `make snapshot OUT=docs/evidence/2026-11-02/fp_before.json FROM=2026-10-03 TO=2026-11-01`
  4. Dry run first: `docker compose exec airflow-scheduler airflow backfill create --dag-id recon_daily --from-date 2026-10-26 --to-date 2026-11-01 --reprocess-behavior completed --max-active-runs 1 --dry-run`. It lists 7 dates.
  5. `make reprocess FROM=2026-10-26 TO=2026-11-01`. While it runs, write `scripts/results.py` (S9.1).
  6. When all 7 runs are green: `make clear-day DAY=2026-10-14`.
  7. When it is green: `make snapshot OUT=docs/evidence/2026-11-02/fp_after.json FROM=2026-10-03 TO=2026-11-01`.
  8. `make compare BEFORE=docs/evidence/2026-11-02/fp_before.json AFTER=docs/evidence/2026-11-02/fp_after.json`
  9. Commit the three evidence files.
- **If the history is shorter** (cut-order item 4), keep the older day inside the loaded history and outside the reprocess range:

  | History loaded | Reprocess | Older day to clear |
  |---|---|---|
  | 2026-10-04 to 2026-11-01 (planned) | 2026-10-26 to 2026-11-01 | 2026-10-14 |
  | 2026-10-18 to 2026-11-01 | 2026-10-26 to 2026-11-01 | 2026-10-20 |
  | 2026-10-25 to 2026-11-01 | 2026-10-30 to 2026-11-01 | 2026-10-26 |

  If [T] times 8 is more than about 45 minutes, reprocess 3 days (2026-10-30 to 2026-11-01) instead of 7. That is also cut-order item 4.
- **You write:** the runs and the checks.
- **Files:** `docs/evidence/2026-11-02/fp_before.json`, `fp_after.json`, `compare.json`.
- **Done when:** `compare` prints `[P] of [P] (table, partition) groups identical, [R] rows, as_of [A] in both` with your measured values and exits 0, and `docs/evidence/2026-11-02/compare.json` exists.
- **Traps:**
  - Never pause the DAG during the proof. Never edit code during it.
  - The snapshot range starts on 2026-10-03, one day before the world start, because USD accounting dates can fall there.
  - A non-zero compare is a finding, never something to hide: log it, fix the root cause, and run the whole procedure again.
  - Never edit evidence files by hand.
- **Commit:** `docs(docs): add the rerun-proof evidence of 2026-11-02 (S8.2)`
- **Failure log:** a changed group, its cause and the fix.

### Explain check M8

What do the fingerprints compare? What would a `_loaded_at` column do to the proof? Why must `as_of` match in both snapshots?

---

## M9. Results and the real-data number

Monday 10:00-10:45, 0.75 h. **Done when:** `docs/evidence/2026-11-02/summary.json` holds N1 and N2, and N3 if it was measured.

The three numbers, with their exact definitions. Any number you quote outside this repo comes only from `summary.json`.

| # | Results-table wording (brackets filled from your run) | Exact definition |
|---|---|---|
| N1 | "Reprocessed [D] days and re-ran 1 older day out of order: [P] of [P] partitions identical ([R] rows fingerprinted)." | P = (table, partition) groups across the 3 raw tables (per `_arrival_date`) and the 2 mart tables (per `recon_date`) in the window; identical = same COUNT, BIT_XOR and BIGNUMERIC SUM before and after, with the same `as_of` in both; D = logical dates in the reprocess; R = the sum of COUNT over all groups |
| N2 | "[M] MID-days reconciled with [U] minor units unexplained: each MID-day's revenue-minus-statement gap equals the sum of its dated reason codes, computed two independent ways. [K] of [K] deliberate code mutations turned a test red." | M = rows of `analytics.fct_recon_daily` as of [A]; U = `SUM(ABS(unexplained_minor))`. Use the claim only if U = 0 and the latest run's `assert_recon_decomposition_closes` passed. K comes from `docs/testing.md` |
| N3 | "Real NBK rates: on [W] of [C] weekend and holiday days, carrying the last weekday rate forward differed from NBK's own published rate by up to [X] KZT per USD ([Y] bps); weekday rates agreed exactly on [E] of [E] days." | Over KZT days d in [scope_start, as_of]: C = days with no Frankfurter row dated d; W = those where the carried-forward rate differs from NBK RSS for d; X = the largest absolute difference; Y = X divided by the NBK rate, times 10,000, one decimal; E = days with a Frankfurter row, all of which must equal NBK RSS |

If the G1 host-run fallback was used, N1 says "re-ran [D] days from the command line".

### S9.1 `scripts/results.py` and `scripts/storage.py`

- **Clock:** Mon 10:00-10:15 (0.25 h). Most of it is written during S8.2's waiting time.
- **Goal:** one `summary.json` with N1 and N2 and the context to reproduce them, and a `storage.json` with the stored bytes per dataset.
- **Why it matters:** every number in the README comes from a file written by a command, with a date and a git SHA. N2 states exactly what the identity proves, and nothing more. Concepts: "The two-calendar bridge and the identity (and why it is not a tautology)", "Metric definitions".
- **Learn first:** [INFORMATION_SCHEMA.TABLE_STORAGE](https://docs.cloud.google.com/bigquery/docs/information-schema-table-storage); [cost controls](https://docs.cloud.google.com/bigquery/docs/best-practices-costs).
- **Do:**
  1. You write the queries in `results.py`: the N2 query on `<marts>.fct_recon_daily` (row count, `SUM(ABS(unexplained_minor))`, `COUNTIF(unexplained_minor != 0)`, first and last day, `MAX(as_of_date)`); N1 read from `compare.json`; K counted from `docs/testing.md`; the result of `assert_recon_decomposition_closes` read from a dbt `run_results.json`: the file given with the option `--run-results PATH`, or by default the most recently written `runs/dbt/*/target/run_results.json`, which belongs to the DAG build that made the current marts (after S8.2, the cleared run for 2026-10-14); plus the seed, the world start, the window, `as_of`, `git rev-parse HEAD` and the date.
  2. You write the query in `storage.py`: sizes from `<dataset>.__TABLES__` (and from `TABLE_STORAGE` if probe P7 found it readable), written to the file given with `--out`, by default `docs/evidence/<UTC date>/storage.json`.
  3. An agent scaffolds the file IO and the two options. Add `make results` and `make storage` as in "Make targets: what each runs, and the step that adds it".
  4. Commit your code first, so the SHA the script records is the code that ran. Then `make results` and `make storage OUT=docs/evidence/2026-11-02/storage.json`.
- **You write:** the queries and the rules. **Agent may scaffold:** the file IO.
- **Files:** `scripts/results.py`, `scripts/storage.py`, `Makefile`, `docs/evidence/2026-11-02/summary.json`, `docs/evidence/2026-11-02/storage.json`.
- **Done when:** both targets exit 0. `python3 -m json.tool docs/evidence/2026-11-02/summary.json` shows the N1 and N2 values, the seed, the world start, the window, `as_of` and the git SHA. In the dev shell, `grep -c "$GCP_PROJECT" docs/evidence/2026-11-02/*.json` prints `0` for every file.
- **Traps:** the mutation clause of N2 is used only because S7.5 ran. Bytes are never a headline number: at this size the 10 MB minimum per query dominates.
- **Commit:** `feat(scripts): write summary.json and storage.json (S9.1)`, ending with the line `written with AI`. Then `docs(docs): add the results of 2026-11-02 (S9.1)`.
- **Failure log:** a number that did not match what you expected, and why.

### S9.2 `scripts/fx_report.py` (N3; cut-order item 1)

- **Clock:** Mon 10:15-10:45 (0.5 h).
- **Goal:** N3: how far the weekend carry-forward is from NBK's own published rates, with weekday agreement checked exactly.
- **Why it matters:** it is the only number from real data, and the check can fail. Concept: "FX rates, direction, cross rates and the carry-forward".
- **Learn first:** [ElementTree](https://docs.python.org/3.13/library/xml.etree.elementtree.html); [decimal](https://docs.python.org/3.13/library/decimal.html); the NBK RSS format in `docs/specs/data_and_generator.md`.
- **Do:**
  1. For each calendar day d in [scope_start, as_of]: if `landing/fx/provider=nbk_rss/rate_date=YYYY-MM-DD.xml` exists, use it. Otherwise request `https://nationalbank.kz/rss/get_rates.cfm?fdate=DD.MM.YYYY` once, never for a d on or after today (UTC), and save the XML at that path.
  2. Check that the XML `<date>` echoes d and that the USD `<quant>` is 1. Parse `<description>` with `Decimal`.
  3. You write the comparison with `units_per_usd` from `analytics.int_fx__usd_rates_daily`. On weekdays the two must be equal, or the script exits non-zero. Weekend and holiday gaps are measured for N3.
  4. Write `docs/evidence/2026-11-02/fx_report.json`. Add `make fx-report`.
  5. Run `make fx-report`, then `make results` again so `summary.json` includes N3.
- **You write:** the comparison and the N3 rules. **Agent may scaffold:** the fetch and the XML parsing.
- **Files:** `scripts/fx_report.py`, `Makefile`, `landing/fx/provider=nbk_rss/rate_date=*.xml` (committed), `docs/evidence/2026-11-02/fx_report.json`.
- **Done when:** `make fx-report` exits 0, `fx_report.json` is written, the XML files are committed, and `summary.json` holds N3.
- **Traps:** NBK returns its latest rate for future dates, which is why the date-echo check exists. Never parse a rate as a float. One request per day, one at a time, each with a timeout. The carry-forward count is not a headline: it mostly counts weekends. If N3 is not done by 14:30, drop it (cut-order item 1).
- **Commit:** `feat(fx): add the NBK RSS weekend cross-check (S9.2)`, then `docs(docs): add the FX report of 2026-11-02 (S9.2)`.
- **Failure log:** a weekday disagreement is a real-data finding. Log it before you change any code.

### Explain check M9

Which numbers are synthetic and which are real? Why is the carry-forward a convention?

---

## M10. Publish (gate G2)

Monday 11:00-12:30, 1.5 h. **Done when (gate G2, 12:30):** the repo is public, tagged `v1.0`, a clean clone passes, and there are no banned names and no secrets.

### S10.1 The README first screen and sections

- **Clock:** Mon 11:00-11:36 (0.6 h).
- **Goal:** a first screen that is true, with measured numbers only.
- **Why it matters:** reviewers read the first screen and little else. Concept: "Words I use and words I never use"; the honesty rules are in `AGENTS.md`.
- **Learn first:** the README skeleton (its first-screen order and its sections); [Mermaid on GitHub](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams).
- **Do:**
  1. You write every README sentence from the skeleton, in its order. Copy numbers only from `summary.json`. Delete any results row without a measured value.
  2. You write the two saved demo queries: `dbt/analyses/exceptions_queue.sql` (the open work queue from `fct_recon_exceptions`, oldest and largest first) and `dbt/analyses/one_mid_day_bridge.sql` (one MID-day's gap and its dated components from `fct_recon_daily`). Their shapes are in "Saved analyses (`dbt/analyses/`)" in `docs/specs/dbt_project.md`.
  3. Compile them against the Airflow dataset (compiling writes nothing to BigQuery): `(cd dbt && uv run dbt compile --select exceptions_queue one_mid_day_bridge --target airflow)` in the dev shell. Paste the compiled `exceptions_queue` SQL from `dbt/target/compiled/` into the console, run it, and take the screenshot `docs/img/exceptions_queue.png`. Take `docs/img/airflow_grid.png` from the Grid view.
  4. Fill "How I used AI" and "What this does not prove" from the skeleton.
- **You write:** all text.
- **Files:** `README.md`, `dbt/analyses/exceptions_queue.sql`, `dbt/analyses/one_mid_day_bridge.sql`, `docs/img/exceptions_queue.png`, `docs/img/airflow_grid.png`.
- **Done when:** `grep -nE '<!--|\[WRITE|\[[A-Za-z]{1,8}\]([^(]|$)' README.md` prints nothing (the README skeleton's own check, see "Evidence and placeholders": no FILL comment, no `[WRITE: ...]` marker and no placeholder left), every number in the README is in a file under `docs/evidence/`, and the banner line matches the skeleton word for word.
- **Traps:** the BigQuery console shows your project id in its header and in table paths: crop it out of every screenshot. Never "production", "accuracy", "real-time" or "scalable". Label synthetic and real data where the skeleton says.
- **Commit:** `docs(repo): write the README first screen from evidence (S10.1)`
- **Failure log:** none expected.

### S10.2 ADR-0001 to 0003 in your words; the failure log complete

- **Clock:** Mon 11:36-11:54 (0.3 h).
- **Goal:** three accepted decisions written by you, and a failure log with no gaps.
- **Why it matters:** an ADR you can defend is evidence; a pasted one is a risk in any interview. There is no concepts.md heading.
- **Learn first:** the three drafts in `docs/adr/`.
- **Do:**
  1. Rewrite ADR-0001, 0002 and 0003 in your own words. Change their status to Accepted, and update the index in `docs/adr/README.md`. ADR-0004 to 0010 stay Proposed.
  2. Read `docs/failure_log.md`: every entry has a symptom, a cause and a fix.
- **You write:** all of it.
- **Files:** `docs/adr/0001-warehouse-bigquery-sandbox.md`, `docs/adr/0002-raw-write-path-and-time-model.md`, `docs/adr/0003-reconciliation-method.md`, `docs/adr/README.md`, `docs/failure_log.md`.
- **Done when:** the three ADRs show Accepted, the index agrees, and no failure-log entry is missing a field.
- **Traps:** ADR text never names an employer or a company.
- **Commit:** `docs(adr): accept ADR-0001 to 0003 in my own words (S10.2)`
- **Failure log:** none.

### S10.3 The clean-clone check

- **Clock:** Mon 11:54-12:09 (0.25 h).
- **Goal:** a stranger's clone installs, tests, parses and builds without any of your local state.
- **Why it matters:** reproducibility is part of the claim. This check writes nothing to BigQuery. There is no concepts.md heading.
- **Learn first:** nothing new.
- **Do:**
  ```sh
  CC="$(mktemp -d)" && cd "$CC"
  gh repo clone bainazarseitek/ledger-vs-statement && cd ledger-vs-statement
  cp .env.example .env                       # fill in GCP_PROJECT and AIRFLOW_UID
  make setup && make check
  (cd dbt && DBT_PROFILES_DIR="$PWD" GCP_PROJECT=ci-dummy RAW_DATASET=raw_dev DBT_KEYFILE=/nonexistent/sa.json uv run dbt parse)
  docker compose build
  cd ~/Developer/ledger-vs-statement && rm -rf "$CC"
  ```
- **You write:** the run.
- **Files:** none in the repo (a temporary folder).
- **Done when:** every command exits 0.
- **Traps:** the clone has no pre-push hook and no keys; that is expected. Never push from the clean clone. `dbt parse` needs the variables to exist, but it never connects.
- **Commit:** none, unless the check found a fix: then `fix(<area>): <what> (S10.3)`.
- **Failure log:** anything that only worked because of your local state.

### S10.4 Name review, public, description, topics, tag `v1.0`

- **Clock:** Mon 12:09-12:30 (0.35 h).
- **Goal:** the repo is public, with commit dates intact, and nothing in it or its history names a banned word or holds a secret.
- **Why it matters:** once public, history is permanent. Concept: "Words I use and words I never use"; the naming rules are in `AGENTS.md`.
- **Learn first:** [gh repo edit](https://cli.github.com/manual/gh_repo_edit).
- **Do:**
  1. Scan with the hook's rules: the file contents, the file paths, every commit message, and the branch and tag names on GitHub.
     ```sh
     sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' ~/.config/lvs/banned_words.txt | grep -v -e '^$' -e '^#' |
       sed -e 's/.*/(^|[^[:alnum:]])&([^[:alnum:]]|$)/' > "$TMPDIR/lvs_words.re"
     git grep -n -I -i -E -f "$TMPDIR/lvs_words.re"; echo "exit=$?"
     git ls-files | grep -n -i -E -f "$TMPDIR/lvs_words.re"; echo "exit=$?"
     git log --all --format=%B | grep -n -i -E -f "$TMPDIR/lvs_words.re"; echo "exit=$?"
     git ls-remote --refs origin | cut -f2 | grep -n -i -E -f "$TMPDIR/lvs_words.re"; echo "exit=$?"
     git log --all --oneline -- keys .env
     rm "$TMPDIR/lvs_words.re"
     ```
  2. Run the README check from "Evidence and placeholders" once more: it prints nothing. Read by eye: `README.md`, every file in `dbt/seeds/`, every file in `docs/`, and `git log`. Then re-check nationalbank.kz for terms, because `landing/fx/` commits NBK rates ("Licences" in `docs/specs/data_and_generator.md`). If NBK now publishes terms, follow them in the README's "Licence" section and commit before step 3. If they forbid sharing the files, stop before step 4.
  3. `git tag -a v1.0 -m "v1.0: call-ready floor"` (or `v0.9-call-ready` if the floor was cut), then `git push origin main v1.0`.
  4. `gh repo edit --visibility public --accept-visibility-change-consequences`
  5. `gh repo edit --description "Daily revenue vs settlement-statement reconciliation per merchant account. Airflow 3 + dbt on the BigQuery sandbox, no DML. Synthetic payments, real NBK exchange rates. Learning project."`
  6. `for t in reconciliation payments bigquery dbt airflow data-engineering data-quality idempotency fx-rates; do gh repo edit --add-topic "$t"; done`
  7. Open the repo in a private browser window.
- **You write:** the review and the commands.
- **Files:** the tag `v1.0`; the GitHub settings (visibility, description, topics).
- **Done when:** the four scans print `exit=1`, the `keys .env` log prints nothing, and `gh repo view --json visibility,description,repositoryTopics` shows `PUBLIC`, the description and the 9 topics. The tag is on GitHub.
- **Traps:** never rewrite history before going public: the commit dates are evidence. If a scan finds something already pushed, stop and fix it before the visibility change.
- **Commit:** the tag `v1.0` (or `v0.9-call-ready`).
- **Failure log:** anything the review found.

### Explain check M10

What does this project not prove? What did AI write?

**Gate G2** (12:30): if something is not true yet, publish what is true and list the rest as "in progress".

---

## BUF. Protected buffer

Monday 13:00-14:30, 1.5 h. Spend it on debugging first and README polish second, never on new features. If it is unused at 13:30 and nothing is red, U1's `scripts/eval.py` may start on a branch. Nothing unfinished at 14:30 reaches the README.

## FREEZE. Read the first screen as a stranger, then freeze

Monday 14:30-15:00, 0.5 h. This is planned work and counts in the floor's hours. It is not part of the buffer, so debugging never runs into it: at 14:30, stop and start here.

1. Open the public repo in a private browser window. Read the first screen as someone who has never heard of the project.
2. Check every number on it against `docs/evidence/2026-11-02/summary.json`, and every link.
3. Run the "Call-ready checklist (Monday 15:00)".
4. At 15:00 the code is frozen: no code or data changes until after the call. A typo fix in prose is fine if it changes no number.

---

## Gates and kill switches

| Gate | When | Pass | If missed |
|---|---|---|---|
| G0 | Sun 12:00, hard stop 13:00 | Auth works on the host, DML is refused, the write path is chosen | Key blocked: ADC. Decorator loads failed: shard tables. Both write paths failed: Plan B, or stop. See "G0 fallbacks" and "Plan B: the GCP Free Trial" |
| G-skel | Sun 14:15, hard stop 16:00 | `smoke_bigquery` green inside Docker | Stop Docker work at 16:00. Build M3 to M5 on the host as planned. Take one more 1-hour Docker slot before G1 |
| G1 | Sun 22:15, hard stop 23:00 | One `recon_daily` run green end to end; the backfill started | Stop and sleep. Monday 08:00-09:00 is one Airflow fix slot (below) |
| G2 | Mon 12:30 | Public, tagged, clean clone passes, no banned names, no secrets | Publish what is true and list the rest as "in progress" |
| Freeze | Mon 15:00 | The call-ready checklist is all true | Tag `v0.9-call-ready`. The README first screen says exactly what works |

**Monday's Airflow fix slot (only if G1 was missed), 08:00-09:00:**

1. Fix the problem. Make the latest day green: clear the failed runs (`docker compose exec airflow-scheduler airflow tasks clear recon_daily -s <first failed day> -e 2026-11-01 -y`), or `make unpause` if the DAG was never unpaused (on Monday that creates the run for 2026-11-01).
2. Green by 09:00: load 14 days of history, newest first. If 2026-10-31 and 2026-11-01 are both green: `make backfill-dry FROM=2026-10-18 TO=2026-10-30`, then `make backfill FROM=2026-10-18 TO=2026-10-30`. If only 2026-11-01 is green: use `TO=2026-10-31`.
3. While that backfill runs, do S8.1 and S9.1 (scripts only, no dbt edits). Start S7.2 only when no run is active. The buffer shrinks by the time this took. The proof uses the 14-day row of the history table in S8.2.
4. When that backfill has finished, commit the FX files it landed, as in S7.1: `ls landing/fx/provider=nbk/*.meta.json | wc -l` prints 15, then `git add landing/fx && git commit -m "chore(fx): land real NBK rates for the backfilled window (S7.1)"`.
5. Not green by 09:00: switch to the "G1 host-run fallback".

---

## Cut order and the slip rule

**Cut order inside the floor.** When time runs short, drop items from the top, one at a time:

| # | Cut | Saves |
|---|---|---|
| 1 | `scripts/fx_report.py` (N3). The README results table then shows N1 and N2 only | 0.5 h |
| 2 | `warn_exception_share_7d` and `warn_fx_restated` | 0.15 h |
| 3 | The mapped `load_raw` becomes a loop inside one task | 0.1 h |
| 4 | History 28 days, then 14, then 7 (backfill FROM 2026-10-04, then 2026-10-18, then 2026-10-25); reprocess 7 days, then 3, plus the out-of-order day | Wall-clock time |
| 5 | The `fct_recon_exceptions` view becomes the saved query `dbt/analyses/exceptions_queue.sql` | 0.3 h |
| 6 | The `fetch_fx` task becomes a committed, hand-fetched JSON in `landing/fx/` (the FX stays real) | 0.2 h |
| 7 | The fee checks (D5 and B3 stay in the data, but no fee flags). This is a real loss of signal, so it is last | 0.3 h |

**Never cut:** dedup with its key test; the FULL OUTER JOIN matcher with its statuses and dated components; `assert_recon_decomposition_closes` and `assert_no_money_lost_between_layers`; the rerun proof; the synthetic and real labels; keys out of git.

**The slip rule.** T0 is Sunday 10:00 Astana. For each full hour that T0 slips, cut one item from the top of the cut order before you start. A delay of less than an hour is absorbed by the buffer. Every Sunday block, gate and hard stop moves later by the same delay. Monday's times never move (G2 at 12:30, freeze at 15:00), so a late Sunday leaves a smaller Monday buffer. If you reach G1's moved hard stop without a green run, stop and sleep, and use Monday's fix slot.

---

## G0 fallbacks

Each fallback was decided in advance. Record the one you use in ADR-0001 (auth) or ADR-0002 (write path).

| Probe failed | Fallback | Steps it changes |
|---|---|---|
| S1.1: the account must pick an organization, or billing is attached | Use the personal account. Never build on a billed project | S1.1 |
| S1.2: key creation is blocked | ADC: `brew install --cask gcloud-cli`, then `gcloud auth application-default login`; dbt `method: oauth`; mount the ADC file read-only into the containers and drop `key_path` from the connection extras (details in `docs/specs/bigquery_sandbox_and_costs.md` and `docs/specs/airflow_and_docker.md`). About 20-40 minutes | S1.3 profile, S2.2 compose, S2.5 |
| S1.3: `dbt debug` fails | Fix the env vars or the profile. Never bare `dbt` | S1.3 |
| P2: the INSERT succeeded | Billing is on. Stop and check the Billing page | All |
| P3: decorator loads do not replace one partition | Daily shard tables `raw.<table>_YYYYMMDD`, each loaded with WRITE_TRUNCATE as a whole table; dbt sources with identifier `<table>_*` and `_TABLE_SUFFIX` filters; fixed schemas. ADR-0002 records it. If shard loads also fail: Plan B | S2.3 (no partitioned tables), S4.1 (the target is the shard table; an empty day deletes the shard), S5.1 (sources), S8.1 (one group per shard) |
| P4: a wrong-day row is accepted | The loader's own assertion is the guard (already planned) | None |
| P5: the partition delete does not empty the day | The rule becomes "never produce empty partitions", which is true for v1.0 data. Document it | S4.1 |
| P6: a table-level expiration appears | Note it. The 28-day window stays well inside it | None |
| P7: neither storage view is readable | `storage.py` uses the table API: `list_tables`, then `get_table(...).num_bytes` | S9.1 |
| F1: Frankfurter does not answer | Commit a hand-fetched JSON into `landing/fx/` and cut the fetch task (cut-order item 6) | S4.2, S6.1 |

---

## G1 host-run fallback

Use this only if G1 was missed and Monday's fix slot did not make Airflow green by 09:00. The same functions run from the host into `raw_dev` and `analytics_dev`, and the proof scripts read those datasets.

```sh
make days FROM=2026-10-04 TO=2026-11-01         # generate, fetch and load every day into raw_dev
git add landing/fx && git commit -m "chore(fx): land real NBK rates for the loaded window (S7.1)"
make dbt-build                                  # one build over the whole window, target dev
make snapshot OUT=docs/evidence/2026-11-02/fp_before.json FROM=2026-10-03 TO=2026-11-01 RAW_DS=raw_dev MARTS_DS=analytics_dev
make days FROM=2026-10-26 TO=2026-11-01 && make dbt-build      # reprocess 7 days
make day DATE=2026-10-14 && make dbt-build                     # one older day, out of order
make snapshot OUT=docs/evidence/2026-11-02/fp_after.json FROM=2026-10-03 TO=2026-11-01 RAW_DS=raw_dev MARTS_DS=analytics_dev
make compare BEFORE=docs/evidence/2026-11-02/fp_before.json AFTER=docs/evidence/2026-11-02/fp_after.json
make results MARTS_DS=analytics_dev RUN_RESULTS=dbt/target/run_results.json   # no dbt command since the last make dbt-build
make fx-report MARTS_DS=analytics_dev           # cut-order item 1 applies as usual
```

Then:
- In this mode every `make results`, including the second one in S9.2, takes `MARTS_DS=analytics_dev RUN_RESULTS=dbt/target/run_results.json`. Run it after a `make dbt-build`, with no other dbt command in between, so that file holds that build's test results. The DAG's `runs/dbt/` files are missing, or stale from a failed Airflow attempt.
- Do M7 on the host as written, and skip S7.6.
- In N1 write "re-ran [D] days from the command line".
- The README first screen says "Airflow DAG: in progress", and any talk material outside this repo uses the fallback wording.
- Keep the Airflow fix for after the call.

---

## Plan B: the GCP Free Trial

**When:** only if probe P3 and the shard-table fallback both fail, or if the storage quota error appears (`Quota exceeded: Your project exceeded quota for free storage for projects`, RESOURCE_EXHAUSTED). Never because something is slow or new. Never create a second sandbox project instead.

**Eligibility:** you qualify. You have never paid for Google Cloud, Firebase or Google Maps, and never started a trial. The trial happens once per person, so it is not spent lightly.

**Steps** (details in `docs/specs/bigquery_sandbox_and_costs.md`, Plan B; [free trial terms](https://docs.cloud.google.com/free/docs/free-cloud-features)):

1. Sign up for the Free Trial as "Individual", with your own Visa or Mastercard that allows international and recurring payments. Turn any VPN off.
2. If the form asks for a prepayment or refuses the card: stop. Do not try another person's card or account, and do not switch to another warehouse. Record the outcome in ADR-0001 and publish what is true.
3. Create a new project and link it to the trial billing account. Never link or convert the sandbox project.
4. On day 1: keep `maximum_bytes_billed` everywhere (already in the profile and the scripts), and set a [budget alert](https://docs.cloud.google.com/billing/docs/how-to/budgets) (it only alerts). No BigQuery Studio notebooks and no Spark procedures.
5. Never click Activate or Upgrade.
6. Put two dates in your calendar: day 80 (export the evidence) and day 90 (the trial ends; resources stop and are deleted 30 days later).

**What changes in this plan:**

- S1.1: the new project id goes into `.env` and into your private banned-word list.
- S1.2: create `lvs-pipeline` and its key in the new project. Delete the old key in the old project's IAM page.
- S1.4: P2 now succeeds, because a billed project allows DML. That is expected under Plan B: record it in ADR-0001. The code stays DML-free.
- S2.3: run `make bq-setup` in the new project, so every dataset is created fresh.
- The code, the 45-day guard and the window do not change.
- The README banner and one-liner say "a BigQuery Free Trial project (no paid upgrade)" instead of "the BigQuery sandbox". "No DML" still describes the code, but never claim that the platform refuses DML.
- Time: about 1-2 hours. Apply the slip rule from that point.

---

## Call-ready checklist (Monday 15:00)

All must be true. Tag `v1.0`, or `v0.9-call-ready` if the floor had to be cut.

1. The repo is public, with its description and topics. The first screen is true: banner, problem, diagram, and a results table with measured rows only (a row with no measured value is deleted).
2. The pipeline ran green on at least 7 consecutive days of data through Airflow. If G1 failed, it ran from the host CLI and the first screen says "Airflow DAG: in progress".
3. `docs/evidence/2026-11-02/summary.json` holds N1 and N2 (and N3 if measured), with the seed, the world start, the window, `as_of` and the git SHA.
4. The pre-push hook passed on every push, the manual name review is done, and `git log --all -- keys .env` prints nothing.
5. Any number used outside this repo is copied only from `summary.json`.

---

## After the call: R0 (optional), then the upgrades M11 to M17

The upgrades come in a fixed order, 8.75 hours in total. Each ends with a tag, from `v1.1` (U1) to `v1.7` (U7). **The swap rule (the only one):** if your next interview is a data-engineering technical round, build the v1.x Postgres `app_db` watermark extract (about 1.5-2 h, described in `docs/roadmap.md`) in place of U7.

### Before every upgrade session

1. **Work on a branch** named after the upgrade (for example `u1-floor-completion`). Merge it into `main` when its milestone's **Done when** holds, then tag on `main` and push. The hook runs on every push.
2. **Close any gap in the history first.** With catchup off, a stack that was stopped or paused creates only the latest day when it runs again, so days are missing and `assert_arrival_days_complete` fails (that is the test doing its job). List the runs, then load the missing days newest first: `make backfill-dry FROM=<first missing day> TO=<last missing day>`, then `make backfill` with the same dates. Every gap-filling run except the one that closes the gap fails `assert_arrival_days_complete` in `dbt_build` (its loads succeed); that is expected. When the run for the oldest missing day (it runs last and closes the gap) is green, clear `dbt_build` of the latest day, then of those failed runs, newest first (or record them under "Planned red runs (not bugs)").
3. **Mind the window.** `check_window` refuses any day older than 45 days. From 2026-11-19 (UTC), 2026-10-04 is refused, so any step that would re-load the whole window then needs a new one: reset the datasets and move `RECON_WORLD_START` (the `make demo` item in `docs/roadmap.md`). Partitions expire 60 days after their date, so the 2026-10-04 partition goes around 2026-12-03. The v1.0 numbers stay safe in `docs/evidence/2026-11-02/`.
4. **Mind the storage.** Run `make storage` after each upgrade. Until U3 adds the bytes-written ledger, stop at 1 GiB written in total (your own cap; the lifetime sandbox quota is 10 GiB and is not refunded).
5. **New evidence goes into a new dated folder,** `docs/evidence/<date>/`. Never overwrite `2026-11-02`.
6. **Generator changes change the world.** U4 builds a separate held-out world. U6 (the late batch D6) and U7 (a new MID) change the main world's files: the golden hash changes on purpose, say why in the commit, and re-load the affected days in order.
7. **Design first, again.** The specs describe v1.0. For an upgrade they do not cover, write a short design note in the matching spec or ADR and commit it before the code, as you did for the floor.

---

### R0. Study the references (optional, outside the 25 hours)

- **Clock:** optional; after the call, before M11. Time box: 90 minutes in total, outside the 25 hours. You may split it and read each repo just before the upgrade it informs (the last column below). No upgrade depends on it: steps that cite R0 notes work without them.
- **Goal:** see how mature public projects solve the problems you just solved, and take ideas, not code, into the upgrades.
- **Why it matters:** comparing your own design with a senior one is the fastest way to see what you missed, and it gives you honest answers to "how would a team do this?". Concepts: "The two-calendar bridge and the identity (and why it is not a tautology)", "Deduplication with QUALIFY".
- **Learn first:** nothing. This step is the reading.
- **Do:**
  1. Clone each repo shallow, outside the project, and never run anything in it:
     ```sh
     mkdir -p ~/Developer/reference-repos && cd ~/Developer/reference-repos
     git clone --depth 1 https://github.com/fivetran/dbt_stripe.git
     git clone --depth 1 https://github.com/juspay/hyperswitch-reconciliation.git
     git clone --depth 1 https://github.com/dbt-labs/dbt-audit-helper.git
     git clone --depth 1 https://github.com/Velir/dbt-ga4.git
     git clone --depth 1 https://github.com/astronomer/cosmos-ebook-companion.git
     git clone --depth 1 https://github.com/astronomer/astronomer-cosmos.git
     git clone --depth 1 --filter=blob:none --sparse https://github.com/cal-itp/data-infra.git
     git -C data-infra sparse-checkout set warehouse/models/intermediate/payments warehouse/models/mart/payments airflow/dags
     chmod -R a-w ~/Developer/reference-repos
     ```
     `data-infra` is a large monorepo (about 300 MB of history), so it is checked out sparsely: only the folders below, plus the files of their parent folders (which include `warehouse/dbt_project.yml`). `chmod -R a-w` makes the clones read-only on disk; run `chmod -R u+w ~/Developer/reference-repos` before you delete them.
  2. Read these files, and only these. The paths were checked on 2026-11-01. If one has moved, search its repo for the file name.

     | Repo and licence | Read | Look for | Read before |
     |---|---|---|---|
     | `fivetran/dbt_stripe` (Apache-2.0) | `integration_tests/tests/integrity/integrity_balance_transactions.sql`; skim the 15 files in `integration_tests/tests/consistency/`, and read `consistency_payout_itemized_3.sql` and `consistency_ending_balance_reconciliation_itemized_4.sql`; the payout reconciliation models `models/stripe_financial_reports/stripe__payout_itemized_3.sql` and `models/stripe_financial_reports/stripe__ending_balance_reconciliation_itemized_4.sql`; `DECISIONLOG.md`; `models/stripe__subscription_item_mrr_report.sql` | Count and sum preserved between layers (compare with your `assert_no_money_lost_between_layers`); how a payout is itemized against an ending balance (explained vs unexplained); a decision log as an ADR model; the MRR report for the v2 work | M11 (the ADRs), v2 |
     | `cal-itp/data-infra` (AGPL-3.0: read only, never copy) | `warehouse/models/intermediate/payments/int_payments__settlements_deduped.sql`; `warehouse/models/mart/payments/_payments.yml`; `airflow/dags/dbt_all_dag.py` (Airflow 2); `warehouse/dbt_project.yml` | Dedup of a settlement that arrives with two statuses; processor vs acquirer facts with tolerance tests; a production Cosmos DAG; lookback vars that keep development builds small | M16 (U6) |
     | `juspay/hyperswitch-reconciliation` (Apache-2.0) | `ai-docs/domains/reconciliation/ONE-TO-ONE-STRATEGIES.md` | Expected, Posted and Mismatched states; inclusive tolerance boundaries; principal-plus-fees matching | M14 (U4), M17 (U7) |
     | `dbt-labs/dbt-audit-helper` (Apache-2.0) | `macros/compare_relations.sql`; `macros/compare_and_classify_relation_rows.sql`; the examples in `README.md` | Row-level comparison of two relations: a second, independent way to check your fingerprint proof | M13 (U3) |
     | `Velir/dbt-ga4` (MIT) | `models/staging/base/base_ga4__events.sql`; `models/staging/recommended_events/stg_ga4__event_purchase_deduplicated.sql`; the native unit tests in `models/staging/stg_ga4__events.yml`; `.github/workflows/pr.yml`; `scripts/ci/test.sh` | QUALIFY dedup over a canonical key; business-key dedup; unit tests in YAML; secret-free pull-request checks with uv. Never install this package in the sandbox: its incrementals use MERGE | M11 (UT3), M12 (U2) |
     | `astronomer/cosmos-ebook-companion` (no licence: read only, never copy) | `dags/basic_examples_per_dwh/examples_DbtDag/example_DbtDag_bigquery.py`; `dags/advanced_examples/example_inject_dbt_vars.py`; `Dockerfile` | A dbt venv inside an Airflow image; a BigQuery profile mapping; templated dbt vars. Translate `/usr/local/airflow` paths to `/opt/airflow` | The v1.x Cosmos item |
     | `astronomer/astronomer-cosmos` (Apache-2.0) | `docs/guides/dbt_setup/execution-modes-local-conflicts.rst`; `dev/dags/basic_cosmos_dag.py` | Why dbt needs its own venv next to Airflow; not emitting assets on backfill runs | The v1.x Cosmos item |

  3. For each repo, write three bullets in your own words: one idea you will use, one thing you do differently and why, one question it raises. Keep them in your own notes, or in the matching ADR when you accept it.
- **You write:** the notes. **Agent may scaffold:** nothing; an agent may explain a file you are reading.
- **Files:** none in the repo; the clones live in `~/Developer/reference-repos/`.
- **Done when:** seven repos cloned read-only, every listed file read, three bullets per repo written.
- **Traps:**
  - Never run their code: no `pip`, `uv`, `dbt`, `make`, `docker`, `astro` or scripts in those folders. Open them in an editor in restricted mode, and never allow a folder's automatic tasks or environment files.
  - Copy code only from the Apache-2.0 and MIT repos, keep their licence notice, and say where it came from (a comment in the file and a line in the README). AGPL and no-licence repos are read only: take ideas in your own words.
  - Never clone them inside `~/Developer/ledger-vs-statement`.
- **Commit:** none in the project (the clones are not part of it).
- **Failure log:** none.

---

## M11 (U1). Floor completion

1.25 h. **Done when:** UT3 and UT4 were seen red, then green; mutation 5 is recorded; the seeded self-test runs; ADR-0004 to 0007 are accepted. Tag `v1.1`.

### S11.1 UT3 red, then green

- **Clock:** 0.25 h.
- **Goal:** dedup pinned by a unit test: the earliest delivery wins, a tie is broken by `delivery_id`, a delivery after `as_of` is excluded, copies are counted.
- **Why it matters:** generic tests prove uniqueness; only a unit test proves which copy is kept. Concepts: "Deduplication with QUALIFY", "Unit tests versus data tests".
- **Learn first:** UT3 `ut_events_dedup_first_delivery` in `docs/specs/dbt_project.md`; optionally, the unit tests in Velir's `stg_ga4__events.yml` (from R0).
- **Do:** write UT3 from the spec. To see it red, temporarily change the dedup order to `delivered_ts, delivery_id DESC`: the tie on `evt_y` then keeps `dlv_y_2`, so UT3 fails every time. `make dbt-unit` is red; record it in "Planned red runs (not bugs)". Restore the order; `make dbt-unit` is green; `make dbt-build`.
- **You write:** the test. **Agent may scaffold:** nothing.
- **Files:** `dbt/models/_unit_tests.yml`, `docs/failure_log.md`.
- **Done when:** red, then green, and `make dbt-build` ends with `ERROR=0`.
- **Traps:** mock every direct parent, including `stg_recon__as_of` and the source. Never commit the temporary break. Do not make the break by dropping `delivery_id` from the order: with two rows at the same `delivered_ts`, `ROW_NUMBER` may keep either one, so UT3 can stay green by chance and the red run is not honest.
- **Commit:** `test(dbt): add UT3 dedup cases, seen red first (S11.1)`
- **Failure log:** the red run in its "Planned red runs (not bugs)" row.

### S11.2 UT4 red, then green

- **Clock:** 0.3 h.
- **Goal:** the fee boundary is inclusive, one line can carry two causes, and half-up rounding is asserted directly.
- **Why it matters:** an off-by-one at a tolerance boundary is the classic money bug. Concept: "Minor units and integer fee arithmetic".
- **Learn first:** UT4 `ut_lines_fee_boundary_and_two_causes` and the integer fee arithmetic in the dbt spec. Recheck each expected number by hand with `DIV`.
- **Do:** write UT4. To see it red, temporarily change `>` to `>=` in `is_fee_mismatch`; `make dbt-unit` is red; record it in "Planned red runs (not bugs)". Restore; green; `make dbt-build`.
- **You write:** the test.
- **Files:** `dbt/models/_unit_tests.yml`, `docs/failure_log.md`.
- **Done when:** red, then green, and `make dbt-build` ends with `ERROR=0`.
- **Traps:** a variance equal to the tolerance is within it. The gross-1020 line expects `expected_fee_minor = 26` (half-up of 25.5).
- **Commit:** `test(dbt): add UT4 fee-boundary cases, seen red first (S11.2)`
- **Failure log:** the red run in its "Planned red runs (not bugs)" row.

### S11.3 Mutation 5

- **Clock:** 0.1 h.
- **Goal:** proof that UT4 catches a rounding change.
- **Why it matters:** see S7.5. Concept: "The mutation check".
- **Learn first:** mutation 5 in the dbt spec.
- **Do:** the S7.5 procedure, for mutation 5 only. From your upgrade branch, `git switch -c mutation-check`. Change half-up fee rounding to floor in `dbt/models/marts/fct_recon_lines.sql`. In the dev shell, run `(cd dbt && uv run dbt run --target dev)`, then `(cd dbt && uv run dbt test --target dev)`, and write down every test that ends in FAIL or ERROR (UT4 is the expected one). Revert with `git checkout -- dbt/models/marts/fct_recon_lines.sql`. Switch back to your upgrade branch, `git branch -D mutation-check`, then `make dbt-build`. Add the row to `docs/testing.md` on your upgrade branch.
- **You write:** the mutation and the row.
- **Files:** `docs/testing.md`.
- **Done when:** `docs/testing.md` has 5 rows, and `make dbt-build` is green again on your upgrade branch.
- **Traps:** run no Airflow task while `dbt/` is mutated. Never run the mutation with `make dbt-build` (see the S7.5 traps).
- **Commit:** `docs(docs): record mutation 5 (S11.3)`
- **Failure log:** only if UT4 stayed green.

### S11.4 `scripts/eval.py`, `make eval` and the README self-test row

- **Clock:** 0.4 h.
- **Goal:** the seeded self-test: per cause, the raw counts of planted, flagged, TP, FP and FN, scored against an answer key that never enters BigQuery.
- **Why it matters:** you wrote both the defects and the matcher, so this is a self-test, not accuracy. Benign noise that crosses the tolerance makes false alarms possible by design. Concept: "The seeded self-test, and why it is not accuracy".
- **Learn first:** the ground-truth format and the scoring rules in `docs/specs/data_and_generator.md`; ADR-0007 as drafted.
- **Do:** you write the scoring rules. An agent scaffolds the IO. The script regenerates the answer key in memory if the truth files are absent, reads the marts with SELECT queries only, and writes `docs/evidence/<date>/eval.json`. Add `make eval`. Add one README row with the label "Seeded self-test (synthetic, not accuracy)".
- **You write:** the scoring. **Agent may scaffold:** the IO.
- **Files:** `scripts/eval.py`, `Makefile`, `docs/evidence/<date>/eval.json`, `README.md`.
- **Done when:** `make eval` exits 0, and `eval.json` holds raw counts per cause and the number of benign final lines.
- **Traps:** never "accuracy", "precision", "recall" or "detection rate" as a headline. Benign spikes flagged as fee mismatches are false alarms; D5 overcharges within tolerance are misses; both are by design. Score only final lines. Never load the truth into BigQuery.
- **Commit:** `feat(scripts): add the seeded self-test (S11.4)`, ending with the line `written with AI`.
- **Failure log:** a scoring surprise, with its cause.

### S11.5 ADR-0004 to 0007 accepted

- **Clock:** 0.2 h.
- **Goal:** the FX policy, orchestration, dbt-runtime and evaluation decisions in your words.
- **Why it matters:** see S10.2.
- **Learn first:** the four drafts; your R0 notes, if you did R0.
- **Do:** rewrite each in your words; set Accepted; update `docs/adr/README.md`. ADR-0004 may cite N3 from `fx_report.json`. Merge the branch, tag `v1.1`, push.
- **You write:** all of it.
- **Files:** `docs/adr/0004-fx-policy.md` to `docs/adr/0007-evaluation-and-answer-key.md`, `docs/adr/README.md`; the tag `v1.1`.
- **Done when:** the four ADRs show Accepted, and `v1.1` is on GitHub.
- **Traps:** no company or employer names.
- **Commit:** `docs(adr): accept ADR-0004 to 0007 (S11.5)`
- **Failure log:** none.

---

## M12 (U2). CI on GitHub Actions

1.0 h. **Done when:** the CI badge is green, and a deliberately broken branch fails. Tag `v1.2`.

### S12.1 `.github/workflows/ci.yml`

- **Clock:** 0.3 h.
- **Goal:** every push runs `uv sync --frozen`, ruff (with AIR301 and AIR302 on `dags/`) and pytest.
- **Why it matters:** a green badge is a cheap hygiene signal on the first screen. There is no concepts.md heading.
- **Learn first:** [GitHub Actions quickstart](https://docs.github.com/en/actions/get-started/quickstart); [ruff rules](https://docs.astral.sh/ruff/rules/) (the AIR rules); optionally, Velir's `pr.yml` (from R0).
- **Do:** an agent scaffolds the workflow: on push and pull request; `uv sync --frozen`; `uv run ruff check .`; `uv run ruff check --select AIR301,AIR302 dags/`; `uv run pytest`. You read every line.
- **You write:** the review. **Agent may scaffold:** the YAML.
- **Files:** `.github/workflows/ci.yml`.
- **Done when:** the workflow is green on your branch.
- **Traps:** no secrets and no BigQuery in CI. dbt unit tests need a warehouse, so they never run in CI. Actions are free for public repos.
- **Commit:** `ci(ci): add lint and tests (S12.1)`, ending with the line `written with AI`.
- **Failure log:** a CI-only failure, with its cause.

### S12.2 The DAG import test, the loader test and the truth-isolation test

- **Clock:** 0.4 h.
- **Goal:** tests that pin the DAG settings, the loader's partition rules and the answer key's isolation, all without a warehouse.
- **Why it matters:** the DAG's interval semantics are easy to break silently. A test catches a change of timetable, catchup, concurrency or pool. Concept: "Timetables: CronTriggerTimetable vs CronDataIntervalTimetable".
- **Learn first:** [DAG best practices](https://airflow.apache.org/docs/apache-airflow/3.3.2/best-practices.html) (testing DAGs).
- **Do:**
  1. You write `tests/test_dag.py`. It starts with `pytest.importorskip("airflow")`, so the main venv (which has no Airflow) skips it. It asserts a `CronDataIntervalTimetable`, `catchup` False, `max_active_runs` 1, and pool `dbt_serial` on `dbt_build`.
  2. CI runs it in its own venv, because Airflow and dbt cannot share one. Download the constraints file first, then install from the local copy:
     ```sh
     curl -sSfL -o constraints-3.13.txt https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.13.txt
     uv venv .venv-airflow --python 3.13
     uv pip install --python .venv-airflow/bin/python "apache-airflow==3.3.2" pytest --constraints constraints-3.13.txt
     .venv-airflow/bin/python -m pytest tests/test_dag.py
     ```
  3. You write `tests/test_load.py`: the partition assertion and the empty-day delete, with a fake client (no network).
  4. You write the truth-isolation test: the loader's table list excludes `_truth`, and no dbt source points at it.
- **You write:** all assertions.
- **Files:** `tests/test_dag.py`, `tests/test_load.py` (the loader rules and the truth-isolation checks), `.github/workflows/ci.yml`.
- **Done when:** `make test` passes on the host, and CI passes all three.
- **Traps:** import the DAG file by path. Keep the fake client tiny: record the calls, return the row counts.
- **Commit:** `test(tests): pin DAG settings, loader rules, truth isolation (S12.2)`
- **Failure log:** a setting the test found wrong.

### S12.3 `dbt parse`, the secret check, the badge

- **Clock:** 0.3 h.
- **Goal:** CI also parses the dbt project and fails on a committed secret; the README shows the badge.
- **Why it matters:** parsing catches broken YAML and refs without a warehouse. Concept: "Artifacts: manifest.json and run_results.json".
- **Learn first:** [dbt deps](https://docs.getdbt.com/reference/commands/deps).
- **Do:**
  1. In CI: `uv run dbt deps --project-dir dbt`, then `DBT_PROFILES_DIR=dbt GCP_PROJECT=ci-dummy RAW_DATASET=raw_dev DBT_KEYFILE=/nonexistent/sa.json uv run dbt parse --project-dir dbt`.
  2. The secret check: `test -z "$(git ls-files keys .env)"`, and `! git grep -n -I '"private_key"' -- '*.json'` (a service-account key is a JSON file with that field).
  3. Add the badge to the README: `![CI](https://github.com/bainazarseitek/ledger-vs-statement/actions/workflows/ci.yml/badge.svg)`.
  4. Prove it can fail: push a branch `ci-break-test` with a deliberate lint error, see CI red, then `git push origin --delete ci-break-test` and delete it locally.
  5. Merge, tag `v1.2`, push.
- **You write:** the review and the break test. **Agent may scaffold:** the YAML lines.
- **Files:** `.github/workflows/ci.yml`, `README.md`; the tag `v1.2`.
- **Done when:** the badge is green on `main`, and the break-test run was red.
- **Traps:** never put a real key or project id into CI variables.
- **Commit:** `ci(ci): parse dbt, check for secrets, add the badge (S12.3)`
- **Failure log:** none expected.

---

## M13 (U3). Proof and operations hardening

1.0 h. **Done when:** the full-window proof passes, the negative control shows the proof can fail, raw data matches across the two runtimes, runs leave a record, and the no-DML check finds nothing. Tag `v1.3`.

### S13.1 The full-window reprocess and compare

- **Clock:** 0.2 h of your time; the reprocess runs in the background.
- **Goal:** N1 over the whole loaded window, not only the last 7 days.
- **Why it matters:** a bigger proof is stronger evidence. It was kept off Monday's critical path on purpose. Concept: "The fingerprint proof".
- **Learn first:** the procedure in S8.2.
- **Do:** follow S8.2 with FROM = the first loaded day and TO = the latest loaded day, writing to a new dated folder in `docs/evidence/`. Check the window first ("Before every upgrade session", point 3).
- **You write:** the runs.
- **Files:** `docs/evidence/<date>/`.
- **Done when:** compare exits 0, and the new evidence is committed.
- **Traps:** the reprocess takes [T] times the number of days; start it when you can leave it alone.
- **Commit:** `docs(docs): add the full-window rerun proof (S13.1)`
- **Failure log:** a changed group.

### S13.2 The negative control

- **Clock:** 0.2 h.
- **Goal:** proof that the proof itself can fail: a wrong seed must show changes, and the right seed must restore identity.
- **Why it matters:** a check that cannot fail proves nothing, including this one. Concept: "The fingerprint proof".
- **Learn first:** nothing new.
- **Do** (on the host, in the development datasets, so the Airflow datasets stay untouched):
  1. No Airflow run is active (the landing folder is shared).
  2. Reload `raw_dev` with the frozen code: `make days FROM=2026-10-25 TO=2026-10-31 && make dbt-build`. Those days were first loaded in S4.3, before `g1-freeze`, so a generator or loader fix made later would leave them stale and show a false difference.
  3. `make snapshot OUT="$TMPDIR/nc_before.json" FROM=2026-10-25 TO=2026-10-31 RAW_DS=raw_dev MARTS_DS=analytics_dev`
  4. `make day DATE=2026-10-28 RECON_SEED=20261102 && make dbt-build`, then a snapshot to `$TMPDIR/nc_wrong.json`. `make compare BEFORE="$TMPDIR/nc_before.json" AFTER="$TMPDIR/nc_wrong.json"` must exit non-zero. Copy its output at once (the next compare overwrites it): `cp "$TMPDIR/compare.json" docs/evidence/<date>/negative_control_wrong_seed.json`.
  5. `make day DATE=2026-10-28 && make dbt-build`, then a snapshot to `$TMPDIR/nc_right.json`. `make compare BEFORE="$TMPDIR/nc_before.json" AFTER="$TMPDIR/nc_right.json"` must exit 0. Then `cp "$TMPDIR/compare.json" docs/evidence/<date>/negative_control_right_seed.json`.
- **You write:** the runs.
- **Files:** `docs/evidence/<date>/`.
- **Done when:** the wrong seed showed changes, and the right seed showed identity.
- **Traps:** a variable on the `make` command line overrides the value from `.env`. Never run the wrong seed against `raw`.
- **Commit:** `docs(docs): add the negative control (S13.2)`
- **Failure log:** the wrong-seed run is a row in "Planned red runs (not bugs)". A compare that stayed identical with the wrong seed is a real entry: the proof has a hole, so fix it.

### S13.3 The cross-runtime check

- **Clock:** 0.1 h.
- **Goal:** the same raw partitions from the host (`raw_dev`) and from Airflow (`raw`) for the 7 overlapping days, 2026-10-25 to 2026-10-31.
- **Why it matters:** the host and the container run different Python patch versions and different clients. Identical bytes show the generator and loader do not depend on the runtime. Concept: "Idempotency".
- **Learn first:** nothing new.
- **Do:** first reload `raw_dev` with the frozen code, with no Airflow run active: `make days FROM=2026-10-25 TO=2026-10-31 && make dbt-build`. (S4.3 loaded those days before `g1-freeze`; without the reload, a later generator or loader fix would show up as a false difference.) Then add a `--raw-only` option to `scripts/prove_idempotency.py` (the marts differ between the two runtimes, because their windows differ). Snapshot the raw tables for those 7 days with `RAW_DS=raw_dev`, then with `RAW_DS=raw`, and compare.
- **You write:** the option and the run.
- **Files:** `scripts/prove_idempotency.py`, `docs/evidence/<date>/`.
- **Done when:** compare exits 0.
- **Traps:** the comparison ignores dataset names and compares the groups.
- **Commit:** `feat(scripts): compare raw data across runtimes (S13.3)`
- **Failure log:** a difference, with its cause.

### S13.4 `record_run`, the bytes-written ledger, the 8 GiB stop

- **Clock:** 0.4 h.
- **Goal:** each run leaves a record in `runs/daily/<date>.json`; a ledger adds up the bytes each run wrote; `check_window` stops the DAG at 8 GiB.
- **Why it matters:** the lifetime storage quota is metered in a way Google does not document, so assume every byte written counts. Concept: "Bytes processed, bytes billed and maximum_bytes_billed".
- **Learn first:** "The bytes-written ledger (U3, after v1.0)" in `docs/specs/bigquery_sandbox_and_costs.md`; [TriggerRule in the DAG docs](https://airflow.apache.org/docs/apache-airflow/3.3.2/core-concepts/dags.html).
- **Do:** you write a `record_run` task after `dbt_build` with `trigger_rule=TriggerRule.NONE_FAILED`; the ledger, in a new module `src/recon/ledger.py` (one JSON record per write under `runs/ledger/`: the load jobs' `output_bytes` plus the size of every table each build rewrote; the writers are `load_day`, `record_run` and `make dbt-build`); and the 8 GiB stop in `check_window` and in the host commands that call `check_run_date`. The folder comes from a new variable, `RECON_RUNS_DIR`: `$(CURDIR)/runs` in the Makefile header and `/opt/airflow/runs` in `x-airflow-common` of the compose file. The record format, the writers and the stop message are under "The bytes-written ledger (U3, after v1.0)" in `docs/specs/bigquery_sandbox_and_costs.md`.
- **You write:** all of it.
- **Files:** `src/recon/ledger.py` (new), `src/recon/load.py` (`load_day` writes a record), `src/recon/cli.py` (the host stop), `dags/recon_daily.py`, `Makefile`, `docker-compose.yaml`.
- **Done when:** a one-day backfill writes `runs/daily/<date>.json`, and the ledger total grows by that run's bytes.
- **Traps:** never edit the DAG while a run is active. After you add `RECON_RUNS_DIR` to the compose file, run `make down`, then `make up`: containers read their environment only when they are created.
- **Commit:** `feat(dag): record each run and stop at 8 GiB written (S13.4)`
- **Failure log:** a ledger total that did not match `make storage`.

### S13.5 `make no-dml`

- **Clock:** 0.1 h.
- **Goal:** a check that no compiled SQL and no dbt log ever contains DML.
- **Why it matters:** "no DML" becomes a measured claim. Concept: "DDL and DML, and why this project has no DML".
- **Learn first:** ADR-0009 as drafted.
- **Do:** an agent scaffolds the grep: case-insensitive, for `merge into`, `insert into`, `delete from` and `update ... set`, over the compiled SQL and logs under `runs/dbt/` and `dbt/target/`. Accept ADR-0009 in your words. Merge, tag `v1.3`, push.
- **You write:** the ADR. **Agent may scaffold:** the grep.
- **Files:** `Makefile`, `docs/adr/0009-window-and-expiry.md`, `docs/adr/README.md`; the tag `v1.3`.
- **Done when:** `make no-dml` reports 0 matches and exits 0.
- **Traps:** grep the compiled SQL, not your own docs, which mention these words.
- **Commit:** `build(repo): add the no-DML check (S13.5)`, ending with the line `written with AI`.
- **Failure log:** any match, with its cause.

---

## M14 (U4). The held-out world

1.5 h. **Done when:** the held-out evaluation is in the README, with the misses explained. Tag `v1.4`.

### S14.1 The held-out configuration

- **Clock:** 0.4 h. Start only after `v1.3` is tagged: the matcher must be fixed before it meets data it was not designed for.
- **Goal:** a second world with a new seed, doubled defect rates, and four defects the matcher was not built for: H1 duplicate statement line, H2 undeclared deduction, H3 T+3 late settlement, H4 a redelivery whose payload changed.
- **Why it matters:** scoring on a world generated after the code was frozen is the honest answer to "your test grades itself". Concept: "The seeded self-test, and why it is not accuracy".
- **Learn first:** the held-for-later classes in the "Defect catalog", and "Held-out world (U4)", both in `docs/specs/data_and_generator.md`.
- **Do:** you write H1 to H4, each on its own new stream purpose and switched off in the main `world.toml`. The held-out world file `src/recon/world_heldout.toml`, with its own `seed`, turns them on. `RECON_WORLD_FILE` selects it, and the checks in "Held-out world (U4)" stop any command that mixes the two worlds. Add `landing_heldout/` to `.gitignore` and `.dockerignore` before any held-out file exists. Add the datasets `raw_heldout` and `analytics_heldout`, and a third dbt target `heldout` (dataset `analytics_heldout`) to `dbt/profiles.yml`.
- **You write:** all of it.
- **Files:** `src/recon/generator.py`, `src/recon/world.toml`, `src/recon/world_heldout.toml`, `src/recon/config.py`, `src/recon/cli.py`, `tests/test_generator.py`, `dbt/profiles.yml`, `.gitignore`, `.dockerignore`.
- **Done when:** the main world's golden hash still passes; the held-out world generates into `landing_heldout/`; a command with `RECON_WORLD_FILE=world_heldout.toml` but no `RECON_LANDING_DIR` stops before it writes anything; and `git check-ignore landing_heldout/_truth/x` prints the path.
- **Traps:** a new class on an old stream would change the main world.
- **Commit:** `feat(generator): add the held-out world (S14.1)`
- **Failure log:** a main-world change you did not intend.

### S14.2 Load and build the held-out world

- **Clock:** 0.3 h.
- **Goal:** 14 days of the held-out world loaded and built from the host.
- **Why it matters:** the same code path, on data it has never seen. Concept: "The seeded self-test, and why it is not accuracy".
- **Learn first:** nothing new.
- **Do:** select the held-out world as "Held-out world (U4)" in `docs/specs/data_and_generator.md` describes, with three variables on the command line: run `make days FROM=<14 days before yesterday> TO=<yesterday> RECON_WORLD_FILE=world_heldout.toml RECON_LANDING_DIR="$PWD/landing_heldout" RAW_DATASET=raw_heldout`. Then run `(cd dbt && RAW_DATASET=raw_heldout uv run dbt build --target heldout)` in the dev shell.
- **You write:** the runs.
- **Files:** none, unless code changed.
- **Done when:** the build finishes, and the tests that should fail on the unseen defects do fail.
- **Traps:**
  - Every date inside the 45-day guard, ending yesterday (UTC). Never point the held-out run at `raw` or `analytics`.
  - Pass all three variables on every held-out `make` command. Without `RECON_LANDING_DIR`, the held-out files would overwrite the main world's landing files and answer key in `landing/`. The mixing check stops such a command before it writes.
  - Type `"$PWD/landing_heldout"`, never `$(CURDIR)/landing_heldout`. `$(CURDIR)` works only inside the Makefile. In the shell, `$(...)` runs a command, so zsh prints `command not found: CURDIR` and the value becomes `/landing_heldout`.
- **Commit:** none, unless code changed.
- **Failure log:** each failing test and the defect behind it.

### S14.3 Score it and publish the misses

- **Clock:** 0.3 h.
- **Goal:** a README table of planted, caught and missed, with every miss explained.
- **Why it matters:** "caught most, and here is why the rest were missed" is more credible than a perfect score. Concept: "The seeded self-test, and why it is not accuracy".
- **Learn first:** your S11.4 rules.
- **Do:** run `make eval` against the held-out datasets, with the same `RECON_WORLD_FILE=world_heldout.toml` and `RECON_LANDING_DIR="$PWD/landing_heldout"` as S14.2, so it reads the held-out answer key. Write the table: H1 should fail the grain test loudly, H2 the statement arithmetic test, H4 the redeliveries test.
- **You write:** the table and the explanations.
- **Files:** `README.md`, `docs/evidence/<date>/eval.json`.
- **Done when:** the table is in the README, and its numbers come from a new `eval.json`.
- **Traps:** the same vocabulary rules: a seeded self-test, never accuracy.
- **Commit:** `docs(repo): publish the held-out evaluation (S14.3)`
- **Failure log:** a miss you did not predict.

### S14.4 The v1.4 fixes

- **Clock:** 0.5 h.
- **Goal:** handle the duplicate statement line and similar cases, each fix pinned by a unit test seen failing first; ADR-0010 accepted.
- **Why it matters:** fixing after a held-out miss, with a failing test first, is the professional loop. Concept: "Unit tests".
- **Learn first:** your misses from S14.3; the v1.x matching items in `docs/roadmap.md`.
- **Do:** you write the fixes (`settle_rank`, the status `duplicate_in_statement`), each with a unit test seen red first. Accept ADR-0010. Merge, tag `v1.4`, push.
- **You write:** all of it.
- **Files:** `dbt/models/marts/fct_recon_lines.sql`, `dbt/models/_unit_tests.yml`, `docs/adr/0010-synthetic-world-design.md`, `docs/adr/README.md`; the tag `v1.4`.
- **Done when:** the new unit tests were red, then green; `make dbt-build` is green; `v1.4` is on GitHub.
- **Traps:** the held-out world is now known, so do not re-score the same world as if it were new.
- **Commit:** `feat(dbt): handle duplicate statement lines (S14.4)`
- **Failure log:** each red-first run as a row in "Planned red runs (not bugs)".

---

## M15 (U5). The point-in-time snapshot and the completeness curve

1.0 h. **Done when:** one incremental model runs in the sandbox without DML, and the completeness curve is in the README. Tag `v1.5`.

### S15.1 Probe P8

- **Clock:** 0.15 h.
- **Goal:** proof that `insert_overwrite` with `copy_partitions` runs in the sandbox with copy jobs and no MERGE.
- **Why it matters:** this is the only incremental path the sandbox allows. Concepts: "insert_overwrite and copy_partitions", "Copy jobs".
- **Learn first:** "P8 (optional): dbt `copy_partitions` avoids DML" in `docs/specs/bigquery_sandbox_and_costs.md`; [BigQuery configs](https://docs.getdbt.com/reference/resource-configs/bigquery-configs) (`copy_partitions`).
- **Do:** run P8 as the probe table says, if it was not run at G0.
- **You write:** the run.
- **Files:** `docs/adr/0008-materialization-and-incremental.md` (the P8 result).
- **Done when:** `Copying table(s)` appears in the dbt log, and a case-insensitive grep for `merge into` or `insert into` finds 0 lines.
- **Traps:** the dbt docs' `copy_partitions` example also sets `time_ingestion_partitioning`, which uses INSERT. Do not copy it.
- **Commit:** none, or `docs(adr): record probe P8 (S15.1)`.
- **Failure log:** a P8 failure, which sends U5 to its full-rebuild fallback.

### S15.2 `fct_recon_status_daily`

- **Clock:** 0.45 h.
- **Goal:** a daily point-in-time snapshot of every line's status, partitioned by `as_of_date`.
- **Why it matters:** it shows what you knew on each day, the history that dbt snapshots would give, built without MERGE. Concept: "Incremental models and is_incremental()".
- **Learn first:** `copy_partitions` in the [BigQuery configs](https://docs.getdbt.com/reference/resource-configs/bigquery-configs); the config in this step.
- **Do:** you write the model with `materialized='incremental'`, `incremental_strategy='insert_overwrite'`, `partition_by={'field': 'as_of_date', 'data_type': 'date', 'granularity': 'day', 'copy_partitions': true}`, `on_schema_change='fail'`, `full_refresh=false`. It reads only arrivals up to `var('run_date')`, which the DAG passes from `{{ data_interval_start | ds }}`. `as_of_date` is NOT NULL, with a `not_null` test.
- **You write:** the model and the DAG change.
- **Files:** `dbt/models/marts/fct_recon_status_daily.sql`, `dbt/models/marts/_marts.yml`, `dags/recon_daily.py`.
- **Done when:** two daily runs create two partitions, and the build is green.
- **Traps:** a NULL partition value crashes this path (dbt-adapters issue 2086). Never a static `partitions` list. Never `insert_overwrite` without `copy_partitions`. Quote the JSON of `--vars` carefully in the bash command.
- **Commit:** `feat(dbt): add the point-in-time status snapshot (S15.2)`
- **Failure log:** any quoting or partition error.

### S15.3 Verify it and accept ADR-0008

- **Clock:** 0.15 h.
- **Goal:** evidence that the snapshot is DML-free and that reprocessing one old day changes only its own partition.
- **Why it matters:** the incremental claim needs the same rigour as the floor. Concept: "The fingerprint proof".
- **Learn first:** nothing new.
- **Do:** grep `runs/dbt/<date>/logs/dbt.log` for `Copying table(s)` and for `merge into` and `insert into`. Clear one old day; compare fingerprints of the snapshot table before and after. Accept ADR-0008, or record the full-rebuild fallback.
- **You write:** the checks and the ADR.
- **Files:** `docs/adr/0008-materialization-and-incremental.md`, `docs/adr/README.md`, `docs/evidence/<date>/`.
- **Done when:** only the cleared day's partition changed, and ADR-0008 is accepted.
- **Traps:** a reprocess that changes other partitions is a finding, not noise.
- **Commit:** `docs(adr): accept ADR-0008 with the copy_partitions evidence (S15.3)`
- **Failure log:** an unexpected change.

### S15.4 `rpt_settlement_completeness` and the chart

- **Clock:** 0.25 h.
- **Goal:** the share of the booked amount matched by 0 to 5 days after booking, shown as a Mermaid xychart in the README.
- **Why it matters:** it makes "in transit is not missing" visible at a glance. Concept: "Line statuses, due dates and scope".
- **Learn first:** [Mermaid on GitHub](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams).
- **Do:** you write the model and the chart. The chart's numbers come from a dated evidence file. Merge, tag `v1.5`, push.
- **You write:** all of it.
- **Files:** `dbt/models/marts/rpt_settlement_completeness.sql`, `README.md`, `docs/evidence/<date>/`; the tag `v1.5`.
- **Done when:** the chart renders on GitHub, and its numbers are in `docs/evidence/<date>/`.
- **Traps:** a chart is a result: the same evidence rules apply.
- **Commit:** `feat(dbt): add the settlement completeness curve (S15.4)`
- **Failure log:** none expected.

---

## M16 (U6). Statement batches and a late-batch incident

1.0 h. **Done when:** the late-batch gate was seen red, then green. Tag `v1.6`.

### S16.1 `raw.statement_batches`

- **Clock:** 0.3 h.
- **Goal:** one row per MID per arrival date with the control totals: line count, gross, fee, net.
- **Why it matters:** real statements carry headers that must foot to their lines. Concept: "Settlement and the settlement statement".
- **Learn first:** optionally, cal-itp's `_payments.yml` (from R0); the batch and summary rows of the [Adyen settlement details report](https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report/).
- **Do:** you write the schema JSON, the generator output and the loader for the new table.
- **You write:** all of it.
- **Files:** `src/recon/schemas/statement_batches.json`, `src/recon/generator.py`, `src/recon/load.py`, `dags/recon_daily.py` (the mapped table list).
- **Done when:** the table loads one partition per day, like the others.
- **Traps:** the same load protocol: one job per partition, never DML.
- **Commit:** `feat(load): add statement batches with control totals (S16.1)`
- **Failure log:** a batch total that did not match its lines in the generator's own output.

### S16.2 `assert_statement_foots` and the batch-based completeness

- **Clock:** 0.3 h.
- **Goal:** an error test that each batch's totals equal the sum of its lines; completeness judged per batch by due accounting date.
- **Why it matters:** this replaces the v1.0 assumption that every MID settles every day. Concept: "Data quality checks: integrity gates and business gates".
- **Learn first:** `assert_arrival_days_complete` in the dbt spec, the rule you are replacing.
- **Do:** you write the test and the change to `assert_arrival_days_complete`.
- **You write:** all of it.
- **Files:** `dbt/tests/assert_statement_foots.sql`, `dbt/tests/assert_arrival_days_complete.sql`, `dbt/models/staging/` (the new source and its staging model).
- **Done when:** `make dbt-build` is green on the current data.
- **Traps:** the per-batch rule must still catch a missing file.
- **Commit:** `test(dbt): statements must foot to their batch totals (S16.2)`
- **Failure log:** a day the new completeness rule judged differently from the old one, and why.

### S16.3 Plant D6, the late batch

- **Clock:** 0.2 h.
- **Goal:** one MID-day file arrives 3 days late (generator 1.1.0, on its own stream); the gate goes red until it lands, then green.
- **Why it matters:** you see an integrity gate fire on an incident, and recover from it. Concept: "Data quality checks: integrity gates and business gates".
- **Learn first:** D6 in the "Defect catalog".
- **Do:** you write D6. Update the golden hash on purpose and say why in the commit. Re-load the affected days in order, as the spec says.
- **You write:** all of it.
- **Files:** `src/recon/generator.py`, `src/recon/world.toml`, `tests/test_generator.py`.
- **Done when:** the runs before the late batch lands are red, and the run after it is green.
- **Traps:** check the window first. Re-load in order, never mixed.
- **Commit:** `feat(generator): plant the late-batch incident D6 (S16.3)`
- **Failure log:** the red runs go in "Planned red runs (not bugs)". Write a real entry only if the recovery did not go as planned.

### S16.4 The business gate at error level

- **Clock:** 0.2 h.
- **Goal:** a break share above 10%, with the minimum count, fails the run.
- **Why it matters:** the step from "report it" to "stop the line" is a business decision; the minimum count keeps noise from stopping it. Concept: "Data quality checks: integrity gates and business gates".
- **Learn first:** `warn_exception_share_7d` in the dbt spec, the warning version of this gate.
- **Do:** you write the error-level gate. Merge, tag `v1.6`, push.
- **You write:** all of it.
- **Files:** `dbt/tests/` (the error-level gate), `dbt/dbt_project.yml` (its var); the tag `v1.6`.
- **Done when:** the gate passes on normal data. One scratch build with the error threshold set to 0 through `--vars` (in the dev shell, target `dev`) fails on this gate, and the next normal build is green again.
- **Traps:** keep the warning at 2% and the error at 10%. Never change the threshold in `dbt_project.yml` to make a run pass.
- **Commit:** `test(dbt): fail the run on a break share above 10% (S16.4)`
- **Failure log:** a normal day on which the gate fired, and why.

---

## M17 (U7). The cross-currency MID and the tolerance sweep

2.0 h. **Done when:** the identity still closes with an FX component, and the tolerance sweep is in the README. ADR-0004 updated. Tag `v1.7`.

### S17.1 `mid_kzt_usd_01`

- **Clock:** 0.6 h.
- **Goal:** a MID that charges in KZT and settles in USD at a PSP markup on the previous day's NBK rate.
- **Why it matters:** the presentment currency and the settlement currency differ. It is the first question a finance reader asks. Concept: "Presentment currency vs settlement currency".
- **Learn first:** the [Stripe payout reconciliation report](https://docs.stripe.com/reports/payout-reconciliation) (presentment and settlement amounts); ADR-0004.
- **Do:** you write the new MID in the seeds and the generator. `fetch_fx` now runs before `generate_day`, and the generator fails loudly if a rate is missing.
- **You write:** all of it.
- **Files:** `dbt/seeds/mids.csv`, `src/recon/generator.py`, `src/recon/world.toml`, `tests/test_generator.py`, `dags/recon_daily.py`.
- **Done when:** a day generates with the new MID, and a missing rate stops generation with a clear error.
- **Traps:** a new MID changes every day's files, so check the window, update the golden hash on purpose, and re-load in order.
- **Commit:** `feat(generator): add the cross-currency MID (S17.1)`
- **Failure log:** a missing-rate stop on a real day (for example a holiday), and how you handled it.

### S17.2 The FX component

- **Clock:** 0.6 h.
- **Goal:** an FX component per line in INT64 cents, with one rounding stage; the identity extended; the cost of processing in bps.
- **Why it matters:** "how do you know a gap was FX?" gets a measured answer. Concepts: "Minor units and integer fee arithmetic", "The two-calendar bridge and the identity (and why it is not a tautology)".
- **Learn first:** the identity and the dated components in the dbt spec, the parts you extend.
- **Do:** you write the component, the extended identity and the bps metric.
- **You write:** all of it.
- **Files:** `dbt/models/marts/fct_recon_lines.sql`, `dbt/models/marts/fct_recon_daily.sql`, `dbt/models/marts/_marts.yml`.
- **Done when:** `unexplained_minor` is still 0 on every MID-day.
- **Traps:** one rounding stage only; NUMERIC before division; never FLOAT64.
- **Commit:** `feat(dbt): add the FX component to the identity (S17.2)`
- **Failure log:** every time the identity did not close.

### S17.3 NBK RSS as a dbt provider

- **Clock:** 0.4 h.
- **Goal:** NBK's own feed as a second provider inside dbt, with an exact weekday-agreement test.
- **Why it matters:** the weekend policy becomes a decision backed by your measured gap. Concept: "FX rates, direction, cross rates and the carry-forward".
- **Learn first:** ADR-0004; your `fx_report.json`.
- **Do:** you write the provider and the test. Update ADR-0004 with the measured evidence.
- **You write:** all of it.
- **Files:** `dbt/models/staging/` (the NBK RSS source and model), `docs/adr/0004-fx-policy.md`.
- **Done when:** the agreement test passes, and ADR-0004 states which provider is primary on weekends, and why.
- **Traps:** never blend providers in one rate.
- **Commit:** `feat(dbt): add NBK RSS as a second FX provider (S17.3)`
- **Failure log:** a weekday disagreement.

### S17.4 The tolerance sweep

- **Clock:** 0.4 h.
- **Goal:** how false alarms and misses move as the fee and FX tolerance bands change, as a small table and a Mermaid chart.
- **Why it matters:** a tolerance is a trade-off, and the sweep shows it. Concept: "Tolerance".
- **Learn first:** the tolerances in the dbt spec (they live in seeds and vars, so they can be swept).
- **Do:** you write the sweep; the numbers come from a dated evidence file. Merge, tag `v1.7`, push.
- **You write:** all of it.
- **Files:** `README.md`, `docs/evidence/<date>/`, and the sweep query (in `dbt/analyses/` or `scripts/eval.py`); the tag `v1.7`.
- **Done when:** the table and the chart are in the README, and their numbers are in `docs/evidence/<date>/`.
- **Traps:** synthetic data, so label the sweep as a seeded self-test.
- **Commit:** `feat(scripts): add the tolerance sweep (S17.4)`
- **Failure log:** none expected.
