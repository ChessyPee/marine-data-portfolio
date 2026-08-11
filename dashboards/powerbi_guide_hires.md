> **On a Mac?** Power BI Desktop is Windows-only. If you're on this Mac
> session, you'll need an actual Windows machine or VM to follow this --
> the Streamlit app (`streamlit_app_hires.py`) is the cross-platform
> equivalent of everything below and needs nothing installed beyond
> Python.

# Power BI: Maria Island Hi-Res Mooring Dashboard

Power BI connects straight to the Postgres tables/views built in
`maria_island/schema_hires.sql` -- no CSV re-import needed, and it'll
always reflect whatever's currently loaded via `load_hires.py`.

## 1. Connect

1. Open Power BI Desktop -> **Get Data** -> **PostgreSQL database**.
2. **Server**: `aws-0-ap-northeast-2.pooler.supabase.com` (the Session
   Pooler host, not the plain `db.<ref>.supabase.co` direct-connection
   host -- the direct host is IPv6-only, and most networks/ISPs can't
   route to it. Get this from your Supabase project: **Connect** button ->
   **Direct** tab -> **Session pooler** -> copy the `host` value). Leave
   port blank (defaults to 5432, which matches).
3. **Database**: `postgres`.
4. **Data Connectivity mode**: **Import** (not DirectQuery) -- 287K raw
   rows is still small enough to import comfortably, and Import gives you
   offline access if wifi drops mid-demo.
5. Credentials prompt: choose **Database** (not Windows), then:
   - **User name**: `postgres.<your-project-ref>` -- note the pooler
     requires this dotted form, not plain `postgres` (that's the #1 thing
     that trips people up switching from the direct-connection string).
   - **Password**: your Supabase database password.
6. If Power BI complains it can't find a PostgreSQL driver: it needs the
   **Npgsql** .NET driver installed separately (Power BI's PostgreSQL
   connector doesn't bundle it). Download it from Npgsql's releases page
   and restart Power BI Desktop.
7. In the Navigator window, load: `dim_sensor_deployment`,
   `fact_sensor_reading`, `vw_daily_temp_analysis`,
   `vw_warm_spell_groups_hires`, `vw_stratification`.

## 2. Build these visuals (mirrors the Streamlit app's 4 panels)

**KPI cards (top row)**
- Latest `temp_c` from `vw_daily_temp_analysis` filtered to
  `nominal_depth_m = 20` (surface) and `= 85` (bottom) -- two cards
- Latest `stratification_c` from `vw_stratification`
- Count of rows in `vw_warm_spell_groups_hires`

**Daily trend + anomaly chart**
- Line chart: X = `day`, Y = `temp_c`, from `vw_daily_temp_analysis`
- Add `clim_mean` and `clim_p90` as two more line series on the same axis
  to show the climatology band (Power BI doesn't have a native band-fill
  for line charts the way Plotly does -- an Area chart with `clim_p90` as
  the top series and `clim_mean` layered under it approximates the same
  shaded-band look)
- Legend/slicer: `nominal_depth_m`, so you can toggle 20m vs 85m
- Conditional formatting or a second scatter layer for `is_warm_day = TRUE`
  rows, colored distinctly

**Warm-spell timeline**
- This is the one visual Power BI doesn't do natively (no built-in Gantt).
  Two options:
  - Install the free **Gantt chart** visual from AppSource (Microsoft's own),
    feed it `spell_start` / `spell_end` / `nominal_depth_m` from
    `vw_warm_spell_groups_hires`
  - Or simplify to a table visual sorted by `spell_start` -- less visual,
    but zero extra installs and still shows the same underlying events

**Stratification chart**
- Bar/column chart: X = `day`, Y = `stratification_c`, from
  `vw_stratification`
- Conditional formatting rule: positive values one color, negative
  another (Power BI's built-in "Format by rule" on the Y value does this
  without a helper column)

## 3. Publish

File -> **Publish** -> **Publish to web** (or to your organization's Power
BI workspace, if this is for internal use rather than a portfolio link).
Same caveat as the Rock Lobster guide: publish-to-web is a static
snapshot unless you set up a scheduled refresh (needs a gateway, Pro
tier) -- fine for a portfolio piece, just say so if asked.

Also worth restating from the Supabase free-tier note in the main README:
the database pauses after 7 days idle -- open any query against it the
morning of an interview/demo to wake it up before you rely on a live
refresh.
