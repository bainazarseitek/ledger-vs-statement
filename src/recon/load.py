import hashlib
import io
import json
from datetime import date, timedelta
from pathlib import Path

from google.cloud import bigquery

from recon.config import load_mids

SCHEMA_DIR = Path(__file__).parent / "schemas"
TABLES = ["payment_events", "settlement_lines", "fx_rates"]
STANDARD_NAMES = {"INTEGER": "INT64", "BOOLEAN": "BOOL", "FLOAT": "FLOAT64"}   # the API reports legacy type names
MAX_RUN_AGE_DAYS = 45


def schema_doc(table):
    return json.loads((SCHEMA_DIR / f"{table}.json").read_text())


def schema_fields(doc):
    return [bigquery.SchemaField.from_api_repr(f) for f in doc["fields"]]   # not schema_from_json: it wants a bare list


def ensure_tables(client, dataset):
    """Create the dataset in US and the three raw tables from their schema JSON, if missing."""
    ds = bigquery.Dataset(f"{client.project}.{dataset}")
    ds.location = "US"
    ds = client.create_dataset(ds, exists_ok=True)       # returns the existing dataset if it is already there
    if ds.location != "US":
        raise RuntimeError(f"dataset {dataset} is in {ds.location}, expected US")
    for name in TABLES:
        doc = schema_doc(name)
        table = bigquery.Table(f"{client.project}.{dataset}.{doc['table']}", schema=schema_fields(doc))
        table.time_partitioning = bigquery.TimePartitioning(
            type_=doc["time_partitioning"]["type"], field=doc["time_partitioning"]["field"])
        table.clustering_fields = doc["clustering_fields"]
        table.description = doc["description"]
        table.labels = doc["labels"]
        client.create_table(table, exists_ok=True)       # creates it, or does nothing if it exists
        check_same_shape(client.get_table(table.reference), table)


def check_same_shape(actual, expected):
    """exists_ok=True never changes an existing table, so compare, and fail loudly on any difference."""
    same = (actual.time_partitioning is not None
            and actual.time_partitioning.field == expected.time_partitioning.field
            and actual.time_partitioning.type_ == expected.time_partitioning.type_
            and actual.clustering_fields == expected.clustering_fields
            and columns(actual) == columns(expected))
    if not same:
        raise RuntimeError(f"{actual.table_id} in {actual.dataset_id} exists with a different shape: "
                           "drop it, run make bq-setup, then reload the window")


def columns(table):
    return [(f.name, STANDARD_NAMES.get(f.field_type, f.field_type), f.mode) for f in table.schema]


def check_run_date(run_date: date, world_start: date, today_utc: date) -> None:
    """The one guard on run dates, shared by the host CLI and the DAG's check_window. Never lifted."""
    if run_date < world_start:
        raise ValueError(f"run date {run_date} is before RECON_WORLD_START {world_start}: "
                         "no business existed yet")
    if run_date >= today_utc:
        raise ValueError(f"run date {run_date} has not ended in UTC (today is {today_utc}): "
                         "use yesterday or earlier")
    if run_date < today_utc - timedelta(days=MAX_RUN_AGE_DAYS):
        raise ValueError(f"run date {run_date} is more than {MAX_RUN_AGE_DAYS} days old: its partition "
                         "would expire too soon. Pick a date inside the window. This guard is never lifted")


# --- reading one table's landing files for one arrival day ---

def read_ndjson(path):
    """A missing expected file is an error, not an empty day. A 0-byte file has no rows."""
    if not path.exists():
        raise FileNotFoundError(f"expected landing file is missing: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def fx_rows(run_date, landing_dir):
    """Raw fx_rates rows from the landed Frankfurter body, after checking its sha256 against the meta file."""
    rel = f"fx/provider=nbk/arrival_date={run_date.isoformat()}.json"
    body_path = Path(landing_dir) / rel
    meta_path = body_path.with_name(f"arrival_date={run_date.isoformat()}.meta.json")
    body, meta = body_path.read_bytes(), json.loads(meta_path.read_text())
    if hashlib.sha256(body).hexdigest() != meta["sha256"]:
        raise ValueError(f"{rel} does not match the sha256 in its meta file: a landed FX file was changed")
    rates = json.loads(body, parse_float=str)             # rates stay exact text, never float
    return [{"provider": "nbk", "base": r["base"], "quote": r["quote"], "rate_date": r["date"],
             "rate_text": str(r["rate"]),
             "requested_from": (run_date - timedelta(days=6)).isoformat(), "requested_to": run_date.isoformat(),
             "fetched_at": meta["fetched_at"], "_arrival_date": run_date.isoformat(), "_source_file": rel}
            for r in rates]


def landed_rows(table, run_date, landing_dir):
    r, landing = run_date.isoformat(), Path(landing_dir)
    if table == "payment_events":
        return read_ndjson(landing / f"payment_events/arrival_date={r}/part-000.ndjson")
    if table == "settlement_lines":
        return [row for m in load_mids()                  # exact file names from mids.csv, never a glob
                for row in read_ndjson(landing / f"settlement_lines/arrival_date={r}/mid={m.mid}.ndjson")]
    if table == "fx_rates":
        return fx_rows(run_date, landing_dir)
    raise ValueError(f"unknown raw table {table}")


def load_day(client, dataset, table, run_date, landing_dir):
    """Load every landed row of `table` for arrival day run_date into its one partition."""
    rows = landed_rows(table, run_date, landing_dir)
    r = run_date.isoformat()
    for row in rows:                                      # every check runs before any job
        if row["_arrival_date"] != r:
            raise ValueError(f"{table}: row with _arrival_date {row['_arrival_date']} in the files of run date {r}")
        if table == "payment_events" and row["delivered_ts"][:10] != r:
            raise ValueError(f"{table}: delivery {row['delivery_id']} has DATE(delivered_ts) "
                             f"{row['delivered_ts'][:10]}, run date {r}")
    return load_partition(client, dataset, table, run_date, rows)


def load_partition(client, dataset, table, run_date, rows):
    """Exactly one write for (table, day): a WRITE_TRUNCATE load job, or a partition delete when empty."""
    dest = f"{client.project}.{dataset}.{table}${run_date:%Y%m%d}"     # one partition, no dashes
    if not rows:
        client.delete_table(dest, not_found_ok=True)      # a table operation, not DML
        return {"table": table, "rows": 0, "action": "deleted", "output_bytes": 0, "job_id": None}
    payload = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode()
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=schema_fields(schema_doc(table)),          # the same list as the table
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_NEVER,   # a missing table fails loudly
        max_bad_records=0,                                # one bad row fails the whole job
    )
    job = client.load_table_from_file(io.BytesIO(payload), dest, job_config=job_config, location="US")
    job.result()                                          # waits, raises on error
    if job.output_rows != len(rows):
        raise RuntimeError(f"{dest}: load wrote {job.output_rows} rows, {len(rows)} were landed")
    return {"table": table, "rows": len(rows), "action": "loaded", "output_bytes": job.output_bytes,
            "job_id": job.job_id}
