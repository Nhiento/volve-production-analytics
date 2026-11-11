-- Monthly field oil vs. water injection, with producer uptime for filtering out shutdowns.
with prod as (
    select
        strftime(prod_date, '%Y-%m')  as month,
        sum(oil_vol)                  as oil_sm3,
        avg(uptime_pct)               as prod_uptime_pct
    from {{ ref('stg_daily_production') }}
    group by month
),
inj as (
    select
        strftime(inj_date, '%Y-%m')          as month,
        coalesce(sum(water_injected), 0)     as injected_sm3   -- months with only NULLs count as 0, as in the notebook
    from {{ ref('stg_daily_injection') }}
    group by month
)
select
    p.month,
    round(p.oil_sm3, 0)          as oil_sm3,
    round(i.injected_sm3, 0)     as injected_sm3,
    round(p.prod_uptime_pct, 1)  as prod_uptime_pct
from prod p
join inj i on i.month = p.month
order by p.month
