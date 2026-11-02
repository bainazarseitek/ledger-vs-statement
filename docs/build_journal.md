# Build journal

One entry per step of `docs/build_plan.md`, written by the AI agent that built the project in build mode (`AGENTS.md`, heading "Build mode"). Each entry says what was built, how it works, the commands that ran with their real output, what went wrong, and questions an interviewer could ask. The last entry always names the next step.

Steps S0.1 to S3.5 were built on 2026-11-01, before build mode existed. Their entries were written on 2026-11-02 from the commits, the code and the outputs recorded during that session. Synthetic numbers below are design consequences or outputs of this repo's own runs, never results from elsewhere.

## S0.1: Start clean with the `.gitignore` first

**Date and commit:** 2026-11-01, `60a031c` (committed by the owner).

**What was built:**
- `.gitignore`: exactly the 15 lines from `docs/build_plan.md`, "S0.1 Start clean: Docker, the folder, git, `.gitignore`".
- No code and no functions. Sub-steps 1 to 3 (Docker, the folder, `git init -b main`) are owner-only, and the owner did them before the session.

**How it works:**
Git reads `.gitignore` before it stages anything. A path that matches a pattern there is left out of `git add -A` and `git status`. The file went into the very first commit, before any key, `.env` or generated data existed. So the service-account key can never be committed by accident, not even in the first commit.

Secrets come first:

`.gitignore:1`
```text
keys/
```

The landing folder is ignored, except for the real FX files:

`.gitignore:3`
```text
landing/*
```

`.gitignore:4`
```text
!landing/fx/
```

`landing/*` ignores what is inside `landing/` but not the folder itself, so `!landing/fx/` can bring the FX subfolder back. Git cannot re-include a child of a folder that is itself ignored, so writing `landing/` would have silently dropped the FX files as well. That is the trap named in the step. The FX rates are real and stay immutable once they land ("Files you do not touch" in `AGENTS.md`), so they must stay tracked. The generated payments and the answer key in `landing/_truth/` must never be committed ("Honesty, labels and vocabulary", rule 9). The other choice was to add ignore rules later, once the files exist. The step rejects that because one early `git add -A` could put a key into history for good.

**Commands and output:**
- `git config user.email` (sub-step 4): checks which email the commits will carry, since it becomes public along with the repo.
- `git check-ignore keys/sa.json .env landing/_truth/x` printed all three paths.
- `git check-ignore landing/fx/provider=nbk/arrival_date=2026-10-20.json` printed nothing (exit=1). The FX files stay tracked.
- Em dash check `git grep -n --untracked $'\xe2\x80\x94'`: exit=1 (clean).
- `git log --oneline` showed one commit:
  ```text
  60a031c chore(repo): ignore keys, .env and generated data first (S0.1)
  ```

**What went wrong:** Nothing.

**Interview questions:**
1. *Why commit the `.gitignore` before anything else?*
   Ignore rules only protect files that are not yet tracked. If the rules exist before the key does, no command can stage the key by accident. Once a key is in a commit, removing it later does not remove it from history. You have to rotate the key.
2. *Why `landing/*` with `!landing/fx/` instead of `landing/`?*
   Git does not look inside an ignored folder, so a later `!` rule for a child of that folder has no effect. `landing/*` ignores only the folder's contents, so the negation can re-include `landing/fx/`. `git check-ignore` on an FX path printing nothing proves the FX files are still tracked.

## S0.2: The private banned-word list and the pre-push hook

**Date and commit:** 2026-11-01, no commit (nothing in the repo changes).

**What was built:**
- `~/.config/lvs/banned_words.txt`: written by the owner (owner-only, sub-step 2). Its contents are private and were never read.
- `.git/hooks/pre-push`: an exact copy of the hook text in `docs/build_plan.md`, "S0.2 The private banned-word list and the pre-push hook". It lives outside the tracked tree, and `git clone` does not copy it.

**How it works:**
Git runs `.git/hooks/pre-push` before every push. It passes one line per ref on stdin: `local_ref local_sha remote_ref remote_sha`. The hook reads the private list, cleans it, and turns each word into a regex that only matches the whole word. It then scans every outgoing commit: the full file tree, the file paths and the commit message. It also scans the branch or tag name and any annotated tag message. Any match sets `status=1`, and git refuses the push.

It drops blank lines and comments first, because an empty pattern would match every line:

`docs/build_plan.md:325`
```sh
    grep -v -e '^$' -e '^#' > "$words"
```

It fails closed. A missing or empty list blocks the push instead of letting it through:

`docs/build_plan.md:326`
```sh
  if [ ! -s "$words" ]; then
```

On a new branch, every commit not yet on any remote is in scope:

`docs/build_plan.md:344`
```sh
      range="$local_sha --not --remotes"          # new branch: every commit not yet on the remote
```

It scans each commit's whole tree, not only the diff:

`docs/build_plan.md:350`
```sh
      if git grep -n -I -i -E -f "$patterns" "$c" >&2; then
```

Why this approach: it follows "Names" in `AGENTS.md`, rules 2, 3 and 5. The list stays outside the repo, so the hook contains no banned word itself. Each word is wrapped as `(^|[^[:alnum:]])word([^[:alnum:]]|$)`, so `_`, `-`, `.` and `/` separate words. That way a word inside a snake_case name or a branch name is caught too. The hook checks every outgoing commit, so a word that was added and later removed still blocks the push, because history becomes public. The step rejects two alternatives. One is committing the list or a hook that contains the words. The other is relying on a manual check before each push.

**Commands and output:**
- First install: a `sed` command that copied lines 307 to 364 of the plan by number. Running the hook on `main` gave:
  ```text
  .git/hooks/pre-push: line 1: -: command not found
  ```
  and `exit=2`. The hook failed closed and blocked pushes.
- Reinstall: the hook was extracted between its code-fence markers with `awk`. The copy is identical to the plan text, and `sh -n` reported no syntax error.
- Canary test, re-run by the agent on commit `00258c8`:
  ```text
  00258c8e0806d6c887c4feed228450ae021c956c:hook_test.txt:1:zqxwcanary
  pre-push: banned word in the files of commit 00258c8e0806d6c887c4feed228450ae021c956c
  exit=1
  ```
- Run on `main` with the real list: `exit=0`.

**What went wrong:** The first install copied the hook by fixed line numbers (307 to 364). The plan had shifted by two lines since it was first read. The hook file therefore started with two Markdown lines and was missing its last two lines (`fi` and `exit "$status"`). Running it gave `line 1: -: command not found` and `exit=2`. Because the hook fails closed, this could only block pushes. It could not let a word through. The fix was to extract the hook between its code-fence markers instead of by line numbers. See docs/failure_log.md, F-001.

**Interview questions:**
1. *Why scan the whole tree of every outgoing commit, not just the diff of the last one?*
   Pushing makes every commit in the range public, along with every file in it. A word that was added in one commit and deleted in the next is still in history. Scanning only the final tree or the last diff would miss it.
2. *What does "fails closed" mean here, and why does it matter?*
   If the hook breaks (a missing list, an empty list, a bad line, or a syntax error as in F-001), it exits non-zero and git blocks the push. A guard that fails open would let a word through silently whenever it broke. Failing closed turns a hook bug into an annoyance instead of a leak.

## S0.3: The design first, the defect catalog, and the private GitHub repo

**Date and commit:** 2026-11-01, `d2cb9ff` and `231d97e`. Build-mode sync on 2026-11-02: `1d19f1e`.

**What was built:**
- `docs/design.md`: goals, non-goals, sources, architecture, the three dates, the window, costs and risks. Copied from the planning pack.
- `docs/specs/data_and_generator.md`: the simulated business, the generator rules and the pre-registered "Defect catalog". Copied from the planning pack.
- The named planning files from sub-step 5:
  - `README.md`, `AGENTS.md`, `CLAUDE.md`
  - `docs/build_plan.md`, `docs/roadmap.md`, `docs/failure_log.md`
  - `docs/learning/concepts.md`
  - `docs/specs/dbt_project.md`, `docs/specs/airflow_and_docker.md`, `docs/specs/bigquery_sandbox_and_costs.md`
  - `docs/adr/README.md` and the ten `docs/adr/00*.md` drafts
- `LICENSE`: the MIT text with `Copyright (c) 2026 Bainazar Seitek`.
- The private GitHub repo `ledger-vs-statement`, with `origin` set.
- Outside the repo: one row in `~/Developer/learning/projects/README.md`.
- `1d19f1e`: synced `AGENTS.md`, `docs/build_plan.md`, `docs/learning/concepts.md` and the README "How I used AI" note from the pack after the owner switched to build mode.

**How it works:**
The order of commits is the evidence. The first content commit holds only the design and the defect catalog. It comes after the `.gitignore` commit and before any code or matcher SQL. The catalog states the expected outcome of every planted defect. A reviewer can run `git log --reverse` and see that those expectations existed before the matcher.

`docs/specs/data_and_generator.md:760`
```text
**This is the pre-registered catalog.** It is committed in M0, before any matcher SQL exists. The commit order is part of the evidence: it shows the matcher was written to meet the catalog, not the catalog written to fit the matcher's output. After that first commit, the catalog changes only through the table under "Catalog changes after the first commit".
```

`docs/design.md:25`
```text
4. **Honest evidence:** synthetic data labelled, real rates stored as published, the defect catalog committed before any matcher SQL, and every number dated and tied to a `make` target.
```

Before the planning commit, the staged content and the file paths were scanned with the same whole-word regex the hook uses:

`docs/build_plan.md:426`
```sh
     sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' ~/.config/lvs/banned_words.txt | grep -v -e '^$' -e '^#' |
```

Every planning document keeps its first line, which says that the code is the truth where they differ:

`docs/build_plan.md:1`
```text
Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.
```

Why this approach: it follows `docs/build_plan.md`, "S0.3 Design first", and `AGENTS.md`, "Commit style" rule 1. Files were copied by name, never as the whole folder, because the planning pack also holds private files. The step rejects two alternatives. One is writing the catalog after the matcher exists, which would be grading your own homework. The other is copying the whole pack. The repo was created private (`gh repo create ... --private`). Only the owner changes its visibility, at S10.4.

Decision recorded: the owner kept the Google Cloud project id equal to the repo name, because the console created it that way. Since that name is already public, it is deliberately not on the banned-word list: it would block every push. Code still reads the id only from the `GCP_PROJECT` environment variable:

`src/recon/bq.py:12`
```python
    return bigquery.Client(project=os.environ["GCP_PROJECT"], location="US")
```

**Commands and output:**
- After copying `docs/design.md` and `docs/specs/data_and_generator.md`: banned-word scan exit=1 (clean), em dash check exit=1 (clean).
- Design commit: `d2cb9ff docs(repo): add the design and the pre-registered defect catalog (S0.3)`.
- After copying the planning files and writing `LICENSE`:
  - staged-content scan (`git grep ... --cached`): exit=1
  - path scan (`git ls-files | grep ...`): exit=1
  - em dash check: exit=1
  - nothing from `keys/`, `.env`, `runs/` or `logs/` was staged
- Planning commit: `231d97e docs(repo): add the planning documents (S0.3)`.
- `git log --reverse --format='%h %ad %s' --date=iso`, first three lines:
  ```text
  60a031c 2026-11-01 15:29:18 +0500 chore(repo): ignore keys, .env and generated data first (S0.1)
  d2cb9ff 2026-11-01 16:24:08 +0500 docs(repo): add the design and the pre-registered defect catalog (S0.3)
  231d97e 2026-11-01 16:26:43 +0500 docs(repo): add the planning documents (S0.3)
  ```
- `gh repo create ledger-vs-statement --private --source=. --remote=origin --push`: succeeded. The pre-push hook ran on this first push.
- `gh repo view --json visibility -q .visibility`:
  ```text
  PRIVATE
  ```

**What went wrong:** The owner first committed the design with a message that VS Code generated, "Refactor code structure for improved readability and maintainability". That message is vague and does not follow "Commit style". It was amended before any push to `docs(repo): add the design and the pre-registered defect catalog (S0.3)`, which is commit `d2cb9ff`. Amending was allowed because the commit had not been pushed yet. No failure-log entry: nothing failed or gave a wrong result.

**Interview questions:**
1. *How does the commit history prove the tests were not tuned to the answers?*
   The defect catalog is in commit `d2cb9ff`, dated before any code or matcher SQL. Any later change to the catalog needs its own commit that says why. Anyone can check this with `git log --reverse`, and since the history is never rebased or force-pushed, that order cannot be quietly rewritten.
2. *Why is the project id not on the banned-word list, and is that a leak?*
   The id equals the public repo name, so listing it would block every push. It is still never written into code or docs: code reads it from `GCP_PROJECT`, and saved output writes `<project>`. The guard against leaking it is the rule plus the env var, not the hook.

## Explain check M0

**Why is the defect catalog committed before any matcher SQL?**
The commit history then shows that the expected outcome of every planted defect and every benign behaviour was fixed before the matcher existed. In this repo the catalog is in `d2cb9ff`, right after the `.gitignore` commit and before the first code commit, `dbae9d5` (S1.3). Because of that order, the catalog cannot be quietly reshaped to fit what the matcher happens to catch. Any change after that commit goes through the table under "Catalog changes after the first commit" in `docs/specs/data_and_generator.md`, with its own commit and a reason. It is the first defence against "you graded your own homework". The answer key and the self-test results are never used to tune matcher SQL ("Honesty, labels and vocabulary", rule 10).

Next step: S1.1.

## S1.1: Sandbox project and the `probe` dataset

**Date and commit:** 2026-11-01, no commit (owner action).

**What was built:**
- A BigQuery sandbox project with no billing account. The owner did this in the console.
- A dataset `probe` in the `US` multi-region.
- Nothing changed in the repo.

**How it works:**
The sandbox is a Google Cloud project with no billing account linked. Nothing can be billed, so it costs $0. The same rule makes BigQuery refuse DML: `INSERT`, `UPDATE`, `DELETE` and `MERGE`. It also makes every table, view and partition expire after 60 days. These two limits drive the whole design. The rules come from "S1.1 Create the sandbox project (You, about 12 minutes)" in `docs/specs/bigquery_sandbox_and_costs.md` and from ADR-0001 (`docs/adr/0001-warehouse-bigquery-sandbox.md`). The plan rejects two alternatives. One is a billed project, which allows DML but can cost money. The other is a second sandbox project to reset quotas, which the Google Cloud Terms forbid.

The plan's trap says to keep a project id that differs from the repo name. In M0 the owner decided otherwise, so the project id equals the repo name. One effect is in the probe script: `redact()` replaces the project id with `<project>`, so it also replaces the repo name anywhere it appears in saved probe output.

**Commands and output:**
- There are no repo commands. The owner checked three things in the console: the SANDBOX badge, the dataset `probe` (US), and a Billing page with no billing account.

**What went wrong:** Nothing.

**Interview questions:**
- *Why build on a sandbox and not a free trial?* A sandbox has no billing account, so no bill is possible. The cost is a set of hard limits: no DML, 60-day expiry and a lifetime 10 GiB of storage. The project is designed around those limits, and the free trial stays as Plan B.
- *Why must the dataset be in `US`?* Every query, load and dbt target uses `location: US`. A BigQuery job runs in one location, so datasets in two locations could not be joined in one query.

## S1.2: Service account `lvs-pipeline` and its key

**Date and commit:** 2026-11-01, no commit (owner action).

**What was built:**
- The service account `lvs-pipeline`, with two project-level roles: BigQuery Job User and BigQuery Data Editor.
- A JSON key at `keys/sa.json`, mode `600`. Git ignores it.

**How it works:**
A service account is a robot identity. The pipeline runs as `lvs-pipeline`, never as the owner. It gets the least it needs. Job User lets it run query and load jobs. Data Editor lets it create tables and write data. It gets nothing else, so a leaked key cannot change IAM or billing. The key lives only in `keys/`, which `.gitignore` covers from S0.1. `chmod 600` makes it readable only by the owner's user. The steps follow "S1.2 Service account and key (You, about 12 minutes)" and "Key handling rules" in `docs/specs/bigquery_sandbox_and_costs.md`. The alternative is ADC, the owner's own login through `gcloud auth application-default login`. It is kept as the fallback in "G0 fallbacks" in `docs/build_plan.md`, for the case where key creation is blocked.

**Commands and output:**
The agent checked metadata only and never opened the key.
```
$ ls -l keys/sa.json
-rw------- ... keys/sa.json
$ git check-ignore keys/sa.json
keys/sa.json
$ git status --short
(no output)
```
- `~/Downloads` held no JSON file afterwards.

**What went wrong:** Nothing.

**Interview questions:**
- *Why two roles and not BigQuery Admin?* Least privilege. The pipeline only runs jobs and writes data. Admin could also delete datasets and change access, so a leaked key would do far more damage.
- *What do you do if the key leaks?* Delete the key in the console's IAM page, create a new one and move it to `keys/sa.json`. Only the owner may delete or rotate keys (`AGENTS.md`, "Owner-only actions"). The pre-push hook and `make check` exist so a leak through git does not happen.

## S1.3: Host venv, dbt profile and project, `dbt debug`

**Date and commit:** 2026-11-01, `dbae9d5`.

**What was built:**
- `pyproject.toml`: the uv project, not a package. It pins `dbt-core==1.12.6`, `dbt-bigquery==1.12.1` and `dbt-core-experimental-parser==2.0.8`, has the dev group `pytest` and `ruff>=0.13`, and sets `[tool.pytest.ini_options]` with `pythonpath = ["src"]`.
- `uv.lock` and `.python-version` (3.13).
- `.env.example`: the four lines `AIRFLOW_UID`, `GCP_PROJECT`, `RECON_SEED`, `RECON_WORLD_START`.
- `dbt/profiles.yml`: profile `ledger_vs_statement`, with targets `dev` and `airflow`.
- `dbt/dbt_project.yml`, minimal: name, profile, `require-dbt-version` and `flags: send_anonymous_usage_stats: false`.
- `Makefile`: the header and the targets `doctor`, `setup`, `lint`, `check`.
- `.env` (ignored). The owner created it from `.env.example`.

**How it works:**
Two dbt programs exist on this Mac. `~/.local/bin/dbt` is dbt v2, a different engine. The project calls dbt only as `uv run dbt`, which runs the pinned 1.12.6 from the project venv. `make doctor` refuses to pass unless that pinned version answers:

`Makefile:17`
```make
	which -a dbt
```
`Makefile:18-20`
```make
	@v="$$(uv run dbt --version)"; echo "$$v"; \
	echo "$$v" | grep -q -e '- installed: 1.12.6' && echo "$$v" | grep -q -e '- bigquery: 1.12.1' \
	  || { echo "doctor: need dbt-core 1.12.6 and dbt-bigquery 1.12.1 from the project venv" >&2; exit 1; }
```
`which -a dbt` only lists the binaries. Nothing runs the v2 one. (Line 21 of the current Makefile, the `airflow pools get dbt_serial` check, came later in `f7bc8ec`.)

The Makefile header exports host-only paths that never go into `.env`. dbt 1.12 loads `.env` from its working directory, and shell values win over it:

`Makefile:6-7`
```make
export DBT_PROFILES_DIR := $(CURDIR)/dbt
export DBT_KEYFILE := $(CURDIR)/keys/sa.json
```

The profile reads the key path and the project id from environment variables, so neither one is written in a committed file. Every target caps the bytes a query may bill:

`dbt/profiles.yml:7-8`
```yaml
      keyfile: "{{ env_var('DBT_KEYFILE') }}"
      project: "{{ env_var('GCP_PROJECT') }}"
```
`dbt/profiles.yml:15`
```yaml
      maximum_bytes_billed: 1000000000
```

`make check` runs lint and then fails if git tracks `keys/` or `.env`. Today it also runs `test`, which S3.4 added:

`Makefile:34-35`
```make
check: lint test
	@test -z "$$(git ls-files keys .env)" || { echo "check: keys/ or .env is tracked by git" >&2; exit 1; }
```

Why this approach: it follows S1.3 in `docs/build_plan.md`, the profile in `docs/specs/dbt_project.md`, and "Versions and pins" in `AGENTS.md`. It rejects three things: a bare `dbt` call that could pick up v2, `uv init --app` without `--bare` (that would make the repo a package), and usage stats, which would write `dbt/.user.yml` on the first run.

**Commands and output:**
- The owner ran `uv init --bare --python 3.13`, `uv python pin 3.13`, `uv add dbt-core==1.12.6 dbt-bigquery==1.12.1 dbt-core-experimental-parser==2.0.8` and `uv add --dev pytest "ruff>=0.13"`, then created `.env` from `.env.example`.
```
$ make doctor
which -a dbt
~/.local/bin/dbt
...
- installed: 1.12.6
...
- bigquery: 1.12.1
(exit 0)

$ make check
All checks passed!
(exit 0)
```
- `(cd dbt && uv run dbt debug --target dev)`: `dbt/logs/dbt.log` shows `Command dbt debug succeeded`. No `dbt/.user.yml` was created.

**What went wrong:** Nothing.

**Interview questions:**
- *Why does `make doctor` check the version text instead of trusting the lock file?* The lock file says what should be installed. `doctor` checks what actually runs. With two dbt binaries on the machine, a wrong `PATH` could run the other engine quietly, and the grep makes that fail loudly.
- *Why is `maximum_bytes_billed` in the profile when the sandbox is free?* The sandbox has a monthly query quota, and the cap stops one bad query from using it up. A query that would bill more than 1 GB fails before it runs. The same cap is set on every Python query.

## S1.4: Run the G0 probes

**Date and commit:** 2026-11-01, `4bebb6e`. The evidence file was committed later in `03600ec` (see "What went wrong").

**What was built:**
- `scripts/g0_probe.py`, a throwaway probe script:
  - helpers `redact`, `q`, `by_day`, `load_rows`, `row`, `result`, `utc`;
  - one function per probe: `p1`, `p2`, `p3` (with the fallback `shard_check`), `p4`, `p5`, `p6`, `p7`, `f1`;
  - `main` with `--only` and `--plan-b`.
- `Makefile`: the target `probe`.
- `docs/evidence/2026-11-01/g0_probe.json`, written by the script.

**How it works:**
Each probe tests one platform rule with a few KB of data in the dataset `probe`. It returns a record with `PASS` or `FAIL`, a detail line, evidence and the full error text. `main` prints one line per probe and writes everything to `docs/evidence/<UTC date>/g0_probe.json`. Before anything is printed or saved, `redact` removes the service-account email and the project id, because BigQuery error messages contain the request URL and the URL contains the project id:

`scripts/g0_probe.py:28`
```python
    return SA_EMAIL.sub("<sa>", str(text)).replace(PROJECT, "<project>")
```

P2 tries one `INSERT`. It passes only when the insert is refused with the sandbox's exact message:

`scripts/g0_probe.py:99`
```python
    passed = not accepted and DML_REFUSED in text
```

P3 tests the write path the whole loader depends on: a load job with `WRITE_TRUNCATE` into a partition decorator, `table$YYYYMMDD`. It loads the other day first, then file A (2 rows) and file B (1 row) into yesterday's partition. It passes only if yesterday holds file B's one row and the other day is untouched:

`scripts/g0_probe.py:117-118`
```python
        load_rows(f"{T}${Y:%Y%m%d}", [row(Y, 1, "10:00:00"), row(Y, 2, "23:59:59")], SCHEMA)  # file A: 2 rows
        load_rows(f"{T}${Y:%Y%m%d}", [row(Y, 99, "12:00:00")], SCHEMA)                        # file B: 1 row
```

