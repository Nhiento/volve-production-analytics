-- Where availability was lost, by well and year.
select
    well_name,
    strftime(prod_date, '%Y')                                              as year,
    count(*)                                                               as record_days,
    count(*) filter (where on_stream_hrs = 0)                              as fully_offline_days,
    count(*) filter (where on_stream_hrs > 0 and on_stream_hrs < 24)       as partial_days,
    round(sum(24 - least(coalesce(on_stream_hrs, 0), 24)), 0)              as hours_lost,
    round(avg(uptime_pct), 1)                                              as avg_uptime_pct
from {{ ref('stg_daily_production') }}
group by well_name, year
order by well_name, year
