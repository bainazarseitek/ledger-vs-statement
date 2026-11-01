Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0003: Reconciliation method

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** M10, step S10.2, after the mutation check in `docs/testing.md` (M7)

## Context

1. The ledger books PSP (payment service provider) webhook captures, one per payment, by UTC booking date. Each MID (merchant account) statement lists gross, fee and net by the PSP's accounting date.
2. Finance wants every MID-day where the two disagree, and why, to the minor unit.
3. Causes co-occur: a sale can shift day, settle at another amount and carry a wrong fee.
4. In BigQuery, `INT64 / INT64`, `POW()` and `CEIL()` on INT64 return FLOAT64.

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

## Decision

1. Match on `payment_id` with an equality `FULL OUTER JOIN` (never OR conditions): `int_ledger__captures` against `stg_psp__settlement_lines`, filtered to `record_type = 'SALE'` before the join. Money is INT64 minor units in the settlement currency; the gross tolerance is 0.
2. One `match_status` per line, judged against the row's `as_of_date`: `matched` when both sides exist; a one-sided line older than `scope_start` is `before_scope`; otherwise a ledger-only line is `in_transit` before its `due_date` and `missing_in_statement` from it on, and a statement-only line is `missing_in_ledger`. Matched lines get `date_shift` and `is_amount_mismatch`.
3. Integer fee check: a half-up expected fee, a ceil tolerance in per-MID basis points with a minimum, an inclusive boundary. `is_fee_mismatch` is false for `before_scope` lines, so `is_exception` and `fct_recon_exceptions` agree.
4. Dated components (L: ledger amount on booking date a; S: statement gross on accounting date b):

| Line | Contributes |
|---|---|
| matched, a = b | `amount_mismatch`: L - S on b |
| matched, a != b | `timing_cutoff` or `date_mismatch`: +L on a, -L on b; `amount_mismatch` on b |
| ledger-only | its status: +L on a |
| statement-only | its status: -S on b |

5. Per (`mid`, `currency`, `recon_date`), the top-down `gap_minor` comes from the input models, never the matcher. `unexplained_minor` is that gap minus the 7 components and must be 0; fees stay out. Error tests: `assert_recon_decomposition_closes`, `assert_no_money_lost_between_layers`.
6. `fct_recon_exceptions`: one row per (line, cause), with a signed amount and a cause date. CASE, fee formulas and SQL: `docs/specs/dbt_project.md`.

## Consequences

**Cost.** One equality join over about 200 lines a day (design estimate).

**Better.** Every difference has a dated cause; timing nets to zero across days; the integrity tests can fail (the M7 mutation check in `docs/testing.md` comes before any "fails when..." claim).

**Worse.** Integrity tests check bookkeeping, not labels (UT1, UT2 and, from U1, the seeded self-test of ADR-0007 check labels); v1.0 is same-currency with positive amounts.

**Revisit when.** U7's cross-currency MID adds an FX component; refunds need a sign-aware fee formula; U4 repeats a statement line (v1.4 adds `duplicate_in_statement`).

## Sources (checked 2026-11-01)

BigQuery functions https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/mathematical_functions; outer joins need an equality (forum report) https://discuss.google.dev/t/query-execution-failed-full-outer-join-cannot-be-used-without-a-condition-that-is-an-equality-of-fields-from-both-sides-of-the-join/118804; public statement schemas https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report/ and https://docs.stripe.com/reports/payout-reconciliation; layer preservation https://github.com/fivetran/dbt_stripe; inclusive tolerances https://github.com/juspay/hyperswitch-reconciliation.
