"""
Step 2 (hi-res): CLEAN / TRANSFORM
Light Python pass over the raw IMOS ANMN Maria Island (NRSMAI) sub-surface
mooring export -- drops columns that are pure clutter for this analysis and
applies a plausibility sanity net, but leaves IMOS's own quality_control
flags untouched. Real QC filtering (which rows get used in an aggregate)
happens in schema_hires.sql views, not here -- see clean.py in this same
folder for the same philosophy applied to the monthly dataset.

The source file has a 22-line "#"-commented metadata block (column
definitions + QC flag meanings) above the real header row, which is why
this needs its own reader instead of a plain pd.read_csv.

Columns dropped as irrelevant to every research question in
NEXT_STEPS_reef_and_mooring.md: FID, timeseries_id, index (row-id noise),
platform_code (constant -- always NRSMAI-SubSurface), CNDC/PRES/PRES_REL
and their quality_control columns (conductivity and pressure aren't used;
salinity is already delivered as PSAL), TIME/LATITUDE/LONGITUDE
quality_control (always empty in this export), geom (WKT string, redundant
with LATITUDE/LONGITUDE), and the six trailing "*_b" boolean columns
(redundant "does this row have a value" flags -- the value columns
themselves are the signal).

Run:
    python clean_hires.py
Input:
    data/raw/mooring_hires_raw.csv
Output:
    data/clean/mooring_hires_clean.csv
"""

from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).parent / "data" / "raw" / "mooring_hires_raw.csv"
CLEAN_PATH = Path(__file__).parent / "data" / "clean" / "mooring_hires_clean.csv"

HEADER_ROW = 22  # 0-indexed row of the real header (line 23 in the file)

KEEP_COLUMNS = {
    "site_code": "site_code",
    "deployment_code": "deployment_code",
    "instrument_nominal_depth": "nominal_depth_m",
    "TIME": "timestamp",
    "LATITUDE": "latitude",
    "LONGITUDE": "longitude",
    "DEPTH": "depth_m",
    "DEPTH_quality_control": "depth_qc",
    "TEMP": "temp_c",
    "TEMP_quality_control": "temp_qc",
    "PSAL": "psal",
    "PSAL_quality_control": "psal_qc",
}

# Physically plausible bounds for SE Australian shelf water / practical
# salinity -- a sanity net only. Profiling the raw file showed every
# out-of-range TEMP value here was already flagged temp_qc=4 (bad) by
# IMOS, so this doesn't silently drop anything the QC column didn't
# already catch.
MIN_TEMP_C, MAX_TEMP_C = 0, 30
MIN_PSAL, MAX_PSAL = 0, 40


def main():
    raw = pd.read_csv(RAW_PATH, skiprows=HEADER_ROW, usecols=list(KEEP_COLUMNS))
    raw = raw.rename(columns=KEEP_COLUMNS)
    n_before = len(raw)

    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)

    raw = raw[raw["temp_c"].between(MIN_TEMP_C, MAX_TEMP_C)]
    raw = raw[raw["psal"].between(MIN_PSAL, MAX_PSAL)]
    n_after_plausibility = len(raw)

    raw = raw.drop_duplicates(subset=["deployment_code", "nominal_depth_m", "timestamp"])
    n_after = len(raw)

    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw.sort_values(["deployment_code", "nominal_depth_m", "timestamp"]).to_csv(
        CLEAN_PATH, index=False
    )

    print(f"Kept {n_after_plausibility}/{n_before} rows after temp/psal plausibility filtering.")
    print(f"Dropped {n_after_plausibility - n_after} exact-duplicate row(s).")
    print(f"Cleaned {n_after} rows -> {CLEAN_PATH}")
    print(f"Date range: {raw['timestamp'].min()} to {raw['timestamp'].max()}")
    print(f"Deployments: {sorted(raw['deployment_code'].unique())}")
    print(f"Nominal depths: {sorted(raw['nominal_depth_m'].unique())}")


if __name__ == "__main__":
    main()
