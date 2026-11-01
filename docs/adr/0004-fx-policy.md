Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0004: FX policy

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** U1 (M11), step S11.5. If `scripts/fx_report.py` was cut before v1.0, say so here when accepting; U7 adds the cross-check inside dbt.

## Context

1. FX is the only real data. In v1.0 no MID converts currency, so rates feed only USD reporting and one real-data check.
2. Frankfurter v2 serves central-bank rates with no key; `providers=nbk` pins the National Bank of Kazakhstan (NBK). Blended rates mix sources and can shift.
3. Frankfurter's NBK series (KZT per 1 USD) has weekday rows only. NBK's own RSS feed adds weekends, but answers a future date with its latest rate. The rerun proof needs rates that never change after they land.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| Frankfurter blended rates | one call | mixed sources; can shift | Rejected |
| Frankfurter v2, provider `nbk`, stored as published | official, JSON, no key | weekday rows only | **Chosen** |
| NBK RSS as the primary source | official, has weekends | XML per day; future dates need a guard | Cross-check in v1.0; U7 decides |
| ECB rates | widely used | no KZT | Rejected |
| A PSP's own rate | what acquirers apply | not public | U7 models a PSP markup |
| Re-fetch every run | fresh | a restated rate breaks the rerun proof | Rejected: fetch once |
| FLOAT64 rates | convenient | binary rounding | Rejected: exact text, NUMERIC in dbt |

## Decision

1. Request `https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT&from=<R-6>&to=<R>`: R-6..R, so a weekend-only range is never empty, and never a date on or after today (UTC). When R-6 has no rate, the answer starts with the last published row before R-6; the landing check allows exactly that one row. Rates stay as NBK publishes them.
2. `fetch_fx` writes the body byte for byte to `landing/fx/provider=nbk/arrival_date=R.json` plus a meta file. An existing file is never refetched or edited, and the folder is committed.
3. `json.loads(body, parse_float=str)` keeps `rate_text` exact; dbt casts it to NUMERIC. `stg_fx__rates` keeps the first-seen value per (`provider`, `base`, `quote`, `rate_date`); `warn_fx_restated` reports changed text.
4. `int_fx__usd_rates_daily` carries the latest earlier rate forward to every day up to `as_of_date`, with `rate_date` and `carry_days`: "a project convention, not NBK's official rate for that day".
5. The build fails if `carry_days` exceeds `var('fx_max_carry_days')` (5) or a rate falls outside 300 to 700 KZT per USD.
6. Reporting only: the macro `to_usd` converts once per MID-day, after summing, with `ROUND(CAST(minor AS NUMERIC) / minor_per_major / units_per_usd, 2)`. Never `POW()`, `INT64 / INT64` or FLOAT64 money.
7. N3 (`scripts/fx_report.py`, first in the cut order) checks the carried rate against NBK's RSS rate for each day from `scope_start` to `as_of_date`: weekdays must agree exactly; weekend gaps are measured. U7 sets the weekend policy from that evidence.

## Consequences

**Cost.** One keyless request per run date and a few KB of committed files.

**Better.** Real, official rates stored exactly; a rebuild months later reuses them; the weekend convention is labelled and measured.

**Worse.** Weekends and holidays use an older rate, off by up to [X] KZT per USD ([Y] bps) on [W] of [C] days (fill from `docs/evidence/2026-11-02/fx_report.json`, or delete if N3 never ran); staging must dedup up to 7 fetches per rate date.

**Revisit when.** N3's gaps matter (U7), a cross-currency MID needs the PSP's rate (U7), Frankfurter changes its API or NBK series, or a holiday pushes `carry_days` above 5.

## Sources (checked 2026-11-01)

Frankfurter https://frankfurter.dev/ and https://github.com/lineofflight/frankfurter/blob/main/CHANGELOG.md; NBK feed https://nationalbank.kz/rss/get_rates.cfm?fdate=31.10.2026; ECB https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html; `parse_float` https://docs.python.org/3/library/json.html; BigQuery math https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/mathematical_functions.
