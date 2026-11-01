import json
from pathlib import Path

from google.cloud import bigquery

SCHEMA_DIR = Path(__file__).parent / "schemas"
TABLES = ["payment_events", "settlement_lines", "fx_rates"]
STANDARD_NAMES = {"INTEGER": "INT64", "BOOLEAN": "BOOL", "FLOAT": "FLOAT64"}   # the API reports legacy type names


def ensure_tables(client, dataset):
    """Create the dataset in US and the three raw tables from their schema JSON, if missing."""
    ds = bigquery.Dataset(f"{client.project}.{dataset}")
    ds.location = "US"
    ds = client.create_dataset(ds, exists_ok=True)       # returns the existing dataset if it is already there
    if ds.location != "US":
        raise RuntimeError(f"dataset {dataset} is in {ds.location}, expected US")
    for name in TABLES:
        doc = json.loads((SCHEMA_DIR / f"{name}.json").read_text())
        schema = [bigquery.SchemaField.from_api_repr(f) for f in doc["fields"]]   # not schema_from_json: it wants a bare list
        table = bigquery.Table(f"{client.project}.{dataset}.{doc['table']}", schema=schema)
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
