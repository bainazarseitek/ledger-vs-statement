-- One row per statement line that arrived on or before as_of_date.
-- No dedup on purpose: a repeated line is a PSP defect and must fail the
-- unique test on line_id.
select
    s.line_id,
    s.statement_id,
    s.mid,
    s.record_type,
    s.payment_id,
    s.captured_ts,
    s.accounting_date,
    s.gross_minor,
    s.fee_minor,
    s.net_minor,
    s.currency,
    s._arrival_date as statement_arrival_date,
    s.is_synthetic
from {{ source('psp', 'settlement_lines') }} as s
cross join {{ ref('stg_recon__as_of') }} as a
where s._arrival_date <= a.as_of_date
