Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# Data and generator spec

This file describes the simulated business and all of its data:
- the entities and how they relate;
- every landing file and every raw table, column by column;
- the time rules (event time, arrival time, cut-offs, settlement lag);
- the random-number rules that make every run repeatable;
- the defect catalog (pre-registered, see "Defect catalog");
- the answer key and how the seeded self-test scores against it;
- the real FX data.

It is precise enough to write `src/recon/generator.py`, `src/recon/config.py`, `src/recon/world.toml`, the three schema files and the FX landing code from it. It gives rules and pseudocode, not finished code. You write the generator's logic yourself.

Two rules sit above everything else here:
1. **Payments are synthetic.** Every payment row carries `is_synthetic = true`, and every synthetic table description starts with `SYNTHETIC:`.
2. **FX rates are real.** They are the National Bank of Kazakhstan (NBK) rates, stored exactly as Frankfurter returned them: the digits of the response body, not NBK's own text. Frankfurter sends each rate as a JSON number, which may drop trailing zeros, so NBK's `457.10` can arrive as `457.1`. Compare rates as numbers (NUMERIC or `Decimal`), never as text. They are landed once and never fetched again.

Other files cover the rest:
- dbt models, the matcher and all tests: `docs/specs/dbt_project.md`.
- Datasets, the load protocol, sandbox limits and storage guards: `docs/specs/bigquery_sandbox_and_costs.md`.
- The DAGs, Docker and day-to-day commands: `docs/specs/airflow_and_docker.md` (heading "Operations runbook").
- Concepts and a full glossary: `docs/learning/concepts.md`.

---

## At a glance

| Data | Origin | Made by | Lands in (local file) | Loaded into |
|---|---|---|---|---|
| Webhook deliveries | SYNTHETIC | `src/recon/generator.py` | `landing/payment_events/arrival_date=R/part-000.ndjson` | `raw.payment_events` |
| Statement lines, one file per MID | SYNTHETIC | `src/recon/generator.py` | `landing/settlement_lines/arrival_date=R/mid=<mid>.ndjson` | `raw.settlement_lines` |
| Answer key | SYNTHETIC | `src/recon/generator.py` | `landing/_truth/booking_date=R.ndjson` | never loaded |
| USD/KZT rates | REAL | `src/recon/fx.py` (Frankfurter v2, provider `nbk`) | `landing/fx/provider=nbk/arrival_date=R.json` and `.meta.json` | `raw.fx_rates` |
| NBK's own daily feed | REAL | `scripts/fx_report.py` | `landing/fx/provider=nbk_rss/rate_date=YYYY-MM-DD.xml` | not loaded in v1.0 |

`R` is the run date: one UTC calendar day. The run for `R` handles everything that arrived during that day. On the host, `make day DATE=R` writes the same files and loads them into `raw_dev` instead of `raw`.

---

## Words used in this document

| Word | Meaning here |
|---|---|
| Minor unit | The smallest unit of a currency. 1 USD = 100 cents, 1 KZT = 100 tiyn. All money is stored as whole minor units (INT64) |
| PSP | Payment service provider: it takes the card payment and later settles it to the merchant. Here: `psp_alpha` |
| Acquirer | The settling side for one merchant account. It decides the accounting day of a sale |
| MID | Merchant ID: one merchant account at the PSP. Each MID has one currency, one cut-off and one fee contract |
| Capture | The moment a payment is taken. It creates revenue |
| Webhook event | A message the PSP sends to our backend when something happens. Here only "payment captured" |
| Delivery | One attempt to send a webhook event. One event can be delivered more than once |
| Statement | A file the PSP sends per MID per arrival day, listing settled payments |
| Statement line | One payment inside a statement, with gross, fee and net |
| Gross, fee, net | Gross is the sale amount. Fee is what the PSP keeps. Net = gross - fee |
| Booking date | Our revenue day: the UTC date of the capture time |
| Accounting date | The PSP's day for the sale, on the MID's own clock |
| Arrival date | The UTC day a delivery or a statement file reached us |
| Cut-off | The moment the PSP's accounting day ends |
| Lag | Calendar days from the accounting date to the statement's arrival date |
| Due date | From this date on (inclusive), a payment with no statement line counts as missing |
| bp | Basis point: 0.01%. 400 bp = 4% |

---

## The simulated business

**The merchant** is a fictional small web-to-app subscription business. It has no name, and no file in this repo names a real merchant, PSP or employer.

It sells 1-week, 4-week and 12-week plans (`p1w`, `p4w`, `p12w`) through a web checkout. The plan catalogue, prices, mix and volumes are **illustrative assumptions**.

How the money moves:
1. A customer pays on the web. The PSP `psp_alpha` captures the payment on one of two merchant accounts. `mid_usd_01` charges and settles in USD. `mid_kzt_01` charges and settles in KZT.
2. The PSP sends a webhook to the merchant's backend. Webhooks are delivered at least once, so the same event can arrive two or three times. Rarely, every delivery of an event is lost.
3. The warehouse books revenue from the webhooks, by the UTC date of the capture.
4. Each MID's acquirer books the same sale on its own accounting date. The USD MID's day ends at midnight UTC-5. The KZT MID's day ends at midnight UTC+5.
5. One or two days later the PSP sends a statement file per MID. Each line carries gross, fee and net.

What finance wants: every MID-day where the two ledgers disagree, and the reason for each difference, to the minor unit.

| Ledger | Built from | Kept by | Day used |
|---|---|---|---|
| Revenue ledger | webhooks | the merchant | booking date (UTC) |
| Statement ledger | statement files | the PSP | accounting date (MID clock) |

Each payment is a single, independent capture. v1.0 has no customer records, no renewals and no subscription states. Also left out of v1.0 (README backlog, never stubs in code): refunds, chargebacks, payouts and statement headers, cross-currency settlement, business-day calendars and holidays, and app-store revenue.

---

## Entities and relationships

```
                       psp_alpha
                           |
             +-------------+-------------+
             |                           |
        mid_usd_01                  mid_kzt_01        contract terms: dbt/seeds/mids.csv
             |   many payments per booking day
             v
   payment  pay_<booking yyyymmdd>_<tag>_<nnnnn>  ---- plan  p1w | p4w | p12w
     |   |
     |   +-- 0..1 capture event  evt_<payment_id>_cap      (0 only for D3)
     |   |        +-- 1..3 deliveries  dlv_<event_id>_<attempt>        -> raw.payment_events
     |   |
     |   +-- 0..1 statement line  ln_<payment_id>           (0 only for D2)
     |   |        +-- inside exactly 1 statement  stmt_<mid>_<arrival yyyymmdd>  -> raw.settlement_lines
     |   |
     |   +-- 1 answer-key row (local file only, never loaded)
     |
     +-- 1 order  ord_<booking yyyymmdd>_<tag>_<nnnnn>      (carried, unused for matching in v1.0)

   Real and independent of payments:
     USD/KZT rate per rate_date, seen in 1 to 7 daily fetches            -> raw.fx_rates
```

| Entity | Id format | Example | Where it lives |
|---|---|---|---|
| PSP | fixed name | `psp_alpha` | `mids.csv` column `psp` |
| Merchant account (MID) | `mid_<currency>_<nn>` | `mid_kzt_01` | `mids.csv` |
| Plan | `p1w`, `p4w`, `p12w` | `p4w` | `world.toml`, column `plan_id` |
| Payment | `pay_<yyyymmdd>_<tag>_<nnnnn>` | `pay_20261020_kzt_00042` | `payment_id` in both raw synthetic tables |
| Order | `ord_<yyyymmdd>_<tag>_<nnnnn>` | `ord_20261020_kzt_00042` | `raw.payment_events.order_id` |
| Capture event | `evt_<payment_id>_cap` | `evt_pay_20261020_kzt_00042_cap` | `raw.payment_events.event_id` |
| Delivery | `dlv_<event_id>_<attempt>` | `dlv_evt_pay_20261020_kzt_00042_cap_1` | `raw.payment_events.delivery_id` |
| Statement | `stmt_<mid>_<yyyymmdd of arrival>` | `stmt_mid_kzt_01_20261022` | `raw.settlement_lines.statement_id` |
| Statement line | `ln_<payment_id>` | `ln_pay_20261020_kzt_00042` | `raw.settlement_lines.line_id` |
| Answer-key row | keyed by `payment_id` | see "Ground truth (answer key)" | `landing/_truth/` only |
| FX observation (real) | (provider, base, quote, rate_date) per fetch | (`nbk`, `USD`, `KZT`, 2026-10-23) | `raw.fx_rates` |

Id rules:
1. `<yyyymmdd>` in payment and order ids is the payment's booking date.
2. `<tag>` is the MID currency in lower case: `usd` or `kzt`. `config.py` must fail at load time if two MIDs would get the same tag (the U7 cross-currency MID will need its own tag).
3. `<nnnnn>` is the payment number `n` within its (booking date, MID), starting at 1, zero-padded to 5 digits. `n` is the draw order, not the time order: `_00001` is not necessarily the day's earliest capture.
4. `<attempt>` is 1 for the first delivery, then 2 and 3 for redeliveries in time order.
5. Ids are readable on purpose, so you can debug and explain them. There is no personal data anywhere: no names, emails, card numbers, IP addresses or bank details.

---

## Contract terms and world parameters

The split is deliberate:
- **Contract terms** that both the merchant and the PSP know (currency, cut-off, lag, fee schedule, tolerance) live in `dbt/seeds/mids.csv`. The generator and dbt read the same file. Sharing them is legitimate: finance knows its contract.
- **Everything finance does not know** (volumes, timing noise, defects, PSP mistakes) lives in `src/recon/world.toml`. dbt never sees it. The one value finance does know there is `statement_grace_days`: a copy of a dbt var, kept equal by a required test (see "World parameters").

### Merchant accounts (`dbt/seeds/mids.csv`)

Exact file content:

```
mid,psp,currency,statement_utc_offset_hours,max_settlement_lag_days,fee_bps,fee_fixed_minor,fee_tol_bps,fee_tol_min_minor
mid_usd_01,psp_alpha,USD,-5,2,290,30,10,5
mid_kzt_01,psp_alpha,KZT,5,2,250,0,10,500
```

| Column | Seed type | Meaning |
|---|---|---|
| `mid` | STRING | merchant account id |
| `psp` | STRING | always `psp_alpha` in v1.0 |
| `currency` | STRING | charge and settlement currency (the same in v1.0) |
| `statement_utc_offset_hours` | INT64 | fixed offset of the acquirer's clock. Accounting date = DATE(capture time + offset hours) |
| `max_settlement_lag_days` | INT64 | the contract's longest lag: a line arrives at most this many days after its accounting date |
| `fee_bps` | INT64 | percentage fee in basis points (290 = 2.90%) |
| `fee_fixed_minor` | INT64 | fixed fee per line, in minor units (30 = 0.30 USD) |
| `fee_tol_bps` | INT64 | per-line fee tolerance, in basis points of gross |
| `fee_tol_min_minor` | INT64 | the smallest tolerance, in minor units |

Every column gets an explicit type in `dbt/seeds/_seeds.yml`, so dbt never infers FLOAT64 (the dbt side is in `docs/specs/dbt_project.md`).

The fee rules use integer arithmetic only, identical in Python and SQL. In Python, `//` is floor division, which equals truncation for the non-negative values used here:

```
expected_fee_minor  = (gross_minor * fee_bps + 5000) // 10000 + fee_fixed_minor           (half-up)
fee_tolerance_minor = max(fee_tol_min_minor, (gross_minor * fee_tol_bps + 9999) // 10000)  (ceiling)
```

Contract arithmetic for the plan prices (worked values, not results):

| MID | gross_minor | expected_fee_minor | fee_tolerance_minor |
|---|---|---|---|
| `mid_usd_01` | 699 | 50 | 5 |
| `mid_usd_01` | 1999 | 88 | 5 |
| `mid_usd_01` | 3999 | 146 | 5 |
| `mid_kzt_01` | 349000 | 8725 | 500 |
| `mid_kzt_01` | 999000 | 24975 | 999 |
| `mid_kzt_01` | 1999000 | 49975 | 1999 |

All grosses are positive in v1.0. Refunds (negative amounts) would need a sign-aware rule and are not in v1.0.

### Currencies (`dbt/seeds/currencies.csv`)

```
currency,minor_per_major
USD,100
KZT,100
```

Both values follow ISO 4217. The generator does not read this file. dbt uses it for the USD reporting columns.

### World parameters (`src/recon/world.toml`)

Parsed with the standard-library `tomllib`. Every value is an integer or a string, so no float ever touches an amount, a fee or a threshold. Rates are in basis points. The values below are the v1.0 design. You write one comment per value, in your own words.

