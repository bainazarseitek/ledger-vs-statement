import logging
import os

from google.cloud import bigquery

MAX_BYTES_BILLED = 1_000_000_000
log = logging.getLogger(__name__)


def host_client() -> bigquery.Client:
    """Host only. Credentials come through ADC: GOOGLE_APPLICATION_CREDENTIALS (the key), or the gcloud file in the fallback."""
    return bigquery.Client(project=os.environ["GCP_PROJECT"], location="US")


def query(client, sql, params=(), *, dry_run=False, use_cache=True) -> bigquery.QueryJob:
    """Every Python query in the project goes through here, Airflow tasks included (client from the hook)."""
    config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        query_parameters=list(params),
        dry_run=dry_run,
        use_query_cache=use_cache and not dry_run,
    )
    job = client.query(sql, job_config=config, location="US")
    if not dry_run:
        job.result()
    log.info("query job=%s bytes_processed=%s bytes_billed=%s cache_hit=%s",
             job.job_id, job.total_bytes_processed, job.total_bytes_billed, job.cache_hit)
    return job


def rows(job) -> list[dict]:
    """Read a query result row by row. No pandas, no Storage Read API."""
    return [dict(row.items()) for row in job.result()]
