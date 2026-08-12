-- Step 1+2 (SQL ETL path): CLEAN, TYPE-CAST, DEDUPE, and MODEL --
-- entirely in SQL, from stg_mooring_hires_raw (loaded verbatim by
-- load_raw_sql.py) into the same dim_sensor_deployment / fact_sensor_reading
-- tables schema_hires.sql defines. This is the SQL-only equivalent of
-- clean_hires.py + load_hires.py combined -- same column drops, same
-- plausibility bounds, same natural key, same "respect IMOS's own QC flag,
-- don't invent extra filtering on top of it" rule.
--
-- Run after load_raw_sql.py has populated stg_mooring_hires_raw, and after
-- schema_hires.sql has created dim_sensor_deployment / fact_sensor_reading.

-- 0. GOVERNANCE: capture a start timestamp for the load-audit row written
--    at the end of this script. A TEMP TABLE survives for the lifetime of
--    this script's transaction (db.py's run_sql_file runs an entire file
--    as one transaction) without leaving anything behind afterward.
CREATE TEMP TABLE _load_meta AS SELECT now() AS started_at;

-- 1. CLEAN: type-cast, drop irrelevant columns, apply the plausibility net,
--    dedupe on the real natural key. Mirrors clean_hires.py's KEEP_COLUMNS
--    dict (everything else -- FID, timeseries_id, row_index, platform_code,
--    CNDC/PRES/PRES_REL + their qc columns, TIME/LATITUDE/LONGITUDE qc
--    columns, geom, the six *_b flags -- is simply never selected) and its
--    MIN_TEMP_C/MAX_TEMP_C, MIN_PSAL/MAX_PSAL bounds.
DROP TABLE IF EXISTS stg_mooring_hires_clean;

CREATE TABLE stg_mooring_hires_clean AS
SELECT DISTINCT ON (deployment_code, nominal_depth_m, "timestamp")
    site_code, deployment_code, nominal_depth_m, "timestamp",
    latitude, longitude, depth_m, depth_qc, temp_c, temp_qc, psal, psal_qc
FROM (
    SELECT
        site_code,
        deployment_code,
        NULLIF(instrument_nominal_depth, '')::numeric   AS nominal_depth_m,
        NULLIF(time_raw, '')::timestamptz                AS "timestamp",
        NULLIF(latitude_raw, '')::numeric                AS latitude,
        NULLIF(longitude_raw, '')::numeric               AS longitude,
        NULLIF(depth_raw, '')::numeric                   AS depth_m,
        NULLIF(depth_qc, '')::smallint                   AS depth_qc,
        NULLIF(temp_raw, '')::numeric                    AS temp_c,
        NULLIF(temp_qc, '')::smallint                    AS temp_qc,
        NULLIF(psal_raw, '')::numeric                    AS psal,
        NULLIF(psal_qc, '')::smallint                    AS psal_qc
    FROM stg_mooring_hires_raw
) typed
-- Plausibility net only -- profiling the raw file showed every
-- out-of-range TEMP value here was already flagged temp_qc = 4 (bad) by
-- IMOS, so this doesn't silently drop anything the QC column didn't
-- already catch. Rows are NOT filtered by quality_flag here -- that
-- filtering belongs in the analysis views (vw_reading_flags etc. in
-- schema_hires.sql), not in the cleaned table itself.
WHERE temp_c BETWEEN 0 AND 30
  AND psal BETWEEN 0 AND 40
ORDER BY deployment_code, nominal_depth_m, "timestamp";

CREATE UNIQUE INDEX ON stg_mooring_hires_clean (deployment_code, nominal_depth_m, "timestamp");

-- 2. MODEL: dim_sensor_deployment -- one row per real instrument
--    (deployment_code + nominal_depth_m, confirmed the true natural key
--    by profiling), deployment_start/end derived as MIN/MAX timestamp.
--    Mirrors load_hires.py's groupby(["deployment_code", "nominal_depth_m"]).
--    ON CONFLICT DO NOTHING makes this safe to re-run (idempotent) against
--    data already loaded via the Python path.
INSERT INTO dim_sensor_deployment (deployment_code, nominal_depth_m, deployment_start, deployment_end)
SELECT deployment_code, nominal_depth_m, MIN("timestamp"), MAX("timestamp")
FROM stg_mooring_hires_clean
GROUP BY deployment_code, nominal_depth_m
ON CONFLICT (deployment_code, nominal_depth_m) DO NOTHING;

-- 3. MODEL: fact_sensor_reading -- resolve deployment_id via a join back
--    to the dimension table just populated, instead of load_hires.py's
--    pandas merge. Same UNIQUE (deployment_id, timestamp) idempotency.
INSERT INTO fact_sensor_reading (deployment_id, "timestamp", depth_m, depth_qc, temp_c, temp_qc, psal, psal_qc)
SELECT d.deployment_id, c."timestamp", c.depth_m, c.depth_qc, c.temp_c, c.temp_qc, c.psal, c.psal_qc
FROM stg_mooring_hires_clean c
JOIN dim_sensor_deployment d
    ON d.deployment_code = c.deployment_code
   AND d.nominal_depth_m = c.nominal_depth_m
ON CONFLICT (deployment_id, "timestamp") DO NOTHING;

-- 4. GOVERNANCE: record this run in the load audit trail. rows_rejected
--    here means "dropped by the plausibility filter or dedupe" -- not
--    "skipped by ON CONFLICT", since a conflict means the data was
--    already correctly loaded by a prior run, not that this run failed
--    to account for it.
INSERT INTO etl_load_log (pipeline, source_file, rows_source, rows_loaded, rows_rejected, started_at, finished_at, notes)
SELECT
    'sql',
    'mooring_hires_raw.csv',
    (SELECT COUNT(*) FROM stg_mooring_hires_raw),
    (SELECT COUNT(*) FROM stg_mooring_hires_clean),
    (SELECT COUNT(*) FROM stg_mooring_hires_raw) - (SELECT COUNT(*) FROM stg_mooring_hires_clean),
    m.started_at,
    now(),
    'etl_clean_and_model_sql.sql full run'
FROM _load_meta m;