```toml
generator_version = "1.0.0"
lookback_days = 5
statement_grace_days = 1

[volume]
mean_per_day = { mid_usd_01 = 130, mid_kzt_01 = 70 }
jitter_pct = 10

[plans]
order = ["p1w", "p4w", "p12w"]
weight_pct = [30, 50, 20]

[plans.price_minor]
USD = [699, 1999, 3999]
KZT = [349000, 999000, 1999000]

[time]
local_hour_weights = [3, 2, 1, 1, 1, 1, 2, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5, 6, 7, 8, 9, 9, 7, 5]

[webhooks]
first_delivery_delay_s = [1, 30]
redelivery_bp = 400
redelivery_one_copy_bp = 7500
redelivery_delay_s = [60, 21600]

[settlement]
lag_one_day_bp = 9000

[defects]
missing_in_statement_bp = 50
missing_in_ledger_bp = 40
amount_mismatch_bp = 40
amount_delta_bp = [100, 2000]
fee_overcharge_bp = 100
combo_fee_overcharge_bp = 2500

[fee_noise]
spike_bp = 100
```

| Key | Value | Meaning |
|---|---|---|
| `generator_version` | `"1.0.0"` | written into every answer-key row; bumped whenever output changes |
| `lookback_days` | 5 | a run recomputes booking days R-5..R (only R-3..R are needed; see "What one run ingests"). U6's late batch D6 needs at least 6 (see "Held for later") |
| `statement_grace_days` | 1 | a copy of the var of the same name in `dbt/dbt_project.yml`; the answer key needs it for `due_date`. The required M3 test `test_grace_days_match_dbt` fails if the two differ. The minimal project file from S1.3 has no `vars:` block yet, so in S3.1 add `vars:` with `statement_grace_days: 1` to it, together with this key. S5.1 keeps that line |
| `volume.mean_per_day` | 130 USD, 70 KZT | mean captures per booking day per MID |
| `volume.jitter_pct` | 10 | daily count drawn uniformly in `[mean * 90 // 100, mean * 110 // 100]`: USD 117..143, KZT 63..77 |
| `plans.order` | `p1w`, `p4w`, `p12w` | the fixed order every plan list follows |
| `plans.weight_pct` | 30, 50, 20 | plan mix in percent (0.30, 0.50, 0.20) |
| `plans.price_minor.USD` | 699, 1999, 3999 | USD prices in cents |
| `plans.price_minor.KZT` | 349000, 999000, 1999000 | KZT prices in tiyn (3,490, 9,990 and 19,990 KZT) |
| `time.local_hour_weights` | 24 integers | weight of each local hour 0..23 on the MID's clock: an evening peak |
| `webhooks.first_delivery_delay_s` | 1..30 | seconds from capture to the first delivery |
| `webhooks.redelivery_bp` | 400 | D1: 4% of capture events get redelivered |
| `webhooks.redelivery_one_copy_bp` | 7500 | D1 events get 1 extra copy (75%), otherwise 2 (25%) |
| `webhooks.redelivery_delay_s` | 60..21600 | each extra copy arrives 60 s to 6 h after the first delivery |
| `settlement.lag_one_day_bp` | 9000 | lag 1 day (90%), otherwise 2 days (10%) |
| `defects.missing_in_statement_bp` | 50 | D2: 0.5% of payments |
| `defects.missing_in_ledger_bp` | 40 | D3: 0.4% of payments |
| `defects.amount_mismatch_bp` | 40 | D4: 0.4% of payments |
| `defects.amount_delta_bp` | 100..2000 | D4 size: 1% to 20% of the amount |
| `defects.fee_overcharge_bp` | 100 | D5: 1.0% of settled lines |
| `defects.combo_fee_overcharge_bp` | 2500 | 25% of D4 lines also get D5 |
| `fee_noise.spike_bp` | 100 | B3: 1% of eligible lines get a fee spike |

The D5 overcharge range and the B3 noise ranges depend on each line's tolerance. They are rules, defined under "Defect catalog", not TOML values.

**Rotation rule (local hours to UTC hours).** A MID's weight for UTC hour `h` (0..23) is `local_hour_weights[(h + statement_utc_offset_hours) mod 24]`. Python's `%` already returns a non-negative result for a positive modulus, so `(h - 5) % 24` works. The resulting UTC-hour lists (total weight 106 for both):
- `mid_usd_01` (offset -5): `[8, 9, 9, 7, 5, 3, 2, 1, 1, 1, 1, 2, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5, 6, 7]`
- `mid_kzt_01` (offset +5): `[1, 2, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5, 6, 7, 8, 9, 9, 7, 5, 3, 2, 1, 1, 1]`

Design consequence (not a result): UTC hours 00-04 hold 38 of 106 USD weight, so about 36% of USD captures fall on the previous accounting date. UTC hours 19-23 hold 8 of 106 KZT weight, so about 7.5% of KZT captures fall on the next accounting date.

### Where config is read from (`src/recon/config.py`)

`config.py` turns three inputs into frozen dataclasses (`World` for the TOML values, one `Mid` per CSV row):
1. Environment variables: `RECON_SEED` (parsed with `int()`), `RECON_WORLD_START` (`date.fromisoformat`), `RECON_LANDING_DIR` (a path).
2. `world.toml`, found next to `config.py`: `Path(__file__).parent / "world.toml"`. From U4, `RECON_WORLD_FILE` can name another file in the same folder, and that file also sets its own seed (see "Held-out world (U4)").
3. `mids.csv`, found at `Path(__file__).resolve().parents[2] / "dbt" / "seeds" / "mids.csv"`. On the host that is the repo's `dbt/seeds/mids.csv`. In the container it is `/opt/airflow/dbt/seeds/mids.csv`, because the compose file mounts `./src` at `/opt/airflow/src` and `./dbt` at `/opt/airflow/dbt`. No extra environment variable is needed.

Checks when config loads (fail loudly on any): 24 hour weights; `plans.order`, `plans.weight_pct` and both price lists have the same length; weights sum to 100; currency tags are unique; every MID currency has a price list.

The generator functions take `seed` and `world_start` as arguments. Only the DAG and the CLI read them from the environment, so tests never depend on `.env`.

---

## Time model and arrival semantics

### Three dates

| Date | Definition | Clock | Stored in |
|---|---|---|---|
| Booking date | `DATE(event_ts)` | UTC | derived in dbt (`int_ledger__captures.booking_date`); also in ids and the answer key |
| Accounting date | `DATE(event_ts + statement_utc_offset_hours hours)` | the MID's fixed offset | `raw.settlement_lines.accounting_date` |
| Arrival date | the UTC day a delivery or a file reached us | UTC | `_arrival_date` on every raw row (the partition column) |

Say "three dates (arrival, booking, accounting)" or "two time axes". Never "bitemporal".

All timestamps are UTC with whole seconds. No clock skew between the PSP and us is modelled: a statement line's `captured_ts` equals the webhook's `event_ts`.

### Cut-offs and time zones

- `mid_usd_01` uses a fixed UTC-5. Its accounting day D runs from D 05:00 UTC to D+1 05:00 UTC. A capture at 00:00:00..04:59:59 UTC belongs to the previous accounting day.
- `mid_kzt_01` uses a fixed UTC+5. Its accounting day D runs from D-1 19:00 UTC to D 19:00 UTC. A capture at 19:00:00..23:59:59 UTC belongs to the next accounting day.
- Offsets are fixed numbers, never time-zone names, so Python and BigQuery cannot disagree and there is no daylight saving. For KZT this matches reality (Kazakhstan has used UTC+5 all year since 2024-03-01). For USD it is a simplification: US Eastern time switches between UTC-5 and UTC-4.
- The pipeline's own day is the UTC day. The DAG runs at 00:00 UTC (05:00 Astana) for the day that just ended.

### Timing table

| Feed | When it is created | Which file it arrives in |
|---|---|---|
| Capture (`event_ts`) | UTC hour from the MID's UTC-hour weights; second uniform within the hour | not a file |
| First delivery | `event_ts` + 1 to 30 s | the events file of `DATE(delivered_ts)`; a capture at 23:59:50 can land in the next day's file |
| Redelivery (D1) | 60 s to 6 h after the first delivery | the events file of `DATE(delivered_ts)`, often the next day |
| Accounting date | `DATE(event_ts + statement_utc_offset_hours)` | not a file |
| Statement line | accounting date + lag (1 or 2 days) | `stmt_<mid>_<arrival yyyymmdd>`, file `settlement_lines/arrival_date=<arrival>/mid=<mid>.ndjson` |
| FX | fetched once by run R for R-6..R | `landing/fx/provider=nbk/arrival_date=R.json` |

### Webhooks

1. Each payment has one capture event (`event_type = payment.captured`), except D3 payments, which have none.
2. First delivery: `delivered_ts = event_ts + delay`, delay 1..30 s. A capture at 23:59:45 can arrive after midnight: its first delivery lands in the next day's file, while its booking date stays the capture date.
3. Redeliveries (D1): 1 or 2 extra copies, each 60 s to 6 h after the first delivery. Many land on the next UTC day.
4. Every copy carries the same payload: `event_id`, `event_type`, `payment_id`, `order_id`, `mid`, `plan_id`, `amount_minor`, `currency`, `event_ts`. Only `delivery_id`, `delivered_ts`, `_arrival_date` and `_source_file` differ.
5. The landing rows are already flat. A real webhook is nested JSON with signature headers. This project models the row a backend stores after parsing it.

### Statements (T+1 and T+2)

1. One statement per MID per arrival day: `stmt_<mid>_<yyyymmdd of arrival>`. It holds every line whose arrival date is that day.
2. Statement arrival date = accounting date + lag. Lag is 1 calendar day for 90% of lines and 2 for 10%.
3. Statements arrive every calendar day, weekends included. This is a simplification; business-day calendars are on the roadmap.
4. One statement can hold lines from two accounting dates: the T+1 lines of accounting day A-1 and the T+2 lines of accounting day A-2.
5. A file's time of arrival within the day is not modelled. Only its date matters.
6. Due date = expected accounting date + `max_settlement_lag_days` (2) + `statement_grace_days` (1). A line always arrives at least one day before its due date.

### What one run ingests

Run `R` ingests everything that arrived during UTC day `R`: deliveries with `DATE(delivered_ts) = R`, and the statement files dated `R`. That is the meaning of one Airflow data interval in this project. FX is the exception: run `R` fetches the real rates for R-6..R once.

How far an arrival can trail its booking date (design limits):

| Row | Arrival date minus booking date |
|---|---|
| First delivery | 0 or 1 |
| Redelivery | 0 or 1 (the latest is 23:59:59 + 30 s + 6 h) |
| Statement line, `mid_usd_01` | (-1 or 0) + (1 or 2) = 0 to 2 |
| Statement line, `mid_kzt_01` | (0 or +1) + (1 or 2) = 1 to 3 |

So a run needs booking days R-3..R. `lookback_days = 5` leaves 2 days of margin, and a pytest proves the limit (see "Generator tests"). The late batch D6 (U6) needs booking days R-6..R, so generator 1.1.0 raises `lookback_days` (see "Held for later").

### Worked example (illustrative)

This example is hand-made to show the rules. The generator's real row for this id will differ.

`pay_20261020_kzt_00042`: plan `p4w`, 999000 tiyn (9,990.00 KZT), captured 2026-10-20 20:15:07 UTC.

