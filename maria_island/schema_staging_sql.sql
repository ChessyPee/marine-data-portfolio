-- Step 0 (SQL ETL path): staging table for the raw mooring export.
-- Column order matches the raw CSV header exactly (mooring_hires_raw.csv,
-- line 23 -- the 22 lines above it are IMOS's metadata/QC-flag-meaning
-- block, not data). Every column is TEXT on purpose: this table's only job
-- is to hold the file's contents verbatim, with zero interpretation -- the
-- same "raw stays raw" principle clean_hires.py already followed in
-- Python, just expressed as a table instead of a DataFrame. All type
-- casting, filtering, and modeling happens downstream in
-- etl_clean_and_model_sql.sql.

DROP TABLE IF EXISTS stg_mooring_hires_raw;

CREATE TABLE stg_mooring_hires_raw (
    fid                                     TEXT,
    timeseries_id                           TEXT,
    row_index                               TEXT,
    site_code                               TEXT,
    platform_code                           TEXT,
    deployment_code                         TEXT,
    instrument_nominal_depth                TEXT,
    time_raw                                TEXT,
    time_qc                                 TEXT,
    latitude_raw                            TEXT,
    latitude_qc                             TEXT,
    longitude_raw                           TEXT,
    longitude_qc                            TEXT,
    depth_raw                               TEXT,
    depth_qc                                TEXT,
    temp_raw                                TEXT,
    temp_qc                                 TEXT,
    cndc_raw                                TEXT,
    cndc_qc                                 TEXT,
    psal_raw                                TEXT,
    psal_qc                                 TEXT,
    pres_raw                                TEXT,
    pres_qc                                 TEXT,
    pres_rel_raw                            TEXT,
    pres_rel_qc                             TEXT,
    geom                                    TEXT,
    depth_b                                 TEXT,
    temp_b                                  TEXT,
    cndc_b                                  TEXT,
    psal_b                                  TEXT,
    pres_b                                  TEXT,
    pres_rel_b                              TEXT
);
