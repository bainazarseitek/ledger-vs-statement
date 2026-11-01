"""G0 probes for the BigQuery sandbox. Writes a few KB into dataset `probe` only."""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from google.api_core import exceptions as gexc
from google.cloud import bigquery

PROJECT = os.environ["GCP_PROJECT"]
CAP = 1_000_000_000                      # the maximum_bytes_billed used everywhere in the project
client = bigquery.Client(project=PROJECT, location="US")
TODAY = dt.datetime.now(dt.UTC).date()
Y, Y1 = TODAY - dt.timedelta(days=1), TODAY - dt.timedelta(days=2)
T = f"{PROJECT}.probe.raw_pay"           # created by P3, used by P4 to P7
SA_EMAIL = re.compile(r"[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com")
SIXTY_DAYS_MS = 5_184_000_000            # the sandbox's 60-day expiry
DML_REFUSED = "DML queries are not allowed in the free tier"


def redact(text):
    """Remove the service-account email and the project id before anything is saved."""
    return SA_EMAIL.sub("<sa>", str(text)).replace(PROJECT, "<project>")


def q(sql, params=(), cap=CAP):
    """One query with the bytes cap and no cache. Returns (job, rows as dicts)."""
    config = bigquery.QueryJobConfig(maximum_bytes_billed=cap, use_query_cache=False,
                                     query_parameters=list(params))
    job = client.query(sql, job_config=config)
    return job, [dict(row.items()) for row in job.result()]


def by_day(sql):
    """Rows of a small GROUP BY d query as tuples, for exact comparisons."""
    _, rows = q(sql)
    return [tuple(r.values()) for r in rows]


def load_rows(destination, rows, schema, create="CREATE_NEVER"):
    """One NDJSON load job with WRITE_TRUNCATE: the same settings as the real loader."""
    payload = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=create,
        max_bad_records=0,
    )
    job = client.load_table_from_file(io.BytesIO(payload), destination, job_config=config)
    job.result()
    return job


def row(day, x, hms):
    """A probe row. TIMESTAMP text in the raw format of this project: YYYY-MM-DD HH:MM:SS+00:00."""
    return {"d": day.isoformat(), "x": x, "ts": f"{day.isoformat()} {hms}+00:00"}


SCHEMA = [bigquery.SchemaField("d", "DATE", mode="REQUIRED"),
          bigquery.SchemaField("x", "INT64"),
          bigquery.SchemaField("ts", "TIMESTAMP")]


def result(pid, passed, detail, evidence=None, error_text=None):
    """The record every probe returns."""
    return {"id": pid, "status": "PASS" if passed else "FAIL", "detail": detail,
            "evidence": evidence, "error_text": error_text}


def utc(day, hour):
    return dt.datetime.combine(day, dt.time(hour), dt.UTC)


# --- P1 to P3 and the shard check ---------------------------------------------------------

def p1():
    """DDL works: CTAS and a view."""
    q(f"CREATE OR REPLACE TABLE `{PROJECT}.probe.t` AS SELECT 1 AS x")
    q(f"CREATE OR REPLACE VIEW `{PROJECT}.probe.v` AS SELECT x FROM `{PROJECT}.probe.t`")
    _, rows = q(f"SELECT x FROM `{PROJECT}.probe.v`")
    return result("P1", rows == [{"x": 1}], f"CTAS and view ran; view returned {rows}", rows)


def p2(plan_b):
    """DML is refused. On Plan B (billing on) the INSERT must be accepted instead."""
    try:
        q(f"INSERT INTO `{PROJECT}.probe.t` (x) VALUES (2)")
        accepted, text = True, "the INSERT was accepted"
    except gexc.GoogleAPICallError as e:
        accepted, text = False, redact(e)
    if plan_b:
        return result("P2", accepted, f"Plan B: INSERT accepted = {accepted}", error_text=text)
    passed = not accepted and DML_REFUSED in text
    if accepted:
        detail = "INSERT ACCEPTED: billing is on. Stop and check the Billing page"
    else:
        detail = "INSERT refused as expected" if passed else "refused, but with another message"
    return result("P2", passed, detail, error_text=text)


