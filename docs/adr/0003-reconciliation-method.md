Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0003: Reconciliation method

- **Status:** Accepted
- **Date:** 2026-11-01
- **Accepted on:** 2026-11-02
- **Accept at:** M10, step S10.2, after the mutation check in `docs/testing.md` (M7). The mutation check ran on 2026-11-02 (UTC).
- **Written by:** an AI agent in build mode (the owner's decision of 2026-11-02 in `AGENTS.md`, heading "Build mode"), checked against the code and `docs/evidence/`. "I" below is the project's voice.

## Context

1. The ledger books the PSP (payment service provider) webhook captures, one per payment, by UTC booking date. Each MID (merchant account) statement lists gross, fee and net per line, by the PSP's accounting date.
2. Finance wants to see every MID-day where the two disagree, and why, to the minor unit.
3. Causes can happen together: one sale can shift day, settle at another amount and carry a wrong fee.
4. In BigQuery, `INT64 / INT64`, `POW()` and `CEIL()` on INT64 return FLOAT64, so they cannot touch money.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| MID-day totals only | simple | no cause per payment | Rejected |
| One reason per line from thresholds | one label | misattributes co-occurring causes | Rejected |
| Exact `payment_id` match, status plus flags, dated components | a cause per line; totals rebuilt bottom-up | more columns | **Chosen** |
| Fuzzy match first | no shared key needed | not needed: both sides carry the PSP reference | Later |
| Compare in USD | one currency | sub-cent residuals | Rejected |
| Identity checked against its own residual | always green | a tautology: it can never fail | Rejected |
| A fixed 1-unit fee tolerance | strict | ignores amount and currency | Rejected |

Why I chose the exact match: both sides carry the PSP's `payment_id`, so there is nothing to guess. Matching line by line gives every payment its own cause, and the MID-day totals can then be rebuilt from the lines and checked against totals computed without the matcher. A single reason per line would hide a second cause on the same payment, so a line gets one status plus separate flags. Comparing in USD would add rounding residuals that are not real differences, so I compare in the settlement currency.

## Decision

1. I match on `payment_id` with an equality `FULL OUTER JOIN` (never an `OR` condition): `int_ledger__captures` against `stg_psp__settlement_lines`, with `record_type = 'SALE'` filtered in the `statement` CTE before the join. Money is INT64 minor units in the settlement currency, and the gross tolerance is 0.
2. Each line gets exactly one `match_status`, judged against the row's `as_of_date`:
   - `matched` when both sides exist;
   - `before_scope` when a one-sided line is dated before `scope_start`;
   - otherwise a ledger-only line is `in_transit` while `as_of_date` is before its `due_date`, and `missing_in_statement` from the `due_date` on;
   - a statement-only line is `missing_in_ledger`.
3. A matched line also gets `date_shift` and `is_amount_mismatch`. `date_shift` is `none` when the accounting date equals the booking date, `timing_cutoff` when it equals the expected accounting date from the MID's cut-off, and `date_mismatch` otherwise.
4. The fee check uses integers only. The expected fee is `DIV(gross * fee_bps + 5000, 10000) + fee_fixed_minor` (half up). The tolerance is `GREATEST(fee_tol_min_minor, DIV(gross * fee_tol_bps + 9999, 10000))` (a ceiling in per-MID basis points, with a minimum). A variance equal to the tolerance is within it. `is_fee_mismatch` is false for `before_scope` lines, so `is_exception` and `fct_recon_exceptions` agree.
5. Each line adds dated components to its MID-day (L is the ledger amount on booking date a, S the statement gross on accounting date b):

| Line | Contributes |
|---|---|
| matched, a = b | `amount_mismatch`: L - S on b |
| matched, a != b | `timing_cutoff` or `date_mismatch`: +L on a, -L on b; `amount_mismatch` on b |
| ledger-only | its status: +L on a |
| statement-only | its status: -S on b |

6. Per (`mid`, `currency`, `recon_date`), `fct_recon_daily` computes the top-down `gap_minor` from the input models, never from the matcher. `unexplained_minor` is that gap minus the 7 components, and it must be 0. Fees stay out of this identity. Two error-level tests guard it: `assert_recon_decomposition_closes` and `assert_no_money_lost_between_layers`.
7. `fct_recon_exceptions` has one row per (line, cause), with a signed amount and a cause date. The CASE logic, the fee formulas and the SQL are in `docs/specs/dbt_project.md`.

## Consequences

**Cost.** One equality join over about 200 lines a day (a design estimate, not a result).

**Better.** Every difference has a dated cause, and a timing shift nets to zero across its two days. The identity closed on real runs of synthetic payments: on 2026-11-02, `make results` found 60 MID-days from 2026-10-03 to 2026-11-01 with 0 minor units unexplained, 0 days not closing, and `assert_recon_decomposition_closes` passing (`docs/evidence/2026-11-02/summary.json`, N2). The integrity tests can fail: in the mutation check in `docs/testing.md`, 4 of 4 deliberate code mutations turned a test red. Changing the `FULL OUTER JOIN` to an `INNER JOIN` and moving the `SALE` filter after the join each turned both integrity tests red.

**Worse.** The integrity tests check the bookkeeping, not the labels. The labels are checked by the unit tests UT1 and UT2 and, from U1, by the seeded self-test of ADR-0007. v1.0 handles one currency per MID and positive amounts only.

**Revisit when.** U7's cross-currency MID needs an FX component; refunds need a sign-aware fee formula; or U4 repeats a statement line (v1.4 adds `duplicate_in_statement`).

## Sources (checked 2026-11-01)

BigQuery functions https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/mathematical_functions; outer joins need an equality (forum report) https://discuss.google.dev/t/query-execution-failed-full-outer-join-cannot-be-used-without-a-condition-that-is-an-equality-of-fields-from-both-sides-of-the-join/118804; public statement schemas https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report/ and https://docs.stripe.com/reports/payout-reconciliation; layer preservation https://github.com/fivetran/dbt_stripe; inclusive tolerances https://github.com/juspay/hyperswitch-reconciliation.
