"""
Reef Life Survey: Invasive Urchin Spread Monitor -- Streamlit app.
Reads directly from Postgres (reef_life_survey/analysis_02_urchin_spread.sql
views + Maria Island's vw_daily_temp_analysis), so it always reflects
whatever is currently loaded in the database.

Companion to the two Maria Island dashboards -- this one tracks the
invasive urchin's spread through Tasmanian reef sites and relates it to
real sea temperature where the two records actually overlap.

Run locally:
    streamlit run dashboards/streamlit_app_reef.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine  # noqa: E402

# Green -> blue -> red: a deliberate multi-hue sequential scale (this
# portfolio's default is single-hue) for "how long ago", framed as a
# temperature-like urgency gradient per explicit request. Trade-off: a
# single hue is generally safer for magnitude (monotonic lightness reads
# unambiguously; multi-hue can look like it has category breaks that
# aren't real) -- kept anyway since the visual intent here is deliberate.
GBR = [
    [0.0, "#1a9850"], [0.25, "#66c2a5"], [0.5, "#2a78d6"],
    [0.75, "#8073ac"], [1.0, "#a50f15"],
]
COLOR_SITES = "#2a78d6"
COLOR_EXTENT = "#eb6834"
COLOR_TEMP = "#2ca25f"  # light green, as originally requested -- was gray, easy to miss on white
TEXT_BLACK = "#000000"
GRID = "#333333"

SPECIES_NOTE = (
    "**\"Invasive urchin\"** = *Centrostephanus rodgersii* (long-spined sea urchin, invasive). "
    "**\"Native urchin\"** = *Heliocidaris erythrogramma* (purple sea urchin, native to Tasmania)."
)
SOURCE_NOTE = (
    "Source: IMOS National Reef Monitoring Network (Reef Life Survey), downloaded via the "
    "Australian Ocean Data Network Portal (portal.aodn.org.au). Temperature: IMOS ANMN Maria "
    "Island National Reference Station (NRSMAI), same portal."
)

st.set_page_config(page_title="Reef Life Survey: Invasive Urchin Monitor", layout="wide")
st.title("Reef Life Survey: Invasive Urchin Spread Monitor")
st.caption(
    "Tracking Centrostephanus rodgersii's spread across Tasmanian reef sites (1992-2026), and "
    "relating it to real sea temperature where the two records overlap. Ties to the long-spined "
    "sea urchin barrens issue threatening kelp forests and, downstream, the abalone and rock "
    "lobster fisheries."
)
st.caption(SPECIES_NOTE)


@st.cache_data(ttl=3600)
def load_data():
    engine = get_engine()
    detections = pd.read_sql("SELECT * FROM vw_urchin_first_detection", engine)
    colonized = pd.read_sql("SELECT * FROM vw_urchin_colonized_sites_by_year ORDER BY yr", engine)
    extent = pd.read_sql("SELECT * FROM vw_urchin_southern_extent ORDER BY yr", engine)
    temp = pd.read_sql(
        """
        SELECT EXTRACT(YEAR FROM day)::int AS yr, AVG(temp_c) AS mean_temp_c, AVG(clim_p90) AS p90_temp_c
        FROM vw_daily_temp_analysis WHERE nominal_depth_m = 20
        GROUP BY yr ORDER BY yr
        """,
        engine,
    )
    sightings = pd.read_sql(
        """
        SELECT site_code, latitude, longitude, EXTRACT(YEAR FROM survey_date)::int AS yr,
               SUM(total) AS count
        FROM rls_clean_invertebrate
        WHERE species_name = 'Centrostephanus rodgersii' AND total > 0
        GROUP BY site_code, latitude, longitude, yr
        ORDER BY yr, site_code
        """,
        engine,
    )
    statewide = pd.read_sql("SELECT * FROM vw_statewide_trend ORDER BY yr", engine)
    combined = pd.read_sql("SELECT * FROM vw_site_year_combined", engine)
    lag = pd.read_sql(
        """
        WITH by_site_year AS (
            SELECT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr,
                SUM(CASE WHEN species_name='Jasus edwardsii' THEN total ELSE 0 END) AS lobster,
                SUM(CASE WHEN species_name='Centrostephanus rodgersii' THEN total ELSE 0 END) AS urchin
            FROM rls_clean_invertebrate GROUP BY site_code, EXTRACT(YEAR FROM survey_date)::int
        )
        SELECT *, LAG(lobster) OVER (PARTITION BY site_code ORDER BY yr) AS lobster_prev_year
        FROM by_site_year
        """,
        engine,
    )
    species_trend = pd.read_sql(
        """
        WITH species_yearly AS (
            SELECT species_name, EXTRACT(YEAR FROM survey_date)::int AS yr, SUM(total) AS total_count
            FROM rls_clean_fish GROUP BY species_name, EXTRACT(YEAR FROM survey_date)::int
        )
        SELECT species_name, REGR_SLOPE(total_count, yr) AS trend_per_year, COUNT(*) AS years_observed
        FROM species_yearly GROUP BY species_name HAVING COUNT(*) >= 10 ORDER BY trend_per_year DESC
        """,
        engine,
    )
    return detections, colonized, extent, temp, sightings, statewide, combined, lag, species_trend


try:
    detections, colonized, extent, temp, sightings, statewide, combined, lag, species_trend = load_data()
except Exception as e:
    st.error(
        "Couldn't reach the database. Check that DATABASE_URL / DB_* are set "
        "(as .env locally, or as Secrets on Streamlit Community Cloud)."
    )
    st.exception(e)
    st.stop()

n_confounded = int(detections["is_confounded"].sum())
n_sightings = int(colonized["colonized_sites"].sum())

# Per-year site list, for the "Colonized sites" hover -- lets a hover
# show which actual sites contributed to that year's count, not just the
# bare number.
sites_by_year = (
    sightings.groupby("yr")["site_code"]
    .apply(lambda s: ", ".join(sorted(s)))
    .reindex(colonized["yr"])
    .fillna("")
    .values
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Sites with confirmed detection", len(detections))
col2.metric("Confounded w/ first survey", f"{n_confounded} ({n_confounded/len(detections):.0%})")
col3.metric("Years of urchin site data", f"{colonized['yr'].min()}-{colonized['yr'].max()}")
col4.metric("Years of real temp data", f"{temp['yr'].min()}-{temp['yr'].max()}")

# --- Map ---
st.subheader("First-detection year by site")
# Tasmania's own geographic centroid, NOT the mean of detection sites --
# every site sits on the coast (mostly the east coast), so centering on
# their mean skews the map east and pushes the island's landmass left of
# frame (found by actually looking at the rendered map, not assumed).
lat_center, lon_center = -42.0, 146.8
MAP_ZOOM = 6.8
cmin, cmax = detections["first_detected_year"].min(), detections["first_detected_year"].max()
confident = detections[~detections["is_confounded"]]
confounded = detections[detections["is_confounded"]]

fig_map = go.Figure()
fig_map.add_trace(go.Scattermapbox(
    lat=confident["latitude"], lon=confident["longitude"],
    mode="markers", name="Confident first detection",
    marker=dict(size=12, color=confident["first_detected_year"], colorscale=GBR,
                 cmin=cmin, cmax=cmax, showscale=True,
                 colorbar=dict(title="First<br>detected", tickfont=dict(color=TEXT_BLACK))),
    text=[f"{r.site_code}<br>First detected: {int(r.first_detected_year)}" for r in confident.itertuples()],
    hoverinfo="text",
))
fig_map.add_trace(go.Scattermapbox(
    lat=confounded["latitude"], lon=confounded["longitude"],
    mode="markers", name="Confounded with first survey year",
    marker=dict(size=9, color=confounded["first_detected_year"], colorscale=GBR,
                 cmin=cmin, cmax=cmax, showscale=False, opacity=0.45),
    text=[f"{r.site_code}<br>First detected: {int(r.first_detected_year)} (= first survey year, uncertain)"
          for r in confounded.itertuples()],
    hoverinfo="text",
))
fig_map.update_layout(
    mapbox=dict(style="open-street-map", zoom=MAP_ZOOM, center=dict(lat=lat_center, lon=lon_center)),
    height=750, margin=dict(l=0, r=0, t=10, b=0),
    # Explicit light paper background -- Streamlit's dark theme otherwise
    # swallows the black colorbar/legend text (found by actually looking
    # at the rendered page, not assumed) since a Scattermapbox figure has
    # no plot_bgcolor of its own to fall back on like the line charts do.
    paper_bgcolor="#fcfcfb",
    font=dict(color=TEXT_BLACK),
    legend=dict(font=dict(color=TEXT_BLACK), x=0.01, y=0.03,
                 bgcolor="rgba(255,255,255,0.85)", bordercolor=TEXT_BLACK, borderwidth=1),
)
st.plotly_chart(fig_map, use_container_width=True)
st.caption(
    f"{len(detections)} sites with a confirmed detection, from {n_sightings} site-year sighting "
    f"records in rls_clean_invertebrate. Faint markers ({n_confounded}/{len(detections)}) are "
    "confounded with that site's first-ever survey year -- can't distinguish genuine arrival from "
    "'nobody looked here before'. " + SOURCE_NOTE
)

# --- Interactive animated map ---
st.subheader("Sightings by year (drag the slider, or press play)")
fig_anim = go.Figure()
years_sorted = sorted(sightings["yr"].unique())
count_min, count_max = sightings["count"].min(), sightings["count"].max()
REDS = ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"]
frames = []
for yr in years_sorted:
    d = sightings[sightings["yr"] == yr]
    frames.append(go.Frame(
        name=str(yr),
        data=[go.Scattermapbox(
            lat=d["latitude"], lon=d["longitude"], mode="markers",
            marker=dict(size=(d["count"] / count_max * 28).clip(lower=6), color=d["count"],
                         colorscale=REDS, cmin=count_min, cmax=count_max, showscale=True,
                         colorbar=dict(title="Count", tickfont=dict(color=TEXT_BLACK))),
            text=[f"{r.site_code}<br>Count: {int(r.count)}" for r in d.itertuples()],
            hoverinfo="text",
        )],
    ))
first = sightings[sightings["yr"] == years_sorted[0]]
fig_anim.add_trace(go.Scattermapbox(
    lat=first["latitude"], lon=first["longitude"], mode="markers",
    marker=dict(size=(first["count"] / count_max * 28).clip(lower=6), color=first["count"],
                 colorscale=REDS, cmin=count_min, cmax=count_max, showscale=True,
                 colorbar=dict(title="Count", tickfont=dict(color=TEXT_BLACK))),
    text=[f"{r.site_code}<br>Count: {int(r.count)}" for r in first.itertuples()],
    hoverinfo="text",
))
fig_anim.frames = frames
fig_anim.update_layout(
    mapbox=dict(style="open-street-map", zoom=MAP_ZOOM, center=dict(lat=lat_center, lon=lon_center)),
    height=750, margin=dict(l=0, r=0, t=10, b=0),
    paper_bgcolor="#fcfcfb", font=dict(color=TEXT_BLACK),
    updatemenus=[dict(
        type="buttons", showactive=False, x=0.02, y=0.02, xanchor="left", yanchor="bottom",
        buttons=[dict(label="Play", method="animate",
                       args=[None, dict(frame=dict(duration=500, redraw=True), fromcurrent=True)]),
                  dict(label="Pause", method="animate",
                       args=[[None], dict(frame=dict(duration=0), mode="immediate")])],
    )],
    sliders=[dict(
        active=0, x=0.02, y=0, len=0.9,
        currentvalue=dict(prefix="Year: ", font=dict(color=TEXT_BLACK)),
        font=dict(color=TEXT_BLACK),
        steps=[dict(label=str(yr), method="animate",
                     args=[[str(yr)], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                for yr in years_sorted],
    )],
)
st.plotly_chart(fig_anim, use_container_width=True)
st.caption(
    f"{len(sightings)} site-year sighting records, {sightings['site_code'].nunique()} distinct "
    f"sites, {years_sorted[0]}-{years_sorted[-1]}. Marker size and color both encode that year's "
    "count. " + SOURCE_NOTE
)

# --- Timeline: sites + extent, each with a shared temperature overlay ---
st.subheader("Spread over time, vs. sea temperature")
st.caption(
    f"Temperature panel covers {temp['yr'].min()}-{temp['yr'].max()} only (the only real loaded "
    "record) -- overlaps just the tail of the full urchin timeline, not stretched to look longer."
)
fig_tl = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
    specs=[[{"secondary_y": True}], [{"secondary_y": True}]],
    subplot_titles=("Colonized sites (count) vs. sea temperature", "Southernmost extent (latitude) vs. sea temperature"),
)
temp_range = [min(temp["mean_temp_c"].min(), temp["p90_temp_c"].min()) - 0.5,
              max(temp["mean_temp_c"].max(), temp["p90_temp_c"].max()) + 0.5]

GRID_NTICKS = 6  # same tick count on every y-axis (both primary axes + both secondary axes)
                 # so gridline spacing reads as consistent panel to panel, not just per-axis auto-chosen.

for row in (1, 2):
    fig_tl.add_trace(go.Scatter(x=temp["yr"], y=temp["p90_temp_c"], mode="lines",
                                  line=dict(width=0), showlegend=False, hoverinfo="skip"),
                       row=row, col=1, secondary_y=True)
    fig_tl.add_trace(go.Scatter(x=temp["yr"], y=temp["mean_temp_c"], mode="lines",
                                  line=dict(width=0), fill="tonexty", fillcolor="rgba(44,162,95,0.28)",
                                  name="Sea temp mean-p90 band", showlegend=(row == 1), legendgroup="temp",
                                  hoverinfo="skip"),
                       row=row, col=1, secondary_y=True)
    fig_tl.add_trace(go.Scatter(x=temp["yr"], y=temp["mean_temp_c"], mode="lines+markers",
                                  line=dict(color=COLOR_TEMP, width=2, dash="dot"),
                                  name="Sea temp (mean, °C)*", legendgroup="temp", showlegend=(row == 1),
                                  hovertemplate="%{x}: %{y:.2f} °C<extra>Sea temp (mean)</extra>"),
                       row=row, col=1, secondary_y=True)

fig_tl.add_trace(go.Scatter(x=colonized["yr"], y=colonized["colonized_sites"], mode="lines+markers",
                              line=dict(color=COLOR_SITES, width=2), name="Colonized sites",
                              customdata=sites_by_year,
                              hovertemplate="%{x}: %{y} site(s)<br>%{customdata}<extra>Colonized sites</extra>"),
                   row=1, col=1, secondary_y=False)
fig_tl.add_trace(go.Scatter(x=extent["yr"], y=extent["southernmost_latitude"], mode="lines+markers",
                              line=dict(color=COLOR_EXTENT, width=2), name="Southernmost latitude",
                              hovertemplate="%{x}: %{y:.2f}°<extra>Southernmost latitude</extra>"),
                   row=2, col=1, secondary_y=False)

fig_tl.update_layout(
    height=750, font=dict(color=TEXT_BLACK),
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    legend=dict(font=dict(color=TEXT_BLACK), orientation="h", y=1.08),
    hovermode="closest",
)
fig_tl.update_annotations(font=dict(color=TEXT_BLACK))
for row in (1, 2):
    fig_tl.update_xaxes(gridcolor=GRID, linecolor=TEXT_BLACK, zerolinecolor=TEXT_BLACK,
                          tickfont=dict(color=TEXT_BLACK), tickangle=-45, row=row, col=1)
    fig_tl.update_yaxes(gridcolor=GRID, linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK),
                          nticks=GRID_NTICKS, secondary_y=False, row=row, col=1)
    fig_tl.update_yaxes(range=temp_range, linecolor=TEXT_BLACK, tickfont=dict(color=COLOR_TEMP),
                          title=dict(text="Sea temp (°C)*", font=dict(color=COLOR_TEMP)),
                          nticks=GRID_NTICKS, showgrid=False, secondary_y=True, row=row, col=1)
st.plotly_chart(fig_tl, use_container_width=True)
st.caption(
    f"{len(colonized)} year(s) of urchin site-count data, {len(temp)} year(s) of real temperature "
    "data. Right axis (green band + dotted line) is sea temperature on both panels, sharing the "
    "same scale, so the band's position/height is directly comparable panel to panel. "
    "\\* Temperature measured at the Maria Island National Reference Station specifically, used "
    "here as a representative proxy for Tasmanian east-coast sea temperature more broadly -- not a "
    "Tasmania-wide average. " + SOURCE_NOTE
)

# =====================================================================
# Analysis 1: trend near Maria Island -- urchin, canopy, predators,
# each overlaid with the real Maria Island temperature record
# =====================================================================
st.header("Trend near Maria Island: urchin, canopy, and predators vs. sea temperature")
MI_SITES_NOTE = (
    "MIR-S2, MIR-S3, MIR-S5, MIR-S13, MIR-S14 -- the 5 Maria Island Reserve sites with the densest "
    "survey history (39-43 surveys each, 1992-2026), 12-15km from the Maria Island NRS mooring. "
    "Restricted from statewide to these specific nearby sites so the temperature overlay is a "
    "genuinely local comparison, not a state-scale stretch."
)
fig_sw = make_subplots(
    rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
    specs=[[{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": True}]],
    subplot_titles=("Invasive urchin count vs. sea temp", "Canopy cover (%) vs. sea temp",
                      "Lobster & abalone count vs. sea temp"),
)
temp_range_sw = [min(temp["mean_temp_c"].min(), temp["p90_temp_c"].min()) - 0.5,
                  max(temp["mean_temp_c"].max(), temp["p90_temp_c"].max()) + 0.5]
for row in (1, 2, 3):
    fig_sw.add_trace(go.Scatter(x=temp["yr"], y=temp["p90_temp_c"], mode="lines", line=dict(width=0),
                                  showlegend=False, hoverinfo="skip"), row=row, col=1, secondary_y=True)
    fig_sw.add_trace(go.Scatter(x=temp["yr"], y=temp["mean_temp_c"], mode="lines", line=dict(width=0),
                                  fill="tonexty", fillcolor="rgba(44,162,95,0.28)",
                                  name="Sea temp mean-p90 band*", legendgroup="temp", showlegend=(row == 1)),
                       row=row, col=1, secondary_y=True)
    fig_sw.add_trace(go.Scatter(x=temp["yr"], y=temp["mean_temp_c"], mode="lines+markers",
                                  line=dict(color=COLOR_TEMP, width=2, dash="dot"), name="Sea temp (mean)*",
                                  legendgroup="temp", showlegend=(row == 1)), row=row, col=1, secondary_y=True)
fig_sw.add_trace(go.Scatter(x=statewide["yr"], y=statewide["invasive_urchin"], mode="lines+markers",
                              line=dict(color="#a50f15", width=2), name="Invasive urchin"),
                   row=1, col=1, secondary_y=False)
fig_sw.add_trace(go.Scatter(x=statewide["yr"], y=statewide["canopy_pct"], mode="lines+markers",
                              line=dict(color="#2a78d6", width=2), name="Canopy %"),
                   row=2, col=1, secondary_y=False)
fig_sw.add_trace(go.Scatter(x=statewide["yr"], y=statewide["lobster"], mode="lines+markers",
                              line=dict(color=COLOR_SITES, width=2), name="Lobster"),
                   row=3, col=1, secondary_y=False)
fig_sw.add_trace(go.Scatter(x=statewide["yr"], y=statewide["abalone"], mode="lines+markers",
                              line=dict(color=COLOR_EXTENT, width=2), name="Abalone"),
                   row=3, col=1, secondary_y=False)
fig_sw.update_layout(height=950, font=dict(color=TEXT_BLACK), plot_bgcolor="#fcfcfb",
                       paper_bgcolor="#fcfcfb", legend=dict(font=dict(color=TEXT_BLACK), orientation="h", y=1.05))
fig_sw.update_annotations(font=dict(color=TEXT_BLACK))
for row in (1, 2, 3):
    fig_sw.update_xaxes(gridcolor=GRID, linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK),
                          tickangle=-45, row=row, col=1)
    fig_sw.update_yaxes(gridcolor=GRID, linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK),
                          nticks=6, secondary_y=False, row=row, col=1)
    fig_sw.update_yaxes(range=temp_range_sw, linecolor=TEXT_BLACK, tickfont=dict(color=COLOR_TEMP),
                          title=dict(text="Sea temp (°C)*", font=dict(color=COLOR_TEMP)),
                          nticks=6, showgrid=False, secondary_y=True, row=row, col=1)
st.plotly_chart(fig_sw, use_container_width=True)
st.caption(
    f"{len(statewide)} years of urchin/canopy/predator data near Maria Island, {len(temp)} years of "
    f"real temperature data. Sites used: {MI_SITES_NOTE} " + SOURCE_NOTE
)

# =====================================================================
# Analysis 3: canopy vs. urchin-density tier
# =====================================================================
st.header("Does canopy cover fall as invasive urchin density rises?")
tier_order = ["none", "low", "medium", "high"]
combined = combined.copy()
combined["urchin_density_tier"] = pd.cut(
    combined["invasive_urchin_count"], bins=[-0.1, 0, 5, 20, combined["invasive_urchin_count"].max()],
    labels=tier_order,
)
box_data = combined.dropna(subset=["canopy_pct"])
fig_box = go.Figure()
for tier, color in zip(tier_order, ["#1a9850", "#66c2a5", "#eb6834", "#a50f15"]):
    d = box_data[box_data["urchin_density_tier"] == tier]
    fig_box.add_trace(go.Box(y=d["canopy_pct"], name=tier, marker=dict(color=color), boxmean=True))
fig_box.update_layout(
    height=500, font=dict(color=TEXT_BLACK), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    yaxis=dict(title=dict(text="Canopy %", font=dict(color=TEXT_BLACK)), gridcolor=GRID,
                linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)),
    xaxis=dict(title=dict(text="Invasive urchin density tier (real quartile-based cutoffs: 0 / 1-5 / 6-20 / 21+)",
                            font=dict(color=TEXT_BLACK)),
                linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)),
    showlegend=False,
)
st.plotly_chart(fig_box, use_container_width=True)
avg_by_tier = box_data.groupby("urchin_density_tier", observed=True)["canopy_pct"].mean().reindex(tier_order)
st.caption(
    f"n={len(box_data)} site-years with both metrics. Mean canopy % by tier: "
    + ", ".join(f"{t}={v:.1f}%" for t, v in avg_by_tier.items()) + ". "
    "**Counterintuitive result, stated plainly**: canopy is *higher*, not lower, at high-urchin-density "
    "sites in this pooled cross-sectional view -- the opposite of the barren-formation hypothesis. Most "
    "likely explanation: this pools all sites/years together, so it captures *where urchins are* "
    "(kelp-rich reef, their preferred habitat) rather than *what urchins do to a site over time*. "
    "Testing the actual barren-formation hypothesis needs a within-site, before/after time-series "
    "(same site, canopy % before vs. after urchin arrival), not a pooled correlation across different "
    "sites. " + SOURCE_NOTE
)

# =====================================================================
# Analysis 4: fish community vs. canopy status
# =====================================================================
st.header("Fish community: low-canopy vs. healthy-canopy sites")
CANOPY_CUTOFF = combined["canopy_pct"].quantile(0.25)
fish_data = combined.dropna(subset=["canopy_pct", "fish_richness"]).copy()
fish_data["status"] = fish_data["canopy_pct"].apply(lambda c: "low_canopy" if c < CANOPY_CUTOFF else "healthy")
fish_summary = fish_data.groupby("status").agg(
    n=("site_code", "count"), avg_richness=("fish_richness", "mean"), avg_biomass=("fish_biomass", "mean"),
).reindex(["low_canopy", "healthy"])
fc1, fc2 = st.columns(2)
fig_rich = go.Figure(go.Bar(x=fish_summary.index, y=fish_summary["avg_richness"],
                              marker=dict(color=["#eb6834", "#1a9850"])))
fig_rich.update_layout(height=400, font=dict(color=TEXT_BLACK), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
                         title=dict(text="Avg fish species richness", font=dict(color=TEXT_BLACK)),
                         yaxis=dict(gridcolor=GRID, linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)),
                         xaxis=dict(linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)))
fc1.plotly_chart(fig_rich, use_container_width=True)
fig_bio = go.Figure(go.Bar(x=fish_summary.index, y=fish_summary["avg_biomass"],
                             marker=dict(color=["#eb6834", "#1a9850"])))
fig_bio.update_layout(height=400, font=dict(color=TEXT_BLACK), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
                        title=dict(text="Avg fish biomass (g)", font=dict(color=TEXT_BLACK)),
                        yaxis=dict(gridcolor=GRID, linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)),
                        xaxis=dict(linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)))
fc2.plotly_chart(fig_bio, use_container_width=True)
st.caption(
    f"'Low canopy' = canopy % below the real 25th percentile ({CANOPY_CUTOFF:.1f}%), not a guessed "
    "threshold -- true near-zero barrens (<5% canopy) are rare in this dataset (17 site-years total), "
    "too few to compare on their own. n={0} low_canopy, n={1} healthy. Consistent with the Analysis-3 "
    "finding: fish richness and biomass are *higher*, not lower, at low-canopy sites here -- again "
    "likely a where-urchins-are-vs-what-they-do confound, not evidence that barrens help fish."
    .format(int(fish_summary.loc["low_canopy", "n"]), int(fish_summary.loc["healthy", "n"])) + " " + SOURCE_NOTE
)

# =====================================================================
# Analysis 6: native vs. invasive urchin -- do they differ?
# =====================================================================
st.header("Native vs. invasive urchin: correlation with canopy")
corr_data = combined.dropna(subset=["canopy_pct"])
corr_invasive = corr_data["canopy_pct"].corr(corr_data["invasive_urchin_count"])
corr_native = corr_data["canopy_pct"].corr(corr_data["native_urchin_count"])
cc1, cc2 = st.columns(2)
cc1.metric("Corr(canopy %, invasive urchin count)", f"{corr_invasive:+.3f}")
cc2.metric("Corr(canopy %, native urchin count)", f"{corr_native:+.3f}")
st.caption(
    f"n={len(corr_data)} site-years. Both correlations are weak, and in opposite directions -- invasive "
    "urchin count correlates weakly *positively* with canopy (again, likely reflecting where urchins "
    "are found rather than their impact), native urchin count weakly *negatively*. Neither is strong "
    "enough to call a real finding on its own; the honest takeaway is that a pooled correlation like "
    "this can't distinguish habitat preference from ecological impact -- see the Analysis-3 caveat "
    "above. " + SOURCE_NOTE
)

# =====================================================================
# Analysis 5 (bonus): predator (lobster) vs. invasive urchin, with lag
# =====================================================================
st.header("Predator check: does last year's lobster count predict this year's urchin count?")
lag_data = lag.dropna(subset=["lobster_prev_year"]).copy()
fig_lag = go.Figure(go.Scatter(
    x=lag_data["lobster_prev_year"], y=lag_data["urchin"], mode="markers",
    marker=dict(color=lag_data["yr"], colorscale=GBR, showscale=True,
                 colorbar=dict(title="Year", tickfont=dict(color=TEXT_BLACK)), size=6, opacity=0.6),
    text=[f"{r.site_code}, {r.yr}" for r in lag_data.itertuples()], hoverinfo="text",
))
fig_lag.update_layout(
    height=500, font=dict(color=TEXT_BLACK), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    xaxis=dict(title=dict(text="Lobster count, previous year (same site)", font=dict(color=TEXT_BLACK)),
                gridcolor=GRID, linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)),
    yaxis=dict(title=dict(text="Invasive urchin count, this year", font=dict(color=TEXT_BLACK)),
                gridcolor=GRID, linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)),
)
st.plotly_chart(fig_lag, use_container_width=True)
corr_lag = lag_data["lobster_prev_year"].corr(lag_data["urchin"])
st.caption(
    f"n={len(lag_data)} site-year pairs. Correlation: {corr_lag:+.3f} -- essentially zero. No evidence "
    "in this pooled data that more lobsters last year predicts fewer urchins this year (the biocontrol "
    "hypothesis). This doesn't rule out a real effect (lobster predation on urchins is documented at "
    "the individual-animal level), but if it's happening at a scale that shows up in site-level RLS "
    "counts, this simple lag correlation isn't detecting it. " + SOURCE_NOTE
)

# =====================================================================
# Analysis 7 (bonus): which fish species are rising/falling
# =====================================================================
st.header("Which fish species are rising or falling over time?")
# Common names from general reference, not from the dataset (RLS only
# provides scientific names) -- worth double-checking against a field
# guide before quoting confidently in an interview.
COMMON_NAMES = {
    "Trachinops caudimaculatus": "Southern hulafish", "Caesioperca rasor": "Barber perch",
    "Neoodax balteatus": "Little rock whiting", "Notolabrus tetricus": "Bluethroat wrasse",
    "Pempheris multiradiata": "Bigscale bullseye", "Trachurus declivis": "Common jack mackerel",
    "Pictilabrus laticlavius": "Senator wrasse", "Notolabrus fucicola": "Purple wrasse",
    "Acanthaluteres vittiger": "Toothbrush leatherjacket", "Diodon nichthemerus": "Globefish",
    "Atypichthys strigatus": "Mado", "Scorpis lineolata": "Silver sweep",
    "Dinolestes lewini": "Longfin pike", "Olisthops cyanomelas": "Herring cale",
    "Caesioperca lepidoptera": "Butterfly perch", "Parma microlepis": "White-ear",
    "Upeneichthys vlamingii": "Blue-spotted goatfish", "Aplodactylus arctidens": "Marblefish",
    "Girella zebra": "Zebra fish", "Scorpis aequipinnis": "Sea sweep",
}
def display_name(sci):
    common = COMMON_NAMES.get(sci)
    return f"{common} ({sci})" if common else sci

top_rising = species_trend.head(10).sort_values("trend_per_year").copy()
top_falling = species_trend.tail(10).sort_values("trend_per_year").copy()
top_rising["label"] = top_rising["species_name"].apply(display_name)
top_falling["label"] = top_falling["species_name"].apply(display_name)
fig_species = go.Figure()
fig_species.add_trace(go.Bar(y=top_rising["label"], x=top_rising["trend_per_year"],
                               orientation="h", marker=dict(color="#1a9850"), name="Rising"))
fig_species.add_trace(go.Bar(y=top_falling["label"], x=top_falling["trend_per_year"],
                               orientation="h", marker=dict(color="#a50f15"), name="Falling"))
fig_species.update_layout(
    height=600, font=dict(color=TEXT_BLACK), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    xaxis=dict(title=dict(text="Change in count per year  (right of 0 = rising, left of 0 = falling)",
                            font=dict(color=TEXT_BLACK)), gridcolor=GRID, zerolinecolor=TEXT_BLACK,
                zerolinewidth=2, linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)),
    yaxis=dict(linecolor=TEXT_BLACK, tickfont=dict(color=TEXT_BLACK)),
    legend=dict(font=dict(color=TEXT_BLACK)), margin=dict(l=260),
)
st.plotly_chart(fig_species, use_container_width=True)
st.caption(
    f"Top 10 rising and top 10 falling fish species by linear trend (species observed in >=10 distinct "
    f"years only, {species_trend['species_name'].nunique()} species qualify). The x-axis is a **rate of "
    "change** (count/year), not a year -- 0 means no change, bars extend right for species increasing "
    "and left for species decreasing. Raw count trend, not controlled for survey effort changes over "
    "time -- a real trend, but treat the exact slope as indicative, not precise. Common names are from "
    "general reference (not in the source dataset) -- verify before quoting. " + SOURCE_NOTE
)
