"""The rerun proof: fingerprint every (table, partition) group, then compare two snapshots.

snapshot  writes one JSON file with COUNT, BIT_XOR and a BIGNUMERIC SUM of row hashes per partition,
          plus the marts' as_of_date.
compare   prints one summary line, writes compare.json, and exits 1 on any changed group or as_of_date.
The JSON never contains the project id: tables are named <dataset>.<table>.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

RAW_TABLES = ["payment_events", "settlement_lines", "fx_rates"]      # partition column _arrival_date
MART_TABLES = ["fct_recon_lines", "fct_recon_daily"]                   # partition column recon_date

FINGERPRINT_SQL = """
select {part_col} as part,
       count(*) as n,
       bit_xor(farm_fingerprint(to_json_string(t))) as xor_fp,
       sum(cast(farm_fingerprint(to_json_string(t)) as bignumeric)) as sum_fp
from `{project}.{dataset}.{table}` as t
where {part_col} between @from_date and @to_date
group by part
order by part
"""


def fingerprints(client, dataset, table, part_col, from_date, to_date):
    from google.cloud import bigquery

    from recon.bq import query, rows

    params = [bigquery.ScalarQueryParameter("from_date", "DATE", from_date),
              bigquery.ScalarQueryParameter("to_date", "DATE", to_date)]
    sql = FINGERPRINT_SQL.format(part_col=part_col, project=client.project, dataset=dataset, table=table)
    return [{"table": f"{dataset}.{table}", "part": r["part"].isoformat(), "n": r["n"],
             "xor_fp": r["xor_fp"], "sum_fp": str(r["sum_fp"])}            # BIGNUMERIC kept exact as text
            for r in rows(query(client, sql, params, use_cache=False))]


def snapshot(args):
    from recon.bq import host_client, query, rows

    client = host_client()
    groups = []
    for table in RAW_TABLES:
        groups += fingerprints(client, args.raw_dataset, table, "_arrival_date", args.from_date, args.to_date)
    for table in MART_TABLES:
        groups += fingerprints(client, args.marts_dataset, table, "recon_date", args.from_date, args.to_date)
    as_of = rows(query(client, f"select as_of_date from `{client.project}.{args.marts_dataset}.stg_recon__as_of`",
                       use_cache=False))[0]["as_of_date"]
    doc = {"from": args.from_date.isoformat(), "to": args.to_date.isoformat(), "raw_dataset": args.raw_dataset,
           "marts_dataset": args.marts_dataset, "as_of_date": as_of.isoformat(), "groups": groups}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(f"snapshot: {len(groups)} (table, partition) groups, {sum(g['n'] for g in groups)} rows, "
          f"as_of {doc['as_of_date']} -> {out}")


def compare(args):
    before, after = json.loads(Path(args.before).read_text()), json.loads(Path(args.after).read_text())
    key = lambda g: (g["table"], g["part"])
    b, a = {key(g): g for g in before["groups"]}, {key(g): g for g in after["groups"]}
    changed = [{"table": k[0], "part": k[1], "before": b[k], "after": a[k]} for k in sorted(b.keys() & a.keys())
               if (b[k]["n"], b[k]["xor_fp"], b[k]["sum_fp"]) != (a[k]["n"], a[k]["xor_fp"], a[k]["sum_fp"])]
    only_before = [{"table": k[0], "part": k[1]} for k in sorted(b.keys() - a.keys())]
    only_after = [{"table": k[0], "part": k[1]} for k in sorted(a.keys() - b.keys())]
    identical = len(b.keys() & a.keys()) - len(changed)
    as_of_same = before["as_of_date"] == after["as_of_date"]
    ok = not changed and not only_before and not only_after and as_of_same
    rows_total = sum(g["n"] for g in after["groups"])
    if as_of_same:
        summary = f"{identical} of {len(b)} (table, partition) groups identical, {rows_total} rows, as_of {after['as_of_date']} in both"
    else:
        summary = (f"{identical} of {len(b)} (table, partition) groups identical, {rows_total} rows, "
                   f"as_of changed from {before['as_of_date']} to {after['as_of_date']}")
    result = {"identical": ok, "summary": summary, "groups_before": len(b), "groups_after": len(a),
              "groups_identical": identical, "rows": rows_total, "as_of_before": before["as_of_date"],
              "as_of_after": after["as_of_date"], "changed": changed, "only_before": only_before,
              "only_after": only_after, "before_file": Path(args.before).name, "after_file": Path(args.after).name}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(summary)
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("snapshot", help="fingerprint every partition group into a JSON file")
    s.add_argument("--out", required=True)
    s.add_argument("--from", dest="from_date", required=True, type=date.fromisoformat)
    s.add_argument("--to", dest="to_date", required=True, type=date.fromisoformat)
    s.add_argument("--raw-dataset", default="raw")
    s.add_argument("--marts-dataset", default="analytics")
    c = sub.add_parser("compare", help="compare two snapshots; exit 1 on any change")
    c.add_argument("--before", required=True)
    c.add_argument("--after", required=True)
    c.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        snapshot(args)
        return 0
    return compare(args)


if __name__ == "__main__":
    sys.exit(main())
