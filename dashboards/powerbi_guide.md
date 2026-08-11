> **On a Mac?** Power BI Desktop is Windows-only (no native Mac app, and
> Microsoft has no plans to build one). Use `tableau_public_guide.md`
> instead -- same dashboard, built with a tool that actually runs on
> macOS. Keep this file for reference if you ever build on Windows, or
> if you get access to a Windows VM and want the live-connection version.

# Power BI: Rock Lobster Season Progress Dashboard

Power BI connects straight to the Postgres tables/views you built in
`rock_lobster/schema.sql` -- no CSV re-import needed.

## 1. Connect

1. Open Power BI Desktop -> Get Data -> **PostgreSQL database**.
2. Server: your Supabase host (`Project Settings > Database > Connection
   info` -- looks like `db.xxxx.supabase.co`). Database: `postgres`.
3. Use **Import** mode (not DirectQuery) -- this dataset is small and
   Import gives you offline access during the interview if wifi is shaky.
4. Load these tables/views: `fact_rock_lobster_catch`, `dim_quota_year`,
   `vw_season_progress`, `vw_month_over_month`.

## 2. Build these visuals

**KPI cards (top row)**
- Current quota year's cumulative % of TAC taken (`vw_season_progress`,
  latest `cumulative_pct_tac` for the active `quota_year`)
- Same calendar point last season, for comparison (self-filter
  `vw_season_progress` to the prior quota year at the same month number)

**Season progress line chart**
- X axis: `month_date` (use "months into season" if you want years to
  overlay cleanly instead of real calendar dates)
- Y axis: `cumulative_pct_tac` from `vw_season_progress`
- Legend: `quota_year` -- this overlays every season since 2007/08 so a
  panel can see at a glance whether the current season is tracking ahead
  or behind historical pace

**Monthly catch bar chart**
- X: `month_date`, Y: `catch_tonnes` from `fact_rock_lobster_catch`,
  filtered to the current quota year

**Data quality panel** (this is the part that actually differentiates you)
- A table visual on `fact_rock_lobster_catch` filtered to `any_flag = TRUE`,
  showing exactly which rows were flagged and why (`flag_over_quota`,
  `flag_pct_mismatch`) -- this is your live demonstration of the
  "data curation and quality" work, not just the pretty chart

## 3. Publish

File -> **Embed report** -> **Publish to web**. This gives a public link
-- fine here since every number in this dataset is already public
government data. Save the link; drop it in your one-pager for the panel.

Two things to know about this route: there's no way to restrict who can
view the link, and it won't refresh live off the connector once published
(you'd need a scheduled refresh in the Power BI service for that, which
needs a Pro-tier gateway). For a portfolio piece, a static published
snapshot plus a note that it's built on a live Postgres backend is enough
-- you're not trying to ship a production system in three days.