def p3():
    """One WRITE_TRUNCATE load into t$Y replaces exactly that day."""
    client.delete_table(T, not_found_ok=True)                        # a clean start
    table = bigquery.Table(T, schema=SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY, field="d")
    client.create_table(table)
    got, error = None, None
    try:
        load_rows(f"{T}${Y1:%Y%m%d}", [row(Y1, 7, "00:00:00")], SCHEMA)                       # the other day first
        load_rows(f"{T}${Y:%Y%m%d}", [row(Y, 1, "10:00:00"), row(Y, 2, "23:59:59")], SCHEMA)  # file A: 2 rows
        load_rows(f"{T}${Y:%Y%m%d}", [row(Y, 99, "12:00:00")], SCHEMA)                        # file B: 1 row
        got = by_day(f"SELECT d, COUNT(*) AS n, SUM(x) AS s, MIN(ts) AS ts FROM `{T}` GROUP BY d ORDER BY d")
    except gexc.GoogleAPICallError as e:
        error = redact(e)
    if got == [(Y1, 1, 7, utc(Y1, 0)), (Y, 1, 99, utc(Y, 12))]:
        return result("P3", True, f"{Y} holds only file B's row; {Y1} untouched", got)
    return result("P3", False, "the decorator load did not replace exactly one day",
                  {"got": got, "shard_check": shard_check()}, error)


def shard_check():
    """The fallback write path, run only when P3 fails: one whole table per day."""
    shard = f"{PROJECT}.probe.raw_pay_{Y:%Y%m%d}"
    try:
        client.delete_table(shard, not_found_ok=True)
        load_rows(shard, [row(Y, 1, "10:00:00"), row(Y, 2, "23:59:59")], SCHEMA, create="CREATE_IF_NEEDED")
        load_rows(shard, [row(Y, 99, "12:00:00")], SCHEMA, create="CREATE_IF_NEEDED")
        _, rows = q(f"SELECT COUNT(*) AS n, SUM(x) AS s FROM `{PROJECT}.probe.raw_pay_*` "
                    f"WHERE _TABLE_SUFFIX = '{Y:%Y%m%d}'")
    except gexc.GoogleAPICallError as e:
        return {"passed": False, "error": redact(e)}
    return {"passed": rows == [{"n": 1, "s": 99}], "rows": rows}


# --- P4 to P7 ---------------------------------------------------------------------------

def p4():
    """A row for another day is refused, and the table is unchanged."""
    try:
        load_rows(f"{T}${Y:%Y%m%d}", [row(Y1, 5, "01:00:00")], SCHEMA)   # a Y1 row into the Y partition
        refused, text = False, "the load was accepted"
    except gexc.GoogleAPICallError as e:
        refused, text = True, redact(e)
    after = by_day(f"SELECT d, COUNT(*) AS n, SUM(x) AS s FROM `{T}` GROUP BY d ORDER BY d")
    unchanged = after == [(Y1, 1, 7), (Y, 1, 99)]
    return result("P4", refused and unchanged, f"refused = {refused}, table unchanged = {unchanged}",
                  after, text)


def p5():
    """Deleting one partition works, and a second delete does not fail."""
    client.delete_table(f"{T}${Y:%Y%m%d}", not_found_ok=True)
    client.delete_table(f"{T}${Y:%Y%m%d}", not_found_ok=True)        # a second delete must not fail
    left = by_day(f"SELECT d, COUNT(*) AS n FROM `{T}` GROUP BY d ORDER BY d")
    return result("P5", left == [(Y1, 1)], f"after deleting {Y}: {left}", left)


def p6(plan_b):
    """The expirations the sandbox sets. On Plan B there are no sandbox defaults."""
    ds = client.get_dataset(f"{PROJECT}.probe")
    tb = client.get_table(T)
    evidence = {
        "dataset_location": ds.location,
        "default_table_expiration_ms": ds.default_table_expiration_ms,
        "default_partition_expiration_ms": ds.default_partition_expiration_ms,
        "raw_pay_partition_expiration_ms": tb.time_partitioning.expiration_ms,
        "raw_pay_table_expires": tb.expires,                          # None means no table-level expiry
        "t_table_expires": client.get_table(f"{PROJECT}.probe.t").expires,
    }
    if plan_b:
        passed = ds.default_table_expiration_ms is None and tb.expires is None
    else:
        passed = (ds.location == "US" and tb.expires is None
                  and ds.default_table_expiration_ms == SIXTY_DAYS_MS
                  and ds.default_partition_expiration_ms == SIXTY_DAYS_MS
                  and tb.time_partitioning.expiration_ms == SIXTY_DAYS_MS)
    return result("P6", passed, "expirations as expected" if passed else "expirations differ: see evidence",
                  evidence)


