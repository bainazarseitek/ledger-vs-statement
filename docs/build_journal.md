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

**Next step:** S4.1, `load_partition` and `load_day`.
