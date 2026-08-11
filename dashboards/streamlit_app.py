"""
Maria Island Ocean Warming Monitor -- Streamlit app.
Reads directly from Postgres (fact_maria_island_temp + vw_warm_spell_groups),
so it always reflects whatever is currently loaded in the database.

Run locally:
    streamlit run dashboards/streamlit_app.py

Deploy for free:
    Push this repo to GitHub (public), then deploy at
    https://share.streamlit.io -- point it at this file. Add your DB
    secrets under the app's "Secrets" settings in the same KEY = "value"
    format as .env. The app sleeps after ~12 hours idle; open it a few
    minutes before you need to demo it.
"""

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine  # noqa: E402

st.set_page_config(page_title="Maria Island Ocean Warming Monitor", layout="wide")
st.title("Maria Island Ocean Warming Monitor")
st.caption(
    "Long-term surface temperature record, IMOS/AODN National Reference Station, "
    "Tasmania's east coast. Ties to NRE Tas's 'Report Signs of a Marine Heatwave' function."
)


@st.cache_data(ttl=3600)
def load_data():
    engine = get_engine()
    monthly = pd.read_sql(
        "SELECT * FROM vw_temp_rolling_avg ORDER BY month_date", engine,
        parse_dates=["month_date"],
    )
    spells = pd.read_sql(
        "SELECT * FROM vw_warm_spell_groups ORDER BY spell_start", engine,
        parse_dates=["spell_start", "spell_end"],
    )
    return monthly, spells


try:
    monthly, spells = load_data()
except Exception as e:
    st.error(
        "Couldn't reach the database. Check that DATABASE_URL / DB_* are set "
        "(as .env locally, or as Secrets on Streamlit Community Cloud)."
    )
    st.exception(e)
    st.stop()

col1, col2, col3 = st.columns(3)
latest = monthly.iloc[-1]
col1.metric("Latest month", latest["month_date"].strftime("%b %Y"), f"{latest['temp_c']} °C")
col2.metric("Anomaly vs. climatology", f"{latest['anomaly_c']:+.2f} °C")
col3.metric("Warm spells (3+ months) on record", len(spells))

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=monthly["month_date"], y=monthly["temp_c"],
    mode="lines", name="Monthly mean", line=dict(width=1, color="lightgray"),
))
fig.add_trace(go.Scatter(
    x=monthly["month_date"], y=monthly["rolling_12mo_avg_c"],
    mode="lines", name="12-month rolling average", line=dict(width=2.5, color="firebrick"),
))
warm = monthly[monthly["is_warm_month"]]
fig.add_trace(go.Scatter(
    x=warm["month_date"], y=warm["temp_c"],
    mode="markers", name="Anomalously warm month",
    marker=dict(color="orange", size=6),
))
fig.update_layout(
    title="Surface temperature: monthly values, 12-month trend, and warm-month flags",
    xaxis_title="Date", yaxis_title="Temperature (°C)", height=500,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Warm spells (3+ consecutive anomalously warm months)")
st.dataframe(spells, use_container_width=True)

st.caption(
    "Note: 'warm month' here means above that calendar month's 90th-percentile "
    "temperature across the full record -- a simplified monthly stand-in for the "
    "formal daily marine heatwave definition (Hobday et al. 2016), not a replacement for it."
)
