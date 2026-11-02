-- One row per webhook event. Redeliveries (D1) are removed here: the
-- earliest delivery is kept, ties broken by delivery_id so reruns keep the
-- same copy. The as-of filter runs first (WHERE), then the windows, then
-- QUALIFY, so copies_received counts every copy loaded up to as_of_date.
select
    e.event_id,
    e.event_type,
    e.payment_id,
    e.order_id,
    e.mid,
    e.plan_id,
    e.amount_minor,
    e.currency,
    e.event_ts,
    e.delivery_id as first_delivery_id,
    e.delivered_ts as first_delivered_ts,
    e._arrival_date as first_arrival_date,
    count(*) over (partition by e.event_id) as copies_received,
    e.is_synthetic
from {{ source('psp', 'payment_events') }} as e
cross join {{ ref('stg_recon__as_of') }} as a
where e._arrival_date <= a.as_of_date
qualify row_number() over (
    partition by e.event_id
    order by e.delivered_ts, e.delivery_id
) = 1
