# Testing

Three kinds of evidence, kept separate:
1. Integrity tests on the matcher (the identity and layer preservation).
2. Logic tests (dbt unit tests on hand-made rows).
3. Behaviour on planted data (the seeded self-test, from v1.1).

## Mutation check

Run on 2026-11-03 on the dev datasets, starting from commit e2e919d.

| # | Mutation | File | Expected red | Observed red | Result |
|---|---|---|---|---|---|
| 1 | FULL OUTER JOIN changed to INNER JOIN | dbt/models/marts/fct_recon_lines.sql | assert_recon_decomposition_closes, assert_no_money_lost_between_layers | assert_recon_decomposition_closes, assert_no_money_lost_between_layers, ut_lines_status_and_date_shift (UT2) | caught |
| 2 | as_of_date < due_date changed to <= | dbt/models/marts/fct_recon_lines.sql | UT2 | ut_lines_status_and_date_shift (UT2) | caught |
| 3 | QUALIFY removed | dbt/models/staging/stg_psp__payment_events.sql | unique event_id, unique payment_id | unique_stg_psp__payment_events_event_id, unique_int_ledger__captures_payment_id, unique_fct_recon_lines_payment_id, dbt_utils_unique_combination_of_columns_fct_recon_exceptions_payment_id__cause, assert_recon_decomposition_closes, assert_no_money_lost_between_layers | caught |
| 4 | SALE filter moved after the join | dbt/models/marts/fct_recon_lines.sql | assert_recon_decomposition_closes, assert_no_money_lost_between_layers | assert_recon_decomposition_closes, assert_no_money_lost_between_layers, ut_lines_status_and_date_shift (UT2) | caught |

Caught: 4 of 4.

How each mutation was run:

1. Each mutation was made on the scratch branch `mutation-check`, never committed, and reverted with `git checkout -- <file>` before the next one. The branch was deleted afterwards.
2. Each one ran as `uv run dbt run --target dev` (all 9 models built), then `uv run dbt test --target dev` (42 data tests and 2 unit tests). The observed red tests are the entries with `"status": "fail"` in `dbt/target/run_results.json`. No test ended in `error`.
3. Mutation 3 removed the whole four-line `QUALIFY row_number() over (...) = 1` clause.
4. Mutation 4 deleted `where s.record_type = 'SALE'` from the `statement` CTE, added `s.record_type` to that CTE's columns so the moved filter compiles, and added `where s.record_type = 'SALE'` after the `on` clause of the `joined` CTE.
5. Afterwards, `make dbt-build` on `main` rebuilt `analytics_dev` from the correct code: `PASS=56 WARN=0 ERROR=0 SKIP=0`.

Correction (2026-11-02, UTC): "Run on 2026-11-03" above is the Astana (UTC+5) date. In UTC, the date every evidence file in this repo uses, the run was on 2026-11-02.
