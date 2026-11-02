Template drafted with AI assistance before the build and reviewed by me. Every entry below is written by me and describes a real bug in this repo. There are no example entries.

# Failure log

The real bugs I hit while building this project: what broke, why, how I found it and how I fixed it. The log shows how the pipeline was debugged. It does not claim that nothing broke.

## Rules

1. Real bugs only: something broke, gave a wrong result, or cost debugging time. Planned failures are not bugs. They go in "Planned red runs" below.
2. Write the entry when the bug happens, inside the step you are on. It takes about 5 minutes. If you write it later, add "(written YYYY-MM-DD)" at the end of the title line.
3. Never invent, merge, soften or delete an entry. If a fix turns out to be wrong, add a new entry and link the old one.
4. Copy the first error line exactly, in a code block. Replace your project id with `<project>`. Never paste a key, a token, or anything from `keys/` or `.env`.
5. Only bugs from this repo. No stories from any job or internship, no company names, and no word from the private banned-word list.
6. Put the entry id (for example `F-003`) in the message of the commit that fixes it.
7. These results are findings, and each one gets an entry:
   - `make compare` reports a changed group or a changed as_of date;
   - a mutation in the mutation check did not turn its expected test red;
   - a G0 probe failure changed the design (record the probe result in ADR-0001 too);
   - a seeded self-test miss was caused by a bug. Misses by design, such as fee overcharges inside the tolerance, are not bugs.
8. Other records live elsewhere: mutation-check results in `docs/testing.md`, G0 probe results in ADR-0001 (heading "G0 results"), measured numbers in `docs/evidence/<date>/`.
9. AI agents never write an entry's root cause, fix or lesson. When the owner asks, they may fill in the date, step, command and exact error text.

## Areas

Use exactly one of these names in the Area field.

| Area | Use it for |
|---|---|
| `setup` | uv, the host venv, the Makefile, local folders |
| `auth` | the service account, the key, the dbt profile, the Airflow connection |
| `sandbox` | BigQuery sandbox limits: the DML refusal, expiry, the storage quota |
| `docker` | the image build, the compose file, mounts, ports |
| `airflow` | DAG parsing, scheduling, data intervals, backfills, pools |
| `generator` | synthetic data, determinism, arrival files |
| `loader` | load jobs, partitions, the schema JSON files |
| `fx` | the Frankfurter fetch, landed files, NBK feed files |
| `dbt-model` | SQL models, seeds, macros |
| `dbt-test` | generic, singular and unit tests |
| `proof` | fingerprints, compare, the results and storage scripts |
| `ci` | GitHub Actions (from `v1.2`) |
| `docs` | a README or doc statement that turned out to be wrong |

## Index

Add one row per entry, newest at the bottom.

| Id | Date | Step | Area | What broke | Status |
|---|---|---|---|---|---|
| F-001 | 2026-11-01 | S0.2 | setup | the pre-push hook was installed with the wrong lines of the plan | fixed |

## Entry format

Copy this block below the last entry. Fill every field. Write "none" or "unknown" instead of leaving a field out.

````markdown
### F-NNN: <what broke, in plain words>

- **Date:** YYYY-MM-DD HH:MM (UTC+5)
- **Step:** <step id from docs/build_plan.md, for example S3.4, or "none">
- **Area:** <one name from the Areas table>
- **Commit where it showed:** <short SHA, or "not committed">
- **Command:** `<the command you ran>`
- **First error line (exact):**
  ```text
  <paste it here>
  ```
- **Expected:** <what should have happened>
- **Actual:** <what happened>
- **Root cause:** <the real cause, not the symptom, in one or two sentences>
- **How I found it:** <the test, assertion, probe, log line or query that pointed to it>
- **Fix:** <short SHA> <what changed, in one sentence>
- **Proof it is fixed:** `<the command that now passes>`
- **Guard added:** <the test or check that would catch it next time, or "none" and why>
- **Time lost:** <minutes>
- **What I learned:** <one sentence in my own words>
- **Status:** fixed | open | won't fix (<reason>)
````

