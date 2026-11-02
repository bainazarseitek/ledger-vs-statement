"""REAL NBK USD/KZT rates through Frankfurter v2, landed once per run date and never fetched again."""
import hashlib
import json
import logging
import os
import urllib.request
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

log = logging.getLogger(__name__)
USER_AGENT = "ledger-vs-statement (learning project)"


def fx_url(run_date):
    start = run_date - timedelta(days=6)                  # R-6..R: seven days always contain weekdays
    return ("https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT"
            f"&from={start.isoformat()}&to={run_date.isoformat()}")


def check_rates(rates, run_date):
    """Everything that must hold before a byte is landed."""
    if not isinstance(rates, list) or not rates:
        raise ValueError("Frankfurter returned no rows")
    start = run_date - timedelta(days=6)
    dates = []
    for i, r in enumerate(rates):
        if not isinstance(r, dict) or not {"date", "base", "quote", "rate"} <= set(r):
            raise ValueError(f"row {i} lacks date, base, quote or rate: {r}")
        if r["base"] != "USD" or r["quote"] != "KZT":
            raise ValueError(f"row {i} is {r['base']}/{r['quote']}, expected USD/KZT")
        d = datetime.strptime(r["date"], "%Y-%m-%d").date()
        if d > run_date:
            raise ValueError(f"row {i} is dated {d}, after the run date {run_date}")
        if d < start and i > 0:                           # only the first row may be the carry-in before R-6
            raise ValueError(f"row {i} is dated {d}, before {start}; only the first row may be")
        dates.append(d)
    if any(a >= b for a, b in pairwise(dates)):
        raise ValueError(f"rate dates are not strictly increasing: {dates}")


def write_atomic(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    return tmp


def fetch_nbk(run_date, landing_dir):
    """Land fx/provider=nbk/arrival_date=R.json (the body, byte for byte) and its meta file, once."""
    folder = Path(landing_dir) / "fx" / "provider=nbk"
    body_path = folder / f"arrival_date={run_date.isoformat()}.json"
    meta_path = folder / f"arrival_date={run_date.isoformat()}.meta.json"
    if body_path.exists() and meta_path.exists():
        log.info("already landed: %s", body_path.name)
        print(f"already landed: {body_path.name}")
        return {"action": "skipped"}
    if body_path.exists() or meta_path.exists():
        raise RuntimeError(f"only one of {body_path.name} and {meta_path.name} exists: delete the stray file by hand")
    today = datetime.now(UTC).date()
    if run_date >= today:
        raise ValueError(f"run date {run_date} has not ended in UTC (today is {today}): never request it")

    url = fx_url(run_date)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:
        status, body = response.status, response.read()
    fetched_at = datetime.now(UTC).replace(microsecond=0).isoformat(sep=" ")
    if status != 200:
        raise RuntimeError(f"Frankfurter answered HTTP {status} for {url}")
    rates = json.loads(body, parse_float=str)             # rates stay exact text, never float
    check_rates(rates, run_date)

    meta = {"fetched_at": fetched_at, "http_status": status, "sha256": hashlib.sha256(body).hexdigest(), "url": url}
    folder.mkdir(parents=True, exist_ok=True)
    body_tmp = write_atomic(body_path, body)
    meta_tmp = write_atomic(meta_path, (json.dumps(meta, sort_keys=True, separators=(",", ":")) + "\n").encode())
    os.replace(meta_tmp, meta_path)                       # the meta first: the body's final name means "landed"
    os.replace(body_tmp, body_path)
    return {"action": "fetched", "rows": len(rates)}
