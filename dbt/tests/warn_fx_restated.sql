{{ config(severity='warn') }}
-- Warns when one (provider, base, quote, rate_date) has more than one
-- rate_text across fetches in the raw source. A restated rate is an
-- observation about real data, not a pipeline failure: stg_fx__rates keeps
-- the first value either way.
select
    r.provider,
    r.base,
    r.quote,
    r.rate_date,
    count(distinct r.rate_text) as rate_texts,
    string_agg(distinct r.rate_text) as rate_values
from {{ source('fx', 'fx_rates') }} as r
group by r.provider, r.base, r.quote, r.rate_date
having count(distinct r.rate_text) > 1
