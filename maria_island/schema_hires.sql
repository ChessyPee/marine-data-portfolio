-- Maria Island hi-res mooring schema.
-- Two real instruments per mooring deployment (20m and 85m nominal depth)
-- let this dataset answer the stratification question directly, unlike
-- the monthly single-series project. Anomaly detection (spikes,
-- deployment-boundary artifacts) is done here in SQL, not in
-- clean_hires.py, so IMOS's own quality_control flags stay the source of
-- truth and any extra logic sits visibly on top of them.

DROP VIEW IF EXISTS vw_stratification CASCADE;
DROP VIEW IF EXISTS vw_warm_spell_groups_hires CASCADE;
DROP VIEW IF EXISTS vw_daily_temp_analysis CASCADE;
DROP VIEW IF EXISTS vw_reading_flags CASCADE;
DROP TABLE IF EXISTS fact_sensor_reading CASCADE;
DROP TABLE IF EXISTS dim_sensor_deployment CASCADE;

-- One row per real instrument-deployment: a mooring deployment_code has
-- two instruments (20m, 85m), confirmed unique together by profiling the
-- raw file -- deployment_code alone is NOT a unique key here.
CREATE TABLE dim_sensor_deployment (
    deployment_id     SERIAL PRIMARY KEY,
    deployment_code    TEXT NOT NULL,
    nominal_depth_m      NUMERIC(5,1) NOT NULL,
    deployment_start      TIMESTAMPTZ NOT NULL,
    deployment_end        TIMESTAMPTZ NOT NULL,
    CHECK (deployment_end > deployment_start),
    UNIQUE (deployment_code, nominal_depth_m)
);

CREATE TABLE fact_sensor_reading (
    reading_id     BIGSERIAL PRIMARY KEY,
    deployment_id   INT NOT NULL REFERENCES dim_sensor_deployment(deployment_id),
    "timestamp"       TIMESTAMPTZ NOT NULL,
    depth_m             NUMERIC(6,3),
    depth_qc              SMALLINT,
    temp_c                  NUMERIC(5,2) NOT NULL CHECK (temp_c BETWEEN 0 AND 30),
    temp_qc                   SMALLINT,
    psal                        NUMERIC(6,3) CHECK (psal BETWEEN 0 AND 40),
    psal_qc                       SMALLINT,
    UNIQUE (deployment_id, "timestamp")
);

CREATE INDEX idx_reading_ts ON fact_sensor_reading ("timestamp");
CREATE INDEX idx_reading_deployment ON fact_sensor_reading (deployment_id);

-- Rate-of-change spike flag, per deployment. Only looks at readings IMOS
-- itself already called good/probably-good (temp_qc IN (1,2)) -- no point
-- re-diagnosing what temp_qc = 4 already tells you is a fault.
CREATE OR REPLACE VIEW vw_reading_flags AS
SELECT
    r.*,
    d.deployment_code,
    d.nominal_depth_m,
    temp_c - LAG(temp_c) OVER (
        PARTITION BY r.deployment_id ORDER BY r."timestamp"
    ) AS delta_c,
    ABS(temp_c - LAG(temp_c) OVER (
        PARTITION BY r.deployment_id ORDER BY r."timestamp"
    )) > 3 AS flag_spike,
    -- Deployment-boundary caution: within 6 hours of the instrument going
    -- in/out of the water, a step change is more likely a calibration
    -- artifact than a real event -- flag it, don't delete it.
    (r."timestamp" <= d.deployment_start + INTERVAL '6 hours'
     OR r."timestamp" >= d.deployment_end - INTERVAL '6 hours') AS flag_boundary
FROM fact_sensor_reading r
JOIN dim_sensor_deployment d ON d.deployment_id = r.deployment_id
WHERE r.temp_qc IN (1, 2);

