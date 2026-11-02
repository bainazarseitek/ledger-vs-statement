{{ config(labels={'data_origin': 'real'}) }}

-- One row per (currency, day): a rate for every calendar day, so reporting
-- can convert any MID-day to USD. NBK rates come on weekdays only, so a day
-- with no rate carries the last published one forward and records its
-- rate_date and carry_days. This is a project convention, not NBK's official
-- rate for that day. USD gets identity rows with units_per_usd = 1.
with as_of as (

    select a.as_of_date
    from {{ ref('stg_recon__as_of') }} as a

),

rates as (

    select
        r.quote as currency,
        r.provider,
        r.rate_date,
        r.rate
    from {{ ref('stg_fx__rates') }} as r
    where r.provider = 'nbk'
        and r.base = 'USD'

),

spine as (

    select
        b.currency,
        d as day
    from (
        select
            r.currency,
            min(r.rate_date) as first_rate_date
        from rates as r
        group by r.currency
    ) as b
    cross join as_of as a
    cross join unnest(generate_date_array(b.first_rate_date, a.as_of_date)) as d

),

carried as (

    select
        s.currency,
        s.day,
        'nbk' as provider,
        last_value(r.rate ignore nulls) over w as units_per_usd,
        last_value(r.rate_date ignore nulls) over w as rate_date
    from spine as s
    left join rates as r
        on s.currency = r.currency
        and s.day = r.rate_date
    window w as (
        partition by s.currency
        order by s.day
        rows between unbounded preceding and current row
    )

),

usd as (

    select
        'USD' as currency,
        d as day,
        'identity' as provider,
        numeric '1' as units_per_usd,
        d as rate_date
    from (select min(r.rate_date) as first_rate_date from rates as r) as b
    cross join as_of as a
    cross join unnest(generate_date_array(b.first_rate_date, a.as_of_date)) as d

)

select
    c.currency,
    c.day,
    c.provider,
    c.units_per_usd,
    c.rate_date,
    date_diff(c.day, c.rate_date, day) as carry_days
from carried as c

union all

select
    u.currency,
    u.day,
    u.provider,
    u.units_per_usd,
    u.rate_date,
    0 as carry_days
from usd as u
