-- Volve Production Analytics: analytical views

-- 1. Producer KPIs per well.
--    Water cut is volume-weighted (total water / total liquid), which differs
--    from the notebook's average of daily ratios. Both are reported.
CREATE VIEW vw_well_kpis AS
SELECT
    well_name,
    MIN(prod_date)                                        AS first_date,
    MAX(prod_date)                                        AS last_date,
    ROUND(SUM(oil_vol), 0)                                AS total_oil_sm3,
    ROUND(SUM(gas_vol), 0)                                AS total_gas_sm3,
    ROUND(SUM(water_vol), 0)                              AS total_water_sm3,
    ROUND(100.0 * SUM(oil_vol) / (SELECT SUM(oil_vol) FROM daily_production), 1)
                                                          AS share_of_field_oil_pct,
    ROUND(AVG(uptime_pct), 1)                             AS avg_uptime_pct,
    ROUND(100.0 * SUM(water_vol) / (SUM(oil_vol) + SUM(water_vol)), 1)
                                                          AS water_cut_weighted_pct,
    ROUND(AVG(water_cut_pct), 1)                          AS water_cut_daily_avg_pct,
    ROUND(AVG(CASE WHEN on_stream_hrs >= 2 THEN oil_rate_24h END), 0)
                                                          AS avg_oil_rate_sm3_day
FROM daily_production
GROUP BY well_name
ORDER BY total_oil_sm3 DESC;

-- 2. Injector KPIs per well.
CREATE VIEW vw_injector_kpis AS
SELECT
    well_name,
    ROUND(SUM(water_injected), 0)                         AS total_injected_sm3,
    ROUND(AVG(uptime_pct), 1)                             AS avg_uptime_pct,
    ROUND(AVG(CASE WHEN on_stream_hrs >= 2 THEN injection_rate_24h END), 0)
                                                          AS avg_injection_rate_sm3_day,
    SUM(CASE WHEN on_stream_hrs = 0 THEN 1 ELSE 0 END)    AS zero_on_stream_days
FROM daily_injection
GROUP BY well_name
ORDER BY total_injected_sm3 DESC;

-- 3. Field-level monthly totals with field water cut and uptime.
CREATE VIEW vw_field_monthly AS
SELECT
    substr(prod_date, 1, 7)                               AS month,
    COUNT(DISTINCT well_name)                             AS active_producers,
    ROUND(SUM(oil_vol), 0)                                AS oil_sm3,
    ROUND(SUM(gas_vol), 0)                                AS gas_sm3,
    ROUND(SUM(water_vol), 0)                              AS water_sm3,
    ROUND(100.0 * SUM(water_vol) / NULLIF(SUM(oil_vol) + SUM(water_vol), 0), 1)
                                                          AS water_cut_pct,
    ROUND(AVG(uptime_pct), 1)                             AS avg_uptime_pct
FROM daily_production
GROUP BY month
ORDER BY month;

-- 4. First month each well's monthly water cut crossed 50%, 80% and 90%.
CREATE VIEW vw_water_cut_milestones AS
WITH monthly AS (
    SELECT well_name,
           substr(prod_date, 1, 7) AS month,
           100.0 * SUM(water_vol) / NULLIF(SUM(oil_vol) + SUM(water_vol), 0) AS wc
    FROM daily_production
    GROUP BY well_name, month
)
SELECT
    well_name,
    MIN(month)                                            AS first_month,
    MIN(CASE WHEN wc >= 50 THEN month END)                AS first_month_wc_50,
    MIN(CASE WHEN wc >= 80 THEN month END)                AS first_month_wc_80,
    MIN(CASE WHEN wc >= 90 THEN month END)                AS first_month_wc_90
FROM monthly
GROUP BY well_name
ORDER BY first_month;

-- 5. Downtime by well and year: where availability was lost.
CREATE VIEW vw_downtime_by_well_year AS
SELECT
    well_name,
    substr(prod_date, 1, 4)                               AS year,
    COUNT(*)                                              AS record_days,
    SUM(CASE WHEN on_stream_hrs = 0 THEN 1 ELSE 0 END)    AS fully_offline_days,
    SUM(CASE WHEN on_stream_hrs > 0 AND on_stream_hrs < 24 THEN 1 ELSE 0 END)
                                                          AS partial_days,
    ROUND(SUM(24 - MIN(COALESCE(on_stream_hrs, 0), 24)), 0)
                                                          AS hours_lost,
    ROUND(AVG(uptime_pct), 1)                             AS avg_uptime_pct
FROM daily_production
GROUP BY well_name, year
ORDER BY well_name, year;

-- 6. Monthly field oil vs. water injection, with field uptime for filtering.
CREATE VIEW vw_prod_vs_injection AS
WITH prod AS (
    SELECT substr(prod_date, 1, 7) AS month,
           SUM(oil_vol)            AS oil_sm3,
           AVG(uptime_pct)         AS prod_uptime_pct
    FROM daily_production
    GROUP BY month
),
inj AS (
    SELECT substr(inj_date, 1, 7)  AS month,
           COALESCE(SUM(water_injected), 0) AS injected_sm3   -- months with only NULLs count as 0, as in the notebook
    FROM daily_injection
    GROUP BY month
)
SELECT p.month,
       ROUND(p.oil_sm3, 0)          AS oil_sm3,
       ROUND(i.injected_sm3, 0)     AS injected_sm3,
       ROUND(p.prod_uptime_pct, 1)  AS prod_uptime_pct
FROM prod p
JOIN inj i ON i.month = p.month
ORDER BY p.month;

-- 7. Pearson correlation of monthly oil vs. injection, three ways:
--    all_months         levels, every month (matches the notebook's 0.55)
--    uptime_ge_90       levels, only months with average producer uptime >= 90%
--                       (tests whether shutdowns alone created the link)
--    monthly_changes    month-over-month changes (removes the shared long-term
--                       trend, so two series that both just decline over the
--                       years no longer correlate for that reason alone)
CREATE VIEW vw_injection_correlation AS
WITH changes AS (
    SELECT oil_sm3      - LAG(oil_sm3)      OVER (ORDER BY month) AS d_oil,
           injected_sm3 - LAG(injected_sm3) OVER (ORDER BY month) AS d_inj
    FROM vw_prod_vs_injection
),
base AS (
    SELECT 'all_months' AS sample, oil_sm3 AS x, injected_sm3 AS y
    FROM vw_prod_vs_injection
    UNION ALL
    SELECT 'uptime_ge_90', oil_sm3, injected_sm3
    FROM vw_prod_vs_injection
    WHERE prod_uptime_pct >= 90
    UNION ALL
    SELECT 'monthly_changes', d_oil, d_inj
    FROM changes
    WHERE d_oil IS NOT NULL
),
stats AS (
    SELECT sample,
           COUNT(*) AS n,
           AVG(x) AS mx, AVG(y) AS my,
           AVG(x * x) AS mxx, AVG(y * y) AS myy, AVG(x * y) AS mxy
    FROM base
    GROUP BY sample
)
SELECT sample,
       n AS months,
       ROUND((mxy - mx * my) / (sqrt(mxx - mx * mx) * sqrt(myy - my * my)), 2)
           AS pearson_r
FROM stats;
