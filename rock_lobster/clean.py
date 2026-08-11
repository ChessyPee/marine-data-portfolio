"""
Step 2: CLEAN / TRANSFORM
Turns the raw scrape into an analysis-ready table. This is where the real
data-quality work happens -- the source data has several genuine issues
that we handle explicitly (and log) rather than silently overwrite:

  1. Units change over time: pre-2015 tables report catch in KG, later
     tables report TONNES. We normalise everything to tonnes.
  2. Stray double-dots / typos in the source, e.g. "393..07" (2022/23,
     November). We attempt a safe fix (collapse repeated dots) and flag
     the row so it's traceable, rather than silently trusting it.
  3. Future / not-yet-reported months are blank on the page -- these must
     stay NULL, not become 0, or trend charts will show a fake crash.
  4. "TOTAL" rows are season summaries, not monthly observations. We pull
     them out into their own table and use them to cross-check that our
     monthly rows actually sum to what Fishing Tasmania itself reports as
     the season total -- a real reconciliation check, not just a vibe.
  5. Negative "uncaught" values mean the fishery went over quota that
     month (it happens) -- flagged, not deleted.

Run:
    python clean.py
Input:
    data/raw/rock_lobster_catch_raw.csv
Output:
    data/clean/rock_lobster_catch_clean.csv   (monthly observations)
    data/clean/rock_lobster_season_totals.csv (season totals, for QA)
"""

import re
from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).parent / "data" / "raw" / "rock_lobster_catch_raw.csv"
CLEAN_PATH = Path(__file__).parent / "data" / "clean" / "rock_lobster_catch_clean.csv"
TOTALS_PATH = Path(__file__).parent / "data" / "clean" / "rock_lobster_season_totals.csv"

MONTH_RE = re.compile(r"([A-Za-z]+)\s+(\d{4})")
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def to_number(raw: str) -> float | None:
    """Parse a messy numeric string ('393..07', '1,023,187.30', '') safely."""
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).replace(",", "").strip()
    s = re.sub(r"\.{2,}", ".", s)  # collapse "393..07" -> "393.07"
    try:
        return float(s)
    except ValueError:
        return None


def parse_month(label: str, quota_year: str):
    m = MONTH_RE.match(label)
    if not m:
        return None
    month_name, year = m.group(1).lower(), int(m.group(2))
    month_num = MONTHS.get(month_name)
    if month_num is None:
        return None
    return pd.Timestamp(year=year, month=month_num, day=1)


def main():
    raw = pd.read_csv(RAW_PATH, dtype=str, keep_default_na=False)

    monthly = raw[~raw["is_total_row"].astype(str).str.lower().eq("true")].copy()
    totals = raw[raw["is_total_row"].astype(str).str.lower().eq("true")].copy()

    # --- parse dates ---
    monthly["month_date"] = monthly.apply(
        lambda r: parse_month(r["row_label"], r["quota_year"]), axis=1
    )
    unparsed = monthly[monthly["month_date"].isna()]
    if len(unparsed):
        print(f"WARNING: {len(unparsed)} row(s) had an unparseable month label, dropped:")
        print(unparsed[["quota_year", "row_label"]].to_string(index=False))
    monthly = monthly.dropna(subset=["month_date"])

    # --- numeric parsing + typo flag ---
    monthly["catch_had_typo"] = monthly["catch_raw"].astype(str).str.contains(r"\.{2,}")
    monthly["uncaught_had_typo"] = monthly["uncaught_raw"].astype(str).str.contains(r"\.{2,}")
    monthly["catch_value"] = monthly["catch_raw"].apply(to_number)
    monthly["uncaught_value"] = monthly["uncaught_raw"].apply(to_number)
    monthly["pct_tac_taken_scraped"] = monthly["pct_tac_taken_raw"].apply(to_number)
    monthly["tac_tonnes"] = monthly["tac_tonnes_raw"].apply(to_number)

    # --- unit normalisation: kg -> tonnes ---
    is_kg = monthly["catch_unit_raw"].str.lower().eq("kg")
    monthly["catch_tonnes"] = monthly["catch_value"].where(~is_kg, monthly["catch_value"] / 1000)
    monthly["uncaught_tonnes"] = monthly["uncaught_value"].where(~is_kg, monthly["uncaught_value"] / 1000)

    # --- data quality flags ---
    monthly["flag_over_quota"] = monthly["uncaught_tonnes"] < 0
    monthly["flag_not_yet_reported"] = monthly["catch_tonnes"].isna()

    computed_pct = (monthly["catch_tonnes"] / monthly["tac_tonnes"] * 100).round(1)
    monthly["pct_tac_taken_computed"] = computed_pct
    monthly["flag_pct_mismatch"] = (
        (computed_pct - monthly["pct_tac_taken_scraped"]).abs() > 0.5
    ) & monthly["pct_tac_taken_scraped"].notna()

    monthly["any_flag"] = (
        monthly["catch_had_typo"] | monthly["uncaught_had_typo"]
        | monthly["flag_over_quota"] | monthly["flag_pct_mismatch"]
    )

    out_cols = [
        "quota_year", "month_date", "tac_tonnes", "catch_tonnes", "uncaught_tonnes",
        "pct_tac_taken_scraped", "pct_tac_taken_computed",
        "flag_over_quota", "flag_not_yet_reported", "flag_pct_mismatch",
        "catch_had_typo", "uncaught_had_typo", "any_flag",
        "source_url", "scraped_at",
    ]
    clean = monthly[out_cols].sort_values(["quota_year", "month_date"])
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(CLEAN_PATH, index=False)

    # --- reconciliation: do monthly rows sum to the published season total? ---
    totals["catch_value"] = totals["catch_raw"].apply(to_number)
    totals["catch_unit_raw"] = totals["catch_unit_raw"].fillna("tonnes")
    is_kg_t = totals["catch_unit_raw"].str.lower().eq("kg")
    totals["catch_tonnes_published"] = totals["catch_value"].where(~is_kg_t, totals["catch_value"] / 1000)

    monthly_sums = clean.groupby("quota_year")["catch_tonnes"].sum().rename("catch_tonnes_summed")
    recon = totals.set_index("quota_year")[["catch_tonnes_published"]].join(monthly_sums)
    recon["diff_tonnes"] = (recon["catch_tonnes_published"] - recon["catch_tonnes_summed"]).round(2)
    recon["reconciles"] = recon["diff_tonnes"].abs() < 0.5
    recon.to_csv(TOTALS_PATH)

    n_flagged = int(clean["any_flag"].sum())
    print(f"Cleaned {len(clean)} monthly rows -> {CLEAN_PATH}")
    print(f"{n_flagged} row(s) flagged for review (typo/over-quota/pct mismatch).")
    print(f"Season-total reconciliation -> {TOTALS_PATH}")
    print(recon.to_string())
    if not recon["reconciles"].all():
        bad = recon[~recon["reconciles"]]
        print(f"\nWARNING: {len(bad)} quota year(s) did not reconcile against the published total:")
        print(bad.to_string())


if __name__ == "__main__":
    main()
