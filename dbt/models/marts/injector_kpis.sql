-- Injector KPIs per well.
select
    well_name,
    round(sum(water_injected), 0)                                           as total_injected_sm3,
    round(avg(uptime_pct), 1)                                               as avg_uptime_pct,
    round(avg(case when on_stream_hrs >= 2 then injection_rate_24h end), 0) as avg_injection_rate_sm3_day,
    count(*) filter (where on_stream_hrs = 0)                               as zero_on_stream_days
from {{ ref('stg_daily_injection') }}
group by well_name
order by total_injected_sm3 desc
