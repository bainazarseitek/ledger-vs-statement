-- One MID-day's bridge: the gap, each dated component, unexplained_minor,
-- and the lines booked or accounted on that day.
-- Read-only demo query. dbt compiles it (filling in ref()) but never builds it.
-- Edit the two literals in params before the demo. Data is SYNTHETIC.
with params as (

    select
        'mid_kzt_01' as mid,
        date '2026-10-21' as day

),

bridge as (

    select
        d.mid,
        d.currency,
        d.recon_date,
        d.as_of_date,
        d.ledger_gross_minor,
        d.statement_gross_minor,
        d.gap_minor,
        d.timing_cutoff_minor,
        d.date_mismatch_minor,
        d.amount_mismatch_minor,
        d.in_transit_minor,
        d.missing_in_statement_minor,
        d.missing_in_ledger_minor,
        d.before_scope_minor,
        d.unexplained_minor
    from {{ ref('fct_recon_daily') }} as d
    inner join params as p
        on d.mid = p.mid
        and d.recon_date = p.day

),

lines as (

    select
        l.mid,
        l.payment_id,
        l.match_status,
        l.date_shift,
        l.primary_reason,
        l.booking_date,
        l.accounting_date,
        l.ledger_amount_minor,
        l.statement_gross_minor,
        l.amount_diff_minor
    from {{ ref('fct_recon_lines') }} as l
    inner join params as p
        on l.mid = p.mid
        and (l.booking_date = p.day or l.accounting_date = p.day)

)

select
    b.mid,
    b.currency,
    b.recon_date,
    b.as_of_date,
    b.ledger_gross_minor,
    b.statement_gross_minor as day_statement_gross_minor,
    b.gap_minor,
    b.timing_cutoff_minor,
    b.date_mismatch_minor,
    b.amount_mismatch_minor,
    b.in_transit_minor,
    b.missing_in_statement_minor,
    b.missing_in_ledger_minor,
    b.before_scope_minor,
    b.unexplained_minor,
    l.payment_id,
    l.match_status,
    l.date_shift,
    l.primary_reason,
    l.booking_date,
    l.accounting_date,
    l.ledger_amount_minor,
    l.statement_gross_minor,
    l.amount_diff_minor
from bridge as b
left join lines as l
    on b.mid = l.mid
order by
    l.primary_reason,
    l.payment_id
