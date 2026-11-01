"""smoke_bigquery: manual health check. Writes only to dataset probe."""

from __future__ import annotations

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task


@dag(
    dag_id="smoke_bigquery",
    schedule=None,
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["portfolio", "smoke"],
    doc_md=__doc__,
)
def smoke_bigquery():
    @task(retries=0)
    def bq_load_one_row() -> dict:
        import datetime as dt
        import io
        import json

        from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
        from google.cloud import bigquery

        hook = BigQueryHook(gcp_conn_id="google_cloud_default", use_legacy_sql=False, location="US")
        client = hook.get_client(project_id=hook.project_id, location="US")
        yesterday = dt.datetime.now(dt.UTC).date() - dt.timedelta(days=1)   # wall clock: allowed only in this DAG
        table_id = f"{hook.project_id}.probe.smoke"

        schema = [bigquery.SchemaField("d", "DATE", mode="REQUIRED"), bigquery.SchemaField("x", "INT64")]
        table = bigquery.Table(table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(type_=bigquery.TimePartitioningType.DAY, field="d")
        client.create_table(table, exists_ok=True)

        partition = f"{yesterday:%Y%m%d}"
        payload = (json.dumps({"d": yesterday.isoformat(), "x": 1}) + "\n").encode()
        config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        job = client.load_table_from_file(io.BytesIO(payload), f"{table_id}${partition}",
                                          job_config=config, location="US")
        job.result()
        assert job.output_rows == 1, f"load wrote {job.output_rows} rows, expected 1"

        count_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=1_000_000_000,
            query_parameters=[bigquery.ScalarQueryParameter("d", "DATE", yesterday)],
        )
        result = client.query(f"SELECT COUNT(*) AS n FROM `{table_id}` WHERE d = @d",
                              job_config=count_config, location="US").result()
        n = next(iter(result))["n"]
        assert n == 1, f"partition {partition} holds {n} rows, expected 1"
        print(f"probe.smoke${partition} holds {n} row")
        return {"partition": partition, "rows": n, "job_id": job.job_id}

    dbt_debug = BashOperator(
        task_id="dbt_debug",
        bash_command="cd /opt/airflow/dbt && /opt/airflow/dbt_venv/bin/dbt debug --target airflow",
        append_env=True,
    )

    bq_load_one_row() >> dbt_debug


smoke_bigquery()
