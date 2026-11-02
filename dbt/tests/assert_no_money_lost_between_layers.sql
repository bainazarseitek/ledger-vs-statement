-- Fails when, for any MID, the matcher's ledger side or statement side
-- holds a different count or sum than its input model. Catches a dropped
-- same-day matched line with equal amounts, which adds 0 to the gap and so
-- passes assert_recon_decomposition_closes. The SALE filter is the
-- matcher's own filter.
with ledger_in as (

    select
        c.mid,
        count(*) as line_count,
        sum(c.amount_minor) as gross_minor
    from {{ ref('int_ledger__captures') }} as c
    group by c.mid

),

ledger_out as (

    select
        l.mid,
        count(*) as line_count,
        sum(l.ledger_amount_minor) as gross_minor
    from {{ ref('fct_recon_lines') }} as l
    where l.has_ledger
    group by l.mid

),

statement_in as (

    select
        s.mid,
        count(*) as line_count,
        sum(s.gross_minor) as gross_minor,
        sum(s.fee_minor) as fee_minor
    from {{ ref('stg_psp__settlement_lines') }} as s
    where s.record_type = 'SALE'
    group by s.mid

),

statement_out as (

    select
        l.mid,
        count(*) as line_count,
        sum(l.statement_gross_minor) as gross_minor,
        sum(l.statement_fee_minor) as fee_minor
    from {{ ref('fct_recon_lines') }} as l
    where l.has_statement
    group by l.mid

),

compared as (

    select
        coalesce(li.mid, lo.mid, si.mid, so.mid) as mid,
        li.line_count as ledger_in_count,
        lo.line_count as ledger_out_count,
        li.gross_minor as ledger_in_gross_minor,
        lo.gross_minor as ledger_out_gross_minor,
        si.line_count as statement_in_count,
        so.line_count as statement_out_count,
        si.gross_minor as statement_in_gross_minor,
        so.gross_minor as statement_out_gross_minor,
        si.fee_minor as statement_in_fee_minor,
        so.fee_minor as statement_out_fee_minor
    from ledger_in as li
    full outer join ledger_out as lo
        on li.mid = lo.mid
    full outer join statement_in as si
        on coalesce(li.mid, lo.mid) = si.mid
    full outer join statement_out as so
        on coalesce(li.mid, lo.mid, si.mid) = so.mid

)

select
    c.mid,
    c.ledger_in_count,
    c.ledger_out_count,
    c.ledger_in_gross_minor,
    c.ledger_out_gross_minor,
    c.statement_in_count,
    c.statement_out_count,
    c.statement_in_gross_minor,
    c.statement_out_gross_minor,
    c.statement_in_fee_minor,
    c.statement_out_fee_minor
from compared as c
where c.ledger_in_count is distinct from c.ledger_out_count
    or c.ledger_in_gross_minor is distinct from c.ledger_out_gross_minor
    or c.statement_in_count is distinct from c.statement_out_count
    or c.statement_in_gross_minor is distinct from c.statement_out_gross_minor
    or c.statement_in_fee_minor is distinct from c.statement_out_fee_minor
