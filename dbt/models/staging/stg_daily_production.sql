-- Producer well-days, renamed to the project's column standard.
-- Grain: one row per well per day.
select
    cast("DATEPRD" as date)          as prod_date,
    "NPD_WELL_BORE_NAME"             as well_name,
    cast("ON_STREAM_HRS" as double)  as on_stream_hrs,
    cast("BORE_OIL_VOL" as double)   as oil_vol,
    cast("BORE_GAS_VOL" as double)   as gas_vol,
    cast("BORE_WAT_VOL" as double)   as water_vol,      -- negative raw values already set to NULL
    cast("UPTIME_PCT" as double)     as uptime_pct,     -- on_stream_hrs / 24 * 100, capped at 100
    cast("WATER_CUT_PCT" as double)  as water_cut_pct,  -- water / (oil + water) * 100
    cast("OIL_RATE_24H" as double)   as oil_rate_24h,
    cast("GAS_RATE_24H" as double)   as gas_rate_24h
from {{ source('processed', 'production_daily_clean') }}
