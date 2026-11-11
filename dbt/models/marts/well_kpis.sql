-- Producer KPIs per well.
-- Water cut is volume-weighted (total water / total liquid), which differs from the
-- notebook's average of daily ratios. Both are reported.
with prod as (
    select * from {{ ref('stg_daily_production') }}
),
field as (
    select sum(oil_vol) as field_oil from prod
)
select
    well_name,
    min(prod_date)                                                     as first_date,
    max(prod_date)                                                     as last_date,
    round(sum(oil_vol), 0)                                             as total_oil_sm3,
    round(sum(gas_vol), 0)                                             as total_gas_sm3,
    round(sum(water_vol), 0)                                           as total_water_sm3,
    round(100.0 * sum(oil_vol) / any_value(field.field_oil), 1)        as share_of_field_oil_pct,
    round(avg(uptime_pct), 1)                                          as avg_uptime_pct,
    round(100.0 * sum(water_vol) / (sum(oil_vol) + sum(water_vol)), 1) as water_cut_weighted_pct,
    round(avg(water_cut_pct), 1)                                       as water_cut_daily_avg_pct,
    -- under 2 on-stream hours the 24 h rate is unrealistic, so those days are left out
    round(avg(case when on_stream_hrs >= 2 then oil_rate_24h end), 0)  as avg_oil_rate_sm3_day
from prod
cross join field
group by well_name
order by total_oil_sm3 desc
