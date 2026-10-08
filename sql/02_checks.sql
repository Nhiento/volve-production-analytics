-- Volve Production Analytics: data-quality checks
-- Each check writes one row to data_quality_log.
-- error   = the data breaks a rule and would corrupt results
-- warning = valid but needs care when interpreting
-- info    = context worth knowing

DELETE FROM data_quality_log;

-- 1. Validity: duplicate well-days (the primary key should already prevent these)
INSERT INTO data_quality_log
SELECT 'duplicate_well_days', 'daily_production',
       COUNT(*) - COUNT(DISTINCT prod_date || well_name), 'error',
       'Rows sharing the same well and date'
FROM daily_production;

-- 2. Validity: negative volumes
INSERT INTO data_quality_log
SELECT 'negative_volumes', 'daily_production', COUNT(*), 'error',
       'Oil, gas or water volume below zero'
FROM daily_production
WHERE oil_vol < 0 OR gas_vol < 0 OR water_vol < 0;

-- 3. Validity: on-stream hours outside 0-24
--    The raw data has a few 25-hour days (likely daylight-saving clock changes).
INSERT INTO data_quality_log
SELECT 'on_stream_hours_over_24', 'daily_production', COUNT(*), 'warning',
       'On-stream hours above 24 (uptime is capped at 100%)'
FROM daily_production
WHERE on_stream_hrs > 24;

-- 4. Validity: production reported with zero on-stream hours
INSERT INTO data_quality_log
SELECT 'volume_with_zero_hours', 'daily_production', COUNT(*), 'warning',
       'Oil produced on a day with 0 on-stream hours'
FROM daily_production
WHERE on_stream_hrs = 0 AND oil_vol > 0;

-- 5. Validity: inflated rates from very short run times
--    Normalizing a few minutes of flow to 24 hours produces unrealistic rates.
INSERT INTO data_quality_log
SELECT 'rate_from_short_runtime', 'daily_production', COUNT(*), 'warning',
       'Oil rate computed from less than 2 on-stream hours'
FROM daily_production
WHERE on_stream_hrs > 0 AND on_stream_hrs < 2 AND oil_vol > 0;

-- 6. Completeness: missing water volume
INSERT INTO data_quality_log
SELECT 'missing_water_volume', 'daily_production', COUNT(*), 'warning',
       'Water volume is NULL (negative raw values were set to NULL)'
FROM daily_production
WHERE water_vol IS NULL;

-- 7. Completeness: gaps in each well's daily timeline
INSERT INTO data_quality_log
SELECT 'date_gaps', 'daily_production', COUNT(*), 'warning',
       'Days where the next record for a well is more than 1 day later'
FROM (
    SELECT julianday(LEAD(prod_date) OVER (PARTITION BY well_name ORDER BY prod_date))
           - julianday(prod_date) AS gap_days
    FROM daily_production
)
WHERE gap_days > 1;

-- 8. Completeness: missing on-stream hours on injectors
INSERT INTO data_quality_log
SELECT 'missing_on_stream_hours', 'daily_injection', COUNT(*), 'warning',
       'Injection days with no on-stream hours recorded'
FROM daily_injection
WHERE on_stream_hrs IS NULL;

-- 9. Validity: negative injection volumes
INSERT INTO data_quality_log
SELECT 'negative_injection', 'daily_injection', COUNT(*), 'error',
       'Injected water volume below zero'
FROM daily_injection
WHERE water_injected < 0;

-- 10. Info: days fully offline (0 on-stream hours)
INSERT INTO data_quality_log
SELECT 'fully_offline_days', 'daily_production', COUNT(*), 'info',
       'Producer days with 0 on-stream hours'
FROM daily_production
WHERE on_stream_hrs = 0;

SELECT * FROM data_quality_log ORDER BY
    CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END, check_name;
