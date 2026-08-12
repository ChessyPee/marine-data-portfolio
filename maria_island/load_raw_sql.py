"""
Step 0 (SQL ETL path): raw ingest only -- streams mooring_hires_raw.csv
verbatim into stg_mooring_hires_raw using PostgreSQL's native COPY
protocol. This file makes no decisions about the data: no renaming, no
casting, no filtering. Its only reason to exist is that no SQL SELECT
statement can open a file sitting on your laptop -- COPY (or a client
wrapper around it, which is all this is) is the standard way any SQL
engine gets a local file into a table. Every actual transformation lives
in etl_clean_and_model_sql.sql, run after this.

Run:
    python schema_staging_sql.sql   (create the table first, via psql/db.py)
    python load_raw_sql.py          (this script)
    then run etl_clean_and_model_sql.sql
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine, run_sql_file  # noqa: E402

RAW_PATH = Path(__file__).parent / "data" / "raw" / "mooring_hires_raw.csv"
STAGING_SCHEMA = Path(__file__).parent / "schema_staging_sql.sql"
HEADER_OFFSET = 22  # lines of IMOS metadata/QC-flag-meaning block above the real header

# The COPY below relies on column ORDER, not names, matching
# stg_mooring_hires_raw exactly -- if AODN ever reorders/renames/adds a
# column in this export, COPY would still "succeed" but silently load
# values into the wrong columns. Checking the header against this exact
# expected list turns that into a loud failure here instead.
EXPECTED_HEADER = [
    "FID", "timeseries_id", "index", "site_code", "platform_code",
    "deployment_code", "instrument_nominal_depth", "TIME", "TIME_quality_control",
    "LATITUDE", "LATITUDE_quality_control", "LONGITUDE", "LONGITUDE_quality_control",
    "DEPTH", "DEPTH_quality_control", "TEMP", "TEMP_quality_control",
    "CNDC", "CNDC_quality_control", "PSAL", "PSAL_quality_control",
    "PRES", "PRES_quality_control", "PRES_REL", "PRES_REL_quality_control",
    "geom", "depth_b", "sea_water_temperature_b",
    "sea_water_electrical_conductivity_b", "sea_water_salinity_b",
    "sea_water_pressure_b", "sea_water_pressure_due_to_sea_water_b",
]


def check_header(f):
    """Fail fast and loud if the source file's columns don't match what
    stg_mooring_hires_raw and the COPY below expect, instead of letting a
    silently-misaligned load corrupt every downstream table."""
    for _ in range(HEADER_OFFSET):
        next(f)
    header = next(f).strip().split(",")
    if header != EXPECTED_HEADER:
        raise ValueError(
            "Raw CSV header doesn't match the expected schema -- AODN's export "
            "format may have changed. Refusing to load.\n"
            f"Expected: {EXPECTED_HEADER}\n"
            f"Got:      {header}"
        )


def main():
    engine = get_engine()
    run_sql_file(engine, STAGING_SCHEMA)

    with open(RAW_PATH, encoding="utf-8") as f:
        check_header(f)

    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        # The Supabase pooler's default 2-minute statement_timeout is too
        # short for a 287K-row COPY over a long-RTT connection; raise it
        # for just this session (session pooler mode supports SET, unlike
        # transaction-pooler mode).
        cur.execute("SET statement_timeout = '15min'")
        with open(RAW_PATH, encoding="utf-8") as f:
            for _ in range(HEADER_OFFSET):
                next(f)  # skip the metadata block; COPY's HEADER option consumes the real header line
            cur.copy_expert(
                "COPY stg_mooring_hires_raw FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')",
                f,
            )
        raw_conn.commit()
        cur.execute("SELECT COUNT(*) FROM stg_mooring_hires_raw")
        print(f"Loaded {cur.fetchone()[0]} raw rows -> stg_mooring_hires_raw (verbatim, untyped)")
    finally:
        raw_conn.close()


if __name__ == "__main__":
    main()
