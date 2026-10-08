-- Volve Production Analytics: SQLite schema
-- Grain: one row per well per day (facts), one row per wellbore (dimension).
-- Volumes are in Sm3 as reported by Equinor.

DROP VIEW IF EXISTS vw_well_kpis;
DROP VIEW IF EXISTS vw_injector_kpis;
DROP VIEW IF EXISTS vw_field_monthly;
DROP VIEW IF EXISTS vw_water_cut_milestones;
DROP VIEW IF EXISTS vw_downtime_by_well_year;
DROP VIEW IF EXISTS vw_prod_vs_injection;
DROP VIEW IF EXISTS vw_injection_correlation;

DROP TABLE IF EXISTS data_quality_log;
DROP TABLE IF EXISTS daily_production;
DROP TABLE IF EXISTS daily_injection;
DROP TABLE IF EXISTS wells;

-- Dimension: one row per wellbore and role.
-- F-5 and F-1 C appear in both roles, so (well_name, role) is the key.
CREATE TABLE wells (
    well_name   TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('producer', 'injector')),
    first_date  TEXT NOT NULL,
    last_date   TEXT NOT NULL,
    record_days INTEGER NOT NULL,
    PRIMARY KEY (well_name, role)
);

-- Fact: daily oil producer records (WELL_TYPE = 'OP', FLOW_KIND = 'production').
CREATE TABLE daily_production (
    prod_date      TEXT    NOT NULL,          -- YYYY-MM-DD
    well_name      TEXT    NOT NULL,
    on_stream_hrs  REAL,
    oil_vol        REAL,
    gas_vol        REAL,
    water_vol      REAL,                      -- negative values set to NULL in Python
    uptime_pct     REAL,                      -- on_stream_hrs / 24 * 100, capped at 100
    water_cut_pct  REAL,                      -- water / (oil + water) * 100
    oil_rate_24h   REAL,                      -- oil / on_stream_hrs * 24
    gas_rate_24h   REAL,
    PRIMARY KEY (prod_date, well_name)
);

-- Fact: daily water injector records (WELL_TYPE = 'WI', FLOW_KIND = 'injection').
CREATE TABLE daily_injection (
    inj_date           TEXT NOT NULL,
    well_name          TEXT NOT NULL,
    on_stream_hrs      REAL,
    water_injected     REAL,
    uptime_pct         REAL,
    injection_rate_24h REAL,
    PRIMARY KEY (inj_date, well_name)
);

CREATE INDEX idx_prod_well ON daily_production (well_name, prod_date);
CREATE INDEX idx_inj_well  ON daily_injection  (well_name, inj_date);

-- Results of the data-quality checks in 02_checks.sql.
CREATE TABLE data_quality_log (
    check_name  TEXT NOT NULL,
    table_name  TEXT NOT NULL,
    issue_count INTEGER NOT NULL,
    severity    TEXT NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
    description TEXT NOT NULL
);
