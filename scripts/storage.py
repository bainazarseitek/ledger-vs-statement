"""Stored bytes per dataset, written to docs/evidence/<UTC date>/storage.json (or --out). Never a headline number."""
import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

DATASETS = ["raw", "raw_dev", "analytics", "analytics_dev", "probe"]
SA_EMAIL = re.compile(r"[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com")
NOTE = "Bytes stored now. The lifetime quota may count every byte ever written, so this is a lower bound."


def redact(text, project):
    return SA_EMAIL.sub("<sa>", str(text)).replace(project, "<project>")


def from_tables(client, dataset):
    from recon.bq import query, rows

    sql = (f"SELECT table_id, row_count, size_bytes, TIMESTAMP_MILLIS(creation_time) AS created, "
           f"TIMESTAMP_MILLIS(last_modified_time) AS last_modified, type FROM `{client.project}.{dataset}.__TABLES__`")
    found = rows(query(client, sql, use_cache=False))
    return {"tables": sum(1 for r in found if r["type"] == 1), "views": sum(1 for r in found if r["type"] == 2),
            "rows": sum(r["row_count"] or 0 for r in found), "logical_bytes": sum(r["size_bytes"] or 0 for r in found)}


def from_api(client, dataset):
    tables = views = n_rows = n_bytes = 0
    for item in client.list_tables(dataset):
        t = client.get_table(item)
        if t.table_type == "VIEW":
            views += 1
        else:
            tables, n_rows, n_bytes = tables + 1, n_rows + (t.num_rows or 0), n_bytes + (t.num_bytes or 0)
    return {"tables": tables, "views": views, "rows": n_rows, "logical_bytes": n_bytes}


def table_storage(client):
    from google.api_core import exceptions as gexc

    from recon.bq import query, rows

    sql = """SELECT table_schema, deleted,
       SUM(total_logical_bytes) AS logical_bytes, SUM(total_physical_bytes) AS physical_bytes,
       SUM(time_travel_physical_bytes) AS time_travel_bytes, SUM(fail_safe_physical_bytes) AS fail_safe_bytes
FROM `region-us`.INFORMATION_SCHEMA.TABLE_STORAGE
WHERE table_schema IN ('raw', 'raw_dev', 'analytics', 'analytics_dev', 'probe')
GROUP BY table_schema, deleted"""
    try:
        return {"readable": True, "rows": rows(query(client, sql, use_cache=False))}
    except gexc.GoogleAPICallError as e:
        return {"readable": False, "error": redact(e, client.project)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="default: docs/evidence/<UTC date>/storage.json")
    args = parser.parse_args()
    from google.api_core import exceptions as gexc

    from recon.bq import host_client

    client = host_client()
    datasets, method = {}, "__TABLES__"
    for ds in DATASETS:
        try:
            datasets[ds] = from_tables(client, ds)
        except gexc.GoogleAPICallError:
            datasets[ds], method = from_api(client, ds), "api"
    now = datetime.now(UTC).replace(microsecond=0)
    doc = {"measured_at_utc": now.isoformat(sep=" "),
           "git_sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
           "method": method, "datasets": datasets,
           "total_logical_bytes": sum(d["logical_bytes"] for d in datasets.values()),
           "table_storage": table_storage(client), "ledger_total_bytes": None, "note": NOTE}
    out = Path(args.out or f"docs/evidence/{now.date().isoformat()}/storage.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(redact(json.dumps(doc, indent=2, sort_keys=True, default=str), client.project) + "\n")
    print(f"storage: {doc['total_logical_bytes']} logical bytes over {len(datasets)} datasets ({method}) -> {out}")


if __name__ == "__main__":
    main()
