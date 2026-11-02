{{ config(labels={'data_origin': 'real'}) }}

-- One row per published rate date. A rate date appears in several fetch
-- partitions; the first-seen value is kept, rate_text as a stable tie-break.
-- The text is cast to NUMERIC, never parsed as a float.
select
    f.provider,
    f.base,
    f.quote,
    f.rate_date,
    f.rate_text,
    cast(f.rate_text as numeric) as rate,
    f._arrival_date as first_seen_arrival_date
from {{ source('fx', 'fx_rates') }} as f
cross join {{ ref('stg_recon__as_of') }} as a
where f._arrival_date <= a.as_of_date
qualify row_number() over (
    partition by f.provider, f.base, f.quote, f.rate_date
    order by f._arrival_date, f.rate_text
) = 1