Status meanings:
- `fixed`: the fix is committed and the proof command passes.
- `open`: not fixed yet. Say in the entry what is still wrong.
- `won't fix`: left on purpose. Give the reason, for example "outside v1.0 scope, listed in docs/roadmap.md".

## Planned red runs (not bugs)

Some steps ask you to watch a test fail on purpose before the logic exists. Record those runs here, not as entries.

| Test or check | Step | Red run (date, commit) | First failure line | Green commit |
|---|---|---|---|---|
| UT1 `ut_captures_cutoff_both_directions` | S5.3 | 2026-11-02, `72d7ad3` (naive `expected_accounting_date = DATE(event_ts)`) | `1 of 1 FAIL 1 int_ledger__captures::ut_captures_cutoff_both_directions`: `pay_k2`, `pay_k3`, `pay_u1` and `pay_u3` differ in `expected_accounting_date` and `due_date` | `4c131b9` |
| UT2 `ut_lines_status_and_date_shift` | S5.5 | 2026-11-02, `8ed9fe6` (first version labels every line `matched`, no flags, no fee check) | `1 of 2 FAIL 1 fct_recon_lines::ut_lines_status_and_date_shift`: every row but `pay_c` differs in `match_status`, every row in `primary_reason`, `pay_c` to `pay_f` in the fee columns, `pay_c` and `pay_d` in `date_shift`, and `pay_b`, `pay_d` and `pay_e` in `is_exception` | `74fb5d8` |
| UT3 `ut_events_dedup_first_delivery` | S11.1 | | | |
| UT4 `ut_lines_fee_boundary_and_two_causes` | S11.2 | | | |

Correction (2026-11-02) to the UT2 row: the `8ed9fe6` stub labels every line `matched`, and UT2 expects `matched` for both `pay_c` and `pay_d`. So the rows that differed in `match_status` were `pay_a`, `pay_b`, `pay_e` and `pay_f`, not "every row but `pay_c`". The rest of the row is correct.

Add a row for any other planned failure that a step asks for, for example the U3 negative control (S13.2) or the U6 late batch (S16.3). If a planned red run fails for a different reason than the one you expected, for example a broken fixture, that is a bug: write an entry for it.

## Entries

### F-001: the pre-push hook was installed with the wrong lines of the plan (written 2026-11-02)

- **Date:** 2026-11-01 20:00 (UTC+5)
- **Step:** S0.2
- **Area:** setup
- **Commit where it showed:** not committed (the hook lives in `.git/hooks/`, outside the tracked tree)
- **Command:** `echo "refs/heads/main $(git rev-parse main) refs/heads/main 0000000000000000000000000000000000000000" | .git/hooks/pre-push origin test; echo "exit=$?"`
- **First error line (exact):**
  ```text
  .git/hooks/pre-push: line 1: -: command not found
  ```
- **Expected:** `exit=0` on `main` with the real word list.
- **Actual:** `exit=2`. The hook file began with the two Markdown lines `- **The hook text:**` and ```` ```sh ````, and its last two lines (`fi` and `exit "$status"`) were missing.
- **Root cause:** the install command copied lines 307 to 364 of `docs/build_plan.md` by number. The plan had changed after it was first read, and the hook block had moved down by two lines, so the copy was shifted by two lines.
- **How I found it:** the hook's own run on `main` printed a shell error instead of `exit=0`; `head -5 .git/hooks/pre-push | cat -vet` showed the Markdown lines.
- **Fix:** not committed (outside the tracked tree). The hook is now extracted between its code-fence markers with `awk`, not by line numbers, and compared with the plan text (`diff -q`, identical).
- **Proof it is fixed:** the canary run prints `hook_test.txt:1:zqxwcanary`, then `pre-push: banned word in the files of commit 00258c8...` and `exit=1`; the run on `main` prints `exit=0`.
- **Guard added:** none in the repo. The hook fails closed (a broken hook blocks every push), so this bug could not leak a word, only block pushes.
- **Time lost:** 15
- **What I learned:** copy text out of a document by its markers, never by line numbers, because the document can change between reading and copying.
- **Status:** fixed
