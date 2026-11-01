Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0010: Synthetic world design

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** U4 (M14), step S14.4

## Context

1. PSP statements are never public, so the payments are synthetic and labelled so everywhere.
2. The rerun proof needs byte-identical files for the same inputs, on the host and in the container, now and after the window moves.
3. The generator must be small (about 220 lines) and need no dependencies. Python guarantees only `random()` to repeat across versions. Kazakhstan has used UTC+5 all year since 2024-03-01; US local time moves with daylight saving.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| A data-faking library | realistic fields | a changing dependency; no defects or answer key | Rejected |
| A standard-library generator, pure in (seed, day_index, MID, purpose) | deterministic, small | every rule designed by hand | **Chosen** |
| One stream per day, or `randint`, `choices` and `uniform` | simpler, or convenient | a new defect reshuffles every row; not stable across versions | Rejected: a stream per purpose, `random()` only |
| Key on the real date | intuitive | a moved window changes every row | Rejected: `day_index` |
| Emit on the booking date | simple | late data rewrites old partitions | Rejected: by arrival date |
| Real time zones, business-day lags | realistic | moving cut-offs and calendars in Python and SQL | Rejected for v1.0 |
| Hide every parameter from dbt | strict | dbt cannot compute due dates or fees | Rejected: contract terms in a seed |

## Decision

1. The business (illustrative, synthetic): PSP `psp_alpha` with `mid_usd_01` (USD, fixed cut-off UTC-5) and `mid_kzt_01` (KZT, fixed cut-off UTC+5), each settling in its own currency. Statement lines arrive T+1 (90%) or T+2 (10%) calendar days after the accounting date.
2. Contract terms both sides know (offsets, lags, fees, tolerances) live in `dbt/seeds/mids.csv`, read by the generator and dbt. Volumes, noise and defect rates live in `src/recon/world.toml`, hidden from dbt.
3. Payments are a pure function of (seed, `day_index`, MID), with `day_index = (booking_date - RECON_WORLD_START).days` and none before `RECON_WORLD_START`.
4. One stream per purpose: `random.Random(f"{seed}|{day_index}|{mid}|{n}|{purpose}")` for payment n (day-level draws omit `n`; the purposes are under "Determinism" in `docs/specs/data_and_generator.md`). String seeds are stable across processes (CPython seeds them through SHA-512), unlike `hash()`. Only `Random.random()` is called, through `draw_int` and `draw_weighted`.
5. `emit` recomputes the bookings of R-5..R (`lookback_days = 5`) and writes only what arrives on R, plus that day's answer key (ADR-0007).
6. Byte-identical files: sorted rows, `json.dumps(sort_keys=True, separators=(",", ":"))`, atomic renames, Python 3.13 on host and container, and a golden-hash pytest. No personal data.
7. `generator_version = 1.0.0`, frozen with the loader at G1 (tag `g1-freeze`); any later change means a full re-backfill before the proof.

## Consequences

**Cost.** Seconds of CPU and about 0.1 MB of files a day (design estimate); no dependencies.

**Better.** Byte-identical reruns, so the proof tests the pipeline, not the generator; a moved window reproduces the world; a new defect class never disturbs old rows.

**Worse.** Design assumptions, not real PSP behaviour (README "What this does not prove"); no daylight saving or business days; after G1 even a small fix costs a re-backfill.

**Revisit when.** Business-day calendars arrive (v1.x), U7's cross-currency MID needs a rate first (`fetch_fx` before `generate_day`), U4 adds H1 to H4 on new purposes, or the container's Python changes.

## Sources (checked 2026-11-01)

Reproducibility https://docs.python.org/3/library/random.html#notes-on-reproducibility; SHA-512 seeding https://github.com/python/cpython/blob/3.13/Lib/random.py; Kazakhstan UTC+5 https://www.timeanddate.com/news/time/kazakhstan-single-time-zone.html; public statement layouts https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report/ and https://docs.stripe.com/reports/payout-reconciliation.
