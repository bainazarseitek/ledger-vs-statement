"""SYNTHETIC payment webhooks, statement lines and the answer key for one arrival day.

Output depends only on (seed, world_start, run_date) and the committed config. Standard library only.
"""
import json
import math
import os
import random
from datetime import UTC, datetime, time, timedelta
from functools import cache
from pathlib import Path

from recon.config import load_world


@cache
def world():
    return load_world()


# --- random draws: only Random.random(), whose sequence Python keeps stable across versions ---

def stream(seed, day_index, mid_id, *parts):
    """One independent random stream per purpose, keyed by day_index (never the date)."""
    return random.Random("|".join(str(p) for p in (seed, day_index, mid_id, *parts)))


def draw_int(rng, lo, hi):
    """An integer in [lo, hi], both ends included."""
    k = lo + math.floor(rng.random() * (hi - lo + 1))
    return min(k, hi)                                   # guard against float rounding at the top end


def draw_weighted(rng, weights):
    """The index i with probability weights[i] / sum(weights)."""
    x = rng.random() * sum(weights)
    running = 0
    for i, w in enumerate(weights):
        running += w
        if x < running:
            return i
    return max(i for i, w in enumerate(weights) if w > 0)   # float guard


# --- contract arithmetic: integers only, the same formulas dbt uses ---

def expected_fee_minor(gross, mid):
    return (gross * mid.fee_bps + 5000) // 10000 + mid.fee_fixed_minor          # half-up


