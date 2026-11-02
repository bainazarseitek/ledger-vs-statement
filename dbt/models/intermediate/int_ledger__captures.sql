-- One row per captured payment: our revenue ledger with the dates the
-- matcher needs. First version for the UT1 red run: the accounting date
-- ignores the MID's statement cut-off.
select
    e.payment_id,
    e.event_id,
    e.order_id,
    e.mid,
    e.currency,
    e.plan_id,
    e.amount_minor,
    e.event_ts,
    e.first_arrival_date,
    e.copies_received,
    date(e.event_ts) as booking_date,
    date(e.event_ts) as expected_accounting_date,
    date_add(
        date(e.event_ts),
        interval (m.max_settlement_lag_days + {{ var('statement_grace_days') }}) day
    ) as due_date
from {{ ref('stg_psp__payment_events') }} as e
left join {{ ref('mids') }} as m
    on e.mid = m.mid
where e.event_type = 'payment.captured'
