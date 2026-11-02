{{ config(
    materialized='table',
    partition_by={'field': 'recon_date', 'data_type': 'date', 'granularity': 'day'},
    cluster_by=['mid']
) }}

-- The two-calendar bridge. The gap is computed top-down from the input
-- models (ledger_daily, statement_daily), which never pass through the
-- matcher. The dated components come bottom-up from fct_recon_lines only.
-- unexplained_minor is their difference, so a matcher that loses,
-- duplicates or misdates money makes it non-zero. Fees never enter the
-- gross identity. USD columns are for reporting only.
with as_of as (

    select a.as_of_date
    from {{ ref('stg_recon__as_of') }} as a

),

ledger_daily as (

    select
        c.mid,
        c.currency,
        c.booking_date as day,
        count(*) as ledger_line_count,
        sum(c.amount_minor) as ledger_gross_minor
    from {{ ref('int_ledger__captures') }} as c
    group by c.mid, c.currency, c.booking_date

),

statement_daily as (

    select
        s.mid,
        s.currency,
        s.accounting_date as day,
        count(*) as statement_line_count,
        sum(s.gross_minor) as statement_gross_minor,
        sum(s.fee_minor) as statement_fee_minor,
        sum(s.net_minor) as statement_net_minor
    from {{ ref('stg_psp__settlement_lines') }} as s
    where s.record_type = 'SALE'
    group by s.mid, s.currency, s.accounting_date

),

-- One UNION ALL column, not LEAST(MIN(...), MIN(...)): LEAST returns NULL
-- when any argument is NULL, which would empty the spine.
bounds as (

    select
        min(u.d) as first_day,
        max(u.d) as last_day
    from (
        select c.booking_date as d
        from {{ ref('int_ledger__captures') }} as c
        union all
        select s.accounting_date as d
        from {{ ref('stg_psp__settlement_lines') }} as s
        where s.record_type = 'SALE'
    ) as u

),

-- Every MID times every day, so a day with no activity shows zeros.
spine as (

    select
        m.mid,
        m.currency,
        d as recon_date
    from {{ ref('mids') }} as m
    cross join bounds as b
    cross join unnest(generate_date_array(b.first_day, b.last_day)) as d

),

-- L is the ledger amount on booking date a, S the statement gross on
-- accounting date b. A date shift is +L on a and -L on b, so it nets to
-- zero across the two days; the amount difference L - S lands once, on b.
component_rows as (

    select
        l.mid,
        l.currency,
        l.accounting_date as day,
        'amount_mismatch' as component,
        l.ledger_amount_minor - l.statement_gross_minor as amount
    from {{ ref('fct_recon_lines') }} as l
    where l.match_status = 'matched'

    union all

    select
        l.mid,
        l.currency,
        l.booking_date as day,
        l.date_shift as component,
        l.ledger_amount_minor as amount
    from {{ ref('fct_recon_lines') }} as l
    where l.match_status = 'matched'
        and l.date_shift != 'none'

    union all

    select
        l.mid,
        l.currency,
        l.accounting_date as day,
        l.date_shift as component,
        -l.ledger_amount_minor as amount
    from {{ ref('fct_recon_lines') }} as l
    where l.match_status = 'matched'
        and l.date_shift != 'none'

    union all

    select
        l.mid,
        l.currency,
        l.booking_date as day,
        l.match_status as component,
        l.ledger_amount_minor as amount
    from {{ ref('fct_recon_lines') }} as l
    where l.has_ledger
        and not l.has_statement

    union all

    select
        l.mid,
        l.currency,
        l.accounting_date as day,
        l.match_status as component,
        -l.statement_gross_minor as amount
    from {{ ref('fct_recon_lines') }} as l
    where l.has_statement
        and not l.has_ledger

),

components_daily as (

    select
        r.mid,
        r.currency,
        r.day,
        sum(if(r.component = 'timing_cutoff', r.amount, 0)) as timing_cutoff_minor,
        sum(if(r.component = 'date_mismatch', r.amount, 0)) as date_mismatch_minor,
        sum(if(r.component = 'amount_mismatch', r.amount, 0)) as amount_mismatch_minor,
        sum(if(r.component = 'in_transit', r.amount, 0)) as in_transit_minor,
        sum(if(r.component = 'missing_in_statement', r.amount, 0)) as missing_in_statement_minor,
        sum(if(r.component = 'missing_in_ledger', r.amount, 0)) as missing_in_ledger_minor,
        sum(if(r.component = 'before_scope', r.amount, 0)) as before_scope_minor
    from component_rows as r
    group by r.mid, r.currency, r.day

),

