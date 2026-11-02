-- Fails when two deliveries of one event_id in the raw source differ in a
-- business field. Dedup keeps the first delivery, which is only safe if
-- every copy agrees. Reads all raw rows, not only those up to as_of_date.
select
    e.event_id,
    count(*) as deliveries,
    count(distinct e.payment_id) as payment_ids,
    count(distinct e.mid) as mids,
    count(distinct e.amount_minor) as amounts,
    count(distinct e.currency) as currencies,
    count(distinct e.event_ts) as event_timestamps,
    count(distinct e.event_type) as event_types
from {{ source('psp', 'payment_events') }} as e
group by e.event_id
having count(distinct e.payment_id) > 1
    or count(distinct e.mid) > 1
    or count(distinct e.amount_minor) > 1
    or count(distinct e.currency) > 1
    or count(distinct e.event_ts) > 1
    or count(distinct e.event_type) > 1
