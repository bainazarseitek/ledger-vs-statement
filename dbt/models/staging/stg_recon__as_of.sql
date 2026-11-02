{% if execute %}
  {% if target.name == 'airflow' and var('as_of_date', none) is not none %}
    {{ exceptions.raise_compiler_error("as_of_date is for host dev builds only. Never pass it with --target airflow.") }}
  {% endif %}
  {% if target.name == 'airflow' and env_var('RAW_DATASET', 'raw') != 'raw' %}
    {{ exceptions.raise_compiler_error("Target airflow must read RAW_DATASET=raw.") }}
  {% endif %}
  {% if target.name == 'dev' and env_var('RAW_DATASET', 'raw') != 'raw_dev' %}
    {{ exceptions.raise_compiler_error("Target dev must read RAW_DATASET=raw_dev. Run dbt through make, or export RAW_DATASET=raw_dev.") }}
  {% endif %}
{% endif %}

{%- set as_of_var = var('as_of_date', none) %}

-- One row: the newest and the oldest loaded arrival day of payment_events.
-- Models read "today" from here, never from the wall clock.
with arrivals as (

    select
        e._arrival_date
    from {{ source('psp', 'payment_events') }} as e
    {%- if as_of_var is not none %}
    where e._arrival_date <= date '{{ as_of_var }}'
    {%- endif %}

)

select
    {%- if as_of_var is not none %}
    date '{{ as_of_var }}' as as_of_date,
    {%- else %}
    max(a._arrival_date) as as_of_date,
    {%- endif %}
    min(a._arrival_date) as scope_start
from arrivals as a
