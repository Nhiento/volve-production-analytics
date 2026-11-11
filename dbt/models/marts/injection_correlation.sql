-- Pearson correlation of monthly oil vs. injection, three ways:
--   all_months       every month (matches the notebook's 0.55)
--   uptime_ge_90     only months with average producer uptime >= 90%
--                    (tests whether field shutdowns alone created the link)
--   monthly_changes  month-over-month changes (removes the shared long-term decline)
with monthly as (
    select * from {{ ref('prod_vs_injection') }}
),
changes as (
    select
        oil_sm3      - lag(oil_sm3)      over (order by month) as d_oil,
        injected_sm3 - lag(injected_sm3) over (order by month) as d_inj
    from monthly
),
samples as (
    select 'all_months' as sample, oil_sm3 as x, injected_sm3 as y from monthly
    union all
    select 'uptime_ge_90', oil_sm3, injected_sm3 from monthly where prod_uptime_pct >= 90
    union all
    select 'monthly_changes', d_oil, d_inj from changes where d_oil is not null
)
select
    sample,
    count(*)               as months,
    round(corr(x, y), 2)   as pearson_r
from samples
group by sample
