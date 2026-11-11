-- Field totals per month, with field water cut and average producer uptime.
select
    strftime(prod_date, '%Y-%m')                                                  as month,
    count(distinct well_name)                                                     as active_producers,
    round(sum(oil_vol), 0)                                                        as oil_sm3,
    round(sum(gas_vol), 0)                                                        as gas_sm3,
    round(sum(water_vol), 0)                                                      as water_sm3,
    round(100.0 * sum(water_vol) / nullif(sum(oil_vol) + sum(water_vol), 0), 1)   as water_cut_pct,
    round(avg(uptime_pct), 1)                                                     as avg_uptime_pct
from {{ ref('stg_daily_production') }}
group by month
order by month