fees_daily as (

    select
        l.mid,
        l.currency,
        l.accounting_date as day,
        sum(l.expected_fee_minor) as expected_fee_minor,
        sum(l.fee_variance_minor) as fee_variance_minor
    from {{ ref('fct_recon_lines') }} as l
    where l.has_statement
    group by l.mid, l.currency, l.accounting_date

),

daily as (

    select
        p.mid,
        p.currency,
        p.recon_date,
        coalesce(ld.ledger_line_count, 0) as ledger_line_count,
        coalesce(sd.statement_line_count, 0) as statement_line_count,
        coalesce(ld.ledger_gross_minor, 0) as ledger_gross_minor,
        coalesce(sd.statement_gross_minor, 0) as statement_gross_minor,
        coalesce(cd.timing_cutoff_minor, 0) as timing_cutoff_minor,
        coalesce(cd.date_mismatch_minor, 0) as date_mismatch_minor,
        coalesce(cd.amount_mismatch_minor, 0) as amount_mismatch_minor,
        coalesce(cd.in_transit_minor, 0) as in_transit_minor,
        coalesce(cd.missing_in_statement_minor, 0) as missing_in_statement_minor,
        coalesce(cd.missing_in_ledger_minor, 0) as missing_in_ledger_minor,
        coalesce(cd.before_scope_minor, 0) as before_scope_minor,
        coalesce(sd.statement_fee_minor, 0) as statement_fee_minor,
        coalesce(sd.statement_net_minor, 0) as statement_net_minor,
        coalesce(fd.expected_fee_minor, 0) as expected_fee_minor,
        coalesce(fd.fee_variance_minor, 0) as fee_variance_minor,
        cu.minor_per_major,
        fx.units_per_usd,
        fx.rate_date as fx_rate_date,
        fx.carry_days as fx_carry_days
    from spine as p
    left join ledger_daily as ld
        on p.mid = ld.mid
        and p.currency = ld.currency
        and p.recon_date = ld.day
    left join statement_daily as sd
        on p.mid = sd.mid
        and p.currency = sd.currency
        and p.recon_date = sd.day
    left join components_daily as cd
        on p.mid = cd.mid
        and p.currency = cd.currency
        and p.recon_date = cd.day
    left join fees_daily as fd
        on p.mid = fd.mid
        and p.currency = fd.currency
        and p.recon_date = fd.day
    left join {{ ref('currencies') }} as cu
        on p.currency = cu.currency
    left join {{ ref('int_fx__usd_rates_daily') }} as fx
        on p.currency = fx.currency
        and p.recon_date = fx.day

),

bridged as (

    select
        y.*,
        y.ledger_gross_minor - y.statement_gross_minor as gap_minor,
        y.ledger_gross_minor - y.statement_gross_minor
        - (
            y.timing_cutoff_minor
            + y.date_mismatch_minor
            + y.amount_mismatch_minor
            + y.in_transit_minor
            + y.missing_in_statement_minor
            + y.missing_in_ledger_minor
            + y.before_scope_minor
        ) as unexplained_minor
    from daily as y

)

select
    b.mid,
    b.currency,
    b.recon_date,
    o.as_of_date,
    b.ledger_line_count,
    b.statement_line_count,
    b.ledger_gross_minor,
    b.statement_gross_minor,
    b.gap_minor,
    b.timing_cutoff_minor,
    b.date_mismatch_minor,
    b.amount_mismatch_minor,
    b.in_transit_minor,
    b.missing_in_statement_minor,
    b.missing_in_ledger_minor,
    b.before_scope_minor,
    b.unexplained_minor,
    b.statement_fee_minor,
    b.statement_net_minor,
    b.expected_fee_minor,
    b.fee_variance_minor,
    b.units_per_usd,
    b.fx_rate_date,
    b.fx_carry_days,
    {{ to_usd('b.ledger_gross_minor', 'b.minor_per_major', 'b.units_per_usd') }} as ledger_gross_usd,
    {{ to_usd('b.statement_gross_minor', 'b.minor_per_major', 'b.units_per_usd') }} as statement_gross_usd,
    -- Converted once from gap_minor, so it can differ by 0.01 from
    -- ledger_gross_usd - statement_gross_usd.
    {{ to_usd('b.gap_minor', 'b.minor_per_major', 'b.units_per_usd') }} as gap_usd
from bridged as b
cross join as_of as o
