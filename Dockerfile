FROM apache/airflow:3.3.2
# dbt gets its own venv: dbt-bigquery 1.12.1 needs google-cloud-storage<3.2 and dbt-core 1.12.6
# needs pathspec<1.1, while the Airflow 3.3.2 constraints pin google-cloud-storage 3.14.1 and pathspec 1.1.1.
COPY docker/requirements-dbt.txt /tmp/requirements-dbt.txt
RUN python -m venv /opt/airflow/dbt_venv \
 && /opt/airflow/dbt_venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt \
 && /opt/airflow/dbt_venv/bin/dbt --version