`load_rows` uses the same settings as the real loader: `WRITE_TRUNCATE`, `CREATE_NEVER` and `max_bad_records=0`. P4 loads a row with the wrong date into yesterday's partition and expects a refusal. P5 deletes a partition twice and expects the second delete not to fail. P6 reads the expiry settings. P7 tries two storage sources. F1 makes one Frankfurter request for NBK USD/KZT rates and parses the numbers as text (`parse_float=str`), so no float ever touches a rate. "Yesterday" is the UTC date (`TODAY = dt.datetime.now(dt.UTC).date()`).

Why this approach: it follows "Probe summary", "Script skeleton" and the probe sections under "G0 probes runbook" in `docs/specs/bigquery_sandbox_and_costs.md`. The idea is to test the write path, the DML refusal and expiry before writing any pipeline code. The rejected alternative was to start with the loader and find these limits halfway through the build.

**Commands and output:**
- `make probe`, run at 2026-11-01 15:03 UTC:
```
P1  PASS  CTAS and view ran; view returned [{'x': 1}]
P2  PASS  INSERT refused as expected
P3  PASS  2026-10-31 holds only file B's row; 2026-10-30 untouched
P4  PASS  refused = True, table unchanged = True
P5  PASS  after deleting 2026-10-31: only 2026-10-30 with 1 row
P6  PASS  expirations as expected
P7  PASS  readable: ['__TABLES__']
F1  PASS  HTTP 200, 6 rows for 2026-10-25..2026-10-31
wrote docs/evidence/2026-11-01/g0_probe.json
```
- P6 evidence: location `US`; `default_table_expiration_ms` 5184000000; `default_partition_expiration_ms` 5184000000; `raw_pay` partition expiration 5184000000; `raw_pay` table expires `None`; `probe.t` expires 2026-12-31.
- P7 evidence: `__TABLES__` readable. `TABLE_STORAGE` refused because it "hasn't been enabled for project <project>".
- F1 rates: 2026-10-23 447.94, 10-26 451.05, 10-27 451.05, 10-28 455.63, 10-29 457.09, 10-30 453.71. The 10-23 row is the carry-in: 10-25 is a Sunday, so the latest rate on or before the start date is the Friday rate.
- Redaction check on the JSON: 0 matches for the project id, the service-account email and `private_key`.

**What went wrong:**
- `ruff` flagged two rules. UP017 asked for `datetime.UTC` instead of `timezone.utc`, so the script now uses `dt.UTC`. BLE001 flagged the blind `except Exception` in `main`. It stays on purpose, so that any error becomes a FAIL line and not a crash, and it carries a noqa with the reason: `# noqa: BLE001 (any error is a FAIL, not a crash)` (`scripts/g0_probe.py:252`).
- A staging slip: the evidence file `docs/evidence/2026-11-01/g0_probe.json` went into `03600ec` (the S2.1 Docker commit) and not into an S1.5 commit. Its content is unchanged. No failure-log entry.

**Interview questions:**
- *Why does P3 load the other day first?* To prove that `WRITE_TRUNCATE` on `table$YYYYMMDD` replaces only that one partition and not the whole table. If the second load had wiped 2026-10-30 as well, the decorator path would be unsafe, and the fallback would be daily shard tables.
- *Why load jobs and not `INSERT`?* The sandbox refuses all DML, and P2 proved it. Load jobs are not DML, and with `WRITE_TRUNCATE` per partition they are also idempotent: loading the same day twice leaves the same rows.

## S1.5: Record G0, the write path and the authentication

**Date and commit:** 2026-11-01, `61f9d3b` and `f9dcf5a`.

**What was built:**
- `docs/adr/0001-warehouse-bigquery-sandbox.md`, heading "G0 results": a result for every probe, the P2 text, the write path, the authentication, the notes and the run time. Status stays Proposed.
- `README.md`, heading "Platform constraints (G0 probes)": the result table dated 2026-11-01 and the DML refusal text. `f9dcf5a` removed the `FILL` comment.

**How it works:**
The probe results become decisions through the table "Decision rules at G0" in `docs/specs/bigquery_sandbox_and_costs.md`. The key worked and P1 passed, so authentication is the service-account key. P3 passed, so the write path is one `WRITE_TRUNCATE` load per (table, arrival day) into `table$YYYYMMDD`. P5 passed, so the empty-day rule is to delete the partition. P7 found `__TABLES__`, so that is the storage source. F1 passed, so the FX fetch is a live task. The ADR records it:

`docs/adr/0001-warehouse-bigquery-sandbox.md:55-57`
```
- Write path: decorator loads. Authentication: service-account key.
- Notes: empty-day rule (P5) partition delete; storage source (P7) `__TABLES__`; FX fetch (F1) live task.
- Probes run at: 2026-11-01 15:03 UTC
```
`docs/adr/0001-warehouse-bigquery-sandbox.md:54` holds the P2 text word for word, ending with `; reason: billingNotEnabled`. The README quotes its first line:

`README.md:394`
```
> 403 Billing has not been enabled for this project. Enable billing at https://console.cloud.google.com/billing. DML queries are not allowed in the free tier. Set up a billing account to remove this restriction.
```
Why this approach: a decision written down at G0 is not re-decided late at night (`docs/build_plan.md`, S1.5). The rejected alternatives were daily shard tables (ADR-0002's fallback, needed only if P3 failed) and ADC (needed only if the key was blocked). P8 (dbt `copy_partitions`) was not run. It is optional and off the critical path.

**Commands and output:**
- The redaction check on `docs/evidence/2026-11-01/g0_probe.json`: 0 matches for the project id, the service-account email or `private_key`.
- Done-when check: `git show --stat HEAD` should list `g0_probe.json`. It does not list it for either S1.5 commit, because the file went into `03600ec` (see S1.4).

**What went wrong:**
- The evidence JSON is in `03600ec`, not in an S1.5 commit (the staging slip from S1.4). Content unchanged.
- `README.md:396` still reads `What the results decided: [WRITE: 1-2 sentences: the write path and the authentication you chose, from ADR-0001]`. `f9dcf5a` removed only the `FILL` comment, and the owner's sentence is not in the file yet. It should say that the decision is decorator loads with a service-account key.

**Interview questions:**
- *What would have changed if P3 had failed?* The loader would write one whole table per day (`raw_pay_YYYYMMDD`) and read them with a wildcard and `_TABLE_SUFFIX`. ADR-0002 would record the switch. `shard_check` in the probe script already tested that path, so the fallback was ready.
- *Why keep the ADR at "Proposed"?* The owner accepts ADRs himself, in his own words, at S10.2. The agent fills in facts but never marks an ADR Accepted.

## Explain check M1

**Why can't dbt's default incremental strategy run here?**
On BigQuery, dbt's default incremental strategy is `merge`. It sends a `MERGE` statement, and `MERGE` is DML. The sandbox refuses all DML, as P2 showed with a 403. So this project uses no `merge` incrementals, no `insert_overwrite` without `copy_partitions`, and no snapshots. Raw data arrives through load jobs, and the models are views and small rebuilt tables (ADR-0001, ADR-0008).

**What did the DML refusal say?**
P2's `INSERT INTO probe.t (x) VALUES (2)` was refused with this text: "403 Billing has not been enabled for this project. Enable billing at https://console.cloud.google.com/billing. DML queries are not allowed in the free tier. Set up a billing account to remove this restriction.; reason: billingNotEnabled". It is saved in `docs/evidence/2026-11-01/g0_probe.json` and ADR-0001 under "G0 results". `p2()` passes only when the error contains "DML queries are not allowed in the free tier".

**What happens to a row dated 70 days ago?**
P6 measured a partition expiration of 5184000000 ms, which is 60 days. A partition expires 60 days after its date. A row dated 70 days ago lands in a partition that is already past that limit, so the partition expires at once. The load job reports success, but the row is gone. ADR-0009 adds a guard, `check_window`, that refuses run dates older than today minus 45 days, so the pipeline never writes such a date. It is not in the code yet.

## S2.1: Dockerfile and the dbt venv

**Date and commit:** 2026-11-01, `03600ec`

**What was built:**
- `Dockerfile`: builds on `apache/airflow:3.3.2` and adds a second Python venv at `/opt/airflow/dbt_venv`, used only by dbt.
- `docker/requirements-dbt.txt`: the three dbt pins (`dbt-core==1.12.6`, `dbt-bigquery==1.12.1`, `dbt-core-experimental-parser==2.0.8`).
- `.dockerignore`: keeps `keys/`, `.env`, `landing/`, `runs/`, `logs/`, `.venv/`, the dbt build folders and `.git/` out of the build context.
- The same commit also adds `docs/evidence/2026-11-01/g0_probe.json`, the saved G0 probe results from S1.4.

**How it works:**
The image is the official Airflow image plus one layer. That layer creates a separate venv, installs the dbt pins into it, and runs `dbt --version`. If the install is broken, the build fails at once.

`Dockerfile:5`
```dockerfile
RUN python -m venv /opt/airflow/dbt_venv \
```
`Dockerfile:6`
```dockerfile
 && /opt/airflow/dbt_venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt \
```
`Dockerfile:7`
```dockerfile
 && /opt/airflow/dbt_venv/bin/dbt --version
```

Nothing goes into Airflow's own environment, and the venv is not on `PATH`. The DAGs call dbt by its full path, `/opt/airflow/dbt_venv/bin/dbt`. `.dockerignore` existed before the first build, so the key and `.env` never enter the build context, and so never enter the image.

Why: `docs/specs/airflow_and_docker.md`, "The Dockerfile" and "Why dbt has its own virtual environment", and ADR-0006. The Airflow 3.3.2 constraints pin `google-cloud-storage` 3.14.1 and `pathspec` 1.1.1. dbt-bigquery 1.12.1 needs `google-cloud-storage` below 3.2, and dbt-core 1.12.6 needs `pathspec` below 1.1. The rejected option was downgrading packages inside Airflow's environment, which breaks the version set Airflow was tested with.

**Commands and output:**
```text
$ docker build -t ledger-vs-statement-airflow:3.3.2 .
(the owner ran the build)

$ docker image ls ledger-vs-statement-airflow
ledger-vs-statement-airflow   3.3.2   ...   4.32GB

$ docker run --rm --entrypoint /opt/airflow/dbt_venv/bin/dbt ledger-vs-statement-airflow:3.3.2 --version
  - installed: 1.12.6
  ...
  - bigquery: 1.12.1
```

**What went wrong:** Nothing.

**Interview questions:**
1. *Why not install dbt with `_PIP_ADDITIONAL_REQUIREMENTS` or into the Airflow environment?* Airflow 3.3.2 is installed against a constraints file. That file pins `google-cloud-storage` and `pathspec` to versions dbt refuses. One environment can hold only one version of each package, so one of the two tools would get versions it was never tested with. A second venv avoids the conflict without touching Airflow.
2. *How do you know the key is not inside the image?* `.dockerignore` lists `keys/` and `.env`, and it was created before the first build. So those files never enter the build context, and no `COPY` can pick them up. The key reaches the containers only through a read-only bind mount at run time (S2.2).

## S2.2: docker-compose.yaml from the course file

**Date and commit:** 2026-11-01, `feca6a5`

**What was built:**
- `docker-compose.yaml`: the course compose file with the five changes from the spec.
- `config/.gitkeep`, `plugins/.gitkeep`: keep the empty folders in git.
- Folders created: `dags`, `logs`, `config`, `plugins`, `landing`, `runs`.

**How it works:**
The file is the standard Airflow stack the owner already knows. Only five things change:
1. The image is this project's image, built from `build: .`.
2. The API server is published on localhost only.
3. An environment block in `x-airflow-common`, so every Airflow service sees the same values.
4. Five project mounts.
5. `airflow-init` creates and owns `landing` and `runs`, then creates the `dbt_serial` pool.

`docker-compose.yaml:52`
```yaml
  image: ${AIRFLOW_IMAGE_NAME:-ledger-vs-statement-airflow:3.3.2}
```
`docker-compose.yaml:96`
```yaml
    - ./keys:/opt/airflow/keys:ro
```
`docker-compose.yaml:142`
```yaml
      - "127.0.0.1:8083:8080"  # 8080 is kafka-ui, 8082 is the course stack; localhost only
```
`docker-compose.yaml:277`
```yaml
        /entrypoint airflow pools set dbt_serial 1 "one dbt build at a time"
```

The connection `google_cloud_default` is defined only as the environment variable `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT` (`docker-compose.yaml:86`). Its `key_path` points at the mounted key. `DBT_KEYFILE` (`docker-compose.yaml:85`) is a literal container path, not a value read from `.env`.

Why: `docs/specs/airflow_and_docker.md`, "docker-compose.yaml: the changes to the course file", "Mounts" and "The Google Cloud connection". Starting from the course file reuses a stack that is known to work. The rejected option was writing a compose file from scratch. A connection in an environment variable also avoids storing it in the metadata database through the UI.

**Commands and output:**
```text
$ mkdir -p dags logs config plugins landing runs && touch config/.gitkeep plugins/.gitkeep
$ docker compose config --quiet && echo VALID
VALID
$ grep -n 'keys:/opt/airflow/keys:ro' docker-compose.yaml
96:    - ./keys:/opt/airflow/keys:ro
$ grep -n '127.0.0.1:8083:8080' docker-compose.yaml
142:      - "127.0.0.1:8083:8080"  ...
```
The grep runs on the file itself, not on the `docker compose config` output. That output rewrites ports and volumes in long form.

**What went wrong:** Nothing.

**Interview questions:**
1. *Why bind the port to `127.0.0.1`?* A bare `8083:8080` publishes the Airflow UI on every network interface of the laptop, with the default `airflow`/`airflow` login. Binding to localhost means only this machine can reach it.
2. *Why does the pool get created in `airflow-init`?* The pool must exist before any DAG task asks for it. `airflow-init` runs once on every `make up`, after `airflow config list` has confirmed the metadata database exists. `pools set` is idempotent, so running it again changes nothing.

## S2.3: The raw schema contract, the BigQuery helper, ensure_tables, make bq-setup

**Date and commit:** 2026-11-01, `f7bc8ec` (the same commit also holds the S2.5 Makefile targets `up`, `down` and `smoke`, plus the `dbt_serial` check in `doctor`)

**What was built:**
- `src/recon/schemas/payment_events.json` (14 fields), `src/recon/schemas/settlement_lines.json` (14 fields), `src/recon/schemas/fx_rates.json` (10 fields): copied word for word, by script, from `docs/specs/data_and_generator.md`, "Schema JSON files".
- `src/recon/__init__.py`: empty package marker.
- `src/recon/bq.py`: `host_client()`, `query()`, `rows()`.
- `src/recon/load.py`: `ensure_tables(client, dataset)`, `check_same_shape(actual, expected)`, `columns(table)`.
- `src/recon/cli.py`: the `bq-setup` subcommand.
- `Makefile`: the `bq-setup` target.

**How it works:**
Each schema file is one JSON object. It holds the table name, description, labels, partitioning, clustering and a `fields` list. `ensure_tables` creates the dataset in US if it is missing. Then, for each of the three tables, it builds a `bigquery.Table` from its file and creates it with `exists_ok=True`.

`src/recon/load.py:20`
```python
        schema = [bigquery.SchemaField.from_api_repr(f) for f in doc["fields"]]   # not schema_from_json: it wants a bare list
```
`src/recon/load.py:22-23`
```python
        table.time_partitioning = bigquery.TimePartitioning(
            type_=doc["time_partitioning"]["type"], field=doc["time_partitioning"]["field"])
```
`src/recon/load.py:27-28`
```python
        client.create_table(table, exists_ok=True)       # creates it, or does nothing if it exists
        check_same_shape(client.get_table(table.reference), table)
```

`exists_ok=True` never changes a table that already exists. So `check_same_shape` reads the live table back and compares four things with the file:
- the partition field
- the partition type
- the clustering
- the columns

If anything differs, it fails loudly. `columns()` maps the legacy type names the API returns (`INTEGER`, `BOOLEAN`, `FLOAT`) to standard names, so `INT64` in the file equals `INTEGER` from the API (`src/recon/load.py:8`). `ensure_tables` also refuses a dataset that exists in a location other than US (`src/recon/load.py:16-17`).

In `bq.py`, every query goes through `query()`, which always sets the byte cap:

`src/recon/bq.py:18`
```python
        maximum_bytes_billed=MAX_BYTES_BILLED,
```

`host_client()` sets the project explicitly from `GCP_PROJECT` and the location to US. `rows()` reads results row by row, with no pandas and no Storage Read API.

Why: `docs/specs/data_and_generator.md`, "Raw tables" and "Schema JSON files", and `docs/specs/bigquery_sandbox_and_costs.md`, "The pattern: `ensure_tables` from the schema JSON". One file drives the table, the load jobs and a test, so the three cannot disagree. Rejected options:
- `client.schema_from_json`: it expects a file holding only a bare list of fields.
- A table expiration on a partitioned table: it would override the 60-day partition expiry.
- Hand-written DDL per table: it could drift from the load schema.

**Commands and output:**
```text
$ make bq-setup
ok: raw has payment_events, settlement_lines, fx_rates
ok: raw_dev has payment_events, settlement_lines, fx_rates
$ make bq-setup
ok: raw has payment_events, settlement_lines, fx_rates
ok: raw_dev has payment_events, settlement_lines, fx_rates
(second run changed nothing)
```
INFORMATION_SCHEMA check through the Python client (`src/recon/bq.py`):
- All 6 tables (3 in `raw`, 3 in `raw_dev`) have `PARTITION BY _arrival_date` and `CLUSTER BY` in their DDL.
- Table expiration is `None`; partition expiration is `5184000000` ms (60 days).
- Label `data_origin` is `real` for `fx_rates` and `synthetic` for the other two tables.

**What went wrong:** Nothing.

**Interview questions:**
1. *`create_table(exists_ok=True)` already makes this idempotent. Why read the table back?* `exists_ok=True` only skips creation. If an older table exists with a different partition column or schema, the call succeeds silently, and the next load fails or lands data in the wrong place. Reading the table back and comparing it with the file turns that silent drift into a clear error at setup time.
2. *Why partition by `_arrival_date` and not by the business date?* Each day's load replaces exactly one arrival partition with `WRITE_TRUNCATE`. A late or duplicate file then lands under the day it arrived, not under its event date. That keeps reloads idempotent, and it keeps the record of when data arrived, which reconciliation needs.

## S2.4: dags/smoke_bigquery.py

**Date and commit:** 2026-11-01, `abc035b`

**What was built:**
- `dags/smoke_bigquery.py`: the manual DAG `smoke_bigquery`, with the tasks `bq_load_one_row` (TaskFlow) and `dbt_debug` (BashOperator).

**How it works:**
The DAG has `schedule=None`, so it runs only when triggered. `bq_load_one_row` gets a BigQuery client from the Airflow connection through `BigQueryHook`. It then:
1. creates `probe.smoke (d DATE NOT NULL, x INT64)`, partitioned by `d`, if the table is missing;
2. loads one JSON row into yesterday's UTC partition with `WRITE_TRUNCATE`;
3. counts that partition with a parameterized query capped at 1 GB.

`dbt_debug` then runs the container's dbt against the `airflow` target.

`dags/smoke_bigquery.py:29-30`
```python
        hook = BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")
        client = hook.get_client(project_id=hook.project_id, location="US")
```
`dags/smoke_bigquery.py:46`
```python
        job = client.load_table_from_file(io.BytesIO(payload), f"{table_id}${partition}",
```
`dags/smoke_bigquery.py:64`
```python
        bash_command="cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt debug --target airflow",
```

The heavy imports (the Google provider and `google.cloud.bigquery`) sit inside the task function (`dags/smoke_bigquery.py:26-27`). The dag-processor parses the file often, and these imports would slow every parse. The DAG imports `dag` and `task` from `airflow.sdk`, which is the Airflow 3 interface.

Why: `docs/specs/airflow_and_docker.md`, "smoke_bigquery" and "smoke_bigquery code shape". A load job into a partition decorator is the same write path the real loader uses (ADR-0002). The rejected option was `insert_rows_json` or `insert_all`: they are streaming inserts, and the sandbox refuses them. Running the DAG twice still leaves 1 row, because `WRITE_TRUNCATE` replaces the partition.

**Commands and output:**
```text
$ docker run --rm --entrypoint python -v "$PWD/dags:/opt/airflow/dags:ro" \
    ledger-vs-statement-airflow:3.3.2 /opt/airflow/dags/smoke_bigquery.py && echo PARSE_OK
PARSE_OK

$ uv run ruff check dags/ --select AIR301,AIR302
All checks passed!
```

**What went wrong:** Nothing.

**Interview questions:**
1. *Why load through a load job with `$YYYYMMDD` instead of inserting a row?* Streaming inserts are not available in the BigQuery sandbox, and load jobs are free. A load into `table$20261031` with `WRITE_TRUNCATE` replaces that one partition and nothing else. That makes the write idempotent and tests the exact mechanism the real loader depends on.
2. *Why pass `use_legacy_sql=False` to the hook?* `BigQueryHook` defaults to legacy SQL. Queries written in GoogleSQL, like the parameterized `COUNT(*)` here, would fail or behave differently under legacy SQL.

## S2.5: Start the stack and run the smoke DAG (G-skel)

**Date and commit:** 2026-11-01. The Makefile targets are in `f7bc8ec`; there is no separate S2.5 commit.

**What was built:**
- `Makefile`: `up` (`docker compose up -d`), `down` (`docker compose down`), `smoke` (unpause and trigger `smoke_bigquery`), and the `dbt_serial` pool check at the end of `doctor`.

**How it works:**
`make up` starts the stack. `airflow-init` runs once and exits, after creating the folders and the pool. `make smoke` runs Airflow commands inside the scheduler container through one shared prefix:

`Makefile:13`
```make
AIRFLOW := docker compose exec -T airflow-scheduler airflow
```
`Makefile:53-55`
```make
smoke:
	$(AIRFLOW) dags unpause smoke_bigquery
	$(AIRFLOW) dags trigger smoke_bigquery
```
`Makefile:21`
```make
	$(AIRFLOW) pools get dbt_serial
```

One green run proves several links at once:
- the image starts;
- the key is mounted read-only and readable by the container user;
- the connection from the environment variable works;
- a partition load job succeeds;
- the container's dbt reaches BigQuery with the same key.

Why: `docs/specs/airflow_and_docker.md`, "Start the stack", "Run the smoke test", "The pool dbt_serial", and the isolation checks under "Why dbt has its own virtual environment". It follows the walking-skeleton idea in the M2 plan: find plumbing problems early, before any business logic exists. The rejected option was building the pipeline first and debugging Docker at the end.

**Commands and output:**
```text
$ make up
$ docker compose ps
apiserver, dag-processor, scheduler, triggerer, postgres: healthy
airflow-init: Exited (0)

$ docker compose exec airflow-scheduler airflow pools get dbt_serial
dbt_serial | 1 | one dbt build at a time

$ airflow dags list-import-errors
No data found
$ airflow dags list
smoke_bigquery ... is_paused True

Key check in the scheduler: "key readable"; touch on the key -> Read-only file system

dbt isolation checks:
/opt/airflow/dbt_venv/bin/dbt --version -> installed: 1.12.6, bigquery: 1.12.1
command -v dbt -> no dbt on PATH (expected)
airflow env: 3.14.1 1.1.1
dbt venv: 3.1.1 1.0.4

$ make smoke
run manual__2026-11-01T15:23:34 ... state success (15:23:35 to 15:23:52 UTC)
bq_load_one_row log: probe.smoke$20261031 holds 1 row
dbt_debug log: All checks passed!
```
Gate G-skel passed.

**What went wrong:** Nothing broke. The S2.5 Makefile targets were committed together with S2.3 in `f7bc8ec`, not in their own `build(repo): add the up, down and smoke targets (S2.5)` commit.

**Interview questions:**
1. *What is the `dbt_serial` pool for, when only a smoke DAG exists yet?* It has one slot, so at most one dbt build runs at a time across all DAG runs, which matters once backfills run in parallel. Two concurrent builds would race on the same tables and the same `target/` folder. It is created and checked now so the plumbing is proven before `recon_daily` depends on it.
2. *The smoke run is green. What exactly has it proved?* It has proved that the image runs and the read-only key is readable by the container user. It has also proved that the `AIRFLOW_CONN_...` connection authenticates, that a partition-decorator load job works in the sandbox, and that the isolated dbt reaches BigQuery through `DBT_KEYFILE`. It has not proved anything about the business logic, which does not exist yet.

## Explain check M2

**Why does dbt have its own venv?**
The Airflow 3.3.2 constraints pin `google-cloud-storage` 3.14.1 and `pathspec` 1.1.1. dbt-bigquery 1.12.1 needs `google-cloud-storage` below 3.2, and dbt-core 1.12.6 needs `pathspec` below 1.1. One environment holds one version of each package, so the two cannot share. The `Dockerfile` (lines 5 to 7) creates `/opt/airflow/dbt_venv` and installs the three pins from `docker/requirements-dbt.txt` there. The S2.5 check showed the split: the Airflow env has 3.14.1 and 1.1.1, and the dbt venv has 3.1.1 and 1.0.4. The venv is not on `PATH`, so the DAGs call `/opt/airflow/dbt_venv/bin/dbt` by full path, and there is exactly one dbt in the containers.

**How does the key reach the container?**
On the host it is `keys/sa.json` with `chmod 600`. It is gitignored and listed in `.dockerignore`, so it is in no commit and in no image. `docker-compose.yaml:96` bind-mounts `./keys` at `/opt/airflow/keys` read-only, so `touch` on it fails with "Read-only file system". The containers run as `AIRFLOW_UID`, the owner's own user id, so the owner-only file is readable. Only the path travels in environment variables, never the key itself:
- Airflow reads it through `key_path` in `AIRFLOW_CONN_GOOGLE_CLOUD_DEFAULT` (`docker-compose.yaml:86`).
- dbt reads it through `DBT_KEYFILE` (`docker-compose.yaml:85`), which `dbt/profiles.yml` uses as `keyfile`.

**Why does `smoke_bigquery` not touch `raw`?**
`raw` holds the pipeline's real input, and only the daily loader writes it, one arrival partition at a time. The smoke DAG takes "yesterday" from the wall clock (`dags/smoke_bigquery.py:31`). That is allowed only because it never writes business data. A smoke row in `raw` would be a fake payment record that every downstream model and money test would count. So it writes to its own dataset, `probe.smoke`. It still uses the same write path, a `WRITE_TRUNCATE` load into a partition decorator, so it tests the mechanism without polluting the data.

## S3.1: World parameters and contract terms

**Date and commit:** 2026-11-01, `bb29c89`

**What was built:**
- `dbt/seeds/mids.csv`: the two merchant accounts, `mid_usd_01` and `mid_kzt_01`, with their contract terms, exactly as in the spec.
- `src/recon/world.toml`: every synthetic design parameter, each with a one-line comment. It holds the volumes, plan mix, prices, hour weights, webhook timing, settlement lag, defect rates and fee noise.
- `dbt/dbt_project.yml`: a new `vars:` block with `statement_grace_days: 1`.
- `src/recon/config.py`:
  - three frozen dataclasses: `Mid`, `World` and `Env`
  - `load_mids`: reads the CSV and casts the integer columns
  - `load_world`: reads the TOML and the MIDs into one `World`
  - `check`: fails at load time on a broken config
  - `load_env`: reads `RECON_SEED`, `RECON_WORLD_START` and `RECON_LANDING_DIR`

**How it works:**
The config has two sources, and the split matters.

- `mids.csv` holds what both the merchant and the payment service provider (PSP) know: the cut-off offset, the maximum settlement lag, the fee and the fee tolerance. The generator reads it, and dbt will read it later as a seed.
- `world.toml` holds what finance does not know: how many payments there are, how often webhooks repeat, and how often the PSP makes a mistake. dbt never sees this file.

Because of this split, the matcher cannot be tuned to the planted defects. That is what keeps the seeded self-test fair.

Every value is an integer or a string. Rates are in basis points (`_bp`), delays are in seconds (`_delay_s`), and plan weights are in percent. This keeps floats away from the money path from the first line of config.

`src/recon/config.py:61`
```python
        return tuple(Mid(**{k: int(v) if k in INT_COLUMNS else v for k, v in row.items()})
```

`src/recon/world.toml:35`
```toml
missing_in_statement_bp = 50           # D2: 0.5% of payments are never settled
```

`src/recon/config.py:113`
```python
        seed=int(os.environ["RECON_SEED"]),
```

The seed is parsed with `int()`, so `"020261101"` and `"20261101"` give the same random streams. `check` fails loudly in these cases:
- the hour weights are not exactly 24 values
- the plan lists have different lengths
- the plan weights do not sum to 100
- two MIDs would get the same id tag
- a currency has no price list

Only the CLI and the DAG call `load_env`. The generator functions take `seed` and `world_start` as arguments, so tests never depend on `.env`.

This follows `docs/specs/data_and_generator.md`, headings "Contract terms and world parameters" and "Where config is read from (`src/recon/config.py`)", and ADR-0010 (Decision, point 2). It rejects keeping the defect rates in a dbt seed or var, which would let dbt see the answer.

**Commands and output:**
The step's done-when check loaded the config with `PYTHONPATH=src uv run python`. Output, shortened:
```text
Mid(mid='mid_usd_01', psp='psp_alpha', currency='USD', statement_utc_offset_hours=-5, max_settlement_lag_days=2, fee_bps=290, fee_fixed_minor=30, fee_tol_bps=10, fee_tol_min_minor=5)
Mid(mid='mid_kzt_01', ..., statement_utc_offset_hours=5, fee_bps=250, fee_fixed_minor=0, fee_tol_bps=10, fee_tol_min_minor=500)
seed 20261101 world_start 2026-10-04 grace 1 version 1.0.0
```

**What went wrong:** Nothing.

**Interview questions:**
1. *Why are the fee terms in a dbt seed but the defect rates in a TOML file?*
   The fee terms are contract terms that a real finance team would know, so the reconciliation may use them. The defect rates describe the PSP's mistakes, which finance never knows in advance. If dbt could read them, the matcher could be fitted to the answer, and the self-test would prove nothing.
2. *Why integers for every rate and weight?*
   Money must stay in exact minor units from end to end. If a rate were a float such as `0.029`, float rounding could enter the fee arithmetic, and Python and SQL might disagree by one minor unit. Basis points and integer division give the same result in both languages.

## S3.2: `payments_for_day`

**Date and commit:** 2026-11-01, `75cd6cd` (shared with S3.3). The plan names separate commits for S3.2 and S3.3. One commit covers both, because both live in one file.

**What was built:**
- `src/recon/generator.py`:
  - `stream`: one random stream per purpose
  - `draw_int` and `draw_weighted`: the only two draw helpers
  - `expected_fee_minor` and `fee_tolerance_minor`: integer fee arithmetic
  - `utc_hour_weights`: rotates the local-hour weights onto UTC hours
  - `ts`: formats timestamps
  - `payments_for_day`: the payments booked on one UTC day for one MID
  - `one_payment`: one payment, with its deliveries, its statement line and its answer-key row

**How it works:**
`payments_for_day` is a pure function. Its output depends only on the seed, the world start, the booking day and the MID. It first turns the date into `day_index`, the number of days since the world start, and keys every draw by that index, never by the calendar date. A day before the world start returns an empty list.

`src/recon/generator.py:71`
```python
    day_index = (day - world_start).days
```

Each decision has its own random stream. The stream is named by a string such as `20261101|16|mid_kzt_01|42|money`.

`src/recon/generator.py:25`
```python
    return random.Random("|".join(str(p) for p in (seed, day_index, mid_id, *parts)))
```

Python seeds a string through SHA-512, not through `hash()`, so the stream is the same in every process. Because each purpose has its own stream, adding a draw for one purpose never shifts the draws of another.

For each payment, the function picks these in order:
1. the plan
2. the capture time, with the UTC hour drawn from the MID's local-hour weights rotated by its offset
3. one `money` draw that chooses D2, D3, D4 or none
4. the webhook deliveries, with D1 redeliveries
5. the statement lag
6. the D4 amount change, the D5 overcharge or the B3 fee noise

`src/recon/generator.py:102`
```python
    x = draw_int(rng("money"), 0, 9999)
```

Fees use integer arithmetic only: half-up rounding for the fee and a ceiling for the tolerance. dbt will use the same formulas.

`src/recon/generator.py:48`
```python
    return (gross * mid.fee_bps + 5000) // 10000 + mid.fee_fixed_minor          # half-up
```

The accounting date is the capture time moved by the MID's fixed offset (B1, the cut-off shift). It is a structural rule and uses no random draw. D3 gets no deliveries, and D2 gets no statement line, so D1 can never apply to D3, and D4 and D5 can never apply to D2.

This follows `docs/specs/data_and_generator.md`, headings "Determinism", "Random streams", "Draw helpers (the only two)", "Integer money", "`payments_for_day(seed, world_start, day, mid)`" and "Defect catalog". The fee formulas come from `docs/specs/dbt_project.md` under `fct_recon_lines`. It rejects `randint`, `choices` and `uniform` (Python does not promise they stay stable), one shared stream (any new draw would reshuffle every later row) and `round()` on floats.

**Commands and output:**
These checks were run in a Python shell:
- The fee table matched every worked value in the spec:
  - USD: 699 gives 50/5, 1999 gives 88/5, 3999 gives 146/5
  - KZT: 349000 gives 8725/500, 999000 gives 24975/999, 1999000 gives 49975/1999
- The same inputs twice gave equal lists: `True`.
- Another seed gave a different list: `True`.
- 77 KZT payments were booked on 2026-10-20.
- Every amount and fee is an `int`: `True`.
- A day before the world start gives an empty list: `True`.

**What went wrong:** No bug. `ruff` rule FURB122 asked for `writelines` instead of a loop of `write` calls in `write_ndjson`. The change kept the bytes the same, and the golden hash still passed after it.

**Interview questions:**
1. *Why key the streams by `day_index` and not by the date?*
   With `day_index`, moving `RECON_WORLD_START` moves the same world to new dates. A rerun months later can then rebuild the same data inside the sandbox's 60-day partition expiry. If the date were the key, a new start date would create a different world.
2. *Why one random stream per purpose?*
   Streams are independent, so a payment that skips a stream changes nothing else. For example, a D3 payment has no deliveries and never opens the `delivery` stream. A new defect class gets a new purpose name, so every existing row stays byte-identical.

## S3.3: `arrivals`, `emit` and the answer key

**Date and commit:** 2026-11-01, `75cd6cd` (shared with S3.2)

**What was built:**
- `src/recon/generator.py`:
  - `arrivals`: what arrived during one UTC day
  - `write_ndjson`: the atomic, byte-stable file writer
  - `emit`: writes the four files for one run date and returns a dict of counts

**How it works:**
One run date R is one UTC arrival day. A payment's rows arrive on different days:
- the first webhook can land after midnight
- a redelivery can come up to 6 hours later
- the statement line comes 1 or 2 days after the accounting date

So `arrivals` recomputes every payment booked on R-5 to R (`lookback_days = 5`). It then keeps only the rows whose arrival date is R. The answer key holds only the payments booked on R.

`src/recon/generator.py:188`
```python
                events += [row for row in p["deliveries"] if row["_arrival_date"] == r]
```

A delivery's arrival date is the UTC date of its `delivered_ts`. It is set at `src/recon/generator.py:126` as `arrival = delivered.date().isoformat()`.

`emit` writes four files under the landing folder:
- `payment_events/arrival_date=R/part-000.ndjson`
- one `settlement_lines/arrival_date=R/mid=<mid>.ndjson` per MID
- `_truth/booking_date=R.ndjson`

The rows are sorted by key: `delivery_id`, `line_id` or `payment_id`. Each row is JSON with sorted keys and compact separators, followed by `\n`. Each file is written to `<name>.tmp` and then renamed with `os.replace`, so a crash never leaves half a file.

`src/recon/generator.py:205`
```python
        f.writelines(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
        os.replace(tmp, path)
```

`emit` refuses a run date before the world start. The answer key goes to `landing/_truth/`, which is gitignored and never loaded into BigQuery.

This follows `docs/specs/data_and_generator.md`, headings "`arrivals(seed, world_start, run_date)`", "`emit(seed, world_start, run_date, landing_dir) -> dict of counts`", "Byte-identical files" and "Layout", plus ADR-0010 (Decision, points 5 and 6) and ADR-0007. It rejects two alternatives:
- Keeping state between runs, such as a queue of rows that are not delivered yet. A rerun would then depend on earlier runs.
- Writing a file in place. A crash could leave a partial file that the loader would load.

**Commands and output:**
`emit` for 2026-10-20 returned payment_events 230, settlement_lines 198 (`mid_kzt_01` 67, `mid_usd_01` 131) and truth 219.

**What went wrong:** Nothing.

**Interview questions:**
1. *Why does a run recompute five earlier booking days instead of reading what it saved yesterday?*
   Recomputing keeps each run a pure function of its date, with no state carried between runs. Any day can then be rerun alone, in any order, and give the same bytes. The latest a row can arrive is 3 days after its booking day, so 5 days leaves a margin.
2. *Why write to a temporary file and rename?*
   On one filesystem, `os.replace` is atomic: a reader sees either the old file or the whole new one. If the process dies mid-write, only a `.tmp` file is left behind. The final file is never half written, so it is never half loaded.

## S3.4: Generator tests

**Date and commit:** 2026-11-01, `c17f4db`

**What was built:**
`tests/test_generator.py` has 9 tests:
- `test_golden_hash`
- `test_rerun_is_byte_identical`
- `test_other_seed_differs`
- `test_rows_belong_to_their_run`
- `test_each_row_in_exactly_one_file`
- `test_lookback_is_enough`
- `test_rows_match_schema`
- `test_class_counts_within_loose_bounds`
- `test_grace_days_match_dbt`

It also has the helpers `day_files`, `combined_hash`, `booked`, `check_value` and `within`.

**How it works:**
The golden hash emits one day (2026-10-09) into a pytest `tmp_path`. It hashes each of the four files and then hashes the list of `path sha256` lines. Any change to any byte of the output turns the test red.

`tests/test_generator.py:19`
```python
GOLDEN = "7bae06c071d0f45b8322c64a63c58ed4c2a0e8a660dedf4ac013e8cacc8917ac"   # generator 1.0.0, run date 2026-10-09
```

The other tests check these rules:
- Every events row has `_arrival_date = R`, and its `delivered_ts` starts with R.
- Over 10 booking days, every settled payment is in exactly one statement file. No D2 payment is in any statement file, and no D3 payment has a delivery.
- No row arrives more than 3 days after its booking day.
- Every row has exactly the fields of its schema JSON, with the right types.
- The planted class counts over 7 days lie between 0.25 and 3 times their expected value.
- `statement_grace_days` in `world.toml` equals the dbt var.

`tests/test_generator.py:85`
```python
                    assert row["delivered_ts"].startswith(r.isoformat())
```

`tests/test_generator.py:168`
```python
    return 0.25 * expected <= count <= 3 * expected
```

The generator is deterministic, so a bound either always passes or always fails. It never flickers.

This follows `docs/specs/data_and_generator.md`, heading "Generator tests (`tests/test_generator.py`)". It rejects checking by eye that two runs "look the same", and it rejects tight statistical bounds that would need the seed to be changed.

**Commands and output:**
- First run of `uv run pytest`: 8 passed. `test_golden_hash` failed only because `GOLDEN` still held the placeholder `"[GOLDEN_SHA256]"`. The spec says to record the hash once the generator is final for M3, so the real value was recorded with its version and date (generator 1.0.0, run date 2026-10-09).
- Then `make check`: 9 passed, exit 0.

**What went wrong:** No bug. The first red golden-hash test was the expected placeholder step, so there is no failure-log entry.

**Interview questions:**
1. *When may the golden hash change?*
   Before G1, only on purpose, with the reason in the commit. After G1, only together with a `generator_version` bump in `world.toml`, in the same commit, saying why. Changing it just to make the test pass is forbidden, because then the test proves nothing.
2. *What does the 0.25 to 3 times bound protect against, and why is it so loose?*
   It catches a broken threshold or a stream wired to the wrong purpose, which would give zero or many times the expected count. With a few hundred payments a day, a rare class such as D3 at 0.4% has an expected count of only about 5. Natural variation is therefore large, and a tight bound would fail for honest reasons.

## S3.5: `make day` twice gives the same bytes

**Date and commit:** 2026-11-01, `1dae889`

**What was built:**
- `src/recon/cli.py`: the `generate --date` subcommand and its function `generate`.
- `Makefile`:
  - a `day` target that needs `DATE=`
  - a `test` target (`uv run pytest`)
  - `check` now depends on `lint test`

**How it works:**
`make day DATE=YYYY-MM-DD` runs the CLI. The CLI reads the seed, the world start and the landing folder from the environment, calls `emit` and prints the counts as JSON with sorted keys. In M3 the target only generates. S4.3 adds the FX fetch and the load.

`Makefile:44`
```make
	@test -n "$(DATE)" || { echo "day: set DATE=YYYY-MM-DD" >&2; exit 1; }
	uv run python -m recon.cli generate --date $(DATE)
```

`src/recon/cli.py:30`
```python
    gen.add_argument("--date", required=True, type=date.fromisoformat, help="run date, YYYY-MM-DD (UTC)")
```

`date.fromisoformat` rejects a badly formed date before any file is written.

The host and the containers write the same `landing/` folder. That is safe only because the same inputs always give the same bytes.

This follows `docs/build_plan.md`, step S3.5, and the "Idempotency" concept. It rejects a generator that adds a timestamp or a run id to its output, which would make every rerun differ.

**Commands and output:**
- The agent ran the CLI twice for 2026-10-30, with the landing folder pointed at a scratch folder. Both runs returned payment_events 214, settlement_lines 212 (`mid_kzt_01` 78, `mid_usd_01` 134) and truth 207.
- The sha256 of all 4 files was the same in both runs: `diff` printed `IDENTICAL`.
- No `.tmp` files were left over.
- The owner then ran `make day DATE=2026-10-30` twice in the repo, with the step's `find ... | xargs shasum -a 256` and `diff` check. This check confirms that both runs give the same sha256 for every file. `git status --short` confirms that nothing under `landing/` is tracked.

**What went wrong:** Nothing.

**Interview questions:**
1. *Why do byte-identical files matter for the pipeline?*
   They are the first half of idempotency. A rerun of any day writes exactly the same files. With the WRITE_TRUNCATE load into that day's partition in M4, it then leaves BigQuery unchanged. This is what the rerun proof in M8 measures.
2. *Why does `make day` fail when `DATE` is empty instead of using yesterday?*
   A business date must never come from the wall clock. A default of "yesterday" would make the same command give different data on different days. Requiring `DATE` keeps every run tied to an explicit run date.

Next step: S4.1.

## Explain check M3

**1. Why is the generator a pure function of (seed, day_index, MID)?**

A pure function means that a rerun of any day, on any machine, at any time, rebuilds exactly the same rows. Nothing reads the clock, the machine or a state file. Every stream is keyed `seed|day_index|mid|...` at `src/recon/generator.py:25`.

This gives three things:
- Airflow can rerun or backfill any date alone and in any order, and the files are byte-identical. That is the base of the rerun proof.
- `day_index`, not the date, keys the draws. Moving `RECON_WORLD_START` therefore moves the same world to new dates, which keeps reruns inside the sandbox's 60-day expiry.
- Per MID streams mean that adding a MID does not reshuffle another MID's payments.

**2. Why only `random()`?**

Python promises that only `Random.random()` gives the same sequence for the same seed across versions. `randint`, `choice`, `choices`, `uniform` and `shuffle` have no such promise, and their algorithms have changed between versions.

The generator calls `random()` only through `draw_int` and `draw_weighted` (`src/recon/generator.py:28` and `:34`). Each helper turns the float draw into an integer at once, so no float reaches the money path. The seed is a string, which Python seeds through SHA-512 and not `hash()`, so `PYTHONHASHSEED` does not change it. The golden-hash test (`tests/test_generator.py:56`) catches any drift.

**3. Which defect can cross midnight, and what does that do to the arrival files?**

D1, the webhook redelivery. Each extra copy comes 60 seconds to 6 hours after the first delivery (`redelivery_delay_s = [60, 21600]` in `src/recon/world.toml:29`). It lands in the events file of `DATE(delivered_ts)`, which is often the day after the booking day. A first delivery 1 to 30 seconds after a capture just before midnight can also land in the next day's file.

This has three effects:
- **Events spread over two days.** One booking day's events appear in two arrival files and two `raw.payment_events` partitions. The same `event_id` can appear in both, with different `delivery_id` values.
- **Each run recomputes recent bookings.** `arrivals` recomputes booking days R-5 to R and keeps only rows whose `_arrival_date` is R (`src/recon/generator.py:185` to `:192`).
- **Dedup works across the whole table.** Dedup in staging must run over all partitions, not inside one file. It keeps the earliest delivery by `delivered_ts` and then `delivery_id`.

The booking date itself never changes. Only the arrival file does.

## Review of M0 to M3 (2026-11-02)

**Date and commit:** 2026-11-02, `780bf5d`, `c3a82e3`, `ee2479a`.

**What was done:** before starting M4, four reviewers compared the code and records of M0 to M3 with the specs (generator, tables and BigQuery helpers, Docker and Airflow, repo and docs). Each finding was checked by two independent skeptics, and only findings both confirmed were kept. Three survived:

- `tests/test_generator.py`, `test_each_row_in_exactly_one_file`: it checked only that no `delivery_id` repeats, so a delivery dropped by `arrivals` would have passed. It now also asserts that every delivery of every payment booked in the first 10 days appears exactly once (commit `c3a82e3`). This tightens a test; it loosens nothing.
- `docs/adr/0001-warehouse-bigquery-sandbox.md` and `README.md`: the P2 refusal text was cut at different points in the two files. Both now quote the full first line of `error_text` from `docs/evidence/2026-11-01/g0_probe.json`, without the job id (commit `ee2479a`).
- `README.md`, "Platform constraints (G0 probes)": the "What the results decided" sentence was still a placeholder. It now states the decision recorded in ADR-0001 (commit `ee2479a`).

The bug from S0.2 is logged as F-001 in `docs/failure_log.md` (commit `780bf5d`).

**Commands and output:** `make check` after the fixes: `9 passed`, exit 0.


## S4.1: one WRITE_TRUNCATE load job per table and day

**Date and commit:** 2026-11-02, `3ce0221`

**What was built:**
- `src/recon/load.py` has these new pieces:
  - `schema_doc` and `schema_fields`: read a table's schema JSON and turn it into BigQuery `SchemaField` objects.
  - `MAX_RUN_AGE_DAYS = 45` and `check_run_date`: the one guard on run dates.
  - `read_ndjson`: reads one landing file, and fails if the file is missing.
  - `fx_rows`: builds `fx_rates` rows from the landed Frankfurter body.
  - `landed_rows`: picks the exact landing files of one table for one day.
  - `load_day` and `load_partition`: check the rows, then do the one write.

**How it works:**
`load_day` reads every landing file of one table for run date R. For statements that means one file per MID, named from `mids.csv`, never found with a glob. It joins the rows in memory. Then it checks every row before any job runs. Every row must have `_arrival_date` equal to R. Payment events must also have `DATE(delivered_ts)` equal to R.

`src/recon/load.py:114`
```python
    for row in rows:                                      # every check runs before any job
        if row["_arrival_date"] != r:
            raise ValueError(f"{table}: row with _arrival_date {row['_arrival_date']} in the files of run date {r}")
```

`load_partition` makes exactly one write for the table and day. The target is the partition decorator `<table>$YYYYMMDD`. If there are no rows, it deletes that partition. That is a table operation, not DML.

`src/recon/load.py:125`
```python
    dest = f"{client.project}.{dataset}.{table}${run_date:%Y%m%d}"     # one partition, no dashes
    if not rows:
        client.delete_table(dest, not_found_ok=True)      # a table operation, not DML
```

If there are rows, it runs one NDJSON load job with `location="US"`. The job uses WRITE_TRUNCATE, CREATE_NEVER and `max_bad_records=0`. CREATE_NEVER means a missing table fails loudly. Without it, the load could create the table with no partitioning.

`src/recon/load.py:133`
```python
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_NEVER,   # a missing table fails loudly
```

After the job finishes, the loader compares BigQuery's row count with the number of landed rows. A mismatch raises `RuntimeError`.

`src/recon/load.py:139`
```python
    if job.output_rows != len(rows):
        raise RuntimeError(f"{dest}: load wrote {job.output_rows} rows, {len(rows)} were landed")
```

For FX, `fx_rows` first checks the sha256 of the body against the meta file, so a changed landed file fails loudly. It parses rates with `parse_float=str`, so no rate ever becomes a Python float (`src/recon/load.py:90`). It takes `provider` (`nbk`) from the folder name, sets `requested_from` to R-6 and `requested_to` to R, and copies `fetched_at` from the frozen meta file.

`check_run_date` refuses three kinds of date: a date before the world start, a date that has not ended in UTC, and a date more than 45 days old (`src/recon/load.py:60` to `:70`).

This follows "Load protocol" and "How the pipeline refuses old dates" in `docs/specs/bigquery_sandbox_and_costs.md`, and ADR-0002. It rejects three alternatives:
- WRITE_APPEND plus dedup views, because each rerun would add another copy of the day.
- One WRITE_TRUNCATE job per file, because two jobs into the same partition would overwrite each other.
- MERGE, streaming inserts and Cloud Storage, because the sandbox refuses them or they need billing.

ADR-0009 also rejects running with no write guard.

**Commands and output:**
- Tamper test:
  - The landing files of 2026-10-28 were copied to a scratch folder, and one statement row's `_arrival_date` was changed to 2026-10-27.
  - `load_day` was then called with a client stub that raises on any call. Output: `settlement_lines refused before any job: settlement_lines: row with _arrival_date 2026-10-27 in the files of run date 2026-10-28`.
  - The untampered `payment_events` file passed every check and reached the stub at `load_table_from_file`, as expected.
- Missing file: with the events file renamed away, the output was `missing file refused: expected landing file is missing`.

**What went wrong:** Nothing.

**Interview questions:**
1. *Why join all MID files before loading instead of loading each file?*
   WRITE_TRUNCATE replaces the whole partition with what one job loads. Two jobs into `settlement_lines$20261028`, one per MID, would leave only the last MID's rows. Joining the rows first means one job writes the full day.
2. *Why check `_arrival_date` in Python when BigQuery also refuses a row for another partition?*
   The Python check runs before any job, so nothing is written at all and the error names the bad row. With several tables per day, a failure in BigQuery could come after another table was already loaded. Checking first also gives one clear error message instead of a job error.

## S4.2: fetch NBK rates once into immutable landing

**Date and commit:** 2026-11-02, `57822b1`

**What was built:**
- `src/recon/fx.py` has four functions:
  - `fx_url`: builds the request URL for R-6 to R.
  - `check_rates`: checks the answer before anything is landed.
  - `write_atomic`: writes a temp file.
  - `fetch_nbk`: the skip rule, the request, the checks and the two renames.

**How it works:**
`fetch_nbk` first looks for the landed body and its meta file. If both exist, it logs "already landed" and returns without any HTTP request. If only one exists, it fails and asks for the stray file to be deleted by hand.

`src/recon/fx.py:53`
```python
    if body_path.exists() and meta_path.exists():
        log.info("already landed: %s", body_path.name)
        print(f"already landed: {body_path.name}")
        return {"action": "skipped"}
```

Otherwise it refuses any R on or after today (UTC) and requests R-6 to R. It uses a 10-second timeout and the project's User-Agent. Seven days always contain weekdays, so the answer is never empty only because of a weekend. When R-6 has no rate, Frankfurter puts the last earlier rate first. `check_rates` allows exactly that one row.

`src/recon/fx.py:35`
```python
        if d < start and i > 0:                           # only the first row may be the carry-in before R-6
            raise ValueError(f"row {i} is dated {d}, before {start}; only the first row may be")
```

`check_rates` also requires USD/KZT, no date after R, and dates in strictly increasing order. Rates are parsed with `parse_float=str`. The body is written byte for byte as received. The meta file (`fetched_at`, `http_status`, `sha256`, `url`) goes next to it. Both are first written to `.tmp` names. The meta file is renamed first and the body last, because the body's final name is the "landed" signal.

`src/recon/fx.py:77`
```python
    os.replace(meta_tmp, meta_path)                       # the meta first: the body's final name means "landed"
    os.replace(body_tmp, body_path)
```

This follows ADR-0004 and "Landing (immutable)" in `docs/specs/data_and_generator.md`. It rejects three alternatives:
- Fetching again on every run, because a restated rate would break the rerun proof.
- Frankfurter's blended rates, because they mix sources.
- FLOAT64 rates, because binary rounding changes the exact rate.

**Commands and output:**
- First fetch for 2026-10-31: `fetch: {"action": "fetched", "rows": 6}`.
- The body had six rows: 2026-10-23 at 447.94, 2026-10-26 and 2026-10-27 at 451.05, 2026-10-28 at 455.63, 2026-10-29 at 457.09, and 2026-10-30 at 453.71. As the spec predicts for R = 2026-10-31, it starts with 2026-10-23. These rates are real.
- Meta: `{"fetched_at":"2026-11-02 17:44:45+00:00","http_status":200,"sha256":"64fe19dd...","url":"https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD"es=KZT&from=2026-10-25&to=2026-10-31"}`.
- Second call for the same date: `already landed: arrival_date=2026-10-31.json`, then `fetch: {"action": "skipped"}`, with no HTTP request.
- `fetch --date 2026-11-02` was refused with `ValueError: run date 2026-11-02 has not ended in UTC (today is 2026-11-02): use yesterday or earlier`. The CLI's `check_run_date` raised it before `fetch_nbk` ran.

**What went wrong:** ruff rule RUF007 flagged `zip(dates, dates[1:])` and asked for `itertools.pairwise`. The code was changed to `pairwise(dates)` (`src/recon/fx.py:38`). This was a lint fix, not a bug, so there is no failure-log entry.

**Interview questions:**
1. *Why land the FX answer once and never fetch it again?*
   The rates are real data, and a provider can restate them later. If each run fetched again, a rerun of an old day could get different rates and different marts, and the rerun proof would fail. Landing once and committing `landing/fx/` makes every rerun and every fresh clone use the same bytes.
2. *Why does the answer for R = 2026-10-31 start on 2026-10-23?*
   R-6 is 2026-10-25, a Sunday. NBK publishes no rate on weekends, so Frankfurter adds the last rate before the range, which is Friday 2026-10-23. The check allows exactly one such early row, as the first row, so the carry-forward in dbt has a rate to start from.

## S4.3: the host CLI for full development days

**Date and commit:** 2026-11-02, `a33593f` (CLI and Makefile) and `5a83aa0` (the 14 FX files)

**What was built:**
- `src/recon/cli.py`:
  - `guarded`: runs `check_run_date` before anything else.
  - The subcommands `fetch`, `load` (writes to `$RAW_DATASET`), `day` (generate, then fetch, then load) and `days` (every date in a range, oldest first).
  - `generate` is now guarded too.
- `Makefile`: `make day` now runs `recon.cli day`, and `make days FROM= TO=` is new. Both refuse empty values.
- `landing/fx/provider=nbk/`: 7 bodies and 7 meta files, committed.

**How it works:**
Every subcommand calls `guarded` first. It reads the environment and calls `check_run_date` with today's UTC date. A date that is too old, or that has not ended yet, is refused before any file is written or any job runs. The wall clock is only used for this check. It never shapes data.

`src/recon/cli.py:15`
```python
    check_run_date(run_date, env.world_start, datetime.now(UTC).date())
```

`day` runs the steps in the same order as the DAG: generate, fetch, load. `load` runs `load_day` for each of the 3 tables into `$RAW_DATASET`, which the Makefile sets to `raw_dev`. `days` makes one client and loops in Python, oldest date first.

`src/recon/cli.py:76`
```python
    while d <= args.to_date:                              # oldest first; the loop lives in Python, not in shell
        day(argparse.Namespace(date=d), client)
```

`Makefile:48`
```make
	@test -n "$(FROM)" -a -n "$(TO)" || { echo "days: set FROM=YYYY-MM-DD TO=YYYY-MM-DD" >&2; exit 1; }
```

The host runs the same functions as the DAG, so logic can be debugged quickly without touching the Airflow datasets. This follows `docs/build_plan.md` step S4.3, the make-target table in the plan, and the "Idempotency" concept. It rejects a shell loop in the Makefile, and it rejects the unguarded M3 `generate`, which had no date check.

**Commands and output:**
- `make days FROM=2026-10-25 TO=2026-10-31` loaded these rows per day (synthetic events / synthetic statement lines / real FX rows):

  | Day | Events | Statement lines | FX rows |
  |---|---|---|---|
  | 2026-10-25 | 194 | 209 | 5 |
  | 2026-10-26 | 210 | 187 | 5 |
  | 2026-10-27 | 206 | 200 | 5 |
  | 2026-10-28 | 217 | 198 | 5 |
  | 2026-10-29 | 205 | 193 | 5 |
  | 2026-10-30 | 214 | 212 | 6 |
  | 2026-10-31 | 215 | 202 | 6 |

  The FX fetch for 2026-10-31 was skipped because it was already landed.
- Each `raw_dev` table then had 7 partitions, 2026-10-25 to 2026-10-31.
- The count-and-sum query for 2026-10-28 before the reload gave `payment_events` n=217, s=81297064 and `settlement_lines` n=198, s=57491530 (synthetic).
- `make day DATE=2026-10-28` (FX skipped, already landed), then the same query: identical results.
- `git check-ignore landing/payment_events` printed `landing/payment_events`.
- `git ls-files landing/fx` listed the 14 files (7 bodies, 7 meta).
- `make check`: 9 passed, ruff clean.

**What went wrong:** Nothing.

**Interview questions:**
1. *Why does reloading 2026-10-28 give the same counts and sums?*
   The generator writes byte-identical files for the same date, and the FX file is not fetched again. The loader then replaces only the `$20261028` partition of each table with one WRITE_TRUNCATE job. So the rerun puts back exactly the rows it removed, and no other day changes.
2. *Why are the FX files committed but the synthetic landing files ignored?*
   The synthetic files can always be rebuilt from the seed, so committing them would add nothing. The FX files are real answers from an outside API that may change or restate them. Committing them is the only way a fresh clone gets the same rates.

Next step: S5.1.

## Explain check M4

**1. Why one load job per table per day?**

A WRITE_TRUNCATE job replaces the whole target partition with what that one job loads. If each statement file had its own job, the second job would wipe out the first MID's rows. WRITE_APPEND would add a full copy of the day on every rerun.

So `load_day` reads every expected file for the day, joins the rows, checks them, and makes exactly one write in `load_partition` (`src/recon/load.py:110` to `:142`). After the job, `job.output_rows` must equal the number of landed rows (`src/recon/load.py:139`). That one job per (table, day) is what makes a rerun idempotent without any DML.

**2. What exactly does WRITE_TRUNCATE on `t$20261025` replace?**

Only the rows in partition 2026-10-25 of table `t`. Every other partition stays as it was. The table schema is kept, and Google applies the truncation as one atomic update when the job completes. A reader sees the old day or the new day, never a mix.

The destination is built at `src/recon/load.py:125` as `{table}${run_date:%Y%m%d}`, with no dashes. Every row must belong to that day. `load_day` checks `_arrival_date` (and `DATE(delivered_ts)` for events) before any job runs, and BigQuery would also refuse a row for another partition. The schema passed to the job comes from the same JSON as the table, because a different schema would fail the job.

**3. What happens on an empty day?**

`load_partition` deletes the partition with `client.delete_table(dest, not_found_ok=True)` (`src/recon/load.py:127`) and returns `action: "deleted"` with 0 rows. Deleting a partition is a table operation, not DML, so the sandbox allows it. If the partition does not exist, the delete does nothing.

The delete is needed because WRITE_TRUNCATE with zero rows is not run at all. Without the delete, a rerun of a day that is now empty would keep stale rows from an earlier run. A missing expected file is different from an empty day: `read_ndjson` raises `FileNotFoundError` (`src/recon/load.py:77`). Only a 0-byte file counts as a day with no rows.

**Next step:** S5.1, project config, packages, seeds and sources.

## Review of M4 (2026-11-02)

Three reviewers compared `src/recon/load.py`, `src/recon/fx.py`, `src/recon/cli.py` and the `Makefile` with the load protocol, the FX landing rules and the host guard. None reported a deviation, so nothing was changed.

**Next step:** S5.1, project config, packages, seeds and sources.

## S5.1: project config, packages, typed seeds and sources

**Date and commit:** 2026-11-02, `81aac5e`. This entry and the four after it were written later on 2026-11-02, after a review found that S5.1 to S5.5 had no journal entries. The outputs of the original runs were not kept, so the outputs below come from `make dbt-unit`, `make dbt-build` and two read-only queries run on 2026-11-02 during that fix, on the same code and the same 7 loaded days.

**What was built:**
- `dbt/dbt_project.yml`: paths, the `query-comment` with `job-label: true`, the vars, and the materialization per folder.
- `dbt/packages.yml` and `dbt/package-lock.yml`: `dbt-labs/dbt_utils` 1.4.1, locked by `dbt deps`.
- `dbt/seeds/currencies.csv` (2 rows), `dbt/seeds/reason_codes.csv` (9 rows) and `dbt/seeds/_seeds.yml`, which types every column of all three seeds (`mids` included).
- `dbt/models/staging/_sources.yml`: the sources `psp` (`payment_events`, `settlement_lines`) and `fx` (`fx_rates`).
- `Makefile`: `make setup` now runs `dbt deps`; `make dbt-build` is new.

**How it works:**
A seed without `column_types` lets dbt infer a type from the CSV, and a number column can come back as FLOAT64. Typing every column stops that at the door ("Money" in `AGENTS.md`, rule 6).

`dbt/seeds/_seeds.yml:11`
```yaml
        fee_bps: INT64
```

The source dataset comes from the environment, so the same project reads `raw_dev` on the host and `raw` in the DAG, with no custom schema.

`dbt/models/staging/_sources.yml:5`
```yaml
    schema: "{{ env_var('RAW_DATASET', 'raw') }}"
```

Staging and intermediate models are views and marts are tables (`dbt/dbt_project.yml:31` to `:37`). Nothing is incremental, so no config can produce DML. `job-label: true` (`dbt/dbt_project.yml:13` to `:14`) puts the dbt query comment on each BigQuery job as labels. The vars at `dbt/dbt_project.yml:19` to `:24` hold the tunables; `as_of_date` is never set there.

`make dbt-build` (`Makefile:62` to `:63`) runs `cd dbt && uv run dbt build --target dev` with `RAW_DATASET=raw_dev` exported at `Makefile:4`. This follows `docs/build_plan.md` "S5.1 Project config, packages, seeds, sources" and `docs/specs/dbt_project.md`. It rejects inferred seed types and a `generate_schema_name` override.

**Commands and output:**
- `uv run dbt --version`: `installed: 1.12.6`, `bigquery: 1.12.1`.
- `make dbt-build` (the seed lines):
  ```text
  2 of 44 OK loaded seed file analytics_dev.currencies ........................... [INSERT 2 in 6.20s]
  3 of 44 OK loaded seed file analytics_dev.mids ................................. [INSERT 2 in 7.34s]
  4 of 44 OK loaded seed file analytics_dev.reason_codes ......................... [INSERT 9 in 7.83s]
  ```
  "INSERT 2" is dbt's status text. On BigQuery a seed is written by a load job, not by DML.
- `dbt/package-lock.yml` is committed (`git ls-files dbt/package-lock.yml` lists it).

**What went wrong:** Nothing. BigQuery accepted the job labels.

**Interview questions:**
1. *Why give every seed column a type?*
   dbt infers seed types from the CSV text. A money or fee column could become FLOAT64, and a float on the money path breaks exact integer arithmetic. An explicit `INT64` fixes the type before any model reads it.
2. *How does one dbt project read `raw_dev` on the host and `raw` in Airflow?*
   The source schema is `env_var('RAW_DATASET', 'raw')`. The Makefile exports `raw_dev`; the DAG leaves the default `raw`. The output dataset comes from the profile target.

Next step: S5.2.

## S5.2: the four staging models and their generic tests

**Date and commit:** 2026-11-02, `e0c4b23`.

**What was built:**
- `dbt/models/staging/stg_recon__as_of.sql`: one row with `as_of_date` and `scope_start`, plus the target guards.
- `dbt/models/staging/stg_psp__payment_events.sql`: the webhook events, deduplicated.
- `dbt/models/staging/stg_psp__settlement_lines.sql`: the statement lines, not deduplicated.
- `dbt/models/staging/stg_fx__rates.sql`: one first-seen rate per rate date, cast to NUMERIC.
- `dbt/models/staging/_staging.yml`: descriptions and tests (`unique`, `not_null`, `accepted_values`, `relationships`, `dbt_utils.expression_is_true`, `dbt_utils.unique_combination_of_columns`, `dbt_utils.accepted_range`).

**How it works:**
No model may read the wall clock, so "today" is the newest loaded arrival day:

`dbt/models/staging/stg_recon__as_of.sql:32`
```sql
    max(a._arrival_date) as as_of_date,
```

The same file refuses a wrong pairing at compile time: target `dev` must read `raw_dev` (`:8` to `:9`), and target `airflow` must read `raw` and never take the `as_of_date` var (`:2` to `:7`).

Dedup keeps the earliest delivery of each `event_id`, with `delivery_id` as the tie-break so a rerun keeps the same copy. The as-of filter runs in `WHERE`, before the window, so `copies_received` counts every copy loaded up to `as_of_date`:

`dbt/models/staging/stg_psp__payment_events.sql:22`
```sql
where e._arrival_date <= a.as_of_date
qualify row_number() over (
    partition by e.event_id
    order by e.delivered_ts, e.delivery_id
) = 1
```

Statement lines are not deduplicated on purpose (`stg_psp__settlement_lines.sql:1` to `:3`): a repeated line is a PSP defect and must fail `unique` on `line_id`. FX keeps the exact text and casts it once (`stg_fx__rates.sql:12`, `cast(f.rate_text as numeric) as rate`).

This follows `docs/build_plan.md` "S5.2 The four staging models and their generic tests" and the "Deduplication with QUALIFY" concept. It rejects `SELECT DISTINCT` (redeliveries differ in `delivery_id` and `delivered_ts`) and dedup before the as-of filter.

**Commands and output:**
- `make dbt-build` (staging part): the 4 views were created and all 15 staging tests passed, for example:
  ```text
  13 of 44 PASS unique_stg_psp__payment_events_event_id .......................... [PASS in 2.66s]
  22 of 44 PASS unique_stg_psp__settlement_lines_line_id ......................... [PASS in 2.55s]
  ```
- `stg_recon__as_of` on the 7 loaded days: `as_of_date` 2026-10-31, `scope_start` 2026-10-25.

**What went wrong:** Nothing.

**Interview questions:**
1. *Why order the dedup by `delivered_ts` and then `delivery_id`?*
   Two copies can share a `delivered_ts`. Without a unique tie-break, `ROW_NUMBER` may pick a different copy on each run, and a rerun would not be byte-stable.
2. *Why is `copies_received` correct even though `QUALIFY` drops rows?*
   Window functions are computed before `QUALIFY` filters, so `COUNT(*) OVER (PARTITION BY event_id)` sees every copy that passed the `WHERE`.

Next step: S5.3.

## S5.3: UT1 first, then `int_ledger__captures`

**Date and commits:** 2026-11-02, `72d7ad3` (UT1 and the naive model), `4c131b9` (the real cut-off logic), `b78f542` (the green hash in the failure log).

**What was built:**
- `dbt/models/_unit_tests.yml`: UT1 `ut_captures_cutoff_both_directions`, with both direct parents mocked (`stg_psp__payment_events` and the seed `mids`).
- `dbt/models/intermediate/int_ledger__captures.sql`: one row per captured payment with `booking_date`, `expected_accounting_date` and `due_date`.
- `dbt/models/intermediate/_intermediate.yml`: its description and tests.
- `Makefile`: `make dbt-unit` (`Makefile:65` to `:66`).
- `docs/failure_log.md`: the UT1 row in "Planned red runs (not bugs)".

**How it works:**
The PSP books a sale on the day of its statement time zone, not on our UTC day. Each MID has a fixed offset (+5 for KZT, -5 for USD), so the expected accounting date is the capture time shifted by that offset:

`dbt/models/intermediate/int_ledger__captures.sql:18`
```sql
    date(timestamp_add(e.event_ts, interval m.statement_utc_offset_hours hour)) as expected_accounting_date,
```

The due date adds the MID's settlement lag and the grace days (`:19` to `:22`). From the due date on (inclusive), a ledger-only line is missing. The `LEFT JOIN` to `mids` (`:24`) keeps a payment with an unknown MID: its dates come out NULL and the `not_null` tests fail, where an inner join would drop it silently.

UT1 has six rows around both cut-offs: KZT at 18:59:59, 19:00:00 and 19:30:00 UTC, and USD at 03:00, 04:59:59 and 05:00:00 UTC (`dbt/models/_unit_tests.yml:14` to `:19`). The first version used the naive rule `date(e.event_ts) as expected_accounting_date` (`72d7ad3`, line 16 of the model), so UT1 had to be red.

This follows `docs/build_plan.md` "S5.3 UT1 first, then `int_ledger__captures`" and the "Cut-off times, time zones and the accounting date" concept.

**Commands and output:**
- Red run at `72d7ad3`, recorded in `docs/failure_log.md` "Planned red runs (not bugs)": `1 of 1 FAIL 1 int_ledger__captures::ut_captures_cutoff_both_directions`, with `pay_k2`, `pay_k3`, `pay_u1` and `pay_u3` differing in `expected_accounting_date` and `due_date`.
- Green, rerun on 2026-11-02 with `make dbt-unit`:
  ```text
  2 of 2 PASS int_ledger__captures::ut_captures_cutoff_both_directions ........... [PASS in 7.42s]
  ```
- `make dbt-build`: `int_ledger__captures` created, its 5 tests passed, ends `Done. PASS=44 WARN=0 ERROR=0`.

**What went wrong:** Nothing unplanned. The red run was planned, so it has a "Planned red runs" row and no failure-log entry.

**Interview questions:**
1. *A KZT payment at 19:00 UTC on 20 October: which accounting date?*
   21 October. 19:00 UTC plus 5 hours is midnight in the statement zone, so it falls on the next day. 18:59:59 stays on the 20th.
2. *What is the difference between UT1 and a data test?*
   UT1 runs the model's logic on fixed rows chosen to sit on the cut-off edges and compares exact outputs. A data test checks a property of whatever data is loaded, so it would only catch a cut-off bug if the data happened to contain an edge case.

Next step: S5.4.

## S5.4: `int_fx__usd_rates_daily` and the `to_usd` macro

**Date and commit:** 2026-11-02, `bf04a7e`.

**What was built:**
- `dbt/models/intermediate/int_fx__usd_rates_daily.sql`: one row per (currency, day) from the earliest rate date to `as_of_date`, with `units_per_usd`, `rate_date` and `carry_days`.
- `dbt/models/intermediate/_intermediate.yml`: its tests (unique (currency, day), `not_null`, and the staleness bound on `carry_days`).
- `dbt/macros/to_usd.sql`: the one rounding stage for USD reporting columns.

**How it works:**
A date spine makes one row per calendar day (`int_fx__usd_rates_daily.sql:41`, `generate_date_array(b.first_rate_date, a.as_of_date)`). NBK publishes on weekdays only, so a day without a rate takes the last published one and keeps its date:

`dbt/models/intermediate/int_fx__usd_rates_daily.sql:51`
```sql
        last_value(r.rate ignore nulls) over w as units_per_usd,
        last_value(r.rate_date ignore nulls) over w as rate_date
```

`carry_days` is `date_diff(c.day, c.rate_date, day)` (`:85`), and its test bounds it by `var('fx_max_carry_days')` (`_intermediate.yml:64` to `:70`), so a long gap in the feed fails the build. USD gets identity rows with `units_per_usd = 1` and `carry_days = 0` (`:65` to `:77`, `:96`). The carry-forward is a project convention, not NBK's official rate for that day.

The macro casts to NUMERIC before any division, so nothing is INT64 / INT64, and rounds once:

`dbt/macros/to_usd.sql:5`
```sql
round(cast({{ minor_col }} as numeric) / {{ minor_per_major_col }} / {{ units_per_usd_col }}, 2)
```

This follows `docs/build_plan.md` "S5.4 `int_fx__usd_rates_daily` and the `to_usd` macro" and the concepts "As-of joins, date spines and carry-forward" and "FX rates, direction, cross rates and the carry-forward". It rejects `POW()` and FLOAT64 rates.

**Commands and output:**
- `make dbt-build`: the view was created and its 4 tests passed, `carry_days` range test included.
- Spot check, rerun on 2026-11-02 through `recon.bq` (`select currency, day, rate_date, carry_days, units_per_usd from analytics_dev.int_fx__usd_rates_daily where day between '2026-10-23' and '2026-10-27'`), real NBK rates:

  | currency | day | rate_date | carry_days | units_per_usd |
  |---|---|---|---|---|
  | KZT | 2026-10-23 (Fri) | 2026-10-23 | 0 | 447.94 |
  | KZT | 2026-10-24 (Sat) | 2026-10-23 | 1 | 447.94 |
  | KZT | 2026-10-25 (Sun) | 2026-10-23 | 2 | 447.94 |
  | KZT | 2026-10-26 (Mon) | 2026-10-26 | 0 | 451.05 |
  | USD | each day | the same day | 0 | 1 |

  The Saturday KZT row has Friday's `rate_date` and `carry_days = 1`, as the done-when check asks.

**What went wrong:** Nothing.

**Interview questions:**
1. *Why keep `rate_date` next to the carried rate?*
   It shows which published rate a weekend day really used, and `carry_days` is computed from it. Without it a stale rate looks like a fresh one.
2. *Why cast to NUMERIC before dividing in `to_usd`?*
   In BigQuery INT64 / INT64 returns FLOAT64. Casting the minor units to NUMERIC first keeps the whole calculation exact, and `ROUND(..., 2)` is the single rounding stage.

Next step: S5.5.

## S5.5: UT2 first, then `fct_recon_lines`

**Date and commits:** 2026-11-02, `8ed9fe6` (UT2, `_marts.yml` and the stub that labels every line `matched`), `74fb5d8` (the real matcher), `4139e6c` (the green hash in the failure log). After review on 2026-11-02, a dated correction was appended to the UT2 red-run row in `docs/failure_log.md`.

**What was built:**
- `dbt/models/_unit_tests.yml`: UT2 `ut_lines_status_and_date_shift`, with every direct parent mocked: `stg_recon__as_of`, the seed `mids`, `int_ledger__captures` and `stg_psp__settlement_lines` (`:35` to `:70`).
- `dbt/models/marts/fct_recon_lines.sql`: the matcher, a table partitioned by `recon_date` and clustered by `mid`.
- `dbt/models/marts/_marts.yml`: its description and column tests (`unique` and `not_null` on `payment_id`; `not_null` on `recon_date`, `as_of_date`, `match_status` and `primary_reason`; `accepted_values` on `match_status`; `relationships` from `primary_reason` to `reason_codes`).
- `docs/failure_log.md`: the UT2 row in "Planned red runs (not bugs)", and its later correction note.

**How it works:**
The `SALE` filter sits in a CTE before the join. After the join it would also drop every ledger-only line, whose statement columns are NULL (the trap in `AGENTS.md` "Known traps from the plan review"):

`dbt/models/marts/fct_recon_lines.sql:54`
```sql
    where s.record_type = 'SALE'
```

The join is an equality `FULL OUTER JOIN` on `payment_id`, so lines seen on only one side are kept:

`dbt/models/marts/fct_recon_lines.sql:82`
```sql
    full outer join statement as s
        on l.payment_id = s.payment_id
```

One `CASE` gives exactly one `match_status` per line, judged against `as_of_date` from the data. The due date is inclusive: `in_transit` only while `as_of_date < due_date`. A one-sided line dated before `scope_start` is `before_scope`:

`dbt/models/marts/fct_recon_lines.sql:109`
```sql
        case
            when t.has_ledger and t.has_statement then 'matched'
            when t.has_ledger and t.booking_date < t.scope_start then 'before_scope'
            when t.has_ledger and t.as_of_date < t.due_date then 'in_transit'
            when t.has_ledger then 'missing_in_statement'
            when date(t.captured_ts) < t.scope_start then 'before_scope'
            else 'missing_in_ledger'
        end as match_status,
```

`date_shift` (`:117` to `:122`) is `none` when the PSP date equals our booking date, `timing_cutoff` when it equals the MID's expected accounting date, and `date_mismatch` otherwise. The fee check is integer only (`:138` to `:139`): `+ 5000` then `DIV` rounds half up, `+ 9999` then `DIV` is a ceiling. A variance equal to the tolerance is within it (`:151` to `:152`, `>` not `>=`). `primary_reason` (`:190` to `:200`) takes the first true condition in the precedence of `reason_codes.csv`. `is_exception` (`:202` to `:205`) wraps the `date_shift` test in `coalesce(..., false)`, because `FALSE OR NULL` is NULL in BigQuery.

The red stub at `8ed9fe6` wrote `'matched' as match_status` for every row (line 124 of that version) and left the flags and fees empty. UT2's six rows cover each status and both date shifts: `pay_a` in transit, `pay_b` missing on its due date, `pay_c` matched with a cut-off shift, `pay_d` matched with an unexplained date, `pay_e` statement-only in scope, `pay_f` statement-only before scope. Each statement row sets `record_type: SALE` (`_unit_tests.yml:58` to `:61`).

This follows `docs/build_plan.md` "S5.5 UT2 first, then `fct_recon_lines`", `fct_recon_lines` and UT2 in `docs/specs/dbt_project.md`, and the concepts "FULL OUTER JOIN matching", "Line statuses, due dates and scope" and "Minor units and integer fee arithmetic". It rejects an `OR` join condition, a filter after the join, and `ROUND(x * bps / 10000)`.

**Commands and output:**
- Red run at `8ed9fe6`, recorded in `docs/failure_log.md`: `1 of 2 FAIL 1 fct_recon_lines::ut_lines_status_and_date_shift`. The rows that differed in `match_status` were `pay_a`, `pay_b`, `pay_e` and `pay_f` (see the correction note below that table).
- Green, rerun on 2026-11-02 with `make dbt-unit`:
  ```text
  1 of 2 PASS fct_recon_lines::ut_lines_status_and_date_shift .................... [PASS in 8.26s]
  2 of 2 PASS int_ledger__captures::ut_captures_cutoff_both_directions ........... [PASS in 7.42s]
  Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=2
  ```
- `make dbt-build`, rerun on 2026-11-02:
  ```text
  36 of 44 OK created sql table model analytics_dev.fct_recon_lines .............. [CREATE TABLE (1.6k rows, 432.3 KiB processed) in 5.12s]
  Done. PASS=44 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=44
  ```
- Lines per status and primary reason on the 7 synthetic days (as-of 2026-10-31, scope start 2026-10-25), from a query through `recon.bq`: `matched` 1217 (824 `matched`, 362 `timing_cutoff`, 27 `fee_mismatch`, 4 `amount_mismatch`), `before_scope` 178, `in_transit` 175, `missing_in_ledger` 6, `missing_in_statement` 2. These are outputs of this repo's own dev run on synthetic data, not results; the measured results come later from `docs/evidence/`.
- `unexplained_minor` does not exist yet: `fct_recon_daily` and its identity test come in S5.6.

**What went wrong:** The red run was planned. Its first record in "Planned red runs (not bugs)" said "every row but `pay_c`" differed in `match_status`; `pay_d` also expects `matched`, so it did not differ. A dated correction was appended below the table. It is a record error, not a code bug, so it has no failure-log entry.

**Interview questions:**
1. *Why must the `record_type = 'SALE'` filter sit before the join?*
   After a `FULL OUTER JOIN`, a ledger-only line has NULL statement columns, so `WHERE record_type = 'SALE'` would drop it. Those one-sided lines are exactly the exceptions the matcher exists to find.
2. *A ledger-only line has `due_date` 2026-10-28 and the as-of date is 2026-10-28. What is its status?*
   `missing_in_statement`. The due date is inclusive, so `in_transit` only holds while `as_of_date < due_date` (`pay_b` in UT2).

## S5.6: `fct_recon_daily` and the three integrity tests

**Date and commit:** 2026-11-02, `6c97a10`.

**What was built:**
- `dbt/models/marts/fct_recon_daily.sql`: the two-calendar bridge. It has one row per (MID, currency, day), with the gap, seven dated components, `unexplained_minor`, fees and the USD reporting columns.
- `dbt/models/marts/_marts.yml`: its contract (`enforced: true`, `:95` to `:96`), column types and descriptions, and a unique test on (`mid`, `currency`, `recon_date`).
- `dbt/tests/assert_recon_decomposition_closes.sql`, `dbt/tests/assert_no_money_lost_between_layers.sql` and `dbt/tests/assert_redeliveries_identical.sql`: three singular tests. A singular test is a SQL file that passes when it returns no rows.

**How it works:**
The gap is computed top-down, straight from the input models, and never passes through the matcher:

`dbt/models/marts/fct_recon_daily.sql:25`
```sql
        c.booking_date as day,
        count(*) as ledger_line_count,
        sum(c.amount_minor) as ledger_gross_minor
    from {{ ref('int_ledger__captures') }} as c
```

The statement side does the same with `stg_psp__settlement_lines` by `accounting_date` (`:33` to `:47`). The components come bottom-up from `fct_recon_lines` only (`:83` to `:142`). A matched line with a date shift adds +L on its booking date and -L on its accounting date (`:99` to `:104` and `:111` to `:116`). The amount difference L - S lands once, on the accounting date (`:88` to `:92`). One-sided lines add +L or -S on their own date. The identity subtracts the sum of the seven components from the gap:

`dbt/models/marts/fct_recon_daily.sql:230`
```sql
        y.ledger_gross_minor - y.statement_gross_minor as gap_minor,
        y.ledger_gross_minor - y.statement_gross_minor
        - (
            y.timing_cutoff_minor
```

The test then checks that this difference is zero, with no tolerance:

`dbt/tests/assert_recon_decomposition_closes.sql:11`
```sql
where d.unexplained_minor != 0
```

The spine (`:68` to `:78`) crosses every MID in `mids` with every day between the earliest and latest input date, so a day with no activity shows zeros. The bounds use one `UNION ALL` column, not `LEAST(MIN(...), MIN(...))`, because `LEAST` returns NULL if any argument is NULL (`:49` to `:50`). Fees never enter the gross identity. USD columns are added only at the end, through `to_usd` (`:270` to `:274`).

The identity alone cannot see a matched same-day line that was dropped with equal amounts, because it adds 0 to the gap. `assert_no_money_lost_between_layers.sql` therefore compares the count and sums per MID between each input model and the matcher's matching side:

`dbt/tests/assert_no_money_lost_between_layers.sql:92`
```sql
where c.ledger_in_count is distinct from c.ledger_out_count
```

`assert_redeliveries_identical.sql` reads every raw delivery. It returns any `event_id` whose copies differ in a business field (`:15` to `:20`), because keeping the first copy is only safe if all copies agree.

This follows ADR-0003 and "The two-calendar bridge and the identity (and why it is not a tautology)" in `docs/learning/concepts.md`. ADR-0003 rejects an identity checked against its own residual, because it can never fail. Whether each test actually turns red on a broken matcher is shown by the mutation check in S7.5, not yet.

**Commands and output:**
- `uv run dbt --version`: Core 1.12.6, bigquery 1.12.1.
- `make dbt-build`:
  ```text
  39 of 49 PASS assert_no_money_lost_between_layers
  47 of 49 OK created sql table model analytics_dev.fct_recon_daily [CREATE TABLE (18.0 rows, 403.7 KiB processed)]
  48 of 49 PASS assert_recon_decomposition_closes
  49 of 49 PASS dbt_utils_unique_combination_of_columns_fct_recon_daily_mid__currency__recon_date
  Finished running 3 seeds, 2 table models, 36 data tests, 2 unit tests, 6 view models
  Done. PASS=49 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=49
  ```
  `assert_redeliveries_identical` passed earlier in the same build. A warning about NUMERIC with unspecified precision on `units_per_usd`, `ledger_gross_usd`, `statement_gross_usd` and `gap_usd` is expected under the spec, and plain `numeric` was kept.
- The done-when query through `recon.bq` (`use_cache=False`) on synthetic dev data:
  ```text
  [{'days_not_closing': 0, 'abs_unexplained_minor': 0}]
  ```
- Per-MID check (synthetic): `mid_kzt_01` and `mid_usd_01` each have 9 spine days, 2026-10-23 to 2026-10-31. `timing_cutoff_minor` sums to 0 over the window for both, as +L and -L cancel. No `units_per_usd` is NULL.
- `make check`: 9 passed, exit 0. Em dash grep on `dbt`: exit 1 (clean). The grep for `insert|update|delete|merge|current_date|current_timestamp|float64|pow(` in the new files: no match.

**What went wrong:** Nothing. The identity closed on the first build, so there is no failure-log entry. Some notes on deviations. `exception_count` and `exception_abs_minor` are left out until S7.2, as the plan says. `fx_carry_days` is not wrapped in `COALESCE(..., 0)`, because 0 would claim a fresh rate on a day whose `units_per_usd` is NULL. The banned-word grep could not run because the permission check denied it. The owner, or the pre-push hook, runs it before the next push.

**Interview questions:**
1. *Why is `unexplained_minor` not a tautology?*
   The gap comes from `int_ledger__captures` and `stg_psp__settlement_lines`. The components come only from `fct_recon_lines`. If the matcher loses, duplicates or misdates a line, or uses a wrong sign, the two paths disagree and the difference is not zero. A residual defined as "gap minus explained" and then tested against itself could never fail.
2. *Why is `assert_no_money_lost_between_layers` needed when the identity already closes?*
   A matched line on the same day with L = S adds 0 to the gap and 0 to every component. If the matcher dropped it, the identity would still close. Comparing counts and sums per MID between the inputs and the matcher catches that case.

## Explain check M5

**1. Why a tie-break in QUALIFY?**

Dedup keeps one delivery per `event_id` with `ROW_NUMBER()` (`dbt/models/staging/stg_psp__payment_events.sql:23` to `:26`), ordered by `e.delivered_ts, e.delivery_id`. Two copies can share a `delivered_ts`. Without `delivery_id` as the second key, `ROW_NUMBER` may rank the tied rows differently on each build. Then `first_delivery_id` and `first_arrival_date` could change between two builds of the same data, and the rerun proof's fingerprints could differ. `delivery_id` is unique per copy, so the same row wins every time.

**2. Why must the FULL OUTER JOIN keep an equality?**

BigQuery refuses a `FULL OUTER JOIN` whose condition has no equality between the two sides. The design also matches on one exact key: `on l.payment_id = s.payment_id` (`dbt/models/marts/fct_recon_lines.sql:82` to `:83`). An `OR` condition could match one statement line to several ledger lines, which would break the grain of one row per `payment_id` and count money twice. With the equality, each payment gets one row, and `has_ledger` and `has_statement` (`:64` to `:65`) tell which sides it was seen on.

**3. Why can the identity test fail?**

Its two sides come from different models. `gap_minor` is top-down: ledger totals from `int_ledger__captures` by `booking_date` (`dbt/models/marts/fct_recon_daily.sql:20` to `:31`) minus statement totals from `stg_psp__settlement_lines` by `accounting_date` (`:33` to `:47`). The seven components are bottom-up, built only from `fct_recon_lines` (`:83` to `:142`). `assert_recon_decomposition_closes.sql:11` returns any MID-day where they differ by even one minor unit. A matcher that loses a one-sided line, duplicates a line, puts +L or -L on the wrong day, uses a wrong sign or forgets a component makes the sides differ. On the synthetic dev data it returned 0 and 0. The mutation check in S7.5 will show which tests turn red for each planted break.

**4. Why is there no `CURRENT_DATE()` in any model?**

Statuses must depend only on the loaded data. "Today" comes from `max(a._arrival_date) as as_of_date` (`dbt/models/staging/stg_recon__as_of.sql:32`), and the matcher compares against it: `when t.has_ledger and t.as_of_date < t.due_date then 'in_transit'` (`dbt/models/marts/fct_recon_lines.sql:112`). With the wall clock, rebuilding the same data a day later would turn `in_transit` lines into `missing_in_statement`. The rerun proof would fail, and no result could be reproduced. ADR-0002 rejects `CURRENT_DATE()` for this reason.

## Review of M5 (2026-11-02)

Each M5 step was checked by two reviewers (one against the spec, one against the hard rules on DML, money, dates and tests), and every finding by two skeptics. Steps S5.1, S5.2, S5.3, S5.4 and S5.6 had no findings. In S5.5 two were confirmed: the UT2 red-run row in `docs/failure_log.md` named the wrong rows, so a dated correction was appended below the table (`0ca3dfc`; the row itself is kept, as the failure-log rules require), and the S5.1 to S5.5 journal entries were missing (`2a656ef`).

One deliberate deviation is open for the owner. `docs/specs/dbt_project.md`, heading "fct_recon_daily", says every INT64 column of `fct_recon_daily` is wrapped in `COALESCE(..., 0)` so that a day without activity shows zeros. `fx_carry_days` is INT64 but is left unwrapped: it is not an activity count, and the same section says the FX columns may be NULL on a day before the first rate, so a 0 next to a NULL `units_per_usd` would claim a fresh rate that does not exist. Over the full window every day has a rate, so the output is the same either way.


## S6.1: `dags/recon_daily.py`

**Date and commit:** 2026-11-02, `ebdff8e`.

**What was built:**
- `dags/recon_daily.py`: the daily pipeline. A module docstring with the interval rules, `log_failure`, `_bq_client`, `_landing_dir`, and the `recon_daily` DAG with six tasks: `check_window`, `ensure_tables`, `generate_day`, `fetch_fx`, the mapped `load_raw`, and `dbt_build`.

**How it works:**
One run owns one UTC arrival day R. The schedule is an explicit `CronDataIntervalTimetable`, because in Airflow 3 a cron string or `"@daily"` becomes a `CronTriggerTimetable`, whose data interval has zero length:

`dags/recon_daily.py:62`
```python
    schedule=CronDataIntervalTimetable("0 0 * * *", timezone="UTC"),
```

`check_window` turns the data interval into R. It refuses a missing interval, and an interval that is not exactly one UTC day starting at 00:00 (line 82). It then reads the wall clock once, only to check the window, and calls the same `check_run_date` the host CLI uses, so the DAG and `make day` can never disagree about the 45-day guard:

`dags/recon_daily.py:85`
```python
        today = datetime.now(UTC).date()          # the only wall-clock read in the DAG, and only to check
```

`dags/recon_daily.py:93`
```python
            raise AirflowFailException(str(err)) from err
```

`AirflowFailException` fails the task at once with no retry. Every later Python task receives R from `check_window` through XCom as a `YYYY-MM-DD` string. `ensure_tables` first refuses any `RAW_DATASET` other than `raw` (line 99), so the loader and the dbt sources always point at the same dataset. `fetch_fx` retries 3 times with `retry_exponential_backoff=2.0`, a float multiplier, never `True` (line 117). The three loads are one task mapped over the tables:

`dags/recon_daily.py:144`
```python
        load_raw.partial(run_date=rd).expand(table=TABLES),
```

`dbt_build` is a `BashOperator` with the exact inline command from the spec, `pool="dbt_serial"` (one slot, so a backfill run and a scheduled run never build dbt at the same time) and `append_env=True`, so it keeps `PATH`, `HOME` and the key path (lines 134 and 135). Its only template is `{{ data_interval_start | ds }}`, used for the per-day `runs/dbt/<R>/` folders. Heavy imports (the BigQuery hook, the `recon` package) sit inside the task functions, because the dag-processor parses the file about every 30 seconds.

This follows "recon_daily settings", "recon_daily tasks", "The dbt_build command, piece by piece" and "recon_daily code shape" in `docs/specs/airflow_and_docker.md`, and ADR-0005. It rejects `schedule="@daily"` (empty interval), `{{ ds }}` for business dates, and a second copy of the date rules inside the DAG.

**Commands and output:**
- `uv run ruff check dags/` first reported 4 errors (UP017, use `datetime.UTC` instead of `timezone.utc`). Fixed with `ruff --fix`; then `All checks passed!`. `uv run ruff check dags/ --select AIR301,AIR302`: `All checks passed!`.
- `docker compose exec airflow-scheduler airflow dags list-import-errors`: `No data found`.
- `airflow tasks list recon_daily`: `check_window`, `dbt_build`, `ensure_tables`, `fetch_fx`, `generate_day`, `load_raw`.
- `airflow dags list`: `recon_daily` with `is_paused` True (new DAGs start paused).

**What went wrong:** Nothing in the repo. The file was written while the M5 workflow was running and committed only after M5 finished, so the two never staged files at the same time.

**Interview questions:**
1. *Why does a run for 2026-10-25 start on 2026-10-26?* Its data interval is [2026-10-25 00:00, 2026-10-26 00:00) UTC, and a run starts only after its interval has ended. The logical date is 2026-10-25, but the run id carries `run_after`, 2026-10-26, so runs are always named by logical date.
2. *Why is the dbt command not in a `.sh` file?* Airflow treats a `bash_command` string ending in `.sh` as the name of a template file to load, not as a command. Keeping it inline also keeps the one template, `{{ data_interval_start | ds }}`, visible in the DAG.

## S6.2: the first real run

**Date and commit:** 2026-11-02, `050b7d2` (the `unpause` and `pause` targets) and `a59c0b7` (the FX file the run landed).

**What was built:** `make unpause` and `make pause` in the `Makefile`.

**How it works:** with `catchup=False`, unpausing creates exactly one run: the latest complete interval. The plan was written for Sunday 2026-11-01, when that interval would have been 2026-10-31. The build ran on Monday 2026-11-02 at 18:29 UTC, so unpausing created the run for **2026-11-01** instead. This is a date shift, not a deviation: the plan's history (2026-10-04 to 2026-11-01, 29 runs) stays the same, because the backfill in S6.3 then covers 2026-10-04 to 2026-10-31.

**Commands and output:**
- `make unpause`, then `airflow dags list-runs recon_daily`:
  ```text
  recon_daily  scheduled__2026-11-02T00:00:00+00:00  success  run_after 2026-11-02T00:00:00+00:00  logical_date 2026-11-01T00:00:00+00:00  start 18:29:01  end 18:30:21
  ```
- `airflow tasks states-for-dag-run recon_daily 2026-11-01`: all 8 task instances `success` (`check_window`, `ensure_tables`, `generate_day`, `fetch_fx`, `load_raw` map indexes 0, 1 and 2, `dbt_build`). `dbt_build` took 62 seconds of the run.
- The `check_window` log contains `run_date=2026-11-01`.
- **[T] = 80 seconds** (18:29:01 to 18:30:21 UTC).
- `fetch_fx` landed `landing/fx/provider=nbk/arrival_date=2026-11-01.json` and its meta file, committed in `a59c0b7`.

**What went wrong:** Nothing. Gate G1's first half (one run green end to end) passed.

**Interview questions:**
1. *The run id says 2026-11-02 but the run processed 2026-11-01. Why?* In Airflow 3.3.2 a run id is the run type plus `run_after`, the end of the interval. The processed day is the logical date, the start of the interval. `check_window` logs it as `run_date=`, which is the line to read.
2. *Why not `airflow dags trigger -l 2026-10-31` to run an exact day?* A CLI trigger infers its interval from the trigger time, not from `-l`, so it processes yesterday relative to now while recording the logical date you typed. Exact days run only through a one-day backfill after a dry run.

## S6.3: freeze, then the history backfill (G1)

**Date and commit:** 2026-11-02, `9fe1bdd` (the `backfill-dry` and `backfill` targets), tag `g1-freeze` on `9fe1bdd`.

**What was built:** `make backfill-dry FROM= TO=` and `make backfill FROM= TO=`. Both run `airflow backfill create --dag-id recon_daily --from-date $(FROM) --to-date $(TO) --run-backwards --max-active-runs 1`, the dry run with `--dry-run`, and both refuse empty dates.

**How it works:** the tag `g1-freeze` marks the code that produced the history. From now until the rerun proof is committed, nothing changes under `src/recon/` or `dags/`, or in `dbt/seeds/mids.csv`. `--run-backwards` loads newest first, so every run sees a contiguous history from its own date up to the latest loaded day; oldest first, after the 2026-11-01 run exists, would leave a gap that `assert_arrival_days_complete` correctly fails. `--max-active-runs 1` keeps backfill runs one at a time. With [T] = 80 seconds, 28 runs take about 40 minutes, far inside the plan's 4-hour rule, so the full history was kept (no cut-order item 4).

**Commands and output:**
- `git status --short` showed only `.vscode/` (the owner's editor settings, never part of the build). `git tag -a g1-freeze -m "G1: generator and loader frozen"`, then `git push origin main g1-freeze`: `* [new tag] g1-freeze -> g1-freeze` (the pre-push hook ran).
- `make backfill-dry FROM=2026-10-04 TO=2026-10-31`: 28 logical dates, newest first (2026-10-31 down to 2026-10-04); `list-runs` still showed one run, so the dry run created nothing.
- `make backfill FROM=2026-10-04 TO=2026-10-31` at 18:31 UTC: `Created backfill Dag run. backfill_id=1` for each of the 28 dates.

**What went wrong:** Nothing so far. The backfill's result is checked in S7.1.

**Interview questions:**
1. *Why newest first?* `assert_arrival_days_complete` requires a row on every day from `scope_start` to `as_of_date`. Newest first, each finished run extends the loaded history downwards without a hole; oldest first would build marts with a gap between the oldest loaded days and 2026-11-01.
2. *What does the pool `dbt_serial` stop, and what does it not stop?* It stops two `dbt_build` tasks (for example a backfill run and the 00:00 UTC scheduled run) from rebuilding the same marts at once. It does not stop another run's `load_raw` from landing a new day during a build, which is why the backfill must finish before 00:00 UTC.

## Explain check M6

1. *Which interval does the run for 2026-10-25 process?* [2026-10-25 00:00, 2026-10-26 00:00) UTC: everything that arrived during UTC day 2026-10-25. It starts after 2026-10-26 00:00 UTC, and `check_window` returns `2026-10-25`.
2. *Why CronDataIntervalTimetable?* In Airflow 3 a cron string or `"@daily"` becomes a `CronTriggerTimetable`, whose data interval starts and ends at the trigger time. `check_window` would then see a zero-length interval and fail. `CronDataIntervalTimetable("0 0 * * *", timezone="UTC")` gives a one-day interval ending at UTC midnight.
3. *What does a CLI trigger process?* `airflow dags trigger recon_daily -l L` takes its interval from the trigger time, so it processes yesterday relative to now while recording logical date L. Without `-l` there is no interval at all, and `check_window` fails with "No data interval".
4. *Why newest first?* So the loaded history is always contiguous up to the latest day, and the completeness test and the marts never see a hole.

## S7.1: check the overnight backfill

**Date and commit:** 2026-11-02, `0e3f837` (the FX files the backfill landed).

**What was built:**
- No code. 42 new real-data files in `landing/fx/provider=nbk/`: one body file (`arrival_date=R.json`) and one meta file (`arrival_date=R.meta.json`) for each of the 21 run dates 2026-10-04 to 2026-10-24.

**How it works:**
This step checks the backfill from S6.3 before anything is built on top of it. Two things have to be true: every run is green, and the three raw tables have one non-empty partition for each loaded day. A partition is the slice of a table for one `_arrival_date`. The step also commits the FX files the runs landed. They are real NBK rates, and they are never fetched a second time:

`src/recon/fx.py:53`
```python
    if body_path.exists() and meta_path.exists():
        log.info("already landed: %s", body_path.name)
        print(f"already landed: {body_path.name}")
        return {"action": "skipped"}
```

This is why the backfill landed only 21 new dates. The FX files for 2026-10-25 to 2026-10-31 were committed in S4.3 (`5a83aa0`), and the file for 2026-11-01 was committed in S6.2 (`a59c0b7`). 21 + 7 + 1 = 29 meta files. A fresh clone needs all 29 to rebuild the window with the same rates. Fetching again could return different digits if NBK restated a rate. This follows S7.1 in `docs/build_plan.md` and "Files you do not touch" in `AGENTS.md`, where `landing/fx/` is immutable once landed. The rejected alternative is to leave `landing/fx/` untracked and refetch on a clone. A rate fetched again is not guaranteed to match, and that would break reproducibility.

The settlement count on 2026-10-04 is lower than on the other days, and that is expected. The marts take "the first day" from the oldest loaded arrival day:

`dbt/models/staging/stg_recon__as_of.sql:34`
```sql
    min(a._arrival_date) as scope_start
```

On that first day only USD statement lines can arrive, because statements arrive 1 or 2 days after their accounting date. That is the case the S7.4 completeness test allows for, with an interval open at the start.

**Commands and output:**
- `airflow dags list-runs recon_daily --state failed`: `No data found`. The same with `--state running`: `No data found`.
- `airflow dags list-runs recon_daily`: 29 runs, all `success`, logical dates 2026-10-04 to 2026-11-01. That is 28 backfill runs created at 18:31 UTC plus the S6.2 run, all finished by 19:07 UTC.
- The per-day counts, through the Python client: `raw.payment_events`, `raw.settlement_lines` and `raw.fx_rates` each have 29 partitions, 2026-10-04 to 2026-11-01, and no day has zero rows (synthetic payments, real FX):
  ```text
  payment_events    191 to 230 rows per day
  settlement_lines   43 to 214 rows per day (43 on 2026-10-04, where only USD lines can arrive)
  fx_rates            5 or 6 rows per day
  ```
- `ls landing/fx/provider=nbk/*.meta.json | wc -l`: `29`.
- `git add landing/fx && git commit ...`: 42 files changed. Then `git status --short landing/fx` printed nothing.

**What went wrong:** Nothing. No run failed, so there is no failure-log entry and no `tasks clear` was needed.

**Interview questions:**
1. *Why commit real FX files to git when the pipeline could fetch them again?*
   `fetch_fx` lands each date once and skips it from then on (`src/recon/fx.py:53` to `:56`). A rate fetched later could differ if the source restated it, so a clone that refetched might not rebuild the same USD columns. Committing the exact bodies and their meta files makes the window reproducible.
2. *Why does `raw.fx_rates` have only 5 or 6 rows per day when each request covers 7 days?*
   The request for run date R covers R-6 to R. NBK does not publish a rate on every calendar day, so some days in that range have no item. The daily FX model carries the last rate forward over those days, which is a project convention, not NBK's official rate for that day.

## S7.2: `fct_recon_exceptions`, and its two columns in the daily mart

**Date and commit:** 2026-11-02, `6693bc5`.

**What was built:**
- `dbt/models/marts/fct_recon_exceptions.sql`: the analyst work queue, built as a view. It has one row per (`payment_id`, `cause`).
- `dbt/models/marts/fct_recon_daily.sql`: a new CTE `exceptions_daily` and two new columns, `exception_count` and `exception_abs_minor`.
- `dbt/models/marts/_marts.yml`: the model's description and three tests. These are `unique_combination_of_columns` on (`payment_id`, `cause`), `not_null` on `amount_minor`, and `relationships` from `cause` to `reason_codes.code`. The two new columns were also added to the `fct_recon_daily` contract, at positions 22 and 23.

**How it works:**
The queue reads `fct_recon_lines` and drops every out-of-scope line first:

`dbt/models/marts/fct_recon_exceptions.sql:30`
```sql
    where l.match_status != 'before_scope'
```

It then builds one `SELECT` per cause and stacks them with `UNION ALL` (`:34` to `:84`). One line can have two causes, for example an amount difference and a fee overcharge, so it can produce two rows, each with its own signed amount and cause date. The sign rule is that positive means the ledger has more, or the PSP overcharged. That is why a payment missing from the ledger is negated:

`dbt/models/marts/fct_recon_exceptions.sql:49`
```sql
        -l.statement_gross_minor as amount_minor,
```

Each branch carries only `payment_id`, `cause`, `amount_minor` and `cause_date`. The stacked result is joined back to the filtered lines on `payment_id` (`:102` to `:104`) to get `mid`, the dates and the evidence ids. This is safe because `payment_id` is unique in `fct_recon_lines`, and a test enforces that. `age_days` uses `DATE_DIFF` against the loaded `as_of_date`, never the wall clock (`:96`).

The daily mart counts the queue by `cause_date` and sums absolute values, so a +100 break and a -100 break on the same day cannot cancel to 0:

`dbt/models/marts/fct_recon_daily.sql:186`
```sql
        sum(if(e.cause != 'date_mismatch', abs(e.amount_minor), 0)) as exception_abs_minor
```

`date_mismatch` is counted but not summed. Its amount is a whole payment that was booked on the wrong day, not money lost.

This follows `fct_recon_exceptions` and the "Columns (the contract, in this order)" table under `fct_recon_daily` in `docs/specs/dbt_project.md`, and ADR-0008, which makes this the one mart that is a view. A view stores nothing and derives from the fingerprinted lines table. The rejected alternatives are these:
- A table, which would store a second copy of data the lines table already holds.
- A signed daily sum, where offsetting breaks would hide each other.
- Repeating every output column in all five branches. That is longer and easier to get out of order, so the join back was used instead.

**Commands and output:**
- `airflow dags list-runs recon_daily --state running` and `--state queued`: both `No data found`, before any edit under `dbt/`.
- `uv run dbt --version`: `installed: 1.12.6`, `bigquery: 1.12.1 - Up to date!`.
- `make dbt-build`:
  ```text
  47 of 53 OK created sql view model analytics_dev.fct_recon_exceptions ... CREATE VIEW (0 processed)
  51 of 53 OK created sql table model analytics_dev.fct_recon_daily ... CREATE TABLE (18.0 rows, 453.4 KiB processed)
  Done. PASS=53 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=53
  ```
  The three new tests, `assert_recon_decomposition_closes` and the `fct_recon_daily` uniqueness test all passed. The NUMERIC precision warning is the expected one.
- The done-when query through `recon.bq` (`use_cache=False`), `select cause, count(*) from analytics_dev.fct_recon_exceptions group by 1`, on synthetic dev data:
  ```text
  amount_mismatch 4, fee_mismatch 30, missing_in_ledger 6, missing_in_statement 2
  ```
  Only exception causes appear. There are no `before_scope`, `matched`, `in_transit` or `timing_cutoff` rows, and the dev data has no `date_mismatch` rows.
- Extra checks (synthetic):
  - `sum(exception_count)` = 42, the same as the 42 queue rows. `countif(unexplained_minor != 0)` = 0.
  - Signs: `missing_in_statement` 2 of 2 positive, `missing_in_ledger` 6 of 6 negative.
  - `age_days` is between 1 and 6.
  - 0 queue rows have no matching row in the daily spine.
- `make check`: exit 0 (9 passed). The em dash check on `dbt/`: exit 1 (clean). The grep for DML, `CURRENT_DATE`, `CURRENT_TIMESTAMP` and `float` in `dbt/models/marts`: no match.

**What went wrong:** No bug, so there is no failure-log entry. The first build was green. Review found nothing.
- The permission check denied the banned-word grep in this step. The S7.4 and S7.5 runs of it, over the whole tree with `--untracked`, were clean, so this step's text is now covered.
- The `fct_recon_daily` contract was already enforced, from S5.6. The two columns therefore had to go into the contract now, or the build would stop.
- The uncommitted `Makefile` change and the untracked `scripts/*.py` and `.vscode/` were not this step's and were not staged.

**Interview questions:**
1. *Why does the queue have one row per line and cause, not one per line?*
   A line can have more than one problem at once, for example a short settlement and a fee overcharge. Each problem has its own signed amount, its own cause date and its own analyst action. One row per line would have to merge them and lose one amount. The key (`payment_id`, `cause`) is tested as unique.
2. *Why does `exception_abs_minor` sum absolute values?*
   A day with a +5000 amount mismatch and a -5000 missing line would sum to 0 signed, which looks like a clean day. The absolute sum shows 10000 of breaks for an analyst to work. The identity test still uses signed components, so this column is for the warning gate and for reporting.

## S7.3: enforce the `fct_recon_daily` contract

**Date and commit:** 2026-11-02, `c6cba6c` (an empty commit that records the check). The contract itself is in `6c97a10` (S5.6), and `6693bc5` (S7.2) added its columns 22 and 23.

**What was built:**
- No file changed in this step. `dbt/models/marts/_marts.yml` was checked against the spec, broken on purpose, and restored. `c6cba6c` has no file change. Its body says the contract landed early in S5.6.

**How it works:**
A model contract lists the exact columns and types a model must return. With the contract enforced, dbt compares the model's SQL output with that list before it builds the table, and stops the build on any difference:

`dbt/models/marts/_marts.yml:139`
```yaml
    config:
      contract:
        enforced: true
```

Every one of the 29 columns has a `data_type`. `not_null` sits on `mid`, `currency`, `recon_date`, `as_of_date` and `unexplained_minor`:

`dbt/models/marts/_marts.yml:203`
```yaml
      - name: unexplained_minor
        data_type: int64
        description: "gap_minor minus the sum of the seven dated components. Must be exactly 0; assert_recon_decomposition_closes fails otherwise."
        constraints:
          - type: not_null
```

The contract compiles into `create or replace table ... (mid string not null, ...) as select ...`. That is DDL (a statement that defines a table), not DML, so the sandbox allows it. BigQuery enforces only `not_null`, so uniqueness of (`mid`, `currency`, `recon_date`) stays a data test. This follows "Columns (the contract, in this order)" under `fct_recon_daily` in `docs/specs/dbt_project.md` and "Contracts" in `docs/learning/concepts.md`. The rejected alternative is to rely on data tests alone. A changed type would then reach readers before any test noticed it. A uniqueness constraint was not an option either, because BigQuery does not enforce one.

The plan puts the contract in S7.3 ("Order of work" in `docs/specs/dbt_project.md`), but it shipped early in S5.6. This step therefore did the two things that were still open: it checked every type by hand against the spec, and it proved the contract can fail.

**Commands and output:**
- `airflow dags list-runs recon_daily --state running` and `--state queued`: both `No data found`, before the build and again right before the deliberate edit.
- `uv run dbt --version`: Core 1.12.6, bigquery 1.12.1.
- The type check: a script compared the spec table with `_marts.yml`. The result was `{'enforced': True}`, 29 spec rows against 29 YAML rows, all matching in name, `data_type` and `not_null`, in the same order:
  - `mid` and `currency` are string.
  - `recon_date`, `as_of_date` and `fx_rate_date` are date.
  - `units_per_usd` and the three `*_usd` columns are numeric.
  - Every other column is int64.
- `make dbt-build` with the contract:
  ```text
  51 of 53 OK created sql table model analytics_dev.fct_recon_daily .. CREATE TABLE (18.0 rows, 453.4 KiB processed)
  Done. PASS=53 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=53
  ```
  The compiled DDL starts with ``create or replace table `<project>`.`analytics_dev`.`fct_recon_daily` ( mid string not null, ...``. A grep for insert, update, delete and merge in it found 0 matches.
- The deliberate failure: `unexplained_minor` set to `data_type: string`, then `make dbt-build` (exit 2):
  ```text
  This model has an enforced contract that failed.
  | column_name       | definition_type | contract_type | mismatch_reason    |
  | unexplained_minor | INT64           | STRING        | data type mismatch |
  Done. PASS=50 WARN=0 ERROR=1 SKIP=2 NO-OP=0 REUSED=0 TOTAL=53
  ```
  The error comes at compile time, so the table from the green build was not replaced.
- `git restore dbt/models/marts/_marts.yml`, then `git status --short dbt/`: no output. `make dbt-build` after the undo: `PASS=53 WARN=0 ERROR=0`.
- `make check`: 9 passed, exit 0. The em dash check: exit 1 (clean). `git check-ignore keys/sa.json .env`: both paths printed.

**What went wrong:** No real bug, so there is no failure-log entry. The deliberate `string` change is a planned test, not a bug.

Review confirmed 3 findings:
- There was no S7.3 commit.
- The failure test had no record.
- There was no journal entry.

The fixes:
- History was not rewritten, because `6c97a10` is pushed and comes before `g1-freeze`. The 29 types were checked again, and the empty commit `c6cba6c` was made before the failure test, which was then run again with the output above.
- This entry is the record for the second and third findings.

Two points remain for the owner:
- The plan slip: the contract shipped in S5.6, not S7.3. It changes no behaviour.
- `c6cba6c` uses the type `fix` but names no failure-log entry, because there was no bug.

The banned-word grep was denied here too. The clean whole-tree runs in S7.4 and S7.5 cover it.

**Interview questions:**
1. *When the type was wrong, was the old table damaged?*
   No. dbt compares the column types the SQL would return with the contract before it runs the `create or replace table`. The mismatch stopped the build at compile time, so `analytics_dev.fct_recon_daily` kept the table from the last green build, and the two dependent tests were skipped.
2. *Why is uniqueness a data test and not a contract constraint?*
   On BigQuery only `not_null` is enforced. `primary_key` can be declared but is not checked, and `unique` is not supported. So (`mid`, `currency`, `recon_date`) is checked by `dbt_utils.unique_combination_of_columns`, which runs a query and fails on any duplicate.

## S7.4: the completeness error test and the two warning gates

**Date and commit:** 2026-11-02, `e2e919d`.

**What was built:**
- `dbt/tests/assert_arrival_days_complete.sql` (error): fails when a raw file is missing for a day.
- `dbt/tests/warn_exception_share_7d.sql` (warn): flags a MID whose breaks are a large share of its booked gross over 7 days.
- `dbt/tests/warn_fx_restated.sql` (warn): flags a rate date that has more than one published value.

**How it works:**
A singular test is a SQL file that passes when it returns no rows. The completeness test builds a spine, which is one row per day from `scope_start` to `as_of_date`:

`dbt/tests/assert_arrival_days_complete.sql:11`
```sql
    cross join unnest(generate_date_array(a.scope_start, a.as_of_date)) as d
```

It returns every spine day with no `payment_events` partition (`:32` to `:43`). It also returns every (day, MID) with no statement lines, crossing the spine with the `mids` seed. For statements the interval is open at the start:

`dbt/tests/assert_arrival_days_complete.sql:56`
```sql
    where sp.arrival_date > sp.scope_start
```

On the first loaded day a MID can rightly have no statement lines, because the sales they would settle are older than the loaded history. The 43 USD-only lines on 2026-10-04 in S7.1 are that case.

The two warning tests start with `{{ config(severity='warn') }}`, so a hit prints WARN and the run goes on. The exception-share gate needs both a high share and a minimum count:

`dbt/tests/warn_exception_share_7d.sql:29`
```sql
where safe_divide(cast(g.abs_sum as numeric), cast(g.gross_sum as numeric))
        > numeric '{{ var("exception_share_warn") }}'
    and g.exception_sum >= {{ var('exception_min_count') }}
```

Both values are cast to NUMERIC before the division, so no FLOAT64 appears. The limits come from `dbt_project.yml`: `exception_share_warn` 0.02, `exception_min_count` 5, `gate_window_days` 7. `warn_fx_restated` groups the raw FX rows by (`provider`, `base`, `quote`, `rate_date`). It returns groups with more than one `rate_text`, with the values in `STRING_AGG`.

This follows "Singular tests (`dbt/tests/`)" in `docs/specs/dbt_project.md` and "Data quality checks: integrity gates and business gates" in `docs/learning/concepts.md`. A missing file is an incident and must stop the run. Without the test, it would look like a pile of `missing_in_statement` lines. Many exceptions, or a restated rate, are business output for an analyst, not a pipeline failure. The rejected alternatives are these:
- Making the share gate an error, which would fail the pipeline on normal business noise.
- A gate on the share alone. About 70 KZT payments a day make one break enough to trip it.

**Commands and output:**
- `airflow dags list-runs recon_daily --state running` and `--state queued`: both `No data found`.
- `uv run dbt --version`: installed 1.12.6, bigquery 1.12.1.
- `make dbt-build` (exit 0):
  ```text
  5 of 56 PASS warn_fx_restated ... [PASS in 2.31s]
  7 of 56 PASS assert_arrival_days_complete ... [PASS in 2.87s]
  56 of 56 PASS warn_exception_share_7d ... [PASS in 2.41s]
  Done. PASS=56 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=56
  ```
  The NUMERIC precision warning is the existing one from the contract, not a test result.
- `make check`: 9 passed, exit 0.
- The em dash check on `dbt/tests`: exit 1 (clean). The banned-word grep, over the whole tree with `--untracked`: exit 1 (clean). `git check-ignore keys/sa.json .env`: both paths printed.
- The grep for insert, update, delete, merge, `current_date`, `current_timestamp` and `float` in the 3 tests: no match.

**What went wrong:** Nothing. All three tests passed on the first build, so there is no failure-log entry. Review found nothing. The changes in the tree that were not this step's (`Makefile`, `scripts/*.py`, `.vscode/`) were left out of the commit.

**Interview questions:**
1. *Why is the statement interval open at the start but the payment interval closed?*
   Payment webhooks arrive on the day they happen, so every loaded day must have some. Statements arrive 1 or 2 days after their accounting date, so on the first loaded day a MID may have nothing to settle yet. Requiring lines on `scope_start` would fail a correct history.
2. *Why is a high exception share only a warning?*
   Breaks are what reconciliation exists to find. A bad day for a MID is work for an analyst, not proof that the pipeline is broken. A missing file is different: the numbers built on it would be wrong, so that test stays at error.

## S7.5: the mutation check, mutations 1 to 4

**Date and commit:** 2026-11-02, `f0712cb`.

**What was built:**
- `docs/testing.md`: the mutation table (mutation, file, expected red, observed red, result) and how each mutation was run. All 4 were caught.
- The mutations were made only on the scratch branch `mutation-check`. They were never committed, and the branch was deleted.

**How it works:**
A mutation is a deliberate one-line bug. If a test turns red, the test can fail. If no test turns red, the test proves nothing. Mutations 1, 2 and 4 hit the matcher. Mutation 1 changes its join:

`dbt/models/marts/fct_recon_lines.sql:82`
```sql
    full outer join statement as s
```

Mutation 2 changes `<` to `<=` in the in-transit rule:

`dbt/models/marts/fct_recon_lines.sql:112`
```sql
            when t.has_ledger and t.as_of_date < t.due_date then 'in_transit'
```

Mutation 4 moves the statement CTE's `SALE` filter (`:54`) to after the join. Mutation 3 removes the dedup:

`dbt/models/staging/stg_psp__payment_events.sql:23`
```sql
qualify row_number() over (
    partition by e.event_id
    order by e.delivered_ts, e.delivery_id
) = 1
```

Each mutation ran as `dbt run` then `dbt test`, not as `make dbt-build`. `dbt build` does not build a model whose unit test fails. Mutations 1 and 4 also break UT2, so the old tables would stay in place and the identity tests would pass on them. `dbt run` builds the mutated model whatever the unit tests say. The red tests were read from `dbt/target/run_results.json`. A mutation counts as caught when at least one of its expected tests is red. Every test that turned red was recorded, not only the expected ones (Known trap 4 in `AGENTS.md`).

This follows "Mutation check (step S7.5, and mutation 5 in S11.3)" in `docs/specs/dbt_project.md` and "The mutation check" in `docs/learning/concepts.md`. The rejected alternatives are these:
- Running the mutations with `make dbt-build`, which gives false green results.
- Editing the expected column to match what turned red.

**Commands and output:**
- `airflow dags list-runs recon_daily --state running` and `--state queued`: both `No data found`, before the first branch switch and again before switching back.
- `uv run dbt --version`: installed 1.12.6, bigquery 1.12.1.
- Baseline `make dbt-build` on `main` at `e2e919d`: `PASS=56 WARN=0 ERROR=0 SKIP=0`.
- On `mutation-check`, every `dbt run` gave `PASS=9 ERROR=0`. The `dbt test` results (synthetic dev data):
  ```text
  M1 INNER JOIN       PASS=41 ERROR=3  assert_recon_decomposition_closes, assert_no_money_lost_between_layers, ut_lines_status_and_date_shift (UT2)
  M2 < to <=          PASS=43 ERROR=1  ut_lines_status_and_date_shift (UT2)
  M3 QUALIFY removed  PASS=38 ERROR=6  unique_stg_psp__payment_events_event_id, unique_int_ledger__captures_payment_id,
                                       unique_fct_recon_lines_payment_id, dbt_utils_unique_combination_of_columns_fct_recon_exceptions_payment_id__cause,
                                       assert_recon_decomposition_closes, assert_no_money_lost_between_layers
  M4 SALE moved       PASS=41 ERROR=3  assert_no_money_lost_between_layers, assert_recon_decomposition_closes, ut_lines_status_and_date_shift (UT2)
  ```
  Every red test had status `"fail"` in `run_results.json`.
- After each revert with `git checkout -- <file>`, `git status --short dbt/` was empty. `git switch main && git branch -D mutation-check` printed `Deleted branch mutation-check (was e2e919d)`, so the branch held no commit.
- `make dbt-build` on `main` afterwards: `PASS=56 WARN=0 ERROR=0 SKIP=0`.
- `make check`: 9 passed, exit 0. The em dash check on `docs/testing.md`: exit 1 (clean). The banned-word grep: exit 1 (clean). `git check-ignore keys/sa.json .env`: both paths printed.

**What went wrong:** No bug. All four mutations were caught, so there is no failure-log entry. Review found nothing. Three points of interpretation are recorded in `docs/testing.md`:
- Mutation 3 removed the whole four-line `qualify` clause, so the SQL still compiles.
- Mutation 4 also added `s.record_type` to the statement CTE's columns, so the moved filter compiles.
- The observed column lists more tests than the expected one.

Per-test failure row counts were left out, because they are not saved in `docs/evidence/`. One note for the owner: `docs/testing.md` line 10 says "Run on 2026-11-03", which is the local date (UTC+5). In UTC the run was on 2026-11-02, the date the commit time gives. The record is not rewritten. A dated correction can be appended if the owner wants UTC there.

**Interview questions:**
1. *Why run a mutation with `dbt run` and `dbt test` instead of `dbt build`?*
   `dbt build` runs a model's unit tests first and does not build the model if one fails. It also skips everything downstream. A mutation that breaks UT2 would leave yesterday's correct tables in place, and the identity tests would pass on them. `dbt run` builds the broken model, so `dbt test` checks the broken output.
2. *What would you do if a mutation had stayed green?*
   That is a finding, not a pass. It means no test guards that line. Log it in `docs/failure_log.md`, add the missing test, and run the mutation again until the new test turns red. Never weaken the mutation or edit the table to look caught.

## Review of S7.2 to S7.5 (2026-11-02)

Each step had a spec reviewer and a hard-rules reviewer, and every finding two skeptics. S7.2, S7.4 and S7.5 had no findings. In S7.3 three were confirmed, all about records, not code: the contract had already been enforced in S5.6 (`6c97a10`, before `g1-freeze`, so history is not rewritten), there was no S7.3 commit, and the deliberate failure test had no record. The fixer re-ran the failure test (`unexplained_minor | INT64 | STRING | data type mismatch`, `ERROR=1`, then `git restore` and a clean `git status --short dbt/`) and recorded the check in the empty commit `c6cba6c`. `docs/testing.md` gave the Astana date for the mutation run; a dated correction with the UTC date was appended (`4377cb9`).

## S7.6: rebuild the latest marts with the final dbt code

**Date and commit:** 2026-11-02, no commit. The plan's "Commit: none" applies, because no file changes.

**What was built:**
- No code and no files. The `dbt_build` task of the existing run for 2026-11-01 was cleared, so the marts in `analytics` were rebuilt by the final dbt code (last changed in `e2e919d`, S7.4).

**How it works:**
The overnight history runs used the dbt code from before S7.2. The rerun proof must compare the output of one frozen code version, so the latest marts had to be rebuilt by the final code first. Clearing resets task instances of a run that already exists. The scheduler then runs them again with the same data interval. `-t` is a regular expression on task ids:

`docs/specs/airflow_and_docker.md:1028`
```text
- `-t` is a regular expression on task ids. `-t load_raw` clears all three mapped loads. `-t dbt_build` matches only `dbt_build` in this DAG.
```

The task writes its dbt artifacts to a folder named after the run's logical date. That is why `runs/dbt/2026-11-01/target/run_results.json` is the file to check:

`dags/recon_daily.py:32`
```python
    "--target-path /opt/airflow/runs/dbt/{{ data_interval_start | ds }}/target "
```

The DAG excludes unit tests, so the build re-runs every model and data test on `analytics` and no unit test:

`dags/recon_daily.py:31`
```python
    "--exclude-resource-type unit_test "
```

This follows S7.6 in `docs/build_plan.md`, "Clear and rerun a day" in the "Operations runbook" of `docs/specs/airflow_and_docker.md`, and ADR-0005. The rejected alternatives are these:
- Clearing every task of the day. That would also regenerate and reload raw data, which this step does not need.
- `airflow dags trigger`. It takes its interval from the trigger time, not from 2026-11-01.
- A host build. It targets `analytics_dev`, not the proof dataset.

**Commands and output:**
- `airflow dags list-runs recon_daily --state running` and `--state queued`: both `No data found`.
- `docker compose exec airflow-scheduler airflow tasks clear recon_daily -s 2026-11-01 -e 2026-11-01 -t dbt_build -y`, at 19:48:42 UTC.
- `dbt_build` for 2026-11-01: `success`, 19:48:42 to 19:49:49 UTC.
- `runs/dbt/2026-11-01/target/run_results.json` was rewritten and shows a fresh time. Its results: 42 `pass`, 12 `success`. `assert_recon_decomposition_closes`: `pass`.
- From here until the proof is committed, nothing under `dbt/` changes (`AGENTS.md`, "Freeze rules", rule 2).

**What went wrong:** Nothing, so there is no failure-log entry. No test that was green on the host turned red in Airflow, so `analytics` and `analytics_dev` showed no difference.

**Interview questions:**
1. *Why clear only `dbt_build` and not the whole run?*
   The raw partitions for 2026-11-01 were already loaded by frozen loader code. Only the dbt code had changed since the overnight runs. Clearing `dbt_build` rebuilds the marts with the final SQL and leaves raw untouched.
2. *Clearing reruns a task inside an existing run. How is that different from reprocess?*
   A reprocess (`backfill create --reprocess-behavior completed`) creates backfill runs for a range of finished logical dates. A clear resets task instances of one run that already exists. Both keep the run's data interval, so both process the same day.

## S8.1: `scripts/prove_idempotency.py`

**Date and commit:** 2026-11-02, `d3042f1`.

**What was built:**
- `scripts/prove_idempotency.py` has three functions:
  - `fingerprints` runs the fingerprint query for one table.
  - `snapshot` fingerprints the three raw tables by `_arrival_date` and the two mart tables by `recon_date`, records `as_of_date`, and writes one JSON file.
  - `compare` compares two snapshots, writes `compare.json`, prints one summary line and returns the exit code.
- `Makefile`: the targets `reprocess`, `clear-day`, `snapshot` and `compare`. The same commit also added `results`, `storage` and `fx-report`, whose scripts came in S9.1 and S9.2.

**How it works:**
A fingerprint is a short value that changes when any row changes. For each (table, partition) group, the query hashes every whole row and combines the hashes in two ways. It also keeps the row count:

`scripts/prove_idempotency.py:20`
```python
       bit_xor(farm_fingerprint(to_json_string(t))) as xor_fp,
```

`scripts/prove_idempotency.py:21`
```python
       sum(cast(farm_fingerprint(to_json_string(t)) as bignumeric)) as sum_fp
```

`BIT_XOR` alone cancels identical pairs, so a duplicated row pair would vanish. That is why `COUNT` and the `SUM` are kept too. The `SUM` is cast to BIGNUMERIC so it cannot overflow INT64, and it is stored as text so the JSON keeps every digit. The snapshot also reads the marts' `as_of_date`:

`scripts/prove_idempotency.py:51`
```python
    as_of = rows(query(client, f"select as_of_date from `{client.project}.{args.marts_dataset}.stg_recon__as_of`",
```

`compare` passes only when nothing changed, nothing is missing, nothing is new and `as_of` is the same:

`scripts/prove_idempotency.py:72`
```python
    ok = not changed and not only_before and not only_after and as_of_same
```

Tables are written as `<dataset>.<table>`, so the JSON never holds the project id. The defaults are `raw` and `analytics`, and so is the Makefile's `RAW_DS ?= raw`, even though the Makefile sets `RAW_DATASET := raw_dev` for development commands. The reprocess target is a single backfill command:

`Makefile:84`
```makefile
	$(AIRFLOW) backfill create --dag-id recon_daily --from-date $(FROM) --to-date $(TO) --reprocess-behavior completed --max-active-runs 1
```

This follows S8.1 in `docs/build_plan.md`, "The idempotency proof" in `docs/specs/airflow_and_docker.md` and "The fingerprint proof" in `docs/learning/concepts.md`. The rejected alternatives are these:
- Comparing row counts only. A changed value with the same count would pass.
- `BIT_XOR` alone, which cancels identical pairs.
- Excluding columns from the hash. None needs it, because there is no wall-clock column and `fetched_at` comes from the frozen meta file.

**Commands and output:**
- ruff reported an unused `noqa` comment, and it was removed before the commit.
- The test run: two snapshots of 2026-10-28 to 2026-11-01, one after the other, written to `$TMPDIR`. Each printed `25 (table, partition) groups, 3063 rows, as_of 2026-11-01`.
- `compare` on the two test snapshots:
  ```text
  25 of 25 (table, partition) groups identical, 3063 rows, as_of 2026-11-01 in both
  ```
  `exit=0`.
- A grep for the project id in the JSON files: 0 matches.

**What went wrong:** No bug, so there is no failure-log entry. The ruff note was a lint fix, not a bug.

**Interview questions:**
1. *Why keep three numbers per partition instead of one hash?*
   `BIT_XOR` does not depend on row order, but two identical rows XOR to 0, so a duplicated pair would leave it unchanged. `COUNT` catches the extra rows, and the BIGNUMERIC `SUM` of the same hashes catches a different multiset of rows that XORs the same. All three must match.
2. *Why does `compare` fail on a missing or a new group, not only on a changed one?*
   A partition that disappeared or appeared means the rerun wrote somewhere else or dropped a day. Counting only changed groups among the shared keys would report that as identical.

## S8.2: run the proof

**Date and commit:** 2026-11-02, `ae8e1a2` (the three evidence files).

**What was built:**
- `docs/evidence/2026-11-02/fp_before.json`, `fp_after.json` and `compare.json`, all written by `make` targets. No code changed.

**How it works:**
The proof measures N1. A snapshot is taken first. Then the 7 latest finished days are reprocessed, and one older day, 2026-10-14, is cleared out of order. Then a second snapshot is taken and the two are compared. Every raw write is one WRITE_TRUNCATE load into one partition, so a rerun replaces the day instead of appending to it:

`src/recon/load.py:133`
```python
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
```

The out-of-order clear can only pass because `as_of_date` comes from the loaded data, not from the run date. When run 2026-10-14 rebuilds the marts, it still sees 2026-11-01 as the latest arrival day:

`dbt/models/staging/stg_recon__as_of.sql:32`
```sql
    max(a._arrival_date) as as_of_date,
```

The snapshot range starts on 2026-10-03, one day before the world start, because USD accounting dates can fall there. This follows S8.2 in `docs/build_plan.md`, "The idempotency proof" in `docs/specs/airflow_and_docker.md`, and ADR-0002. That ADR rejects `WRITE_APPEND` plus dedup views ("each rerun adds a copy") and `as_of` from a `run_date` var or `CURRENT_DATE()` ("reruns roll the marts back, or differ").

**Commands and output:**
- Frozen code:
  - The M9 scripts were committed first (`9b3fabd`, `8441208`). After that, `git status` showed only `.vscode/`, the owner's untracked editor folder.
  - `git diff --stat g1-freeze` over the frozen paths and `dags/` printed nothing.
- Nothing running: no run active, run 2026-11-01 `success`, DAG unpaused.
- `make snapshot OUT=docs/evidence/2026-11-02/fp_before.json FROM=2026-10-03 TO=2026-11-01`:
  ```text
  146 (table, partition) groups, 17595 rows, as_of 2026-11-01
  ```
- The dry run of the reprocess listed 7 dates.
- `make reprocess FROM=2026-10-26 TO=2026-11-01`: 7 runs created at 19:50:50 UTC. All 7 ended `success`, and the last ended at 20:00:17 UTC.
- `make clear-day DAY=2026-10-14`: every task re-ran, 20:00:55 to 20:02:28 UTC, `success`.
- `make snapshot OUT=docs/evidence/2026-11-02/fp_after.json FROM=2026-10-03 TO=2026-11-01`:
  ```text
  146 (table, partition) groups, 17595 rows, as_of 2026-11-01
  ```
- `make compare BEFORE=docs/evidence/2026-11-02/fp_before.json AFTER=docs/evidence/2026-11-02/fp_after.json`:
  ```text
  146 of 146 (table, partition) groups identical, 17595 rows, as_of 2026-11-01 in both
  ```
  Exit 0. `compare.json` has `"identical": true` and `"changed": []`.
- A grep for the project id in the three files: 0 matches.

**What went wrong:** Nothing. The compare exited 0, so there is no failure-log entry. One small procedure note: the plan's step 1 asks for an empty `git status --short`, and it showed `.vscode/`. That folder is untracked, is not code that the runs execute, and was left alone. All of the proof ran inside UTC day 2026-11-02.

**Interview questions:**
1. *Why clear an older day out of order, on top of the reprocess?*
   A reprocess in date order could hide a bug where a run's output depends on which runs came before it. Clearing 2026-10-14 after 2026-11-01 has run proves that an old day rerun late writes the same raw partitions and leaves the marts' `as_of_date` at 2026-11-01.
2. *What would you do if one group had changed?*
   Treat it as a finding: write it in `docs/failure_log.md` and find the cause in code or procedure. Then fix it and run the whole procedure again from a new `fp_before.json`. Never edit evidence or narrow the snapshot range.

## S9.1: `scripts/results.py` and `scripts/storage.py`

**Date and commit:** 2026-11-02, `9b3fabd` (code) and `09a2585` (evidence).

**What was built:**
- `scripts/results.py` writes `docs/evidence/<UTC date>/summary.json`. It has three parts:
  - `N2_SQL` is the N2 query on `<marts>.fct_recon_daily`.
  - `mutation_counts` counts K from the table in `docs/testing.md`.
  - `decomposition_status` reads the status of `assert_recon_decomposition_closes` from a dbt `run_results.json`.
  
  `main` also reads N1 from `compare.json` and N3 from `fx_report.json` when that file exists.
- `scripts/storage.py`: `from_tables` (`__TABLES__`), `from_api` (the P7 fallback), `table_storage` (`INFORMATION_SCHEMA.TABLE_STORAGE`) and `redact`. It writes `storage.json`.

**How it works:**
The N2 claim is allowed only when U is 0 and the latest DAG build's identity test passed:

`scripts/results.py:65`
```python
          "claim_allowed": n2_row["abs_unexplained_minor"] == 0 and status == "pass"}
```

By default the test status comes from the newest DAG artifact. After S8.2, that is the cleared run for 2026-10-14, which built the current marts:

`scripts/results.py:39`
```python
    path = run_results or max(glob.glob("runs/dbt/*/target/run_results.json"), key=os.path.getmtime)
```

The project id is replaced before the file is written:

`scripts/results.py:87`
```python
    out.write_text(re.sub(re.escape(client.project), "<project>", json.dumps(doc, indent=2, sort_keys=True)) + "\n")
```

The summary also records the seed, the world start, the window, `as_of`, `git rev-parse HEAD`, the date, and the labels "N1 and N2 are measured on synthetic payments" and "N3 is measured on real NBK rates". `storage.py` says plainly what its number is:

`scripts/storage.py:11`
```python
NOTE = "Bytes stored now. The lifetime quota may count every byte ever written, so this is a lower bound."
```

This follows S9.1 and the N1 and N2 rows of the M9 table in `docs/build_plan.md`, "Metric definitions" in `docs/learning/concepts.md`, and "Honesty, labels and vocabulary" in `AGENTS.md`. The rejected alternatives are these:
- Copying numbers into the README by hand.
- Taking the test status from the host's `dbt/target/run_results.json`, which describes `analytics_dev`, not `analytics`.
- Reporting bytes as a result.

**Commands and output:**
- `make storage OUT=docs/evidence/2026-11-02/storage.json`:
  ```text
  5600870 logical bytes over 5 datasets (__TABLES__)
  ```
  This is stored bytes, never a headline number.
- `make results`:
  ```text
  N1: 146 of 146 (table, partition) groups identical, 17595 rows, as_of 2026-11-01 in both
  N2: 60 MID-days, 0 minor units unexplained, decomposition pass, mutations 4 of 4 caught
  ```
- `summary.json`: `git_sha` `ae8e1a2`. `run_results` is `runs/dbt/2026-10-14/target/run_results.json`, the cleared run, as the plan predicts.
- A grep for the project id in every evidence file: 0 matches.

**What went wrong:** No bug, so there is no failure-log entry. Two notes for the owner:
- `git_sha` is `ae8e1a2`, not `9b3fabd`. The script ran after the S8.2 evidence commit. `ae8e1a2` holds `scripts/results.py` unchanged from `9b3fabd`, so the SHA still names the code that ran.
- The `written_at_utc` of `summary.json` is `2026-11-02 20:04:24+00:00`, after `fx_report.json` was written. That is why it holds N3 as well (see S9.2).

**Interview questions:**
1. *Why does `results.py` refuse to rely on the zero alone?*
   U = 0 says the marts' columns add up. It does not say the identity test ran on the build that made them. The claim needs both: the query's 0 and `pass` for `assert_recon_decomposition_closes` in that build's `run_results.json`.
2. *Why is the byte count never a headline?*
   At this size the 10 MB minimum per query dominates any cost, and stored bytes say nothing about whether the reconciliation is right. `storage.json` is there to watch the sandbox quota, not to describe the result.

## S9.2: `scripts/fx_report.py` (N3)

**Date and commit:** 2026-11-02, `8441208` (code) and `52c353d` (`fx_report.json` and the 29 NBK RSS files).

**What was built:**
- `scripts/fx_report.py` has four functions and a `main`:
  - `fetch_rss` reads the landed XML for one day, or makes one request for it.
  - `usd_rate` checks the XML and parses the USD rate.
  - `land` writes the file to a temp name and renames it.
  - `rss_path` builds the file path.
  - `main` compares the rates with `units_per_usd` from `<marts>.int_fx__usd_rates_daily` and writes `docs/evidence/<UTC date>/fx_report.json`.
- 29 real NBK RSS files in `landing/fx/provider=nbk_rss/`, 2026-10-04 to 2026-11-01, committed.

**How it works:**
The project's daily rate carries the last earlier rate forward over days with no Frankfurter row:

`dbt/models/intermediate/int_fx__usd_rates_daily.sql:51`
```sql
        last_value(r.rate ignore nulls) over w as units_per_usd,
```

The script asks NBK's own feed for each day once, and never for today or a later day:

`scripts/fx_report.py:32`
```python
    if d >= today:
        raise ValueError(f"{d} has not ended in UTC: NBK answers future dates with its latest rate")
```

The feed must echo the requested date, and the rate is parsed as a `Decimal`, never a float:

`scripts/fx_report.py:49`
```python
    if echoed != f"{d:%d.%m.%Y}":
```

`scripts/fx_report.py:55`
```python
            return Decimal((item.findtext("description") or "").strip())   # Decimal, never float
```

A day with its own Frankfurter row (`carry_days == 0`) must equal NBK exactly, or the script exits 1. Carried days are measured:

`scripts/fx_report.py:93`
```python
    own = [x for x in usable if x["carry_days"] == 0]       # a Frankfurter row dated d
```

This follows S9.2 and the N3 row of the M9 table in `docs/build_plan.md`, the NBK RSS format in `docs/specs/data_and_generator.md`, and ADR-0004. That ADR rejects "Re-fetch every run" (a restated rate breaks reproducibility) and "FLOAT64 rates" (binary rounding). Known trap 5 in `AGENTS.md` (an empty feed after the last published rate) is handled: `usd_rate` returns `None` and the day is listed in `days_without_nbk_rate`.

**Commands and output:**
- `make fx-report` (exit 0):
  ```text
  N3: on 9 of 9 carried days the carry-forward differed from NBK by up to 5.82 KZT per USD (130.0 bps); own-rate days agreed on 20 of 20
  ```
- 29 NBK RSS files landed in `landing/fx/provider=nbk_rss/` (2026-10-04 to 2026-11-01) and were committed. `days_without_nbk_rate` is `[]` and `weekday_disagreements` is `[]`.
- The largest difference is on 2026-10-04: project `441.91` (carried from `rate_date` 2026-10-02), NBK `447.73`.
- Carried days: 2026-10-04, 10-10, 10-11, 10-17, 10-18, 10-24, 10-25, 10-31 and 11-01. In `fx_report.json` every carried day has `"weekday": false` and every own-rate day has `"weekday": true`.
- `summary.json` holds N3: `C_carried_days` 9, `W_carried_days_differing` 9, `X_max_abs_diff_kzt` "5.82", `Y_bps` "130.0", `E_agreeing` 20 of `E_own_rate_days` 20.

**What went wrong:** No weekday disagreement, so there is no failure-log entry. One observation from the real data: NBK's weekend rate equals the next Monday's published rate. For example, NBK gives `451.05` for Saturday 2026-10-24, which equals the Frankfurter row of Monday 2026-10-26. The carry-forward instead uses Friday's `447.94`. This is why the carry-forward is a project convention, not NBK's official rate for that day. A wording note for the owner: the plan's N3 sentence says "weekday rates", while the script tests own-rate days (`carry_days == 0`). In this window the two sets are the same.

**Interview questions:**
1. *Why check that the XML echoes the requested date?*
   NBK answers a future date with its latest rate instead of an error. Without the echo check, a wrong date could slip in as a valid rate. The script also refuses any day on or after today (UTC) before it sends a request.
2. *Why is the largest gap on 2026-10-04 and not on a later weekend?*
   2026-10-04 is a Sunday, and the rate carried there is from Friday 2026-10-02, before the world start. That is allowed, because the FX request for run date R covers R-6 to R. NBK's Sunday rate equals the following Monday's, so the gap holds a whole weekend's move, and this weekend's move was the largest in the window.

## Explain check M7

*What does each mutation prove?* (Observed results from `docs/testing.md`.)
1. **Mutation 1** changes the FULL OUTER JOIN to an INNER JOIN in `dbt/models/marts/fct_recon_lines.sql`. One-sided lines, a payment in only one ledger, are dropped. `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers` and UT2 turned red. So the identity and preservation tests catch lost lines.
2. **Mutation 2** changes `<` to `<=` in the in-transit rule (`fct_recon_lines.sql:112`). Only UT2 turned red. So the due-date boundary is pinned by a unit test, not by the data: the dev data had no line exactly on its due date.
3. **Mutation 3** removes the `QUALIFY` in `dbt/models/staging/stg_psp__payment_events.sql`. Four uniqueness tests and both money tests turned red. So redelivered webhooks are caught at every layer.
4. **Mutation 4** moves the `SALE` filter after the join. A filter on `s.record_type` after a FULL OUTER JOIN drops the ledger-only rows, whose statement side is null. Both money tests and UT2 turned red.
5. All 4 were caught (`summary.json`: `K_caught` 4, `K_total` 4). Mutation 5 belongs to U1.

*Why is the exception share a warning and the identity an error?*
- `warn_exception_share_7d` describes the business. Breaks are what the analysts work on, so a high share is news for them, not a broken pipeline. With about 70 KZT payments a day, one break could trip a share-only gate.
- A non-zero `unexplained_minor` means the pipeline itself lost, duplicated or misdated money, so nothing it built can be trusted. `assert_recon_decomposition_closes` therefore stays at error, with no tolerance (`AGENTS.md`, "Money", rule 8).

## Explain check M8

*What do the fingerprints compare?*
Each (table, partition) group is compared before and after the reprocess and the out-of-order clear. The groups are:
- `raw.payment_events`, `raw.settlement_lines` and `raw.fx_rates` by `_arrival_date`;
- `analytics.fct_recon_lines` and `analytics.fct_recon_daily` by `recon_date`.

For each group the snapshot keeps `COUNT(*)`, and the `BIT_XOR` and BIGNUMERIC `SUM` of `FARM_FINGERPRINT(TO_JSON_STRING(row))` (`scripts/prove_idempotency.py:20` and `:21`). It also keeps the marts' `as_of_date`. On 2026-11-02 all 146 of 146 groups were identical, 17595 rows, `as_of` 2026-11-01 in both (`docs/evidence/2026-11-02/compare.json`).

*What would a `_loaded_at` column do to the proof?*
It changes on every reload, so every reloaded row would hash differently. Every reprocessed partition would then show as changed, and the proof would fail for a trivial reason. The design has no load-time column: `fetched_at` comes from the frozen meta file, and the review checklist forbids one (`AGENTS.md`, "Review checklist", item 3).

*Why must `as_of` match in both snapshots?*
The mart statuses depend on `as_of_date`, for example `in_transit` against `due_date`. If a new arrival day were loaded between the snapshots, mart rows would change for a legitimate reason. This could happen if midnight UTC passed and the scheduled run added a day. The same `as_of` proves that both snapshots describe the same state of knowledge. That is why the proof ran inside one UTC day, and why `compare` fails on a changed `as_of` (`scripts/prove_idempotency.py:72`).

## Explain check M9

*Which numbers are synthetic and which are real?*
- N1 and N2 are measured on synthetic payments. They describe this pipeline's behaviour on generated data, not any business. `summary.json` says so in its `synthetic` field:
  - N1: 146 of 146 groups identical, 17595 rows.
  - N2: 60 MID-days with 0 minor units unexplained, mutations 4 of 4 caught.
- N3 compares two real sources: the carried-forward NBK series via Frankfurter, and NBK's own RSS rates. On 9 of 9 carried days they differed, by up to 5.82 KZT per USD (130.0 bps). The 20 of 20 own-rate days agreed exactly.
- Stored bytes (`storage.json`) are context, never a result.

*Why is the carry-forward a convention?*
- The Frankfurter series has no row for weekends, so `int_fx__usd_rates_daily` fills those days with the last earlier rate (`last_value(r.rate ignore nulls)`, line 51). That is the project's reporting rule, not NBK's official rate for that day.
- NBK publishes its own weekend rate, and in this window it equals the next Monday's published rate. For example, NBK gives `451.05` for Saturday 2026-10-24, the same as Monday 2026-10-26, while the carry-forward gives Friday's `447.94`.
- The reconciliation never converts currency, so this only affects the USD reporting columns.

**Next step:** S10.1, the README first screen and sections.

## S10.1: the README first screen and the two saved analyses

**Date and commits:** 2026-11-02 (UTC), `5b19df0`, then the review fix `d3a6f38`.

**What was built:**
- `README.md`: every section of the skeleton, written from the evidence. That covers the banner line, the Mermaid data flow, the results table (N1, N2, N3), the quickstart, "What this does not prove" and "How I used AI".
- `dbt/analyses/exceptions_queue.sql`: the open work queue from `fct_recon_exceptions`, oldest and largest first.
- `dbt/analyses/one_mid_day_bridge.sql`: one MID-day's gap and its dated components from `fct_recon_daily`.

**How it works:**
- Every number in the README is copied from `docs/evidence/2026-11-02/summary.json`, `compare.json`, `fx_report.json`, `storage.json` or `docs/testing.md`. The results paragraph names its source and commit (`README.md:23`):
  ```text
  **Results.** Measured on 2026-11-02, window 2026-10-03..2026-11-01, seed 20261101, as of 2026-11-01, commit `ae8e1a2e...`.
  ```
- An analysis is a SQL file that dbt compiles (it fills in `ref()`) but never builds, so it writes nothing to BigQuery. The queue orders by age, then by size (`dbt/analyses/exceptions_queue.sql:17` to `:21`):
  ```sql
  order by
      e.age_days desc,
      abs(e.amount_minor) desc,
      e.payment_id,
      e.cause
  ```
  The last two keys make the order total, so two runs list the rows in the same order.
- Why this way: S10.1 in `docs/build_plan.md` and "Saved analyses (`dbt/analyses/`)" in `docs/specs/dbt_project.md`. The rejected alternative was building the queue as a model. That would add a table the specs do not name, and every byte written counts against the sandbox quota.

**Commands and output:**
- `uv run dbt --version`: dbt-core 1.12.6, bigquery 1.12.1.
- `(cd dbt && uv run dbt compile --select exceptions_queue one_mid_day_bridge --target airflow)`: `Found 9 models, 2 analyses, 42 data tests, 3 seeds, 3 sources`. The compiled queue reads `<project>.analytics.fct_recon_exceptions`. Compile is one of the two read-only commands allowed on target `airflow` from the host.
- The compiled SQL, run through `recon.bq`: `exceptions_queue` returned 177 rows. `one_mid_day_bridge` for `mid_kzt_01` on 2026-10-21 returned 79 rows. These are checks of the queries, not results, and they are not in the README.
- `grep -nE '<!--|\[WRITE|\[[A-Za-z]{1,8}\]([^(]|$)' README.md`: no output, exit 1.
- The banner line matched the skeleton word for word (count 1).
- Vocabulary grep: the only hit is "Production experience. This is a learning project." in "What this does not prove". It negates the word, as `docs/learning/concepts.md` "M10. Publish, gate G2" does.
- `make check`: 9 passed, ruff clean. The em dash check and the banned-word grep were both clean (exit 1).

**What went wrong:**
- The review found two mistakes in the README. Fixed in `d3a6f38`:
  1. Mutation-table rows 1 and 4 had lost a cell, so the observed red tests sat under "Expected red".
  2. A paragraph said the identity test catches a misdated line, but no mutation in `docs/testing.md` shows that. It now claims only what the mutation check shows.
- Neither was a bug in the code, so there is no failure-log entry.
- Not done: the two screenshots `docs/img/exceptions_queue.png` and `docs/img/airflow_grid.png`. They need the BigQuery console and the Airflow UI in a browser, with the project id cropped out, so they are left to the owner (see S10.4 below). The README does not embed them, so no broken image is published.

**Interview questions:**
1. *Why is the work queue an analysis and not a model?*
   It is a view on demand for an analyst. As an analysis it costs nothing to store. dbt compiles it with the right dataset names, and you paste it into the console or run it with `dbt show`.
2. *How do you make sure no number on the first screen is invented?*
   Every number is copied from a file under `docs/evidence/` that a `make` target wrote, and the paragraph names that file and the commit. The placeholder grep fails if any `[N]` is left over.

## S10.2: ADR-0001 to 0003 accepted; the failure log checked

**Date and commits:** 2026-11-02 (UTC), `60a4aa3`, then the review fix `5a0f6a5`.

**What was built:**
- `docs/adr/0001-warehouse-bigquery-sandbox.md`, `0002-raw-write-path-and-time-model.md` and `0003-reconciliation-method.md`: rewritten in plain first-person words and set to `**Status:** Accepted`.
- `docs/adr/README.md`: index rows 0001 to 0003 now read Accepted, "accepted 2026-11-02". ADR-0004 to 0010 stay Proposed.
- `docs/failure_log.md`: read in full, and no change was needed.

**How it works:**
- In build mode the agent writes the "in your words" steps (`AGENTS.md`, "Build mode": "Where a step says a document is written 'in your words' (design doc, ADRs, README...), you draft it"). This overrides "Writing style" rule 6, which says an agent never marks an ADR Accepted. So that nobody is misled about authorship, each accepted ADR now says who wrote it (`docs/adr/0001-warehouse-bigquery-sandbox.md:9`):
  ```text
  - **Written by:** an AI agent in build mode (the owner's decision of 2026-11-02 in `AGENTS.md`, heading "Build mode"), checked against the code and `docs/evidence/`. "I" below is the project's voice.
  ```
- The commit subject "accept ADR-0001 to 0003 in my own words" is the exact subject that S10.2 in `docs/build_plan.md` prescribes. The "my" in it is the plan's wording. The ADR files and the README "How I used AI" section say that the agent wrote the text. The commit is pushed, so its message stays as it is (`AGENTS.md`, "Commit style" rule 9).
- Every statement in the three ADRs was checked against the code:
  - `load_day` and `load_partition` in `src/recon/load.py`;
  - the clustering in the schema JSON files;
  - `stg_recon__as_of`;
  - the `CASE` logic and the fee formulas in `fct_recon_lines`;
  - the gap inputs and the 7 components in `fct_recon_daily`.
- Numbers in the ADRs come only from `docs/evidence/`. Design estimates are labelled as estimates.

**Commands and output:**
- `grep -h "Status:**" docs/adr/0*.md`: 0001 to 0003 Accepted, 0004 to 0010 Proposed.
- The ADR-0001 G0 table and the P2 text, diffed against the previous commit: unchanged.
- The failure log: F-001 has every field of the entry format. The planned red runs for UT1 and UT2 are complete. The UT3 and UT4 rows stay empty, because they are U1 work.
- `make check`: 9 passed, ruff clean. The em dash check and the banned-word grep were both clean.

**What went wrong:**
- The first draft of ADR-0001 said that no quota error had appeared. No evidence file proves that. It now says that the evidence shows `"plan_b": false` and that the failure log has no storage-quota entry.
- The review found that the G0 table credited all of its rows to `g0_probe.json`. That file holds only P1 to P7 and F1. `5a0f6a5` credits only those rows to the file, and the S1.1 to S1.3 rows to the journal.
- Neither was a code bug, so there is no failure-log entry.

**Interview questions:**
1. *Why is ADR-0002's time model three dates and not one?*
   Arrival date (which day's files), booking date (the ledger cut-off) and accounting date (the PSP's settlement day) answer different questions. Raw is partitioned by arrival date, so a rerun of one day replaces exactly that day's files.
2. *Who wrote the ADRs, and how can a reader tell?*
   An AI agent in build mode, from the code and the evidence. Each accepted ADR has a "Written by" line, and the README "How I used AI" section says so too.

## S10.3: the clean-clone check, and the walkthrough

**Date and commits:**
- The clean-clone check: 2026-11-02 (UTC). No commit, because nothing needed fixing. The push before it was `52c353d..5a0f6a5`.
- The walkthrough: `e0ef76a`, then the review fix `30d9f12`.

**What was built:**
- No repo file for the check: it ran in a `mktemp -d` folder that was deleted afterwards.
- `docs/walkthrough.md` (764 lines): the owner's study guide. Its sections follow `AGENTS.md`, "The walkthrough":
  - "The problem and the results"
  - "The architecture"
  - "File by file, in the order the data flows"
  - "Design decisions and their alternatives"
  - "Concepts, each tied to its file"
  - "How it was built"
  - "How to run it from a clean clone"
  - "Drill" (20 questions and five explain-a-file exercises)

**How it works:**
- The check proves that a stranger's clone installs, tests, parses and builds without any local state: no keys, no `.env` values, no hook. `dbt parse` gets dummy variables (`GCP_PROJECT=ci-dummy`, `DBT_KEYFILE=/nonexistent/sa.json`) because parse needs them to exist but never connects.
- The walkthrough was written from the code, with current line numbers re-read from the files. Some line numbers quoted in older journal entries have drifted. For example, the S5.6 entry cites `fct_recon_daily.sql:230` for the identity, which is now at `:252` to `:262`. The walkthrough's numbers are the current ones.

**Commands and output (clean clone):**
1. `gh repo clone bainazarseitek/ledger-vs-statement`: exit 0, HEAD `5a0f6a5`.
2. `cp .env.example .env`: exit 0, placeholders left as they are.
3. `make setup`: exit 0. `uv sync`, then `dbt deps` printed `Installed from version 1.4.1`.
4. `make check`: exit 0, `9 passed in 2.89s`, ruff `All checks passed!`.
5. `dbt parse` with the dummy variables: exit 0, `Running with dbt=1.12.6`, `Registered adapter: bigquery=1.12.1`.
6. `docker compose build`: exit 0. A second build with `--no-cache` (beyond the plan, because the first one reused local layer cache) also exited 0.

**Commands and output (walkthrough):**
- A vocabulary scan of `docs/walkthrough.md`: no match.
- `make check`: 9 passed. The em dash check and the banned-word grep were both clean.

**What went wrong:**
- The clean clone passed on the first run, so there is no fix and no failure-log entry.
- A note on the uncached build: it re-tagged `ledger-vs-statement-airflow:3.3.2`, and pip resolved newer versions of some unpinned transitive dependencies in the dbt venv (the log shows `google_cloud_bigquery-3.47.0`). dbt-core 1.12.6 and dbt-bigquery 1.12.1 are pinned and unchanged. The running containers keep the old image until they are recreated. Nothing failed, so this is not a failure-log entry. It is a reproducibility limit of `docker/requirements-dbt.txt`, which pins only the direct dependencies.
- The walkthrough review found two wrong citations. Fixed in `30d9f12`:
  1. Drill answer 15 put UT1's `pay_k2` on the 20th, but UT1 expects 2026-10-21.
  2. A reason was given for why only UT2 caught mutation 2, and nothing supports that reason. The sentence now says only what `docs/testing.md` records.

**Interview questions:**
1. *What does the clean-clone check prove, and what does it not?*
   It proves that the repo installs, lints, tests, parses and builds the image from its own files and locks. It does not touch BigQuery, so it does not prove the pipeline runs in another person's project. That takes their own sandbox setup (README "Run it in full").
2. *Why does `dbt parse` need `GCP_PROJECT` if it never connects?*
   `profiles.yml` reads it with `env_var()`, and parse renders the profile. A missing variable is a compile error, so a dummy value is enough.

## S10.4: name review and the NBK terms (sub-steps 1 and 2)

**Date and commits:** 2026-11-02 (UTC), `611d926` and `fb5f68c`, pushed (`5a0f6a5..fb5f68c`; the pre-push hook ran and passed).

**What was built:**
- `README.md`, "Licence": a line on NBK's Data License (`README.md:605`).
- `README.md`: the "Design decisions" table now shows ADR-0001 to 0003 as Accepted, and the "How I used AI" line says who rewrote them.

**How it works:**
- Sub-step 1 runs the hook's word list against four places: the file contents, the file paths, every commit message, and the branch and tag names on GitHub. It also lists any commit that ever touched `keys` or `.env`. Each pattern is wrapped as `(^|[^[:alnum:]])word([^[:alnum:]]|$)`, so a word glued to `_` is caught too, unlike the hook's `-w` match.
- Sub-step 2 re-checked the NBK terms, because `landing/fx/` commits NBK rates. NBK now publishes a Data License page. It allows copying, publishing and distributing its official statistical information free of charge, with reference to the source. It does not forbid sharing the files, so the README follows it and the step goes on.

**Commands and output:**
- The four scans (from S10.4 in `docs/build_plan.md`): `exit=1` each, before the edits and again after both commits. `git ls-remote` listed `refs/heads/main` and `refs/tags/g1-freeze`, so the ref scan had real input.
- `git log --all --oneline -- keys .env`: no output.
- The README placeholder grep: no output, exit 1, before and after.
- A secret-pattern scan over the tree and the history (private keys, PEM headers, API and OAuth token prefixes): only `<project id>` placeholder text in two planning documents, and 0 hits in the history.
- The project id: it is the same string as the repo name (the owner's decision in M0), so every match is the repo name. It appears in no other form.
- Every README number checked against the evidence files: all exact.
- `make check` and the em dash check passed before each commit.

**What went wrong:**
- No bug.
- Stale wording found by reading: the README still said ADR-0001 to 0003 were Proposed and that "All ten ADRs are still Proposed". Fixed in `fb5f68c`.
- Out of date and not edited, because it is a planning document: the NBK row of "Licences" in `docs/specs/data_and_generator.md` still says "None published".

**Interview questions:**
1. *Why scan commit messages and ref names, not only files?*
   Once the repo is public, the history is public and permanent, and the plan forbids rewriting it. A banned word in an old commit message cannot be removed later without a force push.
2. *What would you do if NBK's terms forbade sharing the rate files?*
   Stop before making the repo public (S10.4 sub-step 2). `landing/fx/` is committed, so the files would have to leave the history. That needs the owner's decision.

**Not done, and why:**
- Sub-step 3, the tag `v1.0`: it comes right after this entry is committed.
- Sub-steps 4 to 7 are owner-only (`AGENTS.md`, "Build mode", owner-only action 5):
  - make the repo public;
  - set the description;
  - add the 9 topics;
  - check the repo in a private browser window.
- The two S10.1 screenshots: they need the BigQuery console and the Airflow UI.

## Explain check M10

*What does this project not prove?*
README "What this does not prove" lists:
- production experience (it is a learning project);
- real PSP behaviour or real statement file formats;
- detection quality on real data;
- behaviour at scale (about 200 payments a day by design);
- any fact about any real company;
- that every label is right.

The identity and the preservation test show that no minor unit is lost, duplicated or put on the wrong day. They do not show that each line got the right reason. Only N3 is measured on real data, and it measures a reporting convention, not the reconciliation.

*What did AI write?*
- In build mode, an AI agent wrote the code (core logic included) and every document in the build: the README, the three accepted ADRs, this journal and the walkthrough. Every agent commit carries "written with AI".
- The planning documents were drafted with an AI assistant before the build and reviewed by the owner.
- The owner chose the problem and the constraints, reviewed the plan, did the Google Cloud setup and the key, and wrote the private banned-word list.
- The model answer in `docs/learning/concepts.md`, "M10. Publish, gate G2", was written for the plan, where the owner writes the core logic. It is out of date on this point since the build-mode decision of 2026-11-02. The README "How I used AI" section is the current account.

**Gate G2:** everything measured is true and published in the README, and nothing is listed as "in progress". The floor was not cut, so the tag is `v1.0`.

**Next step:** tag `v1.0` (S10.4 sub-step 3). Then the owner-only steps: S10.4 sub-steps 4 to 7, and the two screenshots from S10.1.

## S10.4: the tag `v1.0` (sub-step 3)

**Date and commit:** 2026-11-03 (UTC). The annotated tag `v1.0` points at `9e246e7`.

**What was done:**
- The four scans from S10.4 in `docs/build_plan.md` were run again after the journal commit. Each printed `exit=1`, the `keys .env` log printed nothing, and the README placeholder grep printed nothing.
- `git tag -a v1.0 -m "v1.0: call-ready floor"`, then `git push origin main v1.0`. The pre-push hook ran and passed:
  ```text
  fb5f68c..9e246e7  main -> main
  * [new tag]         v1.0 -> v1.0
  ```
- `git ls-remote --tags origin` lists `refs/tags/g1-freeze` and `refs/tags/v1.0`.

**What went wrong:** nothing.

**Next step:** owner-only. S10.4 sub-steps 4 to 7 (visibility, description, topics, the private-window check), then the two S10.1 screenshots. After that, the owner studies `docs/walkthrough.md` and does its drill.
