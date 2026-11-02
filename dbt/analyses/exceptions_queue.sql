-- The analyst work queue: every open exception, oldest and largest first.
-- Read-only demo query. dbt compiles it (filling in ref()) but never builds it.
-- One row per (payment_id, cause). Data is SYNTHETIC.
select
    e.cause,
    e.mid,
    e.currency,
    e.payment_id,
    e.amount_minor,
    e.cause_date,
    e.age_days,
    e.analyst_action,
    e.event_id,
    e.line_id,
    e.statement_id
from {{ ref('fct_recon_exceptions') }} as e
order by
    e.age_days desc,
    abs(e.amount_minor) desc,
    e.payment_id,
    e.cause