| Step | Value | Rule |
|---|---|---|
| Booking date | 2026-10-20 | UTC date of the capture |
| First delivery | 2026-10-20 20:15:30 UTC (+23 s) | arrives 10-20, attempt 1 |
| Redelivery (D1) | 2026-10-21 02:10:00 UTC (+21,270 s after the first) | arrives 10-21, attempt 2 |
| Accounting date | 2026-10-21 | 20:15 UTC + 5 h = 01:15 on 10-21 (B1) |
| Lag | 1 day | the line arrives 2026-10-22 in `stmt_mid_kzt_01_20261022` |
| Due date | 2026-10-24 | 10-21 + 2 + 1 |
| Fee | expected 24975, noise +120, fee 25095, net 973905 | B3 inside (120 is within 999 // 2 = 499) |

What each run sees: on 10-20 one delivery, so the line is `in_transit`. On 10-21 the redelivery arrives and dedup removes it (`copies_received = 2`); still `in_transit`. From 10-22 the statement line is there: `matched` with `date_shift = timing_cutoff`.

The rows, exactly as the files would hold them (one JSON object per line):

```
landing/payment_events/arrival_date=2026-10-20/part-000.ndjson
{"_arrival_date":"2026-10-20","_source_file":"payment_events/arrival_date=2026-10-20/part-000.ndjson","amount_minor":999000,"currency":"KZT","delivered_ts":"2026-10-20 20:15:30+00:00","delivery_id":"dlv_evt_pay_20261020_kzt_00042_cap_1","event_id":"evt_pay_20261020_kzt_00042_cap","event_ts":"2026-10-20 20:15:07+00:00","event_type":"payment.captured","is_synthetic":true,"mid":"mid_kzt_01","order_id":"ord_20261020_kzt_00042","payment_id":"pay_20261020_kzt_00042","plan_id":"p4w"}

landing/payment_events/arrival_date=2026-10-21/part-000.ndjson
{"_arrival_date":"2026-10-21","_source_file":"payment_events/arrival_date=2026-10-21/part-000.ndjson","amount_minor":999000,"currency":"KZT","delivered_ts":"2026-10-21 02:10:00+00:00","delivery_id":"dlv_evt_pay_20261020_kzt_00042_cap_2","event_id":"evt_pay_20261020_kzt_00042_cap","event_ts":"2026-10-20 20:15:07+00:00","event_type":"payment.captured","is_synthetic":true,"mid":"mid_kzt_01","order_id":"ord_20261020_kzt_00042","payment_id":"pay_20261020_kzt_00042","plan_id":"p4w"}

landing/settlement_lines/arrival_date=2026-10-22/mid=mid_kzt_01.ndjson
{"_arrival_date":"2026-10-22","_source_file":"settlement_lines/arrival_date=2026-10-22/mid=mid_kzt_01.ndjson","accounting_date":"2026-10-21","captured_ts":"2026-10-20 20:15:07+00:00","currency":"KZT","fee_minor":25095,"gross_minor":999000,"is_synthetic":true,"line_id":"ln_pay_20261020_kzt_00042","mid":"mid_kzt_01","net_minor":973905,"payment_id":"pay_20261020_kzt_00042","record_type":"SALE","statement_id":"stmt_mid_kzt_01_20261022"}

landing/_truth/booking_date=2026-10-20.ndjson
{"booking_date":"2026-10-20","due_date":"2026-10-24","extra_copies":1,"fee_noise":"inside","fee_variance_minor":120,"generator_version":"1.0.0","mid":"mid_kzt_01","payment_id":"pay_20261020_kzt_00042","planted":["D1"],"statement_arrival_date":"2026-10-22","timing_shift":1}
```

### Arrival guarantees the generator must keep

These follow from the rules above. Each one is checked by a pytest (see "Generator tests").
1. Every row a run writes belongs to that run: `_arrival_date = R` on every row, `DATE(delivered_ts) = R` on every delivery, and every line in file `R` arrives on `R`.
2. Every delivery appears in exactly one events file. Every statement line appears in exactly one statement file. A D2 payment appears in no statement file.
3. Every arrival of a payment lies in [booking date, booking date + 3].
4. When a payment has both sides, its first delivery never arrives after its statement line. So at any as-of date, a visible statement line has a visible webhook too, unless the payment is D3. In a full window, `missing_in_ledger` can only come from D3.
5. A statement line always arrives before its due date. In a full window, `missing_in_statement` can only come from D2.
6. No payment is booked before `RECON_WORLD_START`. A USD accounting date can be `RECON_WORLD_START - 1` (captures before 05:00 UTC on the first day). No arrival date is ever before `RECON_WORLD_START`.

Consequence for the first day: on `RECON_WORLD_START` the `mid_kzt_01` statement file is empty by design (every KZT line needs at least one day of lag), while `mid_usd_01` already has lines from early-morning captures. dbt's `assert_arrival_days_complete` skips the first day for this reason.

---

## Determinism

### Inputs

Output depends only on `(seed, world_start, run_date)` plus the committed config (`world.toml`, `mids.csv`). Nothing reads the clock, the weekday, the machine, or any state left by an earlier call.

### The one rule: day_index, never the date

`day_index = (booking_date - world_start).days`. Every draw is keyed by `day_index`, never by the calendar date. Moving `world_start` therefore moves the same world to new dates (see "Rolling window and reruns months later").

### Random streams

- Day level: `random.Random(f"{seed}|{day_index}|{mid}|volume")`.
- Per payment: `random.Random(f"{seed}|{day_index}|{mid}|{n}|{purpose}")`.

Where `seed` is the integer from `RECON_SEED` written in decimal (`20261101`), `mid` is the MID id string (`mid_usd_01`) and `n` is the payment number from 1. Because `config.py` parses the seed with `int()`, `"020261101"` and `"20261101"` give the same streams.

Why a string seed is safe: Python seeds a `str` by turning its bytes, plus their SHA-512 digest, into one big integer. It does not use `hash()`, so `PYTHONHASHSEED` has no effect, and the same string gives the same stream in every process and on every machine.

The streams, and the exact draws each one makes, in order. The order is part of this spec: changing it changes the data.

| Purpose | Decides | Draws, in this order |
|---|---|---|
| `volume` (day level) | number of payments for (MID, day) | 1. `count = draw_int(lo, hi)` with the jitter bounds |
| `plan` | the plan | 1. `i = draw_weighted(plans.weight_pct)` |
| `time` | capture time | 1. `utc_hour = draw_weighted(UTC-hour weights of the MID)`; 2. `second = draw_int(0, 3599)` |
| `money` | D2, D3, D4 or none | 1. `x = draw_int(0, 9999)`: D2 if `x < 50`; else D3 if `x < 90`; else D4 if `x < 130`; else none |
| `delivery` | first delivery delay | 1. `delay_s = draw_int(1, 30)` |
| `redelivery` | D1 | 1. `x = draw_int(0, 9999)`: D1 if `x < 400`. If D1: 2. `y = draw_int(0, 9999)`: 1 copy if `y < 7500`, else 2; 3. one `draw_int(60, 21600)` per copy |
| `lag` | statement lag | 1. `x = draw_int(0, 9999)`: 1 day if `x < 9000`, else 2 |
| `amount_delta` | D4 size | 1. `sign = draw_int(0, 1)` (0 = statement lower, 1 = statement higher); 2. `delta_bp = draw_int(100, 2000)` |
| `combo` | whether a D4 line also gets D5 | 1. `x = draw_int(0, 9999)`: D5 if `x < 2500` |
| `fee_defect` | D5 | 1. `x = draw_int(0, 9999)`: D5 if `x < 100`. If D5 (from this draw or from `combo`): 2. `overcharge = draw_int(ceil(0.8 * tol), 10 * tol)` |
| `fee_noise` | B3 | 1. `x = draw_int(0, 9999)`: spike if `x < 100`. Spike: 2. `sign = draw_int(0, 1)` (0 = minus, 1 = plus), 3. `magnitude = draw_int(tol, ceil(1.5 * tol))`. Inside: 2. `v = draw_int(-floor(tol / 2), floor(tol / 2))` |

Thresholds come from `world.toml`; the numbers above are the v1.0 values.

Rules for streams:
1. Create a stream only when the payment needs it: `delivery` and `redelivery` only without D3; `lag`, `fee_defect` only with a statement line; `amount_delta` and `combo` only for D4; `fee_noise` only for lines without D5. Streams are independent, so skipping one changes nothing else.
2. A new defect class gets a new purpose name. It never takes draws from an existing stream, so every existing row stays identical.
3. For the bounds use integers: `ceil(0.8 * tol) = (4 * tol + 4) // 5`, `ceil(1.5 * tol) = (3 * tol + 1) // 2`, `floor(tol / 2) = tol // 2`.

### Draw helpers (the only two)

Python promises only that `Random.random()` keeps producing the same sequence for the same seed across versions. `randint`, `randrange`, `choice`, `choices`, `uniform` and `shuffle` are not covered by that promise. Never use them.

```
draw_int(rng, lo, hi):                 an integer in [lo, hi], both ends included
    u = rng.random()                   0 <= u < 1
    k = lo + floor(u * (hi - lo + 1))
    return min(k, hi)                  guard against float rounding at the top end

draw_weighted(rng, weights):           weights: non-negative integers with a positive sum
    x = rng.random() * sum(weights)
    running = 0
    for i, w in enumerate(weights):
        running = running + w
        if x < running: return i
    return the last index whose weight is above 0      float guard
```

### Integer money

- Amounts, fees, tolerances and deltas are Python `int` from start to end. No `float`, and no `Decimal`, for money in the generator.
- The only floats are the uniform draws inside the two helpers, and they become integers at once.

### Byte-identical files

1. Rows are sorted by key: deliveries by `delivery_id`, statement lines by `line_id`, answer-key rows by `payment_id`.
2. Each row is `json.dumps(row, sort_keys=True, separators=(",", ":"))` followed by `"\n"`, so a file ends with a newline. An empty file is 0 bytes.
3. Timestamps are written as `YYYY-MM-DD HH:MM:SS+00:00`: `datetime.isoformat(sep=" ")` on a UTC datetime with `microsecond = 0` (whole seconds, so no fraction appears). Dates are `YYYY-MM-DD`. Booleans are `true`. Integers are JSON numbers. The answer key's `planted` list is sorted.
4. Files are UTF-8 with LF line endings.
5. Each file is written to `<final name>.tmp` in the same folder, then moved with `os.replace` to its final name. A crash never leaves half a file.
6. The host venv runs Python 3.13, like the container (3.13.15). A golden-hash pytest catches any drift.

### Freeze rule

The generator and loader freeze at gate G1 (tag `g1-freeze`). After that, any change to `generator.py`, `world.toml`, `mids.csv` or a schema file needs:
1. a new `generator_version` if the output changes;
2. a new golden hash in the test;
3. a full re-backfill of the window before the rerun proof.

---

## Generator logic (pseudocode)

### `payments_for_day(seed, world_start, day, mid)`

Returns the payments booked on `day` for one MID. `mid` is the `Mid` record from config (id, currency, offset, lag, fee terms). World values come from config.

1. If `day < world_start`, return an empty list. The business opens on `world_start`.
2. `day_index = (day - world_start).days`.
3. `count = draw_int(volume stream, mean * (100 - jitter_pct) // 100, mean * (100 + jitter_pct) // 100)`.
4. For `n = 1 .. count`, build one payment:
   1. **Plan.** `i = draw_weighted(plan stream, weight_pct)`; `plan_id = order[i]`; `amount_minor = price_minor[currency][i]`.
   2. **Capture time.** `h = draw_weighted(time stream, UTC-hour weights)`; `s = draw_int(time stream, 0, 3599)`; `event_ts = day at 00:00:00 UTC + h hours + s seconds`.
   3. **Ids.** `tag = currency in lower case`; `suffix = yyyymmdd(day) + "_" + tag + "_" + n as 5 digits`; `payment_id = "pay_" + suffix`; `order_id = "ord_" + suffix`; `event_id = "evt_" + payment_id + "_cap"`.
   4. **Accounting date.** `accounting_date = DATE(event_ts + offset hours)`; `timing_shift = (accounting_date - day).days`.
   5. **Money class** from the `money` stream: D2, D3, D4 or none.
   6. **Deliveries** (skip for D3). First: `delivered_ts = event_ts + draw_int(delivery stream, 1, 30)` seconds, attempt 1. Then D1 from the `redelivery` stream: if D1, draw the copy count and one delay per copy, sort the delays from small to large, and add deliveries at `first delivered_ts + delay` with attempts 2 and 3. Each delivery row gets `_arrival_date = DATE(delivered_ts)` and its `_source_file`.
   7. **Statement line** (skip for D2):
      1. `lag` from the `lag` stream; `statement_arrival_date = accounting_date + lag`.
      2. `gross = amount_minor`. If D4: `delta = max(1, (amount_minor * delta_bp + 5000) // 10000)`; `gross = amount_minor - delta` when `sign = 0`, `amount_minor + delta` when `sign = 1`.
      3. `expected = expected_fee_minor(gross)`; `tol = fee_tolerance_minor(gross)` (formulas under "Merchant accounts").
      4. `is_d5 = (first fee_defect draw < 100) or (D4 and combo draw < 2500)`.
      5. If D5: `fee = expected + overcharge` (second `fee_defect` draw); no noise. Otherwise B3 from the `fee_noise` stream: `fee = expected + v`, where `v` is the inside value or the signed spike.
      6. `net = gross - fee`.
      7. The row gets `captured_ts = event_ts`, `record_type = "SALE"`, `statement_id = "stmt_" + mid + "_" + yyyymmdd(statement_arrival_date)`, `line_id = "ln_" + payment_id`, `_arrival_date = statement_arrival_date` and its `_source_file`.
   8. **Answer-key row** (fields under "Ground truth (answer key)").
5. Return the payments in `n` order.

### `arrivals(seed, world_start, run_date)`

1. For each MID (in `mids.csv` order) and each booking day `b` from `run_date - lookback_days` to `run_date` with `b >= world_start`, take `payments_for_day(seed, world_start, b, mid)`.
2. `events` = every delivery row with `_arrival_date = run_date`.
3. `lines[mid]` = every statement row with `_arrival_date = run_date`, for every MID in `mids.csv` (an empty list when there are none).
4. `truth` = the answer-key row of every payment with booking date `run_date`.
5. Sort each list (see "Byte-identical files") and return them.

### `emit(seed, world_start, run_date, landing_dir) -> dict of counts`

1. If `run_date < world_start`, raise `ValueError`. (The DAG's `check_window` also refuses it.)
2. Call `arrivals`.
3. Write each file atomically, all relative to `landing_dir`:
   - `payment_events/arrival_date=R/part-000.ndjson`
   - `settlement_lines/arrival_date=R/mid=<mid>.ndjson` for every MID in `mids.csv`, even when empty
   - `_truth/booking_date=R.ndjson`
4. Return a small dict (it travels through XCom):
   `{"run_date": "R", "payment_events": <rows>, "settlement_lines": <rows>, "settlement_lines_by_mid": {"mid_kzt_01": <rows>, "mid_usd_01": <rows>}, "truth": <rows>, "generator_version": "1.0.0"}`.
5. Running `emit` twice with the same inputs writes the same bytes. `emit` never reads, changes or deletes any other day's files, and never touches `landing/fx/`.

### Code shape and line budget

- `src/recon/generator.py`, about 220 lines: `payments_for_day`, `arrivals`, `emit`, the two draw helpers and small row builders.
- `src/recon/config.py`, about 60 lines.
- Standard library only: `csv`, `dataclasses`, `datetime`, `json`, `math`, `os`, `pathlib`, `random`, `tomllib`.
- You write: the world rules, every defect branch, the selection logic in `arrivals` and the answer key. An agent may scaffold: config loading, the atomic file writer and the pytest harness. You read and can explain every line.

---

## Landing files

### Layout

```
landing/
  payment_events/arrival_date=2026-10-20/part-000.ndjson            gitignored   SYNTHETIC
  settlement_lines/arrival_date=2026-10-20/mid=mid_kzt_01.ndjson    gitignored   SYNTHETIC
  settlement_lines/arrival_date=2026-10-20/mid=mid_usd_01.ndjson    gitignored   SYNTHETIC
  _truth/booking_date=2026-10-20.ndjson                             gitignored   SYNTHETIC, never loaded
  fx/provider=nbk/arrival_date=2026-10-20.json                      committed    REAL (response body)
  fx/provider=nbk/arrival_date=2026-10-20.meta.json                 committed    REAL (fetch record)
  fx/provider=nbk_rss/rate_date=2026-10-20.xml                      committed    REAL (cross-check only)
```

The `key=value` folder names show the partition at a glance. BigQuery never reads these folders; the loader does.

`.gitignore` excludes `landing/*` except `landing/fx/`. The check `git check-ignore keys/sa.json .env landing/_truth/x` prints all three paths. Synthetic files are never committed: they can always be regenerated.

### Format rules for payment and answer-key files

The rules under "Byte-identical files" apply. In addition:
- `_source_file` is the path relative to the landing folder, with forward slashes and no leading `landing/`, for example `payment_events/arrival_date=2026-10-20/part-000.ndjson`. The host and the container then write the same text, so their rows are identical (the U3 cross-runtime check depends on it).
- The generator writes every schema column, including `is_synthetic`, `_arrival_date` and `_source_file`. For these two tables the loader adds nothing.

### Empty days and missing files

1. For every run date the generator writes all four synthetic files: the events file, one statement file per MID and the answer-key file. A file with no rows is 0 bytes.
2. Expected empty file: `mid_kzt_01` on `RECON_WORLD_START` (see "Arrival guarantees the generator must keep").
3. The loader reads exact file names (the MID list comes from `mids.csv`), never a glob, so a leftover `.tmp` file is never loaded.
4. A missing expected file is an error, not an empty day. Treating it as empty would delete a real partition. The loader rules, including the partition delete for a table with no rows, are in `docs/specs/bigquery_sandbox_and_costs.md`.

---

## Raw tables

### Rules shared by all three tables

| Rule | Value |
|---|---|
| Datasets | `raw` (written by the DAG) and `raw_dev` (written by the host CLI), both in location US |
| Partitioning | DAY on `_arrival_date` (DATE). One run owns one partition per table |
| Partition expiry | the sandbox default (60 days) stays. Never set a table expiration on these tables: it would override the partition expiry |
| Clustering | `mid` for the two synthetic tables, `provider` for `fx_rates` |
| Wall-clock columns | none: no `_loaded_at`, no job ids. `fetched_at` is frozen in the meta file. A reload therefore writes identical rows, and the fingerprint proof needs no exclusions |
| Created by | `recon.load.ensure_tables` from the schema JSON, with `exists_ok=True` |
| Written by | one WRITE_TRUNCATE load job per (table, R) into `<table>$YYYYMMDD`, or a partition delete when there are no rows. Never INSERT, UPDATE, DELETE, MERGE or streaming |

### `raw.payment_events`

- **Grain:** one row per webhook delivery that arrived on `_arrival_date`.
- **Key:** `delivery_id` (unique across the table). `event_id` repeats on redeliveries.
- **Description:** `SYNTHETIC: generated by src/recon/generator.py. One row per webhook delivery that arrived on _arrival_date (UTC).`
- **Label:** `data_origin = synthetic`.
- **Design size:** about 210 rows per partition.

| Column | Type | Mode | Meaning | Example |
|---|---|---|---|---|
| `delivery_id` | STRING | REQUIRED | one delivery attempt: `dlv_<event_id>_<attempt>` | `dlv_evt_pay_20261020_kzt_00042_cap_1` |
| `event_id` | STRING | REQUIRED | the webhook event; the same on every redelivery; the dedup key | `evt_pay_20261020_kzt_00042_cap` |
| `event_type` | STRING | REQUIRED | `payment.captured`, the only type in v1.0 | `payment.captured` |
| `payment_id` | STRING | REQUIRED | the PSP payment reference shared with the statement | `pay_20261020_kzt_00042` |
| `order_id` | STRING | REQUIRED | our order id; unused for matching in v1.0 | `ord_20261020_kzt_00042` |
| `mid` | STRING | REQUIRED | merchant account | `mid_kzt_01` |
| `plan_id` | STRING | REQUIRED | `p1w`, `p4w` or `p12w` | `p4w` |
| `amount_minor` | INT64 | REQUIRED | captured amount in minor units, never FLOAT64 | `999000` |
| `currency` | STRING | REQUIRED | ISO 4217, equal to the MID currency | `KZT` |
| `event_ts` | TIMESTAMP | REQUIRED | capture time, UTC, whole seconds | `2026-10-20 20:15:07+00:00` |
| `delivered_ts` | TIMESTAMP | REQUIRED | when our backend received this delivery; `DATE(delivered_ts) = _arrival_date` | `2026-10-20 20:15:30+00:00` |
| `is_synthetic` | BOOL | REQUIRED | always true | `true` |
| `_arrival_date` | DATE | REQUIRED | partition column: the UTC day this delivery arrived | `2026-10-20` |
| `_source_file` | STRING | REQUIRED | landing path relative to the landing folder | `payment_events/arrival_date=2026-10-20/part-000.ndjson` |

### `raw.settlement_lines`

- **Grain:** one row per line of a per-MID statement file that arrived on `_arrival_date`.
- **Key:** `line_id` (unique across the table in v1.0: one line per settled payment).
- **Description:** `SYNTHETIC: generated by src/recon/generator.py. One row per line of a per-MID statement file that arrived on _arrival_date (UTC).`
- **Label:** `data_origin = synthetic`.
- **Design size:** about 200 rows per partition; about 40 on `RECON_WORLD_START` (USD only).
- **Layout source:** modelled on the public Adyen settlement-details and Stripe payout-reconciliation docs (mapping under "Labels and licences").

| Column | Type | Mode | Meaning | Example |
|---|---|---|---|---|
| `statement_id` | STRING | REQUIRED | one statement file: `stmt_<mid>_<yyyymmdd of arrival>` | `stmt_mid_kzt_01_20261022` |
| `line_id` | STRING | REQUIRED | `ln_<payment_id>` | `ln_pay_20261020_kzt_00042` |
| `mid` | STRING | REQUIRED | merchant account | `mid_kzt_01` |
| `record_type` | STRING | REQUIRED | `SALE`, the only type in v1.0 | `SALE` |
| `payment_id` | STRING | REQUIRED | the PSP payment reference; the matching key | `pay_20261020_kzt_00042` |
| `captured_ts` | TIMESTAMP | REQUIRED | the PSP's capture time, UTC (Adyen "Creation Date") | `2026-10-20 20:15:07+00:00` |
| `accounting_date` | DATE | REQUIRED | the PSP's day for the sale | `2026-10-21` |
| `gross_minor` | INT64 | REQUIRED | settled gross in minor units | `999000` |
| `fee_minor` | INT64 | REQUIRED | fee the PSP charged, in minor units | `25095` |
| `net_minor` | INT64 | REQUIRED | `gross_minor - fee_minor` (a dbt test) | `973905` |
| `currency` | STRING | REQUIRED | settlement currency, equal to the MID currency in v1.0 | `KZT` |
| `is_synthetic` | BOOL | REQUIRED | always true | `true` |
| `_arrival_date` | DATE | REQUIRED | partition column: the UTC day the file arrived (accounting date + lag) | `2026-10-22` |
| `_source_file` | STRING | REQUIRED | landing path relative to the landing folder | `settlement_lines/arrival_date=2026-10-22/mid=mid_kzt_01.ndjson` |

### `raw.fx_rates`

- **Grain:** one row per rate observation returned by the fetch made for `_arrival_date`. A rate date appears in up to 9 fetch partitions: 7 from the R-6..R window, plus 2 when a weekend R-6 pulls in the previous weekday's row (one more around a holiday).
- **Key:** (`provider`, `base`, `quote`, `rate_date`, `_arrival_date`).
- **Description:** `REAL: NBK rates via Frankfurter v2. One row per rate observation returned by the fetch made for _arrival_date.`
- **Label:** `data_origin = real`.
- **Design size:** 5 or 6 rows per partition (the weekdays in R-6..R, plus one earlier row when R-6 has no rate).

| Column | Type | Mode | Meaning | Example (illustrative) |
|---|---|---|---|---|
| `provider` | STRING | REQUIRED | `nbk`, taken from the request (the response rows do not carry it) | `nbk` |
| `base` | STRING | REQUIRED | `USD`: NBK publishes KZT per 1 USD | `USD` |
| `quote` | STRING | REQUIRED | `KZT` | `KZT` |
| `rate_date` | DATE | REQUIRED | the date in the API row; on weekends earlier than `requested_to` | `2026-10-23` |
| `rate_text` | STRING | REQUIRED | the rate exactly as Frankfurter returned it (the response body's digits; see "From the landed file to raw rows"); cast to NUMERIC only in dbt | `447.94` |
| `requested_from` | DATE | REQUIRED | first day of the request: R-6 | `2026-10-19` |
| `requested_to` | DATE | REQUIRED | last day of the request: R | `2026-10-25` |
| `fetched_at` | TIMESTAMP | REQUIRED | when the fetch ran, UTC, frozen in the meta file | `2026-11-01 17:42:05+00:00` |
| `_arrival_date` | DATE | REQUIRED | partition column: the run date R whose fetch returned the row | `2026-10-25` |
| `_source_file` | STRING | REQUIRED | landed body path relative to the landing folder | `fx/provider=nbk/arrival_date=2026-10-25.json` |

### Schema JSON files

One JSON file per table drives three things: the table creation in `ensure_tables`, `LoadJobConfig.schema`, and a pytest that checks every emitted row. Each file is one object: table options plus a standard BigQuery `fields` list. JSON has no comments, so the files hold data only.

How the code uses a file:
1. Build the schema: `[SchemaField.from_api_repr(f) for f in doc["fields"]]`. (Do not call `client.schema_from_json` on the whole file: it expects a bare list.)
2. Create: a `Table` with that schema, `TimePartitioning(type_="DAY", field=doc["time_partitioning"]["field"])`, `clustering_fields`, `description` and `labels`, then `create_table(table, exists_ok=True)`.
3. Load: `LoadJobConfig(schema=<the same list>)`.
4. Test: every emitted row has exactly these names, every REQUIRED value is present, and every type matches.

Type names are the GoogleSQL names `INT64` and `BOOL`. When you read a live table's schema back, BigQuery may report them as `INTEGER` and `BOOLEAN`, so a test that compares against a live table maps those names first.

`src/recon/schemas/payment_events.json`:

```json
{
  "table": "payment_events",
  "description": "SYNTHETIC: generated by src/recon/generator.py. One row per webhook delivery that arrived on _arrival_date (UTC).",
  "labels": {"data_origin": "synthetic"},
  "time_partitioning": {"type": "DAY", "field": "_arrival_date"},
  "clustering_fields": ["mid"],
  "fields": [
    {"name": "delivery_id", "type": "STRING", "mode": "REQUIRED", "description": "One delivery attempt: dlv_<event_id>_<attempt>. Unique per row."},
    {"name": "event_id", "type": "STRING", "mode": "REQUIRED", "description": "The webhook event: evt_<payment_id>_cap. The same on every redelivery. The dedup key."},
    {"name": "event_type", "type": "STRING", "mode": "REQUIRED", "description": "payment.captured, the only type in v1.0."},
    {"name": "payment_id", "type": "STRING", "mode": "REQUIRED", "description": "PSP payment reference shared with the statement: pay_<yyyymmdd>_<tag>_<nnnnn>."},
    {"name": "order_id", "type": "STRING", "mode": "REQUIRED", "description": "Our order id: ord_<yyyymmdd>_<tag>_<nnnnn>. Not used for matching in v1.0."},
    {"name": "mid", "type": "STRING", "mode": "REQUIRED", "description": "Merchant account id from dbt/seeds/mids.csv."},
    {"name": "plan_id", "type": "STRING", "mode": "REQUIRED", "description": "p1w, p4w or p12w."},
    {"name": "amount_minor", "type": "INT64", "mode": "REQUIRED", "description": "Captured amount in minor units of currency. Never a float."},
    {"name": "currency", "type": "STRING", "mode": "REQUIRED", "description": "ISO 4217 code, equal to the MID currency."},
    {"name": "event_ts", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Capture time, UTC, whole seconds."},
    {"name": "delivered_ts", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "When our backend received this delivery, UTC, whole seconds. DATE(delivered_ts) = _arrival_date."},
    {"name": "is_synthetic", "type": "BOOL", "mode": "REQUIRED", "description": "Always true."},
    {"name": "_arrival_date", "type": "DATE", "mode": "REQUIRED", "description": "Partition column: the UTC day this delivery arrived. One run owns one arrival date."},
    {"name": "_source_file", "type": "STRING", "mode": "REQUIRED", "description": "Landing file path, relative to the landing folder."}
  ]
}
```

`src/recon/schemas/settlement_lines.json`:

```json
{
  "table": "settlement_lines",
  "description": "SYNTHETIC: generated by src/recon/generator.py. One row per line of a per-MID statement file that arrived on _arrival_date (UTC).",
  "labels": {"data_origin": "synthetic"},
  "time_partitioning": {"type": "DAY", "field": "_arrival_date"},
  "clustering_fields": ["mid"],
  "fields": [
    {"name": "statement_id", "type": "STRING", "mode": "REQUIRED", "description": "One statement file: stmt_<mid>_<yyyymmdd of arrival>."},
    {"name": "line_id", "type": "STRING", "mode": "REQUIRED", "description": "ln_<payment_id>. One line per settled payment in v1.0."},
    {"name": "mid", "type": "STRING", "mode": "REQUIRED", "description": "Merchant account id from dbt/seeds/mids.csv."},
    {"name": "record_type", "type": "STRING", "mode": "REQUIRED", "description": "SALE, the only type in v1.0."},
    {"name": "payment_id", "type": "STRING", "mode": "REQUIRED", "description": "PSP payment reference. The matching key."},
    {"name": "captured_ts", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "The PSP's capture time, UTC, whole seconds (Adyen: Creation Date)."},
    {"name": "accounting_date", "type": "DATE", "mode": "REQUIRED", "description": "The PSP's day for the sale: the capture time shifted by the MID's fixed UTC offset."},
    {"name": "gross_minor", "type": "INT64", "mode": "REQUIRED", "description": "Settled gross amount in minor units."},
    {"name": "fee_minor", "type": "INT64", "mode": "REQUIRED", "description": "Fee charged by the PSP, in minor units."},
    {"name": "net_minor", "type": "INT64", "mode": "REQUIRED", "description": "gross_minor minus fee_minor."},
    {"name": "currency", "type": "STRING", "mode": "REQUIRED", "description": "Settlement currency, equal to the MID currency in v1.0."},
    {"name": "is_synthetic", "type": "BOOL", "mode": "REQUIRED", "description": "Always true."},
    {"name": "_arrival_date", "type": "DATE", "mode": "REQUIRED", "description": "Partition column: the UTC day the statement file arrived (accounting_date plus the lag)."},
    {"name": "_source_file", "type": "STRING", "mode": "REQUIRED", "description": "Landing file path, relative to the landing folder."}
  ]
}
```

`src/recon/schemas/fx_rates.json`:

```json
{
  "table": "fx_rates",
  "description": "REAL: NBK rates via Frankfurter v2. One row per rate observation returned by the fetch made for _arrival_date.",
  "labels": {"data_origin": "real"},
  "time_partitioning": {"type": "DAY", "field": "_arrival_date"},
  "clustering_fields": ["provider"],
  "fields": [
    {"name": "provider", "type": "STRING", "mode": "REQUIRED", "description": "nbk. Taken from the request: the response rows do not carry it."},
    {"name": "base", "type": "STRING", "mode": "REQUIRED", "description": "USD. NBK publishes KZT per 1 USD."},
    {"name": "quote", "type": "STRING", "mode": "REQUIRED", "description": "KZT."},
    {"name": "rate_date", "type": "DATE", "mode": "REQUIRED", "description": "Date in the API row. Weekdays only for this provider, so earlier than requested_to on weekends."},
    {"name": "rate_text", "type": "STRING", "mode": "REQUIRED", "description": "NBK rate, digits exactly as Frankfurter returned them, for example 453.71. Cast to NUMERIC only in dbt."},
    {"name": "requested_from", "type": "DATE", "mode": "REQUIRED", "description": "First day of the request window: _arrival_date minus 6 days."},
    {"name": "requested_to", "type": "DATE", "mode": "REQUIRED", "description": "Last day of the request window: _arrival_date."},
    {"name": "fetched_at", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "When the fetch ran, UTC. Frozen in the meta file, so reloads do not change it."},
    {"name": "_arrival_date", "type": "DATE", "mode": "REQUIRED", "description": "Partition column: the run date R whose fetch returned this row."},
    {"name": "_source_file", "type": "STRING", "mode": "REQUIRED", "description": "Landed body path, relative to the landing folder."}
  ]
}
```

Column names that start with an underscore are allowed in BigQuery. `_arrival_date` and `_source_file` avoid the reserved prefixes (`_TABLE_`, `_FILE_`, `_PARTITION` and the others in the BigQuery schema docs).

---

## Defect catalog

**This is the pre-registered catalog.** It is committed in M0, before any matcher SQL exists. The commit order is part of the evidence: it shows the matcher was written to meet the catalog, not the catalog written to fit the matcher's output. After that first commit, the catalog changes only through the table under "Catalog changes after the first commit".

Planted classes (D) are discrepancies the matcher should find. Benign classes (B) are normal behaviour that must not become exceptions, except where B3's noise is designed to cross the fee tolerance. All rates are design values, labelled synthetic.

### Summary

| Id | Class | Kind | Applies to | Design rate | Raw rows it touches | Expected outcome |
|---|---|---|---|---|---|---|
| D1 | `webhook_redelivery` | planted feed defect | capture events (never D3) | 4% of events; 1 extra copy 75%, 2 copies 25% | 1 or 2 extra `raw.payment_events` rows, often in the next day's partition | removed by dedup; `copies_received` is 2 or 3; no exception |
| D2 | `missing_in_statement` | planted break | payments | 0.5% | no `raw.settlement_lines` row, ever | `in_transit` until `due_date`, then exception `missing_in_statement` |
| D3 | `missing_in_ledger` | planted break | payments | 0.4% | no `raw.payment_events` rows; the statement line exists | exception `missing_in_ledger` |
| D4 | `amount_mismatch` | planted break | payments | 0.4% | the line's `gross_minor`, `fee_minor`, `net_minor` | exception `amount_mismatch`; on combo lines also `fee_mismatch` |
| D5 | `fee_overcharge` | planted break | settled lines | 1.0% of settled lines, plus 25% of D4 lines | the line's `fee_minor`, `net_minor` | exception `fee_mismatch` when the overcharge exceeds the tolerance; at or below it, a miss by design |
| B1 | `cutoff_shift` | benign | every payment, by capture time | about 36% of USD and 7.5% of KZT captures (design consequence) | `accounting_date` differs from the booking date | `matched` with `date_shift = timing_cutoff`; no exception |
| B2 | `settlement_lag` | benign | every settled line | T+1 90%, T+2 10% | the line's `_arrival_date` | `in_transit` while waiting, then `matched` |
| B3 | `fee_noise` | benign, designed to cross the tolerance sometimes | every settled line without D5 | inside 99%, spike 1% | the line's `fee_minor`, `net_minor` | inside: never flagged. Spike above the tolerance: a `fee_mismatch` flag, which the self-test counts as a false alarm |

"Expected outcome" names the statuses and reason codes defined in `dbt/seeds/reason_codes.csv`. The rules that produce them (`match_status`, `date_shift`, `is_amount_mismatch`, `is_fee_mismatch`, `primary_reason`) are in `docs/specs/dbt_project.md` under `fct_recon_lines`.

### D1 `webhook_redelivery`

- **What happens:** the PSP sends the same event again. At-least-once delivery is normal for webhooks.
- **Mechanism:** stream `redelivery`. First draw below 400 bp makes the event D1. Second draw: 1 copy below 7500 bp, else 2. Then one delay per copy in 60..21600 s, sorted, added to the first delivery's time. Attempts 2 and 3 follow time order.
- **Rows touched:** extra `raw.payment_events` rows with the same `event_id` and payload, a new `delivery_id` and a later `delivered_ts`. Each copy lands in the partition of `DATE(delivered_ts)`, so many land on booking date + 1. This is the defect that crosses midnight.
- **Expected outcome:** `stg_psp__payment_events` keeps the earliest delivery (`ORDER BY delivered_ts, delivery_id`) and counts `copies_received`. `assert_redeliveries_identical` passes because every copy has the same payload. No exception. The "duplicate delivery rate" metric counts the removed copies.
- **Answer key:** `planted` contains `D1`; `extra_copies` is 1 or 2.
- **Never with:** D3 (there are no deliveries to copy).

### D2 `missing_in_statement`

- **What happens:** the PSP never settles a captured payment.
- **Mechanism:** stream `money`, draw below 50 bp.
- **Rows touched:** deliveries exist as normal (D1 is possible). No statement line is written in any file.
- **Expected outcome:** a ledger-only line. While `as_of_date < due_date` its status is `in_transit`. From the due date on (inclusive) it is `missing_in_statement`, with exception amount `+L` (the ledger amount) on the booking date.
- **Answer key:** `planted` contains `D2`; `statement_arrival_date` is null; `fee_noise` is `none`; `fee_variance_minor` is null.

### D3 `missing_in_ledger`

- **What happens:** every webhook delivery is lost, but the PSP settles the payment.
- **Mechanism:** stream `money`, draw from 50 up to (not including) 90 bp.
- **Rows touched:** no `raw.payment_events` rows. The statement line is normal (lag from B2, fee from B3 or D5).
- **Expected outcome:** a statement-only line with status `missing_in_ledger`, exception amount `-S` (the statement gross) on the accounting date. If its capture date is before the window's `scope_start`, it is `before_scope` instead (only in partial windows). As `missing_in_ledger`, it still gets the fee check on its statement leg. If it is `before_scope`, it gets neither an exception nor a fee flag.
- **Answer key:** `planted` contains `D3`; `extra_copies` is 0.

### D4 `amount_mismatch`

- **What happens:** the settled amount differs from the booked amount, for example because of a stale ledger price or a PSP adjustment. Call it "settled amount differs". Never call it a partial capture.
- **Mechanism:** stream `money`, draw from 90 up to (not including) 130 bp. Then stream `amount_delta`: `sign = draw_int(0, 1)`, `delta_bp = draw_int(100, 2000)`, `delta = max(1, (amount_minor * delta_bp + 5000) // 10000)`. The statement gross is `amount_minor - delta` when `sign = 0` and `amount_minor + delta` when `sign = 1`. The fee and tolerance are computed on the new gross. Then stream `combo`: below 2500 bp the line also gets D5.
- **Example (contract arithmetic):** a USD 1999 payment with `delta_bp = 1000` gets `delta = 200`, so the statement shows 1799 or 2199.
- **Rows touched:** the line's `gross_minor`, `fee_minor` and `net_minor`.
- **Expected outcome:** `matched` with `is_amount_mismatch = true`, exception `amount_mismatch` with amount `L - S` on the accounting date. A combo line also has `fee_mismatch` when its overcharge exceeds the tolerance: two exception rows for one line, and `primary_reason = amount_mismatch`.
- **Answer key:** `planted` contains `D4`, plus `D5` on combo lines.

### D5 `fee_overcharge`

- **What happens:** the PSP charges more than the contract allows.
- **Mechanism:** stream `fee_defect`. The first draw (made for every line with a statement leg) below 100 bp makes the line D5; a D4 line also becomes D5 through `combo`. For every D5 line, the overcharge is the second `fee_defect` draw: an integer in `[ceil(0.8 * tol), 10 * tol]`, so `[(4 * tol + 4) // 5, 10 * tol]`. The fee is `expected + overcharge`. A D5 line gets no B3 noise.
- **Example (contract arithmetic):** a USD line has `tol = 5`, so the overcharge is 4..50. The values 4 and 5 are at or below the tolerance.
- **Rows touched:** the line's `fee_minor` and `net_minor`.
- **Expected outcome:** if `overcharge > tol`, `is_fee_mismatch = true` and an exception `fee_mismatch` with amount `fee_variance_minor` on the accounting date. If `overcharge <= tol`, no flag: a miss by design (a small share of D5 lines, roughly 2% to 4% by the ranges).
- **Answer key:** `planted` contains `D5`; `fee_noise` is `none`; `fee_variance_minor` equals the overcharge.

### B1 `cutoff_shift`

- **What happens:** the acquirer's day ends at its local midnight, so the PSP books some sales on a different date than our UTC booking date. It happens in both directions: USD sales from 00:00 to 04:59 UTC move back one day, KZT sales from 19:00 to 23:59 UTC move forward one day.
- **Mechanism:** structural, no random draw: `accounting_date = DATE(event_ts + offset hours)`.
- **Rows touched:** `raw.settlement_lines.accounting_date`.
- **Expected outcome:** `matched` with `date_shift = timing_cutoff`; no exception. In the daily bridge the line adds `+L` on the booking date and `-L` on the accounting date, so timing nets to zero across the two days.
- **Answer key:** `timing_shift` is -1 or +1 (0 when there is no shift).

### B2 `settlement_lag`

- **What happens:** statement lines arrive one or two days after their accounting date.
- **Mechanism:** stream `lag`: 1 day below 9000 bp, else 2.
- **Rows touched:** which partition (`_arrival_date`) the line lands in.
- **Expected outcome:** `in_transit` while waiting, then `matched` (or `matched` with `timing_cutoff`). Never `missing_in_statement`, because every lag is at most `max_settlement_lag_days`, which is before the due date.
- **Answer key:** `statement_arrival_date`. The lag is `statement_arrival_date - (booking_date + timing_shift)`.

### B3 `fee_noise`

- **What happens:** real per-line fees vary a little around the contract (card type, rounding). Most variation is small; a few lines vary more.
- **Mechanism:** stream `fee_noise`, only for lines with a statement leg and without D5. First draw below 100 bp makes a spike: `sign = draw_int(0, 1)`, `magnitude = draw_int(tol, ceil(1.5 * tol))`, `v = -magnitude` when `sign = 0`, `+magnitude` when `sign = 1`. Otherwise inside noise: `v = draw_int(-(tol // 2), tol // 2)`. The fee is `expected + v`.
- **Example (contract arithmetic):** a USD line (`tol = 5`) gets inside noise -2..+2 or a spike of magnitude 5..8. A spike of exactly 5 is within the tolerance; 6, 7 and 8 are flagged.
- **Rows touched:** the line's `fee_minor` and `net_minor`.
- **Expected outcome:** inside noise is never flagged (it is at most half the tolerance). A spike equal to the tolerance is within (the boundary is inclusive). A spike above the tolerance gets a `fee_mismatch` flag, which the seeded self-test counts as a false alarm.
- **Answer key:** `fee_noise` is `inside` or `spike`; `fee_variance_minor` equals `v`.
- **Why the generator knows the tolerance:** it computes it from the same contract terms in `mids.csv`. That is what lets benign noise cross the tolerance on purpose, so false alarms are possible and the self-test is not perfect by construction. dbt computes the same tolerance on its own from the same seed file.

### How the classes combine

1. At most one of D2, D3 and D4 per payment: one `money` draw decides.
2. D1 needs deliveries, so it never sits on D3. It can sit on D2, D4, D5 and every B class.
3. D4, D5, B2 and B3 need a statement line, so none of them sits on D2.
4. D5 and B3 never sit on the same line: a D5 line has no noise.
5. B1 depends only on the capture time, so it can sit on top of any class.
6. Lines that produce two exception rows (one per cause, as `fct_recon_exceptions` expects):
   - D4 with D5 above the tolerance: `amount_mismatch` and `fee_mismatch`;
   - D3 with D5 above the tolerance: `missing_in_ledger` and `fee_mismatch`;
   - D3 or D4 with a B3 spike above the tolerance: the planted cause plus a false `fee_mismatch`.

### Causes that are never planted, and what to expect from them

| Cause | Planted by | Expected in a full window from `RECON_WORLD_START` (design, not a result) |
|---|---|---|
| `date_mismatch` | nothing | 0. Any row is a false alarm or a bug |
| `before_scope` | nothing | 0. It appears only when a window starts later than `RECON_WORLD_START`: dev subsets, or after the 60-day expiry |
| `missing_in_ledger` | D3 only | only D3 lines (guarantee 4) |
| `missing_in_statement` | D2 only | only D2 lines past their due date (guarantee 5) |

### Design counts (not results)

Expected values over the 29-day proof window (about 5,800 payments), computed from the rates. The seed decides the real counts, and only the seeded self-test in U1 reports them.

| Class | Expected count |
|---|---|
| D1 | about 230 events with copies, about 290 extra deliveries |
| D2 | about 29 |
| D3 | about 23 |
| D4 | about 23, of which about 6 also D5 |
| D5 | about 58 from the 1% draw, plus the D4 combos |
| B3 spikes | about 57, most of them above the tolerance |
| B1 | about 36% of USD and 7.5% of KZT captures |

So both false alarms (B3 spikes) and misses (D5 at or below the tolerance) are expected by design.

### Held for later

These are never built into v1.0. They become the "defects the matcher was not designed for" in U4, generated only after tag `v1.3`. Each will get its own new stream purpose, so existing rows stay identical. H1 to H4 are switched on only in the held-out world (see "Held-out world (U4)").

| Id | Class | What it will do | Built in |
|---|---|---|---|
| H1 | `duplicate_statement_line` | the PSP repeats a line in a later file. It should fail the `line_id` grain test loudly | U4 |
| H2 | `undeclared_deduction` | net below gross minus fee. It should fail the statement arithmetic test | U4 |
| H3 | `late_settlement_t3` | a line arrives beyond the contract lag. Expected behaviour is decided in U4 | U4 |
| H4 | `redelivery_payload_changed` | a redelivery with a different amount. It should fail `assert_redeliveries_identical` | U4 |
| D6 | `late_batch` | one MID-day statement file arrives 3 days late (generator 1.1.0, which also raises `lookback_days` to at least 6; see below) | U6 |

**Arrival bounds for these classes.** In v1.0 every arrival lies in [booking date, booking date + 3] (arrival guarantee 3), and `lookback_days = 5` lets run R see payments booked from R-5 on. Two later classes stretch that:
- **D6:** a late KZT line can arrive at booking date + 6 (+1 cut-off, +2 lag, +3 late). Run R = booking date + 6 recomputes only booking days R-5..R, so it would silently never emit that line. Generator 1.1.0 therefore raises `lookback_days` to at least 6 and extends `test_lookback_is_enough` to [booking date, booking date + 6] with 6 <= `lookback_days`. Raising the lookback alone changes no v1.0 file: in v1.0 a payment booked on R-6 has no arrival on R.
- **H3:** a KZT line settled at T+3 can arrive at booking date + 4 (+1 cut-off, +3 lag). That is still inside `lookback_days = 5`, but outside the [booking date, booking date + 3] bound. With H3 switched on, arrival guarantee 3 and `test_lookback_is_enough` must allow booking date + 4.

### Catalog changes after the first commit

Every change after the M0 commit gets a row here, with the commit that made it.

| Date | Change | Reason | Commit |
|---|---|---|---|
| (none yet) | | | |

---

## Ground truth (answer key)

### File and fields

`landing/_truth/booking_date=YYYY-MM-DD.ndjson`: one row per payment booked that day, written by `emit` in the run whose run date equals that booking date. Same format rules as the other synthetic files.

| Field | JSON type | Null allowed | Meaning | Example |
|---|---|---|---|---|
| `payment_id` | string | no | the payment | `pay_20261020_kzt_00042` |
| `mid` | string | no | merchant account | `mid_kzt_01` |
| `booking_date` | string (date) | no | UTC date of the capture | `2026-10-20` |
| `planted` | array of strings | no (may be empty) | planted classes, sorted; a subset of `D1`..`D5` | `["D1"]` |
| `extra_copies` | integer | no | redelivered copies: 0, 1 or 2 | `1` |
| `timing_shift` | integer | no | accounting date minus booking date: -1, 0 or 1 | `1` |
| `fee_noise` | string | no | `none`, `inside` or `spike`. `none` when there is no statement line (D2) or the line is D5 | `inside` |
| `fee_variance_minor` | integer | yes | statement fee minus expected fee; null when there is no statement line | `120` |
| `statement_arrival_date` | string (date) | yes | when the line arrives; null for D2 | `2026-10-22` |
| `due_date` | string (date) | no | accounting date + `max_settlement_lag_days` + `statement_grace_days`, for every payment | `2026-10-24` |
| `generator_version` | string | no | from `world.toml` | `1.0.0` |

A row records the generator's intent, not what the matcher should output. A D5 overcharge inside the tolerance still says `"planted": ["D5"]`.

### Isolation

1. The answer key is never loaded into BigQuery. The loader's table list is exactly `payment_events`, `settlement_lines` and `fx_rates`.
2. `landing/_truth/` is gitignored.
3. No dbt source points at it.
4. Only `scripts/eval.py` (U1) reads it. If the files are absent, it regenerates them in memory from `(seed, world_start)`.
5. U2's CI asserts that the loader's list excludes the answer key and that no dbt source points at it.

### Scoring rules (U1, `scripts/eval.py`)

The name is **"seeded self-test (synthetic)"**. Never "accuracy", "precision", "recall" or "detection rate" as a headline.

1. Read `as_of_date` from the marts.
2. Keep lines that are not `before_scope`.
3. A line is final when its statement line has arrived (`statement_arrival_date <= as_of_date`) or when `as_of_date >= due_date`. Score only final lines.
4. For each cause `c` in `missing_in_statement`, `missing_in_ledger`, `amount_mismatch`, `fee_mismatch`, count:
   - planted: lines whose answer key plants the matching class (D2, D3, D4, D5 respectively);
   - flagged: lines with an exception row with cause `c`;
   - TP (planted and flagged), FP (flagged, not planted), FN (planted, not flagged).
5. B3 spikes flagged as `fee_mismatch` are FP. D5 overcharges within the tolerance are FN. Any `date_mismatch` row is FP, because none is planted.
6. D1: compare `SUM(extra_copies)` with `SUM(copies_received - 1)` from staging, over payments booked from `scope_start` to `as_of_date - 1`. Every redelivery arrives by booking date + 1, so all copies of those payments have arrived.
7. Ledger-only lines that are not final must be `in_transit`; count violations.
8. Output raw counts per cause and the number of benign final lines to `docs/evidence/<date>/eval.json`. Until it runs, the README shows no row for it, and drafts use placeholders: [TP], [FP], [FN].

---

## FX data

### Source and request

| Item | Rule |
|---|---|
| Service | Frankfurter v2, no key: `https://api.frankfurter.dev/v2/rates` |
| Request | `https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT&from=<R-6>&to=<R>` |
| Parameter order | exactly as written, so the URL in the meta file is the same text every time |
| Provider | `providers=nbk` pins one official source. Never use blended rates (no `providers`): they mix observation dates and can be restated |
| Base and quotes | always pass both. During planning, a call without `base` returned EUR crosses |
| Window | R-6..R. Seven calendar days always contain weekdays, so the answer is never empty. When `from` has no published rate (R is a Friday or a Saturday, or R-6 is a holiday), the answer also starts with the last published row before it, dated outside the requested range |
| Never | a date on or after today (UTC). `check_window` guarantees `R < today` |
| Headers | `User-Agent: ledger-vs-statement (learning project)`; timeout 10 s |
| Retries | handled by the Airflow task: 3 retries, 30 s delay, `retry_exponential_backoff=2.0`, `max_retry_delay` 10 minutes (`docs/specs/airflow_and_docker.md`) |
| Volume | one request per run date, never repeated once landed. Frankfurter states there are no quotas (only abuse rate limits) and encourages storing observations locally |

### Response format

A flat JSON array of objects with the keys `date`, `base`, `quote` and `rate`. Rows exist for weekdays only. Rows carry no provider field.

| Key | JSON type | Meaning | Example |
|---|---|---|---|
| `date` | string | the rate date, `YYYY-MM-DD` | `2026-10-23` |
| `base` | string | `USD` | `USD` |
| `quote` | string | `KZT` | `KZT` |
| `rate` | number | KZT per 1 USD, as published | `447.94` |

Example body for R = 2026-10-25 (a Sunday; `from=2026-10-19&to=2026-10-25`). Values come from a call made while planning and are shown for the format only. Your landed file is the record; never copy values from this document.

```json
[{"date":"2026-10-19","base":"USD","quote":"KZT","rate":452.12},{"date":"2026-10-20","base":"USD","quote":"KZT","rate":452.59},{"date":"2026-10-21","base":"USD","quote":"KZT","rate":450.69},{"date":"2026-10-22","base":"USD","quote":"KZT","rate":448.61},{"date":"2026-10-23","base":"USD","quote":"KZT","rate":447.94}]
```

### Landing (immutable)

`recon.fx.fetch_nbk(R, landing_dir)`:
1. If `fx/provider=nbk/arrival_date=R.json` exists and its meta file exists, return `{"action": "skipped"}`. It never fetches again. If only one of the two files exists, fail loudly: delete the stray file by hand, then fetch.
2. Check `R < today (UTC)`.
3. Send the request.
4. Check before landing anything:
   1. the HTTP status is 200;
   2. `json.loads(body, parse_float=str)` gives a non-empty list;
   3. every element has `date`, `base`, `quote` and `rate`, with `base = "USD"`, `quote = "KZT"`, `date <= R` and dates strictly increasing. Only the first element may be dated before R-6: when R-6 has no published rate (R is a Friday or a Saturday, or R-6 is a holiday), Frankfurter adds the last published row before it (seen live: `from=2026-10-25&to=2026-10-31` starts with 2026-10-23). Keep that row and load it like the others. A second element before R-6 fails the check.
   If a check fails, land nothing and raise. The task retries, then fails, and the failure goes into `docs/failure_log.md`.
5. Write the body, byte for byte as received, to `fx/provider=nbk/arrival_date=R.json.tmp`.
6. Write the meta file to `fx/provider=nbk/arrival_date=R.meta.json.tmp`.
7. Rename the meta file first, then the body. The body's final name is the "landed" signal.
8. Return `{"action": "fetched", "rows": <n>}`.

The meta file is one JSON object, written with the same `json.dumps` settings and a trailing newline:

| Key | JSON type | Meaning | Example |
|---|---|---|---|
| `fetched_at` | string (timestamp) | UTC time of the fetch, whole seconds, same format as all timestamps | `2026-11-01 17:42:05+00:00` |
| `http_status` | integer | status of the response | `200` |
| `sha256` | string | hex SHA-256 of the body bytes | 64 hex characters |
| `url` | string | the exact request URL | `https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT&from=2026-10-19&to=2026-10-25` |

```json
{"fetched_at":"2026-11-01 17:42:05+00:00","http_status":200,"sha256":"<64 hex characters: sha256 of the body bytes>","url":"https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT&from=2026-10-19&to=2026-10-25"}
```

`fetched_at` is the real time of the fetch, recorded once and frozen. A backfilled day shows a fetch long after `R`. That is honest: it is when the project learned those rates.

The folder `landing/fx/` is committed, so a fresh clone rebuilds the window with the same rates. Fallback (cut-order item 6): run the same fetch from the host CLI and commit the files. FX stays real, and the paths and format are unchanged, so nothing downstream changes.

### From the landed file to raw rows

Before building rows, the loader checks that the SHA-256 of the body equals `sha256` in the meta file. A changed or hand-edited file fails loudly. Then each element of the body becomes one row:

| Column | Value |
|---|---|
| `provider` | `nbk` (from the folder name `provider=nbk`) |
| `base` | the element's `base` |
| `quote` | the element's `quote` |
| `rate_date` | the element's `date` |
| `rate_text` | the element's `rate` after `parse_float=str`: the digits exactly as they appear in the response body. These are Frankfurter's digits, not NBK's own text. A JSON number may drop trailing zeros, so NBK's `457.10` can arrive as `457.1` (no rate ended in 0 while planning, so this was not seen). A whole number without a decimal point parses as `int`, and `str()` gives the same digits |
| `requested_from` | R - 6 |
| `requested_to` | R |
| `fetched_at` | the meta file's `fetched_at` |
| `_arrival_date` | R |
| `_source_file` | `fx/provider=nbk/arrival_date=R.json` |

**Compare rates as numbers, never as text.** `457.1` and `457.10` are the same rate. Use NUMERIC in dbt and `decimal.Decimal` in Python, as the NBK RSS cross-check does. `warn_fx_restated` compares `rate_text` between fetches, so a change in formatting alone would also show up there. Read its values as numbers before you call it a restatement.

**Why the partition is the fetch date, not the rate date.** One fetch returns several rate dates. Partitioning by `rate_date` would make one run write into up to seven partitions, which breaks "one run owns one partition". With `_arrival_date = R`, a rate date simply appears in up to nine partitions (seven, plus two when a weekend R-6 pulls in the previous weekday's row), and `stg_fx__rates` keeps the first-seen value per (provider, base, quote, rate_date); `warn_fx_restated` reports any rate date whose text differs between fetches (both in `docs/specs/dbt_project.md`). It also means old rate dates never meet the 60-day expiry: the partition date is `R`, which the 45-day guard keeps recent.

### Weekend and holiday policy

1. Frankfurter's NBK series has weekday rows only. During planning it had no rows for 24, 25 or 31 Oct 2026.
2. NBK's own feed publishes a rate for every calendar day, weekends included. During planning it showed 451.05 for Saturday 24 Oct (Friday's row: 447.94) and 453.87 for Saturday 31 Oct and Sunday 1 Nov (Friday's row: 453.71). Research context only: your run must re-measure it.
3. **Project convention:** a day with no Frankfurter row takes the latest earlier rate (carry-forward), and the row records `rate_date` and `carry_days`. Always describe it as "a project convention, not NBK's official rate for that day".
4. Holidays: the project keeps no holiday calendar in v1.0. Equal values on consecutive weekdays (451.05 on 26 and 27 Oct during planning) are rows, not gaps. Never infer a holiday from a repeated value.
5. Staleness gate: `carry_days` above `fx_max_carry_days` (5) fails the dbt build. A normal weekend gives 2.
6. Plausibility: a rate between 300 and 700 KZT per USD, which catches unit and direction errors.
7. Where it is built: `int_fx__usd_rates_daily` in `docs/specs/dbt_project.md`.

### How rates are stored, layer by layer

| Layer | Form | Rule |
|---|---|---|
| Landed body | JSON text as received | never edited; committed |
| `raw.fx_rates.rate_text` | STRING | the response body's digits, exactly as Frankfurter returned them |
| `stg_fx__rates.rate` | NUMERIC | `CAST(rate_text AS NUMERIC)` in dbt |
| USD reporting columns | NUMERIC | the `to_usd` macro, once per MID-day, one rounding stage |

Direction everywhere: KZT per 1 USD (`base = USD`, `quote = KZT`), the way NBK publishes it. Never parse a rate with Python `float`, never store FLOAT64, never store an inverted rate. The reconciliation itself never converts currency in v1.0: both MIDs settle in their own currency.

### NBK RSS cross-check files (M9, `scripts/fx_report.py`)

| Item | Rule |
|---|---|
| URL | `https://nationalbank.kz/rss/get_rates.cfm?fdate=DD.MM.YYYY` |
| Days | one request per calendar day `d` in [`scope_start`, `as_of_date`]; skip a day whose file exists |
| Never | `d` on or after today (UTC): NBK answers a future date with its latest rate and no error |
| Landing | the body byte for byte to `landing/fx/provider=nbk_rss/rate_date=YYYY-MM-DD.xml` (committed) |
| Loaded into BigQuery | no, not in v1.0. U7 adds NBK RSS as a second provider inside dbt |

Format, from the files saved while planning: UTF-8 XML, about 14 KB per day, no DOCTYPE. The root element is `<rates>`. It holds `<generator>`, `<title>`, `<link>`, `<description>`, `<copyright>` and `<date>` (the rate date as `DD.MM.YYYY`), then one `<item>` per currency (48 in the planning files). Each item holds:

| Element | Meaning | Example (USD, planning file for 31 Oct, illustration only) |
|---|---|---|
| `fullname` | currency name in Russian | `ДОЛЛАР США` |
| `title` | ISO 4217 code | `USD` |
| `description` | the rate as text, KZT per `quant` units | `453.87` |
| `quant` | units the rate is quoted for: 1, 10, 100, 1000 or 10000 | `1` |
| `index` | `UP`, `DOWN`, or empty when unchanged | `UP` |
| `change` | signed change from the previous rate | `+0.16` |

Checks before using a file:
1. `<date>` equals `d` in `DD.MM.YYYY`.
2. The `USD` item exists and its `quant` is `1`.
3. `description` parses with `decimal.Decimal`, never `float`.
4. Python's standard XML parsers are not hardened against hostile input. Before parsing, refuse a body over 1 MB, or one that contains `<!DOCTYPE` or `<!ENTITY`.

What the report measures (N3; numbers stay placeholders until `make fx-report` runs). Over KZT days `d` in [`scope_start`, `as_of_date`]: [C] = days with no Frankfurter row dated `d`; [W] = those where the carried-forward rate differs from NBK RSS for `d`; [X] = the largest absolute difference; [Y] = X / NBK rate x 10,000 in bps, 1 decimal; [E] = days with a Frankfurter row, all of which must equal NBK RSS exactly. The script exits non-zero if a weekday disagrees: a real-data check that can fail. It writes `docs/evidence/<date>/fx_report.json`.

### Later: ECB rates (U7 and after)

- Request ECB rates in ECB's own direction: `providers=ecb&base=EUR&quotes=USD`. With `base=USD`, Frankfurter recalculates the rate and rounds it to 5 significant digits (seen while planning: 0.89509, against 1 / 1.1172 = 0.8950949).
- Store them EUR-based as published, and compute cross rates in NUMERIC.
- Land them the same way under `landing/fx/provider=ecb/`.
- ECB publishes terms of use on its site. Read them before committing ECB files.

---

## Volumes and storage estimate

Design estimates, not measurements. `scripts/storage.py` measures the real stored bytes into `docs/evidence/<date>/storage.json`.

| Item | Per day | 29-day proof window |
|---|---|---|
| Payments | about 200 (USD 117..143, KZT 63..77) | about 5,800 |
| Webhook deliveries | about 209 | about 6,070 |
| Statement lines | about 199 | about 5,770 |
| FX rows | 5 or 6 (the weekdays in R-6..R, plus one earlier row when R-6 has no rate) | about 153 |
| Answer-key rows (local only) | about 200 | about 5,800 |

Bytes per row, measured on the example rows above (a design estimate):

| Table or file | NDJSON bytes per row (landing) | BigQuery logical bytes per row |
|---|---|---|
| `payment_events` | about 480 | about 250 |
| `settlement_lines` | about 440 | about 215 |
| `fx_rates` | about 60 per element in the body | about 110 |
| answer key | about 275 | not loaded |

BigQuery's logical size rules: STRING is 2 bytes plus the UTF-8 length; INT64, DATE and TIMESTAMP are 8 bytes; BOOL is 1 byte; NUMERIC is 16 bytes.

Totals (design):
- Raw tables in BigQuery: about 0.1 MB per day, about 2.7 MB for the window.
- Synthetic landing files on disk (gitignored): about 0.24 MB per day, about 7 MB for the window.
- Committed FX files: about 0.6 KB per day for Frankfurter body plus meta; about 14 KB per day for NBK RSS XML (about 0.4 MB if every day of the window is checked).

Writes count against the sandbox's lifetime 10 GiB, and Google does not document how that is metered, so assume every byte written counts. A WRITE_TRUNCATE reload rewrites the whole partition, so each reload counts again. The raw layer stays at a few MB even with the history load, the reprocess, the out-of-order day and several dev loads. The dbt marts dominate the writes; their estimate and the 1 GiB self-cap are in `docs/specs/bigquery_sandbox_and_costs.md`.

---

## Rolling window and reruns months later

### The pinned window

| Setting | Value | Where |
|---|---|---|
| `RECON_SEED` | `20261101` | `.env` (and `.env.example`) |
| `RECON_WORLD_START` | `2026-10-04` (a Sunday) | `.env` (and `.env.example`) |
| History | 2026-10-04..2026-10-31, 28 days, loaded newest first on Sunday night | build plan |
| Proof window | 29 days: Monday's 00:00 UTC scheduled run adds 2026-11-01 | build plan |
| Write guard | `check_window` refuses `R` before `RECON_WORLD_START`, `R` older than today (UTC) minus 45 days, and `R >= today` | `dags/recon_daily.py` |
| Expiry | a partition expires 60 days after its date: the 2026-10-04 partition lives until about 2026-12-03 | BigQuery sandbox |

The seed, `world_start`, window, `as_of_date` and git SHA are written into every `docs/evidence/<date>/summary.json`. A demo window is fully described by (seed, world_start, last date).

### A rerun inside the window

Same seed and same `world_start` give byte-identical landing files, so a reload writes identical rows. The rerun proof (N1) rests on this.

### A rerun months later

The old dates are gone by then: their partitions have expired, and `check_window` refuses them anyway. So the window must move forward:
1. Choose `new_start = yesterday (UTC) - 27 days`, so the history is 28 days ending yesterday.
2. Set `RECON_WORLD_START = new_start` in `.env`. Keep `RECON_SEED`.
3. Reset the datasets: follow "Reset the datasets (moving the window)" in `docs/specs/bigquery_sandbox_and_costs.md`. It deletes `raw` and `analytics` (and the dev datasets if you used them), recreates the raw tables with `make bq-setup` and restarts the stack. It ends with the newest-first load of step 4, so run that load only once.
4. Load the history newest first ("Operations runbook" in `docs/specs/airflow_and_docker.md`). FX for the new dates is fetched once and committed. The old FX files stay in git untouched.
5. Write the new numbers into a new dated folder under `docs/evidence/`. The 2026-11-02 evidence stays as the record of the first run.

What stays the same and what changes:

| Stays the same, for each `day_index` | Changes |
|---|---|
| number of payments, plans, amounts, capture time of day | every calendar date, in every date column and every id (`pay_20270118_...` instead of `pay_20261004_...`) |
| planted classes, extra copies, lags, fees and noise | FX rates (real data for the new dates), USD reporting columns, and which days the FX carry-forward covers |
| status counts and the identity per MID-day | fingerprints, because ids and dates are different strings. N1 is re-measured, never copied |

This works because every draw is keyed by `day_index`, nothing depends on the weekday, and both cut-offs are fixed offsets. v1.x adds `make demo` to automate these steps.

---

## Held-out world (U4)

A second synthetic world for the U4 evaluation (M14 in `docs/build_plan.md`). S14.1 creates it only after tag `v1.3`, so the matcher is frozen before it meets this data. It has its own world file, seed, landing folder, datasets and answer key. Nothing in it mixes with the main world, and the main world's files and golden hash stay exactly as they are.

| Item | Main world | Held-out world |
|---|---|---|
| World file | `src/recon/world.toml` | `src/recon/world_heldout.toml`, committed in S14.1 |
| Selected by | `RECON_WORLD_FILE` not set | `RECON_WORLD_FILE=world_heldout.toml` |
| Seed | `RECON_SEED` from `.env` (`20261101`) | the `seed` key in `world_heldout.toml` (rule 3) |
| `world_start` | `RECON_WORLD_START` from `.env` | the same `RECON_WORLD_START` |
| Defects | D1 to D5 at the catalog rates, H1 to H4 off | every D1 to D5 rate doubled, H1 to H4 on |
| Landing folder | `landing/` | `landing_heldout/`: gitignored, never mounted into the containers |
| Raw dataset | `raw_dev` (host), `raw` (Airflow) | `raw_heldout` |
| dbt target and dataset | `dev` and `analytics_dev` (host); `airflow` and `analytics` (DAG) | `heldout` and `analytics_heldout` |
| Runs from | the host and Airflow | the host only |

Rules:
1. **The selector.** `config.py` reads `RECON_WORLD_FILE`, a bare file name in `src/recon/`: `Path(__file__).parent / os.environ.get("RECON_WORLD_FILE", "world.toml")`. It never goes into `.env` (the dev shell would export it to every command) or into the compose file, so the DAG always runs the main world.
2. **Same keys, same checks.** `world_heldout.toml` holds every key of `world.toml`, plus `seed`. The checks under "Where config is read from" apply to it too. The H1 to H4 keys that S14.1 adds are 0 in `world.toml` and above 0 here.
3. **The seed.** A new integer, written into `world_heldout.toml` in S14.1, after `v1.3` is tagged: the UTC date of that tag as YYYYMMDD. When a world file sets `seed`, `config.py` uses it and does not read `RECON_SEED`. `world.toml` never sets `seed`, so the main world and the DAG keep using `RECON_SEED`. The CLI prints the world file and the seed at the start of every command.
4. **The landing folder.** Every held-out command passes `RECON_LANDING_DIR="$PWD/landing_heldout"`, run from the repo root. The layout under `landing_heldout/` is the same as under `landing/` (see "Landing files"). S14.1 adds `landing_heldout/` to `.gitignore` and `.dockerignore` before any held-out file exists, so nothing in it is ever committed, the answer key included.
5. **No mixing.** `config.py` fails when it loads, before anything is written, if the world file and the landing folder do not match: `world_heldout.toml` only with a folder named `landing_heldout`, and `world.toml` never with that folder. The CLI's load commands check the dataset the same way: `world_heldout.toml` only with `RAW_DATASET=raw_heldout`, and `world.toml` never with it. Without these checks, a held-out command that forgot `RECON_LANDING_DIR` would overwrite the main world's landing files and its answer key.
6. **FX.** The held-out run lands its own copy of the real NBK rates in `landing_heldout/fx/`: one request per run date, with the same request, checks and never-fetch-again rule as "Landing (immutable)". These files are not committed. A held-out run never reads or writes `landing/fx/`.
7. **The answer key.** Same file names and fields, under `landing_heldout/_truth/`, and `planted` may also hold `H1` to `H4`. `scripts/eval.py` reads the answer key from `<RECON_LANDING_DIR>/_truth/`, and regenerates it from the selected world file when the files are absent. So a held-out eval passes the same `RECON_WORLD_FILE` and `RECON_LANDING_DIR` as the held-out load (S14.3).
8. **Dates.** The main world's date rules hold: every run date at or after `RECON_WORLD_START`, inside the 45-day guard, and before today (UTC). S14.2 in `docs/build_plan.md` sets the window. Payments booked before the oldest loaded day leave a few one-sided lines on the first days. They are `before_scope`, and the scoring rules skip them.

---

## Generator tests (`tests/test_generator.py`)

Every test uses constants in the test file (`SEED = 20261101`, `WORLD_START = 2026-10-04`), writes into pytest's `tmp_path`, never reads `.env` and never touches BigQuery.

Required in M3 (step S3.4):

| Test | Asserts |
|---|---|
| `test_golden_hash` | `emit(SEED, WORLD_START, 2026-10-09, tmp)`; for the 4 files in sorted path order, build the text `<relative path> <sha256 of file>\n`; its SHA-256 equals the committed constant `GOLDEN = "[GOLDEN_SHA256]"`. Fill the constant after the first green run. Change it only together with a `generator_version` bump (or before `g1-freeze`), and log an unexpected change in `docs/failure_log.md` |
| `test_rerun_is_byte_identical` | `emit` twice into two folders gives identical bytes for every file |
| `test_other_seed_differs` | `SEED + 1` gives a different combined hash |
| `test_rows_belong_to_their_run` | for 10 run dates: every events row has `_arrival_date = R` and `delivered_ts` starting with `R`; every statement row has `_arrival_date = R`, `statement_id` ending in R as `yyyymmdd`, and the file's MID; every row's `_source_file` equals its file's relative path |
| `test_each_row_in_exactly_one_file` | over run dates `WORLD_START`..`WORLD_START + 14`, for payments booked in the first 10 days: each non-D2 payment has exactly one statement line, D2 payments have none, D3 payments have no deliveries, and every `delivery_id` appears once |
| `test_lookback_is_enough` | every arrival of every payment booked in the first 10 days lies in [booking date, booking date + 3], and 3 <= `lookback_days`. Generator 1.1.0 (D6) widens both to 6 (see "Held for later") |
| `test_rows_match_schema` | every emitted row has exactly the field names of its schema JSON; REQUIRED values are not null; STRING is `str`, INT64 is `int` and not `bool`, BOOL is `bool`, DATE matches `YYYY-MM-DD`, TIMESTAMP matches `YYYY-MM-DD HH:MM:SS+00:00` |
| `test_class_counts_within_loose_bounds` | over 7 booking days, each class count lies between 0.25 and 3 times its expected value, where the expected value is the rate times the real base count (payments for D2 to D4, events for D1, settled lines for D5, settled lines without D5 for B3 spikes). If a bound fails for the pinned seed, widen it and record why in the failure log. Never change the seed to make a test pass |
| `test_grace_days_match_dbt` | `statement_grace_days` in `world.toml` equals `vars.statement_grace_days` in `dbt/dbt_project.yml`, read with `yaml.safe_load` (PyYAML comes with dbt-core, so the host venv has it). The answer key's `due_date` and dbt's `due_date` both use this value, so the test stops them drifting apart. A missing var fails the test too: add it in S3.1 (see "World parameters") |

Recommended, cheap, add when time allows:

| Test | Asserts |
|---|---|
| `test_invariants` | D1 never with D3; D4 and D5 never with D2; `net = gross - fee`; `gross > 0` and `fee >= 0`; `timing_shift` in {-1, 0} for USD and {0, 1} for KZT; the first delivery never arrives after the statement line; every statement line arrives before its due date; ids match their patterns; `payment_id` is unique across days |
| `test_no_payments_before_world_start` | `payments_for_day` returns an empty list for `WORLD_START - 1` |
| `test_moved_world_is_the_same_world` | with `WORLD_START + 7`, each `day_index` has the same count, plans, amounts, time of day, planted classes and fees; only dates and ids differ |

---

## Labels and licences

### Labels

1. Every synthetic row has `is_synthetic = true`.
2. Table descriptions start with `SYNTHETIC: generated by src/recon/generator.py` (payment tables) or `REAL: NBK rates via Frankfurter v2` (`raw.fx_rates`). Label `data_origin` is `synthetic` or `real`.
3. README first screen, line 2: "Learning project, built 1-2 Nov 2026 · Payments: SYNTHETIC (seeded generator) · FX: REAL (National Bank of Kazakhstan rates via Frankfurter) · BigQuery sandbox, Airflow 3.3.2, dbt-core 1.12.6 · $0".
4. Prices, mix and volumes are called "illustrative assumptions".
5. The statement layout is "modelled on the public Adyen settlement-details and Stripe payout-reconciliation docs". It claims nothing about how any real PSP behaves.
6. The FX carry-forward is "a project convention, not NBK's official rate for that day".
7. Nothing in this document is a result. Results come only from `docs/evidence/<date>/`, each with a date and a `make` target.

How the statement columns map to the public docs (cited as public schemas only). Both docs show amounts in major units with decimals, for example 100.00. This project stores integer minor units instead.

| Our column | Adyen settlement details report | Stripe itemized payout reconciliation |
|---|---|---|
| `mid` | Merchant Account | no column (one Stripe account) |
| `payment_id` | Psp Reference | `charge_id` |
| `captured_ts` | Creation Date (with TimeZone) | `charge_created_utc` |
| `record_type = SALE` | Type = Settled | `reporting_category` = charge |
| `gross_minor` | Gross Credit (GC) | `gross` |
| `fee_minor` | Commission (NC); this project folds Markup, Scheme Fees and Interchange into one fee | `fee` |
| `net_minor` | Net Credit (NC) | `net` |
| `currency` | Gross Currency, equal to Net Currency here | `currency` |
| `statement_id` | Batch Number (here one batch per MID per arrival day) | `automatic_payout_id` |
| `accounting_date` | no single column: it decides which batch a line joins | no single column |

### Licences

| Item | Licence or terms | What the project does |
|---|---|---|
| This repo: code, docs, generated data | MIT, copyright Bainazar Seitek | `LICENSE` at the root |
| Synthetic data | produced by this repo's own code; contains no third-party data | labelled everywhere; never committed (regenerated on demand) |
| Frankfurter (service, code, docs) | code, docs and images are MIT. Its docs say direct queries to a provider's endpoints "remain subject to each provider's terms" | cite `https://frankfurter.dev/` in the README |
| NBK rates (through Frankfurter and NBK RSS) | Frankfurter's licence page lists NBK's terms as "None published" and describes the rates as public data shared for information | commit the small landed files for reproducibility, with this README attribution: "Exchange rates: National Bank of the Republic of Kazakhstan (nationalbank.kz), retrieved through Frankfurter (frankfurter.dev)." and a note that the cross-check files in `landing/fx/provider=nbk_rss/` come directly from NBK's own RSS feed, not through Frankfurter. Re-check nationalbank.kz for terms before the repo goes public (step S10.4) |
| ECB rates (U7) | ECB's terms of use page | read before committing ECB files |
| Adyen and Stripe docs | read as public schema references only; no text or data copied | cite their URLs |

---

## Check yourself (M3 explain check)

Answer aloud before closing M3. The heading in brackets holds the answer.
1. Why is the generator a pure function of (seed, day_index, MID)? ("Determinism")
2. Why only `random()`, and why integer weights and basis points? ("Draw helpers", "World parameters")
3. Which defect can cross midnight, and what does that do to arrival files? ("D1 `webhook_redelivery`", "Webhooks")
4. Why does a run recompute 5 booking days when 3 are enough? ("What one run ingests")
5. Why is this catalog committed before any matcher SQL? ("Defect catalog")
6. Why is `raw.fx_rates` partitioned by the fetch date and not the rate date? ("From the landed file to raw rows")
7. What changes, and what stays the same, when the window moves forward months later? ("Rolling window and reruns months later")

---

## Sources

- Python `random`, notes on reproducibility and string seeding: https://docs.python.org/3/library/random.html#notes-on-reproducibility and https://docs.python.org/3/library/random.html#random.seed
- Python `json`, `parse_float` (called with the string of every JSON float in the body): https://docs.python.org/3/library/json.html#json.load
- dbt-core 1.12.6 requirements, which include `pyyaml>=6.0` (used by `test_grace_days_match_dbt`): https://pypi.org/project/dbt-core/1.12.6/
- BigQuery schema JSON, type names and column-name rules: https://docs.cloud.google.com/bigquery/docs/schemas
- BigQuery JSON loading, DATE and TIMESTAMP formats: https://docs.cloud.google.com/bigquery/docs/loading-data-cloud-storage-json
- BigQuery data type sizes: https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/data-types
- Frankfurter docs: https://frankfurter.dev/ ; licence and provider terms: https://frankfurter.dev/license/
- NBK RSS feed: https://nationalbank.kz/rss/get_rates.cfm?fdate=DD.MM.YYYY
- Adyen settlement details report: https://docs.adyen.com/reporting/settlement-reconciliation/transaction-level/settlement-details-report/
- Stripe payout reconciliation report: https://docs.stripe.com/reports/payout-reconciliation
