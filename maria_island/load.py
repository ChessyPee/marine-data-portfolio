"""
Step 3: LOAD
Creates the schema (schema.sql) and loads the cleaned CSV into Postgres.

Run:
    python load.py
Requires:
    ../.env configured, and clean.py already run.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine, run_sql_file  # noqa: E402

CLEAN_PATH = Path(__file__).parent / "data" / "clean" / "maria_island_temp_clean.csv"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def main():
    engine = get_engine()

    print("Creating schema...")
    run_sql_file(engine, SCHEMA_PATH)

    clean = pd.read_csv(CLEAN_PATH, parse_dates=["month_date"])
    cols = [
        "month_date", "depth_bin", "temp_c", "climatology_mean_c",
        "climatology_p90_c", "anomaly_c", "is_warm_month", "source_url",
    ]
    clean[cols].to_sql("fact_maria_island_temp", engine, if_exists="append", index=False)
    print(f"Loaded {len(clean)} row(s) into fact_maria_island_temp")
    print("Done. Run verify.sql next.")


if __name__ == "__main__":
    main()
