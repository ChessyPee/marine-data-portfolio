"""
Step 2: CLEAN / TRANSFORM
Resamples raw (often irregular, multi-depth) observations to a monthly
surface-temperature series, then computes a monthly climatology and flags
anomalously warm months.

A note on the "marine heatwave" flag, so it doesn't get oversold in an
interview: the formal definition (Hobday et al. 2016) uses a DAILY
90th-percentile threshold against a 30-year baseline, with an event
requiring >=5 consecutive warm days. We're working at monthly resolution
here, which is a reasonable simplification for a portfolio project but is
NOT the official methodology BOM/IMOS use operationally -- say so if asked.
What we compute: for each calendar month, a climatological mean and 90th
percentile temperature across the whole record, then flag any month whose
observed temperature exceeds that month's 90th percentile as "anomalously
warm". Three or more consecutive warm months become a "warm spell" -- see
vw_warm_spell_groups in schema.sql for the SQL-side version of this.

Run:
    python clean.py
Input:
    data/raw/maria_island_temp_raw.csv
Output:
    data/clean/maria_island_temp_clean.csv
"""

from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).parent / "data" / "raw" / "maria_island_temp_raw.csv"
CLEAN_PATH = Path(__file__).parent / "data" / "clean" / "maria_island_temp_clean.csv"

# Keep only observations shallower than this -- surface temperature is what
# drives the marine heatwave / range-shift story, and mixing in deep casts
# would understate real surface warming.
MAX_DEPTH_M = 10

# Physically plausible bounds for SE Australian shelf water -- anything
# outside this is almost certainly a sensor fault or parsing error, not
# a real reading.
MIN_PLAUSIBLE_C = 5
MAX_PLAUSIBLE_C = 26


def main():
    raw = pd.read_csv(RAW_PATH, parse_dates=["time"])

    n_before = len(raw)
    if raw["depth_m"].notna().any():
        raw = raw[raw["depth_m"].fillna(0) <= MAX_DEPTH_M]
    raw = raw[raw["temp_c"].between(MIN_PLAUSIBLE_C, MAX_PLAUSIBLE_C)]
    n_after = len(raw)
    print(f"Kept {n_after}/{n_before} observations after depth/plausibility filtering.")

    raw["month_date"] = raw["time"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        raw.groupby("month_date", as_index=False)["temp_c"]
        .mean()
        .sort_values("month_date")
    )

    monthly["calendar_month"] = monthly["month_date"].dt.month
    clim = monthly.groupby("calendar_month")["temp_c"].agg(
        climatology_mean_c="mean", climatology_p90_c=lambda s: s.quantile(0.9)
    )
    monthly = monthly.merge(clim, on="calendar_month", how="left")

    monthly["anomaly_c"] = (monthly["temp_c"] - monthly["climatology_mean_c"]).round(2)
    monthly["is_warm_month"] = monthly["temp_c"] > monthly["climatology_p90_c"]

    out = monthly[
        ["month_date", "temp_c", "climatology_mean_c", "climatology_p90_c",
         "anomaly_c", "is_warm_month"]
    ].round({"temp_c": 2, "climatology_mean_c": 2, "climatology_p90_c": 2})
    out["depth_bin"] = f"surface_lt_{MAX_DEPTH_M}m"
    out["source_url"] = "https://portal.aodn.org.au/ (Maria Island NRS long-term product)"

    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(CLEAN_PATH, index=False)

    n_warm = int(out["is_warm_month"].sum())
    print(f"Cleaned {len(out)} monthly rows -> {CLEAN_PATH}")
    print(f"{n_warm} month(s) flagged anomalously warm (> month's 90th percentile).")

    # simple linear trend, for a sanity-check number to quote
    yrs = (out["month_date"] - out["month_date"].min()).dt.days / 365.25
    if len(out) > 24:
        slope = pd.Series(out["temp_c"]).corr(yrs)  # quick correlation check
        import numpy as np
        coef = np.polyfit(yrs, out["temp_c"], 1)[0]
        print(f"Approx. warming trend: {coef:.3f} deg C / year over the record.")


if __name__ == "__main__":
    main()
