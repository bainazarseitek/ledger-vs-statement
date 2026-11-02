{{ config(
    materialized='table',
    partition_by={'field': 'recon_date', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['mid']
) }}

-- First version for the UT2 red run: it joins both sides but labels every
-- line matched, with no flags and no fee check.
with as_of as (

    select
        a.as_of_date,
        a.scope_start
    from {{ ref('stg_recon__as_of') }} as a

),

ledger as (

    select
        c.payment_id,
        c.event_id,
        c.mid,
        c.currency,
        c.copies_received,
        c.event_ts,
        c.booking_date,
        c.amount_minor as ledger_amount_minor,
        c.expected_accounting_date,
        c.due_date
    from {{ ref('int_ledger__captures') }} as c

),

statement as (

    select
        s.line_id,
        s.statement_id,
        s.payment_id,
        s.mid,
        s.currency,
        s.captured_ts,
        s.accounting_date,
        s.statement_arrival_date,
        s.gross_minor,
        s.fee_minor,
        s.net_minor
    from {{ ref('stg_psp__settlement_lines') }} as s
    where s.record_type = 'SALE'

),

joined as (

    select
        coalesce(l.payment_id, s.payment_id) as payment_id,
        coalesce(l.mid, s.mid) as mid,
        coalesce(l.currency, s.currency) as currency,
        l.payment_id is not null as has_ledger,
        s.payment_id is not null as has_statement,
        l.event_id,
        l.copies_received,
        l.event_ts,
        l.booking_date,
        l.ledger_amount_minor,
        l.expected_accounting_date,
        l.due_date,
        s.line_id,
        s.statement_id,
        s.captured_ts,
        s.accounting_date,
        s.statement_arrival_date,
        s.gross_minor as statement_gross_minor,
        s.fee_minor as statement_fee_minor,
        s.net_minor as statement_net_minor
    from ledger as l
    full outer join statement as s
        on l.payment_id = s.payment_id

),

with_terms as (

    select
        j.*,
        m.fee_bps,
        m.fee_fixed_minor,
        m.fee_tol_bps,
        m.fee_tol_min_minor,
        o.scope_start,
        o.as_of_date
    from joined as j
    left join {{ ref('mids') }} as m
        on j.mid = m.mid
    cross join as_of as o

)

select
    j.payment_id,
    j.mid,
    j.currency,
    j.has_ledger,
    j.has_statement,
    j.event_id,
    j.copies_received,
    j.event_ts,
    j.booking_date,
    j.ledger_amount_minor,
    j.expected_accounting_date,
    j.due_date,
    j.line_id,
    j.statement_id,
    j.captured_ts,
    j.accounting_date,
    j.statement_arrival_date,
    j.statement_gross_minor,
    j.statement_fee_minor,
    j.statement_net_minor,
    coalesce(j.booking_date, date(j.captured_ts)) as recon_date,
    j.scope_start,
    j.as_of_date,
    'matched' as match_status,
    cast(null as string) as date_shift,
    cast(null as int64) as amount_diff_minor,
    false as is_amount_mismatch,
    cast(null as int64) as expected_fee_minor,
    cast(null as int64) as fee_tolerance_minor,
    cast(null as int64) as fee_variance_minor,
    false as is_fee_mismatch,
    'matched' as primary_reason,
    false as is_exception
from with_terms as j
