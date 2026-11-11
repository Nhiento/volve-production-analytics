-- First month each well's monthly water cut crossed 50%, 80% and 90%.
with monthly as (
    select
        well_name,
        strftime(prod_date, '%Y-%m')                                              as month,
        100.0 * sum(water_vol) / nullif(sum(oil_vol) + sum(water_vol), 0)         as wc
    from {{ ref('stg_daily_production') }}
    group by well_name, month
)
select
    well_name,
    min(month)                                  as first_month,
    min(case when wc >= 50 then month end)      as first_month_wc_50,
    min(case when wc >= 80 then month end)      as first_month_wc_80,
    min(case when wc >= 90 then month end)      as first_month_wc_90
from monthly
group by well_name
order by first_month
