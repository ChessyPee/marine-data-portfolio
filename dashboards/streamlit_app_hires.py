"""
Maria Island Hi-Res Mooring Monitor -- Streamlit app.
Reads directly from the hi-res views built in maria_island/schema_hires.sql
(vw_daily_temp_analysis, vw_warm_spell_groups_hires, vw_stratification), so
it always reflects whatever is currently loaded in the database.

This is the companion dashboard to dashboards/streamlit_app.py (the monthly
long-term series) -- this one works from raw 15-minute mooring readings at
two real depths (20m / 85m), so it can show three different things the
monthly aggregate can't: a same-day surface-vs-bottom comparison
(stratification), discrete warm-spell events as a timeline rather than a
noisy daily line, and per-depth trend/anomaly detail.

Run locally:
    streamlit run dashboards/streamlit_app_hires.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine  # noqa: E402

# Colors from the portfolio's validated default palette (dataviz skill):
# fixed categorical order -- slot 1 (blue) = shallower depth, slot 2
# (orange) = deeper depth, wherever depth appears as a series. Diverging
# blue<->red with a gray midpoint for stratification (sign, not identity).
COLOR_20M = "#2a78d6"
COLOR_85M = "#eb6834"
COLOR_WARM_MARKER = "#fab219"
COLOR_MUTED = "#898781"
COLOR_GRID = "#333333"
COLOR_STRAT_POS = "#e34948"   # surface warmer than bottom
COLOR_STRAT_NEG = "#2a78d6"   # surface cooler than bottom (inversion)
COLOR_STRAT_MID = "#c3c2b7"
TEXT_BLACK = "#000000"

# Shared layout pieces so every chart's legend labels, axis tick numbers,
# axis titles, and gridlines render in black rather than the softer default
# gray -- readability over subtlety, per explicit request.
AXIS_STYLE = dict(
    gridcolor=COLOR_GRID, linecolor=TEXT_BLACK, zerolinecolor=TEXT_BLACK,
    tickfont=dict(color=TEXT_BLACK), title_font=dict(color=TEXT_BLACK),
)
LEGEND_STYLE_H = dict(orientation="h", y=1.08, font=dict(color=TEXT_BLACK))

st.set_page_config(page_title="Maria Island Hi-Res Mooring Monitor", layout="wide")
st.title("Maria Island Hi-Res Mooring Monitor")
st.caption(
    "Raw 15-minute sensor readings, IMOS/AODN National Reference Station Maria "
    "Island (NRSMAI), two depths (20m / 85m). Companion to the "
    "long-term monthly dashboard -- this one can show same-day surface-vs-bottom "
    "structure and discrete warm-spell events, not just a monthly trend line."
)


@st.cache_data(ttl=3600)
def load_data():
    engine = get_engine()
    daily = pd.read_sql(
        "SELECT * FROM vw_daily_temp_analysis ORDER BY nominal_depth_m, day",
        engine, parse_dates=["day"],
    )
    spells = pd.read_sql(
        "SELECT * FROM vw_warm_spell_groups_hires ORDER BY nominal_depth_m, spell_start",
        engine, parse_dates=["spell_start", "spell_end"],
    )
    strat = pd.read_sql(
        "SELECT * FROM vw_stratification ORDER BY day", engine, parse_dates=["day"],
    )
    trend = pd.read_sql(
        """
        SELECT d.nominal_depth_m,
               ROUND(regr_slope(r.temp_c,
                     EXTRACT(EPOCH FROM r."timestamp") / (365.25*24*3600))::numeric, 4
               ) AS deg_c_per_year
        FROM fact_sensor_reading r
        JOIN dim_sensor_deployment d ON d.deployment_id = r.deployment_id
        WHERE r.temp_qc IN (1, 2)
        GROUP BY d.nominal_depth_m
        """,
        engine,
    )
    coverage = pd.read_sql(
        """
        SELECT COUNT(*) AS n_readings,
               COUNT(DISTINCT deployment_id) AS n_deployments,
               MIN("timestamp") AS earliest, MAX("timestamp") AS latest
        FROM fact_sensor_reading
        """,
        engine,
    ).iloc[0]
    return daily, spells, strat, trend, coverage


try:
    daily, spells, strat, trend, coverage = load_data()
except Exception as e:
    st.error(
        "Couldn't reach the database. Check that DATABASE_URL / DB_* are set "
        "(as .env locally, or as Secrets on Streamlit Community Cloud)."
    )
    st.exception(e)
    st.stop()

st.caption(
    f"Analysis built from **{coverage['n_readings']:,} individual sensor readings** "
    f"across {coverage['n_deployments']} instrument deployments, "
    f"{coverage['earliest']:%d %b %Y} to {coverage['latest']:%d %b %Y} "
    "(15-minute sampling interval, two depths per deployment). "
    "Source: IMOS ANMN National Mooring Network Facility -- Temperature and Salinity "
    "Time-Series, Maria Island National Reference Station (NRSMAI), downloaded via the "
    "[Australian Ocean Data Network Portal](https://portal.aodn.org.au/)."
)

depth_20 = daily[daily["nominal_depth_m"] == 20].sort_values("day")
depth_85 = daily[daily["nominal_depth_m"] == 85].sort_values("day")
latest_strat = strat.iloc[-1] if len(strat) else None
trend_20 = trend.loc[trend["nominal_depth_m"] == 20, "deg_c_per_year"]
trend_85 = trend.loc[trend["nominal_depth_m"] == 85, "deg_c_per_year"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Latest surface (20m)", f"{depth_20.iloc[-1]['temp_c']:.2f} °C" if len(depth_20) else "n/a")
col2.metric("Latest bottom (85m)", f"{depth_85.iloc[-1]['temp_c']:.2f} °C" if len(depth_85) else "n/a")
col3.metric(
    "Stratification (surface - bottom)",
    f"{latest_strat['stratification_c']:+.2f} °C" if latest_strat is not None else "n/a",
)
col4.metric("Warm spells (3+ days) on record", len(spells))

record_years = (coverage["latest"] - coverage["earliest"]).days / 365.25
st.caption(
    f"Linear trend over the record: 20m {trend_20.values[0]:+.3f} °C/yr, "
    f"85m {trend_85.values[0]:+.3f} °C/yr. Only ~{record_years:.0f} years of data -- still "
    "short for a confident climate trend; treat as deployment-to-deployment "
    "variability more than a settled warming signal, though longer than before."
)

st.subheader("Daily temperature by depth, with anomaly flags")
depth_choice = st.radio("Detail view for:", ["20m (surface)", "85m (bottom)"], horizontal=True)
detail = depth_20 if depth_choice.startswith("20") else depth_85
detail_color = COLOR_20M if depth_choice.startswith("20") else COLOR_85M

fig1 = go.Figure()
fig1.add_trace(go.Scatter(
    x=detail["day"], y=detail["clim_p90"], mode="lines",
    line=dict(width=0), showlegend=False, hoverinfo="skip",
))
fig1.add_trace(go.Scatter(
    x=detail["day"], y=detail["clim_mean"], mode="lines",
    line=dict(width=0), fill="tonexty", fillcolor="rgba(137,135,129,0.15)",
    name="Climatology (mean-p90 band)",
))
fig1.add_trace(go.Scatter(
    x=detail["day"], y=detail["temp_c"], mode="lines", name="Daily mean temp",
    line=dict(width=2, color=detail_color),
))
warm = detail[detail["is_warm_day"]]
fig1.add_trace(go.Scatter(
    x=warm["day"], y=warm["temp_c"], mode="markers", name="Anomalously warm day",
    marker=dict(color=COLOR_WARM_MARKER, size=6),
))
fig1.update_layout(
    height=420, xaxis_title="Date", yaxis_title="Temperature (°C)",
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    font=dict(color=TEXT_BLACK),
    xaxis=AXIS_STYLE, yaxis=AXIS_STYLE,
    legend=LEGEND_STYLE_H,
)
st.plotly_chart(fig1, use_container_width=True)

st.subheader("Warm-spell events (3+ consecutive anomalously warm days)")
# Drawn as thick line segments rather than bar+base+timedelta -- the latter
# combination doesn't render reliably against a datetime axis on this
# Plotly version (bars silently fell back to a linear 0-N axis).
fig3 = go.Figure()
for depth_val, color, label in [(20, COLOR_20M, "20m (surface)"), (85, COLOR_85M, "85m (bottom)")]:
    d = spells[spells["nominal_depth_m"] == depth_val]
    first = True
    for _, row in d.iterrows():
        fig3.add_trace(go.Scatter(
            x=[row["spell_start"], row["spell_end"] + pd.Timedelta(days=1)],
            y=[label, label], mode="lines",
            line=dict(color=color, width=18),
            name=label, legendgroup=label, showlegend=False,
            hovertemplate=(
                f"{row['spell_start']:%Y-%m-%d} to {row['spell_end']:%Y-%m-%d}"
                f"<br>{row['n_days']} days, avg {row['avg_temp_c']} °C<extra></extra>"
            ),
        ))
        first = False
fig3.update_layout(
    height=280, xaxis_title="Date",
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    font=dict(color=TEXT_BLACK),
    xaxis=AXIS_STYLE, yaxis=AXIS_STYLE,
    showlegend=False,
)
st.plotly_chart(fig3, use_container_width=True)

st.subheader("Surface vs. bottom, both depths together")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=depth_20["day"], y=depth_20["temp_c"], mode="lines",
                           name="20m (surface)", line=dict(width=1.5, color=COLOR_20M)))
fig2.add_trace(go.Scatter(x=depth_85["day"], y=depth_85["temp_c"], mode="lines",
                           name="85m (bottom)", line=dict(width=1.5, color=COLOR_85M)))
fig2.update_layout(
    height=350, xaxis_title="Date", yaxis_title="Temperature (°C)",
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    font=dict(color=TEXT_BLACK),
    xaxis=AXIS_STYLE, yaxis=AXIS_STYLE,
    legend=LEGEND_STYLE_H,
)
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Stratification: surface minus bottom temperature, by day")
strat_colors = [COLOR_STRAT_POS if v >= 0 else COLOR_STRAT_NEG for v in strat["stratification_c"]]
fig4 = go.Figure()
fig4.add_trace(go.Bar(
    x=strat["day"], y=strat["stratification_c"],
    marker=dict(color=strat_colors), name="Surface - bottom",
))
fig4.add_hline(y=0, line=dict(color=COLOR_STRAT_MID, width=1))
fig4.update_layout(
    height=350, xaxis_title="Date", yaxis_title="Δ Temperature (°C)",
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    font=dict(color=TEXT_BLACK),
    xaxis=AXIS_STYLE, yaxis=AXIS_STYLE,
    showlegend=False,
)
st.plotly_chart(fig4, use_container_width=True)
st.caption(
    "Positive (red) = surface warmer than bottom, the usual stratified case. "
    "Negative (blue) = surface cooler than bottom -- a mixing/inversion event, "
    "worth cross-checking against wind/storm records if it persists."
)

st.divider()
st.caption(
    f"**Data**: {coverage['n_readings']:,} readings, {coverage['n_deployments']} deployments, "
    f"{coverage['earliest']:%Y-%m-%d} to {coverage['latest']:%Y-%m-%d}. "
    "**Source**: IMOS Australian National Mooring Network (ANMN) Facility -- Temperature "
    "and Salinity Time-Series, National Reference Station Maria Island (NRSMAI). "
    "Downloaded from the [AODN Portal](https://portal.aodn.org.au/) "
    "(portal.aodn.org.au). Data provided by IMOS, a national collaborative research "
    "infrastructure supported by the Australian Government."
)
