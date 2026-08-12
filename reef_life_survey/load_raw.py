"""
Step 1: LOAD RAW
Reef Life Survey source files are long-format species/habitat-cover
records, one row per species (fish/invertebrate) or habitat category
(benthic) per survey. No pandas-side cleaning here -- just get each CSV
into its own raw Postgres table (rls_raw_*, schema.sql) verbatim, with
only the join-key columns (site_code, survey_id, survey_date,
species_name) guaranteed NOT NULL by the schema. Run clean_rls.sql after
this for a basic-validated layer (rls_clean_*); deeper per-analysis
aggregation (species-level vs. habitat-group-level vs. site-year-level)
still happens in each analysis's own SQL, since one blanket table can't
fit every grain.

This script never truncates or overwrites: if a table already has rows,
it's skipped rather than reloaded, so re-running is always safe.

Each file has ~71 lines of IMOS metadata/glossary above the real header
(the line starting "FID,survey_id,...").

Run:
    python load_raw.py
Requires:
    ../.env configured.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine, run_sql_file  # noqa: E402

RAW_DIR = Path(__file__).parent / "data" / "raw"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
HEADER_ROW = 71  # 0-indexed row of the real header (line 72 in each file)

SOURCES = [
    ("rls_fish_raw.csv", "rls_raw_fish"),
    ("rls_invertebrate_raw.csv", "rls_raw_invertebrate"),
    ("rls_benthic_raw.csv", "rls_raw_benthic"),
]


def load_one(engine, filename, table):
    with engine.connect() as conn:
        existing = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar()
    if existing:
        print(f"  {table} already has {existing} row(s) -- skipping (never truncates/overwrites).")
        return existing

    df = pd.read_csv(RAW_DIR / filename, skiprows=HEADER_ROW, low_memory=False)
    df.columns = [c.lower() for c in df.columns]
    df["survey_date"] = pd.to_datetime(df["survey_date"]).dt.date
    if "hour" in df.columns:
        # "hour" is a HH:MM:SS time-of-day string with many blanks, not a
        # number -- empty string must become NULL, or Postgres's TIME
        # column rejects it (found via a real load failure, not guessed).
        df["hour"] = df["hour"].replace("", pd.NA)
    n_before = len(df)
    df = df.dropna(subset=["site_code", "survey_id", "survey_date", "species_name"])
    if len(df) < n_before:
        print(f"  Dropped {n_before - len(df)} row(s) missing a required join-key column.")
    # method='multi' batches rows into multi-row INSERTs instead of one
    # round-trip per row -- necessary at this size over a pooled
    # connection with real network latency (~50-280K rows per file).
    df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=2000)
    print(f"Loaded {len(df)} row(s) into {table}")
    return len(df)


def main():
    engine = get_engine()
    print("Creating schema...")
    run_sql_file(engine, SCHEMA_PATH)

    for filename, table in SOURCES:
        print(f"Loading {filename} -> {table} ...")
        load_one(engine, filename, table)

    print("Done.")


if __name__ == "__main__":
    main()
