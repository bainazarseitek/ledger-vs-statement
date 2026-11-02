-- Fails when a day in [scope_start, as_of_date] has no payment_events
-- partition, or a MID has no statement lines on a day in
-- (scope_start, as_of_date]. The first day is excluded for statements,
-- because statements arrive 1 or 2 days after the accounting date.
with spine as (

    select
        d as arrival_date,
        a.scope_start
    from {{ ref('stg_recon__as_of') }} as a
    cross join unnest(generate_date_array(a.scope_start, a.as_of_date)) as d

),

event_days as (

    select distinct
        e._arrival_date
    from {{ source('psp', 'payment_events') }} as e

),

statement_days as (

    select distinct
        s.mid,
        s._arrival_date
    from {{ source('psp', 'settlement_lines') }} as s

),

missing_events as (

    select
        'payment_events' as source_table,
        sp.arrival_date,
        cast(null as string) as mid
    from spine as sp
    left join event_days as ed
        on sp.arrival_date = ed._arrival_date
    where ed._arrival_date is null

),

missing_statements as (

    select
        'settlement_lines' as source_table,
        sp.arrival_date,
        m.mid
    from spine as sp
    cross join {{ ref('mids') }} as m
    left join statement_days as sd
        on sp.arrival_date = sd._arrival_date
        and m.mid = sd.mid
    where sp.arrival_date > sp.scope_start
        and sd._arrival_date is null

)

select me.source_table, me.arrival_date, me.mid from missing_events as me
union all
select ms.source_table, ms.arrival_date, ms.mid from missing_statements as ms