def p7():
    """Storage metadata is readable from at least one source."""
    sources = {
        "__TABLES__": f"SELECT table_id, row_count, size_bytes FROM `{PROJECT}.probe.__TABLES__`",
        "TABLE_STORAGE": "SELECT table_name, total_logical_bytes "
                         "FROM `region-us`.INFORMATION_SCHEMA.TABLE_STORAGE WHERE table_schema = 'probe'",
    }
    evidence = {}
    for name, sql in sources.items():
        try:
            _, rows = q(sql)
            evidence[name] = {"readable": True, "rows": len(rows)}
        except gexc.GoogleAPICallError as e:
            evidence[name] = {"readable": False, "error": redact(e)}
    readable = [name for name, v in evidence.items() if v["readable"]]
    return result("P7", bool(readable), f"readable: {readable or 'none'}", evidence)


# --- F1 and main ------------------------------------------------------------------------

def f1():
    """One Frankfurter request returns NBK USD/KZT rows for weekdays only."""
    start, end = Y - dt.timedelta(days=6), Y                 # R-6..R with R = yesterday; never today or later
    url = ("https://api.frankfurter.dev/v2/rates?providers=nbk&base=USD&quotes=KZT"
           f"&from={start.isoformat()}&to={end.isoformat()}")
    request = urllib.request.Request(url, headers={"User-Agent": "ledger-vs-statement (learning project)"})
    with urllib.request.urlopen(request, timeout=10) as response:
        status, body = response.status, response.read()
    rates = json.loads(body, parse_float=str)                 # rates stay exact text, never float
    passed = (status == 200 and isinstance(rates, list) and len(rates) > 0
              and all(set(r) == {"date", "base", "quote", "rate"} for r in rates)
              and all(r["base"] == "USD" and r["quote"] == "KZT" for r in rates)
              and all(dt.date.fromisoformat(r["date"]).weekday() < 5 for r in rates))
    return result("F1", passed, f"HTTP {status}, {len(rates)} rows for {start}..{end}",
                  {"url": url, "status": status, "rates": rates})


PROBES = {"P1": p1, "P2": p2, "P3": p3, "P4": p4, "P5": p5, "P6": p6, "P7": p7, "F1": f1}
PLAN_B_AWARE = {"P2", "P6"}
NEEDS_TABLE = {"P4", "P5", "P6"}


def table_exists():
    try:
        client.get_table(T)
        return True
    except gexc.NotFound:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="comma-separated probe ids, for example P3,P4")
    parser.add_argument("--plan-b", action="store_true", help="expect a billing-enabled project")
    args = parser.parse_args()
    ids = [p.strip().upper() for p in args.only.split(",")] if args.only else list(PROBES)
    results = []
    for pid in ids:
        if pid in NEEDS_TABLE and not table_exists():
            res = {"id": pid, "status": "SKIP", "detail": "probe.raw_pay missing: P3 did not create it",
                   "evidence": None, "error_text": None}
        else:
            try:
                res = PROBES[pid](args.plan_b) if pid in PLAN_B_AWARE else PROBES[pid]()
            except Exception as e:  # noqa: BLE001 (any error is a FAIL, not a crash)
                res = result(pid, False, f"error: {type(e).__name__}", error_text=redact(e))
        print(redact(f"{pid}  {res['status']}  {res['detail']}"))
        results.append(res)
    out = Path("docs/evidence") / TODAY.isoformat() / "g0_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    earlier = json.loads(out.read_text())["results"] if args.only and out.exists() else []
    doc = {"run_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
           "plan_b": args.plan_b,
           "results": [r for r in earlier if r["id"] not in ids] + results}
    out.write_text(redact(json.dumps(doc, indent=2, default=str)) + "\n")
    print(f"wrote {out}")
    return 0 if all(r["status"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
