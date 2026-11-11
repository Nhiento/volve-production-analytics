-- Check 5: under 2 on-stream hours, scaling to 24 h gives unrealistic rates.
-- The marts already ignore these days when averaging rates; this reports how many.
{{ config(severity = 'warn') }}
select * from {{ ref('stg_daily_production') }}
where on_stream_hrs > 0 and on_stream_hrs < 2 and oil_vol > 0
