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
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine, run_sql_file  # noqa: E402

CLEAN_PATH = Path(__file__).parent / "data" / "clean" / "mooring_hires_clean.csv"
SCHEMA_PATH = Path(__file__).parent / "schema_hires.sql"


def main():
    engine = get_engine()

    print("Creating schema...")
    run_sql_file(engine, SCHEMA_PATH)

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
    print("Done. Run verify_hires.sql next.")


if __name__ == "__main__":
    main()
