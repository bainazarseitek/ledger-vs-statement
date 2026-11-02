"""N3, the real-data check: the weekend carry-forward against NBK's own published rates.

For every KZT day d in [scope_start, as_of_date] of the marts, compare units_per_usd from
<marts>.int_fx__usd_rates_daily with NBK's RSS rate for d (landed once in landing/fx/provider=nbk_rss/).
Days with their own Frankfurter row must agree exactly, or the script exits 1. Carried days are measured.
The carry-forward is a project convention, not NBK's official rate for that day.
"""
import argparse
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RSS_DIR = Path("landing/fx/provider=nbk_rss")
USER_AGENT = "ledger-vs-statement (learning project)"
MAX_BODY = 1_000_000


def rss_path(d):
    return RSS_DIR / f"rate_date={d.isoformat()}.xml"


def fetch_rss(d, today):
    """The landed XML for d, or one request for it. Never a date on or after today (UTC)."""
    path = rss_path(d)
    if path.exists():
        return path.read_bytes(), "landed"
    if d >= today:
        raise ValueError(f"{d} has not ended in UTC: NBK answers future dates with its latest rate")
    url = f"https://nationalbank.kz/rss/get_rates.cfm?fdate={d:%d.%m.%Y}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:
        status, body = response.status, response.read(MAX_BODY + 1)
    if status != 200:
        raise RuntimeError(f"NBK answered HTTP {status} for {d}")
    return body, "fetched"


def usd_rate(body, d):
    """NBK's KZT per 1 USD for d as a Decimal, or None when the feed has no items for d."""
    if len(body) > MAX_BODY or b"<!DOCTYPE" in body or b"<!ENTITY" in body:
        raise ValueError(f"refusing the NBK body for {d}: too large, or it declares a DOCTYPE or an ENTITY")
    root = ET.fromstring(body)
    echoed = (root.findtext("date") or "").strip()
    if echoed != f"{d:%d.%m.%Y}":
        raise ValueError(f"the NBK feed for {d} echoes the date {echoed!r}")
    for item in root.iter("item"):
        if (item.findtext("title") or "").strip() == "USD":
            if (item.findtext("quant") or "").strip() != "1":
                raise ValueError(f"the NBK USD quant for {d} is not 1")
            return Decimal((item.findtext("description") or "").strip())   # Decimal, never float
    return None


def land(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(body)
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marts-dataset", default="analytics")
    args = parser.parse_args()
    from recon.bq import host_client, query, rows

    client, today = host_client(), datetime.now(UTC).date()
    scope = rows(query(client, f"select scope_start, as_of_date from `{client.project}.{args.marts_dataset}.stg_recon__as_of`",
                       use_cache=False))[0]
    spine = {r["day"]: r for r in rows(query(client, f"""select day, units_per_usd, rate_date, carry_days
from `{client.project}.{args.marts_dataset}.int_fx__usd_rates_daily`
where currency = 'KZT' and day between @s and @e order by day""", _params(scope), use_cache=False))}

    days, d = [], scope["scope_start"]
    while d <= scope["as_of_date"]:
        body, how = fetch_rss(d, today)
        nbk = usd_rate(body, d)
        if how == "fetched" and nbk is not None:
            land(rss_path(d), body)                          # landed once, byte for byte, then never fetched again
        s = spine.get(d)
        days.append({"day": d.isoformat(), "weekday": d.weekday() < 5, "nbk_rate": None if nbk is None else str(nbk),
                     "project_rate": None if s is None else str(s["units_per_usd"]),
                     "rate_date": None if s is None else s["rate_date"].isoformat(),
                     "carry_days": None if s is None else s["carry_days"], "source": how})
        d += timedelta(days=1)

    usable = [x for x in days if x["nbk_rate"] is not None and x["project_rate"] is not None]
    own = [x for x in usable if x["carry_days"] == 0]       # a Frankfurter row dated d
    carried = [x for x in usable if x["carry_days"] > 0]
    disagree = [x for x in own if Decimal(x["project_rate"]) != Decimal(x["nbk_rate"])]
    diffs = [(abs(Decimal(x["project_rate"]) - Decimal(x["nbk_rate"])), x) for x in carried]
    differing = [(diff, x) for diff, x in diffs if diff != 0]
    worst = max(differing, key=lambda p: p[0]) if differing else (Decimal(0), None)
    y_bps = (worst[0] / Decimal(worst[1]["nbk_rate"]) * 10000).quantize(Decimal("0.1"), ROUND_HALF_UP) if worst[1] else Decimal("0.0")
    n3 = {"C_carried_days": len(carried), "W_carried_days_differing": len(differing),
          "X_max_abs_diff_kzt": str(worst[0]), "Y_bps": str(y_bps),
          "X_day": worst[1]["day"] if worst[1] else None,
          "E_own_rate_days": len(own), "E_agreeing": len(own) - len(disagree),
          "weekday_disagreements": [x["day"] for x in disagree],
          "days_without_nbk_rate": [x["day"] for x in days if x["nbk_rate"] is None],
          "scope_start": scope["scope_start"].isoformat(), "as_of_date": scope["as_of_date"].isoformat()}
    out = Path(f"docs/evidence/{today.isoformat()}/fx_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"measured_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(sep=" "), "marts_dataset": args.marts_dataset,
           "convention": "the carry-forward is a project convention, not NBK's official rate for that day",
           "n3": n3, "days": days}
    out.write_text(json.dumps(doc, indent=2, sort_keys=True).replace(client.project, "<project>") + "\n")
    print(f"N3: on {n3['W_carried_days_differing']} of {n3['C_carried_days']} carried days the carry-forward differed from "
          f"NBK by up to {n3['X_max_abs_diff_kzt']} KZT per USD ({n3['Y_bps']} bps); own-rate days agreed on "
          f"{n3['E_agreeing']} of {n3['E_own_rate_days']} -> {out}")
    return 1 if disagree else 0


def _params(scope):
    from google.cloud import bigquery

    return [bigquery.ScalarQueryParameter("s", "DATE", scope["scope_start"]),
            bigquery.ScalarQueryParameter("e", "DATE", scope["as_of_date"])]


if __name__ == "__main__":
    sys.exit(main())
