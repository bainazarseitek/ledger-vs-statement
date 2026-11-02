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

**Next step:** S6.1, `dags/recon_daily.py`.
