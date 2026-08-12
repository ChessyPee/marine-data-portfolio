"""
Step 3 (hi-res): LOAD
Creates schema_hires.sql and loads the cleaned mooring CSV into Postgres:
first dim_sensor_deployment (derived from the clean CSV by grouping on
deployment_code + nominal_depth_m), then fact_sensor_reading with the
resolved deployment_id FK.

Run:
    python load_hires.py
Requires:
    ../.env configured, and clean_hires.py already run.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine, run_sql_file  # noqa: E402

RAW_PATH = Path(__file__).parent / "data" / "raw" / "mooring_hires_raw.csv"
CLEAN_PATH = Path(__file__).parent / "data" / "clean" / "mooring_hires_clean.csv"
SCHEMA_PATH = Path(__file__).parent / "schema_hires.sql"
HEADER_OFFSET = 23  # metadata block + header line, to count only data rows


def main():
    started_at = datetime.now(timezone.utc)
    engine = get_engine()

    print("Creating schema...")
    run_sql_file(engine, SCHEMA_PATH)

    with open(RAW_PATH, encoding="utf-8") as f:
        rows_source = sum(1 for _ in f) - HEADER_OFFSET

    clean = pd.read_csv(CLEAN_PATH, parse_dates=["timestamp"])

    deployments = (
        clean.groupby(["deployment_code", "nominal_depth_m"])["timestamp"]
        .agg(deployment_start="min", deployment_end="max")
        .reset_index()
    )
    deployments.to_sql("dim_sensor_deployment", engine, if_exists="append", index=False)
    print(f"Loaded {len(deployments)} deployment(s) into dim_sensor_deployment")

    dim_lookup = pd.read_sql(
        "SELECT deployment_id, deployment_code, nominal_depth_m FROM dim_sensor_deployment",
        engine,
    )
    clean = clean.merge(dim_lookup, on=["deployment_code", "nominal_depth_m"], how="left")
    if clean["deployment_id"].isna().any():
        raise RuntimeError("Some rows failed to match a deployment_id -- check dim load.")

    cols = [
        "deployment_id", "timestamp", "depth_m", "depth_qc",
        "temp_c", "temp_qc", "psal", "psal_qc",
    ]
    clean[cols].to_sql("fact_sensor_reading", engine, if_exists="append", index=False)
    print(f"Loaded {len(clean)} row(s) into fact_sensor_reading")

    log_row = pd.DataFrame([{
        "pipeline": "python",
        "source_file": "mooring_hires_raw.csv",
        "rows_source": rows_source,
        "rows_loaded": len(clean),
        "rows_rejected": rows_source - len(clean),
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc),
        "notes": "clean_hires.py + load_hires.py full run",
    }])
    log_row.to_sql("etl_load_log", engine, if_exists="append", index=False)
    print("Logged this run to etl_load_log.")
    print("Done. Run verify_hires.sql (or validate_hires.py) next.")


if __name__ == "__main__":
    main()
