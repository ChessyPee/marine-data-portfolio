"""
Step 3: LOAD
Creates the schema (schema.sql) and loads the cleaned CSVs into Postgres.

Run:
    python load.py
Requires:
    ../.env configured (see .env.example), and clean.py already run.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine, run_sql_file  # noqa: E402

CLEAN_PATH = Path(__file__).parent / "data" / "clean" / "rock_lobster_catch_clean.csv"
TOTALS_PATH = Path(__file__).parent / "data" / "clean" / "rock_lobster_season_totals.csv"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def main():
    engine = get_engine()

    print("Creating schema...")
    run_sql_file(engine, SCHEMA_PATH)

    clean = pd.read_csv(CLEAN_PATH, parse_dates=["month_date"])
    totals = pd.read_csv(TOTALS_PATH)

    dim = clean[["quota_year", "tac_tonnes"]].drop_duplicates()
    dim.to_sql("dim_quota_year", engine, if_exists="append", index=False)
    print(f"Loaded {len(dim)} row(s) into dim_quota_year")

    fact_cols = [
        "quota_year", "month_date", "catch_tonnes", "uncaught_tonnes",
        "pct_tac_taken_scraped", "pct_tac_taken_computed",
        "flag_over_quota", "flag_not_yet_reported", "flag_pct_mismatch",
        "any_flag", "source_url", "scraped_at",
    ]
    clean[fact_cols].to_sql(
        "fact_rock_lobster_catch", engine, if_exists="append", index=False
    )
    print(f"Loaded {len(clean)} row(s) into fact_rock_lobster_catch")

    qa = totals.rename(columns={"catch_tonnes_published": "catch_tonnes_published"})
    qa[["quota_year", "catch_tonnes_published"]].to_sql(
        "qa_season_totals_published", engine, if_exists="append", index=False
    )
    print(f"Loaded {len(qa)} row(s) into qa_season_totals_published")

    print("Done. Run verify.sql next to check everything landed correctly.")


if __name__ == "__main__":
    main()
