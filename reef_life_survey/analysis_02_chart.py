"""
Analysis 2 charts: geographic spread of the invasive urchin
(Centrostephanus rodgersii). Reads views from
analysis_02_urchin_spread.sql plus Maria Island's vw_daily_temp_analysis
(hi-res mooring project) for the temperature-relationship panel -- no
cleaning/aggregation logic here, that's all already done in SQL; this
file only visualizes.

Display labels use "invasive urchin" / "native urchin" instead of the
full scientific names -- the underlying SQL still filters on the real
species_name for correctness; only the chart text is shortened. Every
chart carries a footnote translating those short labels back to the
scientific name, plus the data-point count and source, so nothing here
means anything unless you can trace where it came from.

Run:
    python analysis_02_chart.py
Output:
    urchin_first_detection_map.png
    urchin_spread_timeline.png
"""

import sys
import textwrap
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine  # noqa: E402

OUT_DIR = Path(__file__).parent

# Tasmania's own geographic centroid, NOT the mean of detection sites --
# every site sits on the coast (mostly the east coast), so centering on
# their mean skews the map east and pushes the island's landmass left of
# frame. Centering on the island itself keeps it visually centered
# regardless of where the data happens to cluster.
TASMANIA_CENTER = dict(lat=-42.0, lon=146.8)
TASMANIA_ZOOM = 6.8

# Green -> blue -> red: a deliberate multi-hue sequential scale (the
# portfolio default is single-hue) per explicit request, framing "how
# long ago" as a temperature-like gradient. Trade-off worth knowing: a
# single hue is generally safer (monotonic lightness reads unambiguously
# as magnitude; a multi-hue ramp can look like it has category breaks
# where there aren't any) -- kept anyway since the visual intent here is
# deliberate, not accidental.
GBR = [
    [0.0, "#1a9850"], [0.25, "#66c2a5"], [0.5, "#2a78d6"],
    [0.75, "#8073ac"], [1.0, "#a50f15"],
]
COLOR_LINE = "#2a78d6"
COLOR_TEMP = "#eb6834"
TEXT_BLACK = "#000000"
GRID = "#333333"

# Standing glossary + source footnote, meant to appear on every chart in
# this project (not just this one) -- established here since this is the
# first chart built, so later analyses (native urchin included) reuse it.
SPECIES_NOTE = (
    "\"Invasive urchin\" = Centrostephanus rodgersii (long-spined sea urchin, invasive). "
    "\"Native urchin\" = Heliocidaris erythrogramma (purple sea urchin, native to Tasmania)."
)
SOURCE_NOTE = (
    "Source: IMOS National Reef Monitoring Network (Reef Life Survey), downloaded via the "
    "Australian Ocean Data Network Portal (portal.aodn.org.au). Temperature: IMOS ANMN Maria "
    "Island National Reference Station (NRSMAI), same portal."
)


def footnote(data_desc: str, chars_per_line: int = 120) -> str:
    # Plotly annotations' "width" auto-wrap option doesn't reliably wrap
    # text through the static (kaleido) image renderer -- found by
    # actually looking at the rendered PNG, not assumed. Wrapping the
    # string ourselves with explicit <br> breaks sidesteps that entirely.
    full = f"{data_desc} {SPECIES_NOTE} {SOURCE_NOTE}"
    return "<br>".join(textwrap.wrap(full, width=chars_per_line))