def fee_tolerance_minor(gross, mid):
    return max(mid.fee_tol_min_minor, (gross * mid.fee_tol_bps + 9999) // 10000)  # ceiling


def utc_hour_weights(w, mid):
    """Rotate the local-hour weights onto UTC hours with the MID's fixed offset."""
    return [w.local_hour_weights[(h + mid.statement_utc_offset_hours) % 24] for h in range(24)]


def ts(value):
    return value.isoformat(sep=" ")                     # YYYY-MM-DD HH:MM:SS+00:00 (whole seconds)


# --- one booking day for one merchant account ---

def payments_for_day(seed, world_start, day, mid):
    """The payments booked on UTC day `day` for one MID, each with its rows and its answer-key row."""
    w = world()
    if day < world_start:
        return []                                       # the business opens on world_start
    day_index = (day - world_start).days
    mean, jitter = w.mean_per_day[mid.mid], w.jitter_pct
    count = draw_int(stream(seed, day_index, mid.mid, "volume"),
                     mean * (100 - jitter) // 100, mean * (100 + jitter) // 100)
    hours = utc_hour_weights(w, mid)
    return [one_payment(seed, w, mid, day, day_index, n, hours) for n in range(1, count + 1)]


def one_payment(seed, w, mid, day, day_index, n, hours):
    def rng(purpose):
        return stream(seed, day_index, mid.mid, n, purpose)

    # plan and amount
    i = draw_weighted(rng("plan"), w.plan_weight_pct)
    plan_id, amount = w.plan_order[i], w.price_minor[mid.currency][i]

    # capture time: an hour from the rotated weights, then a second inside it
    t = rng("time")
    hour, second = draw_weighted(t, hours), draw_int(t, 0, 3599)
    event_ts = datetime.combine(day, time(0), UTC) + timedelta(hours=hour, seconds=second)

    # readable ids
    payment_id = f"pay_{day:%Y%m%d}_{mid.tag}_{n:05d}"
    order_id = f"ord_{day:%Y%m%d}_{mid.tag}_{n:05d}"
    event_id = f"evt_{payment_id}_cap"

    # B1: the PSP's accounting day on the MID's fixed clock
    accounting_date = (event_ts + timedelta(hours=mid.statement_utc_offset_hours)).date()

    # one money draw decides D2, D3, D4 or none (cumulative thresholds)
    d = w.defects
    x = draw_int(rng("money"), 0, 9999)
    d2 = d["missing_in_statement_bp"]
    d3 = d2 + d["missing_in_ledger_bp"]
    d4 = d3 + d["amount_mismatch_bp"]
    money = "D2" if x < d2 else "D3" if x < d3 else "D4" if x < d4 else None
    planted = [money] if money else []

    payload = {"event_id": event_id, "event_type": "payment.captured", "payment_id": payment_id,
               "order_id": order_id, "mid": mid.mid, "plan_id": plan_id, "amount_minor": amount,
               "currency": mid.currency, "event_ts": ts(event_ts), "is_synthetic": True}

    # webhook deliveries (none for D3), with D1 redeliveries
    deliveries, extra_copies = [], 0
    if money != "D3":
        wh = w.webhooks
        first = event_ts + timedelta(seconds=draw_int(rng("delivery"), *wh["first_delivery_delay_s"]))
        times = [first]
        r = rng("redelivery")
        if draw_int(r, 0, 9999) < wh["redelivery_bp"]:
            extra_copies = 1 if draw_int(r, 0, 9999) < wh["redelivery_one_copy_bp"] else 2
            delays = sorted(draw_int(r, *wh["redelivery_delay_s"]) for _ in range(extra_copies))
            times += [first + timedelta(seconds=s) for s in delays]
            planted.append("D1")
        for attempt, delivered in enumerate(times, start=1):
            arrival = delivered.date().isoformat()
            deliveries.append({**payload, "delivery_id": f"dlv_{event_id}_{attempt}",
                               "delivered_ts": ts(delivered), "_arrival_date": arrival,
                               "_source_file": f"payment_events/arrival_date={arrival}/part-000.ndjson"})

    # statement line (none for D2)
    line, fee_noise, fee_variance, statement_arrival = None, "none", None, None
    if money != "D2":
        lag = 1 if draw_int(rng("lag"), 0, 9999) < w.settlement["lag_one_day_bp"] else 2
        statement_arrival = accounting_date + timedelta(days=lag)

        gross = amount
        if money == "D4":
            r = rng("amount_delta")
            sign, delta_bp = draw_int(r, 0, 1), draw_int(r, *d["amount_delta_bp"])
            delta = max(1, (amount * delta_bp + 5000) // 10000)
            gross = amount - delta if sign == 0 else amount + delta

        expected, tol = expected_fee_minor(gross, mid), fee_tolerance_minor(gross, mid)
        fd = rng("fee_defect")
        is_d5 = draw_int(fd, 0, 9999) < d["fee_overcharge_bp"]
        if money == "D4" and draw_int(rng("combo"), 0, 9999) < d["combo_fee_overcharge_bp"]:
            is_d5 = True
        if is_d5:                                       # D5: overcharge, no noise
            fee_variance = draw_int(fd, (4 * tol + 4) // 5, 10 * tol)
            planted.append("D5")
        else:                                           # B3: inside noise, or a spike at or above tol
            r = rng("fee_noise")
            if draw_int(r, 0, 9999) < w.fee_noise["spike_bp"]:
                sign, magnitude = draw_int(r, 0, 1), draw_int(r, tol, (3 * tol + 1) // 2)
                fee_variance, fee_noise = (-magnitude if sign == 0 else magnitude), "spike"
            else:
                fee_variance, fee_noise = draw_int(r, -(tol // 2), tol // 2), "inside"
        fee = expected + fee_variance
        arrival = statement_arrival.isoformat()
        line = {"statement_id": f"stmt_{mid.mid}_{statement_arrival:%Y%m%d}", "line_id": f"ln_{payment_id}",
                "mid": mid.mid, "record_type": "SALE", "payment_id": payment_id, "captured_ts": ts(event_ts),
                "accounting_date": accounting_date.isoformat(), "gross_minor": gross, "fee_minor": fee,
                "net_minor": gross - fee, "currency": mid.currency, "is_synthetic": True,
                "_arrival_date": arrival,
                "_source_file": f"settlement_lines/arrival_date={arrival}/mid={mid.mid}.ndjson"}

    due_date = accounting_date + timedelta(days=mid.max_settlement_lag_days + w.statement_grace_days)
    truth = {"payment_id": payment_id, "mid": mid.mid, "booking_date": day.isoformat(),
             "planted": sorted(planted), "extra_copies": extra_copies,
             "timing_shift": (accounting_date - day).days, "fee_noise": fee_noise,
             "fee_variance_minor": fee_variance,
             "statement_arrival_date": statement_arrival.isoformat() if statement_arrival else None,
             "due_date": due_date.isoformat(), "generator_version": w.generator_version}
    return {"deliveries": deliveries, "line": line, "truth": truth}


# --- one arrival day: what reached us during UTC day run_date ---

def arrivals(seed, world_start, run_date):
    """Recompute booking days R-lookback..R and keep only the rows that arrived on R."""
    w, r = world(), run_date.isoformat()
    events, lines, truth = [], {m.mid: [] for m in w.mids}, []
    for mid in w.mids:
        for back in range(w.lookback_days, -1, -1):
            booking_day = run_date - timedelta(days=back)
            for p in payments_for_day(seed, world_start, booking_day, mid):
                events += [row for row in p["deliveries"] if row["_arrival_date"] == r]
                if p["line"] and p["line"]["_arrival_date"] == r:
                    lines[mid.mid].append(p["line"])
                if booking_day == run_date:
                    truth.append(p["truth"])
    events.sort(key=lambda row: row["delivery_id"])
    for rows in lines.values():
        rows.sort(key=lambda row: row["line_id"])
    truth.sort(key=lambda row: row["payment_id"])
    return events, lines, truth


def write_ndjson(path, rows):
    """Write to <name>.tmp in the same folder, then rename: a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    os.replace(tmp, path)


def emit(seed, world_start, run_date, landing_dir):
    """Write the four synthetic files for arrival day run_date. Returns a small dict of counts."""
    if run_date < world_start:
        raise ValueError(f"run date {run_date} is before the world start {world_start}")
    landing = Path(landing_dir)
    events, lines, truth = arrivals(seed, world_start, run_date)
    r = run_date.isoformat()
    write_ndjson(landing / f"payment_events/arrival_date={r}/part-000.ndjson", events)
    for mid_id, rows in lines.items():
        write_ndjson(landing / f"settlement_lines/arrival_date={r}/mid={mid_id}.ndjson", rows)
    write_ndjson(landing / f"_truth/booking_date={r}.ndjson", truth)
    return {"run_date": r, "payment_events": len(events),
            "settlement_lines": sum(len(rows) for rows in lines.values()),
            "settlement_lines_by_mid": {mid_id: len(rows) for mid_id, rows in sorted(lines.items())},
            "truth": len(truth), "generator_version": world().generator_version}
