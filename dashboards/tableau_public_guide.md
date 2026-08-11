# Tableau Public: Rock Lobster Season Progress Dashboard

Use this instead of `powerbi_guide.md` if you're on a Mac -- Power BI
Desktop is Windows-only with no Mac version. Tableau Public has a real
native Mac app and is free.

The one tradeoff: Tableau Public can't hold a live database connection
(this is true even with a Postgres source, not just Supabase) -- it only
accepts flat files. `rock_lobster/export_for_tableau.py` bridges that by
running your SQL views and writing the results out as CSVs.

## 1. Install

Download from **public.tableau.com/en-us/s/download** -- it's a normal
.dmg installer, no VM or Windows needed.

## 2. Export your data

```bash
cd rock_lobster
python export_for_tableau.py
```
This writes `dashboards/tableau_data/season_progress.csv`,
`month_over_month.csv`, and `flagged_rows.csv`.

## 3. Connect

Open Tableau Public -> Connect -> **Text File** -> select
`season_progress.csv`. Drag `flagged_rows.csv` in as a second connection
if you want the data-quality panel too (join on `quota_year` +
`month_date` if you want them on one sheet, or keep them on separate
dashboard tiles, which is simpler).

## 4. Build these same visuals as the Power BI version

**KPI text/number** -- current quota year's latest `cumulative_pct_tac`
(filter `season_progress.csv` to the max `month_date` within the active
`quota_year`).

**Season progress line chart** -- Columns: `month_date`. Rows:
`cumulative_pct_tac`. Color: `quota_year` -- this overlays every season
since 2007/08 so you can see at a glance whether the current season is
ahead of or behind historical pace.

**Monthly catch bars** -- Columns: `month_date`, Rows: `catch_tonnes`,
filtered to the current quota year.

**Data quality table** -- a text table from `flagged_rows.csv` showing
exactly which rows were flagged and why. This is the part that
demonstrates the "data curation and quality" line in the job description,
not just the pretty chart.

## 5. Publish

File -> **Save to Tableau Public As...** -- this uploads it to your
public Tableau Public profile and gives you a shareable link. Because
it's a snapshot (not live), note the export date somewhere on the
dashboard (a text box with `export_for_tableau.py`'s run date) so it's
clear to a panel what "as of" date the numbers reflect. Before your
interview, just re-run the export + republish if you want fresher numbers.
