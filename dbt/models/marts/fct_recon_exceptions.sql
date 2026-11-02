{{ config(materialized='view') }}

-- The analyst work queue: one row per line and cause. A line with two
-- causes (for example an amount difference and a fee overcharge) gives two
-- rows, each with its own signed amount and cause date. A positive amount
-- means the ledger has more, or the PSP overcharged. Out-of-scope lines
-- never enter the queue.
with lines as (

    select
        l.payment_id,
        l.mid,
        l.currency,
        l.match_status,
        l.date_shift,
        l.is_amount_mismatch,
        l.is_fee_mismatch,
        l.ledger_amount_minor,
        l.statement_gross_minor,
        l.amount_diff_minor,
        l.fee_variance_minor,
        l.recon_date,
        l.booking_date,
        l.accounting_date,
        l.event_id,
        l.line_id,
        l.statement_id,
        l.as_of_date
    from {{ ref('fct_recon_lines') }} as l
    where l.match_status != 'before_scope'

),

causes as (

    select
        l.payment_id,
        'missing_in_statement' as cause,
        l.ledger_amount_minor as amount_minor,
        l.booking_date as cause_date
    from lines as l
    where l.match_status = 'missing_in_statement'

    union all

    select
        l.payment_id,
        'missing_in_ledger' as cause,
        -l.statement_gross_minor as amount_minor,
        l.accounting_date as cause_date
    from lines as l
    where l.match_status = 'missing_in_ledger'

    union all

    select
        l.payment_id,
        'amount_mismatch' as cause,
        l.amount_diff_minor as amount_minor,
        l.accounting_date as cause_date
    from lines as l
    where l.is_amount_mismatch

    union all

    select
        l.payment_id,
        'fee_mismatch' as cause,
        l.fee_variance_minor as amount_minor,
        l.accounting_date as cause_date
    from lines as l
    where l.is_fee_mismatch

    union all

    select
        l.payment_id,
        'date_mismatch' as cause,
        l.ledger_amount_minor as amount_minor,
        l.accounting_date as cause_date
    from lines as l
    where l.date_shift = 'date_mismatch'

)

select
    c.payment_id,
    c.cause,
    l.mid,
    l.currency,
    c.amount_minor,
    c.cause_date,
    l.recon_date,
    l.booking_date,
    l.accounting_date,
    date_diff(l.as_of_date, l.recon_date, day) as age_days,
    l.event_id,
    l.line_id,
    l.statement_id,
    r.analyst_action,
    l.as_of_date
from causes as c
inner join lines as l
    on c.payment_id = l.payment_id
left join {{ ref('reason_codes') }} as r
    on c.cause = r.code
