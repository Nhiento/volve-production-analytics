-- Injector well-days, renamed to the project's column standard.
-- Grain: one row per well per day.
select
    cast("DATEPRD" as date)               as inj_date,
    "NPD_WELL_BORE_NAME"                  as well_name,
    cast("ON_STREAM_HRS" as double)       as on_stream_hrs,
    cast("BORE_WI_VOL" as double)         as water_injected,
    cast("UPTIME_PCT" as double)          as uptime_pct,
    cast("INJECTION_RATE_24H" as double)  as injection_rate_24h
from {{ source('processed', 'injection_daily_clean') }}