def main():
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

    n_confounded = int(detections["is_confounded"].sum())
    n_sightings = int(colonized["colonized_sites"].sum())
    print(f"Sites with a confirmed invasive-urchin detection: {len(detections)}")
    print(f"Year range of first detections: {detections['first_detected_year'].min()}-{detections['first_detected_year'].max()}")
    print(
        f"CAVEAT: {n_confounded}/{len(detections)} sites ({n_confounded/len(detections):.1%}) have "
        "first_detected_year == that site's first-ever survey year -- confounded with 'first time "
        "anyone looked', not necessarily genuine arrival. Shown as hollow markers on the map."
    )
    print(
        f"Temperature panel covers {temp['yr'].min()}-{temp['yr'].max()} only "
        "(the only real loaded record) -- overlaps just the tail of the 1992-2026 urchin timeline, "
        "not the full history. Not stretched or faked to look like a longer overlap."
    )

    # --- Map: one point per site, colored by first-detection year ---
    cmin, cmax = detections["first_detected_year"].min(), detections["first_detected_year"].max()
    fig_map = go.Figure()
    confident = detections[~detections["is_confounded"]]
    confounded = detections[detections["is_confounded"]]
    fig_map.add_trace(go.Scattermapbox(
        lat=confident["latitude"], lon=confident["longitude"],
        mode="markers", name="Confident first detection",
        marker=dict(
            size=12, color=confident["first_detected_year"],
            colorscale=GBR, cmin=cmin, cmax=cmax, showscale=True,
            colorbar=dict(title="First<br>detected", tickfont=dict(color=TEXT_BLACK)),
        ),
        text=[f"{r.site_code}<br>First detected: {int(r.first_detected_year)}" for r in confident.itertuples()],
        hoverinfo="text",
    ))
    fig_map.add_trace(go.Scattermapbox(
        lat=confounded["latitude"], lon=confounded["longitude"],
        mode="markers", name="Confounded with first survey year",
        marker=dict(
            size=9, color=confounded["first_detected_year"],
            colorscale=GBR, cmin=cmin, cmax=cmax, showscale=False,
            opacity=0.45,
        ),
        text=[
            f"{r.site_code}<br>First detected: {int(r.first_detected_year)} (= first survey year, uncertain)"
            for r in confounded.itertuples()
        ],
        hoverinfo="text",
    ))
    fig_map.update_layout(
        mapbox=dict(style="open-street-map", zoom=TASMANIA_ZOOM, center=TASMANIA_CENTER),
        height=760, margin=dict(l=20, r=20, t=40, b=190),
        title="Invasive urchin: first-detection year by site "
              f"(faint = confounded with first survey, {n_confounded}/{len(detections)} sites)",
        font=dict(color=TEXT_BLACK),
        legend=dict(font=dict(color=TEXT_BLACK), x=0.01, y=0.03,
                     bgcolor="rgba(255,255,255,0.85)", bordercolor=TEXT_BLACK, borderwidth=1),
        annotations=[dict(
            text=footnote(f"{len(detections)} sites with a confirmed detection, from {n_sightings} site-year sighting records in rls_clean_invertebrate.", chars_per_line=125),
            xref="paper", yref="paper", x=0, y=-0.14, showarrow=False,
            font=dict(size=11, color=TEXT_BLACK), align="left",
            xanchor="left", yanchor="top",
        )],
    )
    fig_map.write_image(str(OUT_DIR / "urchin_first_detection_map.png"), scale=2, width=1100, height=950)
    print(f"Wrote {OUT_DIR / 'urchin_first_detection_map.png'}")

    # --- Timeline: colonized sites + southern extent + sea temperature ---
    fig_tl = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
        subplot_titles=(
            "Colonized sites (count)", "Southernmost extent (latitude)",
            f"Sea temperature, 20m, {temp['yr'].min()}-{temp['yr'].max()} only (real record; earlier years not loaded)",
        ),
    )
    fig_tl.add_trace(go.Scatter(x=colonized["yr"], y=colonized["colonized_sites"],
                                  mode="lines+markers", line=dict(color=COLOR_LINE, width=2),
                                  name="Colonized sites"), row=1, col=1)
    fig_tl.add_trace(go.Scatter(x=extent["yr"], y=extent["southernmost_latitude"],
                                  mode="lines+markers", line=dict(color="#eb6834", width=2),
                                  name="Southernmost latitude"), row=2, col=1)
    # mean/p90 band, same technique as the maria_island hi-res dashboard
    fig_tl.add_trace(go.Scatter(x=temp["yr"], y=temp["p90_temp_c"], mode="lines",
                                  line=dict(width=0), showlegend=False, hoverinfo="skip"), row=3, col=1)
    fig_tl.add_trace(go.Scatter(x=temp["yr"], y=temp["mean_temp_c"], mode="lines",
                                  line=dict(width=0), fill="tonexty", fillcolor="rgba(235,104,52,0.15)",
                                  name="Mean-p90 band", showlegend=False), row=3, col=1)
    fig_tl.add_trace(go.Scatter(x=temp["yr"], y=temp["mean_temp_c"], mode="lines+markers",
                                  line=dict(color=COLOR_TEMP, width=2), name="Mean temp (°C)"), row=3, col=1)
    fig_tl.update_layout(
        height=900, showlegend=False, font=dict(color=TEXT_BLACK),
        plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
        title="Spread of invasive urchin over time, vs. sea temperature (where real data overlaps)",
        margin=dict(b=190),
        annotations=[dict(
            text=footnote(f"{len(colonized)} year(s) of urchin site-count data, {len(temp)} year(s) of real temperature data.", chars_per_line=110),
            xref="paper", yref="paper", x=0, y=-0.12, showarrow=False,
            font=dict(size=11, color=TEXT_BLACK), align="left",
            xanchor="left", yanchor="top",
        )],
    )
    # Subplot titles are auto-generated annotations -- force their color
    # black too, same as every tick/axis-line/gridline below. Must come
    # AFTER the footnote annotation is added via update_layout above, or
    # update_annotations would also try to recolor the footnote itself
    # (harmless here since it's already black, but order matters in
    # general when annotations differ).
    fig_tl.update_annotations(font=dict(color=TEXT_BLACK))
    for r in (1, 2, 3):
        fig_tl.update_xaxes(gridcolor=GRID, linecolor=TEXT_BLACK, zerolinecolor=TEXT_BLACK,
                              tickfont=dict(color=TEXT_BLACK), row=r, col=1)
        fig_tl.update_yaxes(gridcolor=GRID, linecolor=TEXT_BLACK, zerolinecolor=TEXT_BLACK,
                              tickfont=dict(color=TEXT_BLACK), row=r, col=1)
    fig_tl.write_image(str(OUT_DIR / "urchin_spread_timeline.png"), scale=2, width=1000, height=950)
    print(f"Wrote {OUT_DIR / 'urchin_spread_timeline.png'}")


if __name__ == "__main__":
    main()
