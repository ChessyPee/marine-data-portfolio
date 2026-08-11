"""
Exports dashboard-ready CSVs from Postgres for Tableau Public.

Tableau Public (the free version) can't hold a live database connection --
it only accepts flat files -- so this script is the bridge: it runs your
SQL views and writes their results out as CSVs you then import into
Tableau Public directly.

Run:
    python export_for_tableau.py
Requires:
    ../.env configured, and load.py already run (so the views exist and
    have data).
Output:
    ../dashboards/tableau_data/season_progress.csv
    ../dashboards/tableau_data/month_over_month.csv
    ../dashboards/tableau_data/flagged_rows.csv
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine  # noqa: E402

OUT_DIR = Path(__file__).parent.parent / "dashboards" / "tableau_data"

QUERIES = {
    "season_progress.csv": "SELECT * FROM vw_season_progress ORDER BY quota_year, month_date;",
    "month_over_month.csv": "SELECT * FROM vw_month_over_month ORDER BY month_date;",
    "flagged_rows.csv": (
        "SELECT quota_year, month_date, catch_tonnes, uncaught_tonnes, "
        "flag_over_quota, flag_pct_mismatch, any_flag "
        "FROM fact_rock_lobster_catch WHERE any_flag = TRUE "
        "ORDER BY quota_year, month_date;"
    ),
}


def main():
    engine = get_engine()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, query in QUERIES.items():
        df = pd.read_sql(query, engine)
        path = OUT_DIR / filename
        df.to_csv(path, index=False)
        print(f"{filename}: {len(df)} rows -> {path}")
    print("\nDone. In Tableau Public: Connect > Text File > pick season_progress.csv "
          "to start (it's the one the main dashboard is built on).")


if __name__ == "__main__":
    main()
