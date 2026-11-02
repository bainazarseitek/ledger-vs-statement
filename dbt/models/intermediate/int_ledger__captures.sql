-- One row per captured payment: our revenue ledger with the dates the
-- matcher needs. The LEFT JOIN keeps a payment with an unknown MID visible:
-- its dates come out NULL and the not_null tests fail, where an inner join
-- would drop it silently. The MID's fixed statement offset (+5 KZT, -5 USD)
-- moves the accounting date in both directions (UT1).
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
    date(timestamp_add(e.event_ts, interval m.statement_utc_offset_hours hour)) as expected_accounting_date,
    date_add(
        date(timestamp_add(e.event_ts, interval m.statement_utc_offset_hours hour)),
        interval (m.max_settlement_lag_days + {{ var('statement_grace_days') }}) day
    ) as due_date
from {{ ref('stg_psp__payment_events') }} as e
left join {{ ref('mids') }} as m
    on e.mid = m.mid
where e.event_type = 'payment.captured'
