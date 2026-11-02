{{ config(
    materialized='table',
    partition_by={'field': 'recon_date', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['mid']
) }}

-- The matcher. An equality FULL OUTER JOIN on payment_id keeps the
-- one-sided lines, which are the interesting ones. Every status is judged
-- against as_of_date from the loaded data, never the wall clock. Money stays
-- INT64: the fee check uses DIV only.
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
    -- The filter sits here, before the join. After the join it would also
    -- drop every ledger-only line, whose statement columns are NULL.
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

),

classified as (

    select
        t.*,
        coalesce(t.booking_date, date(t.captured_ts)) as recon_date,
        case
            when t.has_ledger and t.has_statement then 'matched'
            when t.has_ledger and t.booking_date < t.scope_start then 'before_scope'
            when t.has_ledger and t.as_of_date < t.due_date then 'in_transit'
            when t.has_ledger then 'missing_in_statement'
            when date(t.captured_ts) < t.scope_start then 'before_scope'
            else 'missing_in_ledger'
        end as match_status,
        case
            when not (t.has_ledger and t.has_statement) then null
            when t.accounting_date = t.booking_date then 'none'
            when t.accounting_date = t.expected_accounting_date then 'timing_cutoff'
            else 'date_mismatch'
        end as date_shift,
        case
            when t.has_ledger and t.has_statement
                then t.ledger_amount_minor - t.statement_gross_minor
        end as amount_diff_minor,
        t.has_ledger and t.has_statement
        and t.ledger_amount_minor - t.statement_gross_minor != 0 as is_amount_mismatch
    from with_terms as t

),

fees as (

    select
        c.*,
        -- + 5000 then DIV rounds half up; + 9999 then DIV is a ceiling.
        div(c.statement_gross_minor * c.fee_bps + 5000, 10000) + c.fee_fixed_minor as expected_fee_minor,
        greatest(c.fee_tol_min_minor, div(c.statement_gross_minor * c.fee_tol_bps + 9999, 10000)) as fee_tolerance_minor,
        c.statement_fee_minor
        - (div(c.statement_gross_minor * c.fee_bps + 5000, 10000) + c.fee_fixed_minor) as fee_variance_minor
    from classified as c

),

flagged as (

    select
        f.*,
        -- A variance equal to the tolerance is within it.
        f.has_statement and f.match_status != 'before_scope'
        and abs(f.fee_variance_minor) > f.fee_tolerance_minor as is_fee_mismatch
    from fees as f

)

select
    g.payment_id,
    g.mid,
    g.currency,
    g.has_ledger,
    g.has_statement,
    g.event_id,
    g.copies_received,
    g.event_ts,
    g.booking_date,
    g.ledger_amount_minor,
    g.expected_accounting_date,
    g.due_date,
    g.line_id,
    g.statement_id,
    g.captured_ts,
    g.accounting_date,
    g.statement_arrival_date,
    g.statement_gross_minor,
    g.statement_fee_minor,
    g.statement_net_minor,
    g.recon_date,
    g.scope_start,
    g.as_of_date,
    g.match_status,
    g.date_shift,
    g.amount_diff_minor,
    g.is_amount_mismatch,
    g.expected_fee_minor,
    g.fee_tolerance_minor,
    g.fee_variance_minor,
    g.is_fee_mismatch,
    -- The first true condition wins, in the precedence of reason_codes.csv.
    case
        when g.match_status = 'missing_in_statement' then 'missing_in_statement'
        when g.match_status = 'missing_in_ledger' then 'missing_in_ledger'
        when g.is_amount_mismatch then 'amount_mismatch'
        when g.is_fee_mismatch then 'fee_mismatch'
        when g.date_shift = 'date_mismatch' then 'date_mismatch'
        when g.match_status = 'in_transit' then 'in_transit'
        when g.date_shift = 'timing_cutoff' then 'timing_cutoff'
        when g.match_status = 'before_scope' then 'before_scope'
        else 'matched'
    end as primary_reason,
    -- FALSE OR NULL is NULL in BigQuery: the coalesce keeps it TRUE or FALSE.
    g.match_status in ('missing_in_statement', 'missing_in_ledger')
    or g.is_amount_mismatch
    or g.is_fee_mismatch
    or coalesce(g.date_shift = 'date_mismatch', false) as is_exception
from flagged as g
