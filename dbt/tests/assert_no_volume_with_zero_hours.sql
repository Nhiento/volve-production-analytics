-- Check 4: oil reported on a day the well was offline.
{{ config(severity = 'warn') }}
select * from {{ ref('stg_daily_production') }}
where on_stream_hrs = 0 and oil_vol > 0
