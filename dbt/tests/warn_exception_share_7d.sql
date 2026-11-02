{{ config(severity='warn') }}
-- Warns when, for a MID over the last gate_window_days days ending on
-- as_of_date, the break amount is above exception_share_warn of booked
-- gross and there are at least exception_min_count exceptions. The minimum
-- count stops one break on a small day from tripping the gate.
with gated as (

    select
        d.mid,
        sum(d.exception_abs_minor) as abs_sum,
        sum(d.ledger_gross_minor) as gross_sum,
        sum(d.exception_count) as exception_sum
    from {{ ref('fct_recon_daily') }} as d
    cross join {{ ref('stg_recon__as_of') }} as a
    where d.recon_date between
        date_sub(a.as_of_date, interval ({{ var('gate_window_days') }} - 1) day)
        and a.as_of_date
    group by d.mid

)

select
    g.mid,
    g.abs_sum,
    g.gross_sum,
    g.exception_sum,
    safe_divide(cast(g.abs_sum as numeric), cast(g.gross_sum as numeric)) as exception_share
from gated as g
where safe_divide(cast(g.abs_sum as numeric), cast(g.gross_sum as numeric))
        > numeric '{{ var("exception_share_warn") }}'
    and g.exception_sum >= {{ var('exception_min_count') }}