-- Daily aggregation -> climatology (by day-of-year) -> anomaly, per depth.
-- Same describe -> diagnose shape as the monthly project's
-- vw_warm_spell_groups, but at the two real depths in this dataset.
CREATE OR REPLACE VIEW vw_daily_temp_analysis AS
WITH daily AS (
    SELECT
        nominal_depth_m,
        date_trunc('day', "timestamp") AS day,
        AVG(temp_c) AS temp_c
    FROM vw_reading_flags
    WHERE NOT flag_spike AND NOT flag_boundary
    GROUP BY nominal_depth_m, day
),
climatology AS (
    SELECT
        nominal_depth_m,
        EXTRACT(DOY FROM day) AS day_of_year,
        AVG(temp_c) AS clim_mean,
        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY temp_c) AS clim_p90
    FROM daily
    GROUP BY nominal_depth_m, EXTRACT(DOY FROM day)
)
SELECT
    d.nominal_depth_m,
    d.day,
    d.temp_c,
    c.clim_mean,
    c.clim_p90,
    d.temp_c > c.clim_p90 AS is_warm_day
FROM daily d
JOIN climatology c
    ON c.nominal_depth_m = d.nominal_depth_m
   AND c.day_of_year = EXTRACT(DOY FROM d.day)
ORDER BY d.nominal_depth_m, d.day;

-- "Gaps and islands": group consecutive warm days (3+) into spells, per
-- depth -- the hi-res analog of the monthly project's warm-spell view.
CREATE OR REPLACE VIEW vw_warm_spell_groups_hires AS
WITH flagged AS (
    SELECT
        nominal_depth_m,
        day,
        temp_c,
        is_warm_day,
        ROW_NUMBER() OVER (PARTITION BY nominal_depth_m ORDER BY day)
        - ROW_NUMBER() OVER (PARTITION BY nominal_depth_m, is_warm_day ORDER BY day) AS grp
    FROM vw_daily_temp_analysis
)
SELECT
    nominal_depth_m,
    MIN(day) AS spell_start,
    MAX(day) AS spell_end,
    COUNT(*) AS n_days,
    ROUND(AVG(temp_c)::numeric, 2) AS avg_temp_c
FROM flagged
WHERE is_warm_day = TRUE
GROUP BY nominal_depth_m, grp
HAVING COUNT(*) >= 3
ORDER BY nominal_depth_m, spell_start;

-- Stratification: surface (20m) minus bottom (85m) daily temp, the
-- research question this two-depth dataset can answer directly.
CREATE OR REPLACE VIEW vw_stratification AS
SELECT
    s.day,
    s.temp_c AS surface_temp_c,
    b.temp_c AS bottom_temp_c,
    ROUND((s.temp_c - b.temp_c)::numeric, 2) AS stratification_c
FROM (SELECT day, temp_c FROM vw_daily_temp_analysis WHERE nominal_depth_m = 20) s
JOIN (SELECT day, temp_c FROM vw_daily_temp_analysis WHERE nominal_depth_m = 85) b
    ON b.day = s.day
ORDER BY s.day;

-- Governance: load audit trail. Deliberately NOT dropped by the
-- DROP/CREATE block above -- this table's whole purpose is to survive
-- across schema re-runs so there's a persistent history of every load,
-- from either pipeline (Python or SQL). Without this, there's no way to
-- answer "did the last load actually work, and how do I know?" after the
-- fact -- the print() statements in clean_hires.py/load_hires.py are gone
-- the moment the terminal closes.
CREATE TABLE IF NOT EXISTS etl_load_log (
    load_id        BIGSERIAL PRIMARY KEY,
    pipeline        TEXT NOT NULL CHECK (pipeline IN ('python', 'sql')),
    source_file      TEXT NOT NULL,
    rows_source        INT NOT NULL,
    rows_loaded           INT NOT NULL,
    rows_rejected            INT NOT NULL,
    started_at                  TIMESTAMPTZ NOT NULL,
    finished_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes                             TEXT
);
