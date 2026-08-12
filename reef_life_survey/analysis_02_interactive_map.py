"""
Analysis 2 bonus: interactive animated map with a year slider. Each
frame shows the sites where the invasive urchin was actually recorded
present (total > 0) that year -- dots appear/disappear/resize as you
move the slider, rather than showing a fixed "first detection" snapshot
like the static map does. This is the "bonus interactive" version the
static map's own caveats (confounded-with-first-survey sites) don't
need to carry, since here every dot is a real that-year sighting record,
not an inferred "first" anything.

Self-contained HTML (Plotly embedded, not loaded from a CDN) -- open
directly in any browser, no server needed.

Run:
    python analysis_02_interactive_map.py
Output:
    urchin_sightings_animated.html
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine  # noqa: E402

OUT_DIR = Path(__file__).parent
REDS = ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"]

SPECIES_NOTE = (
    "\"Invasive urchin\" = Centrostephanus rodgersii (long-spined sea urchin, invasive). "
    "\"Native urchin\" = Heliocidaris erythrogramma (purple sea urchin, native to Tasmania)."
)
SOURCE_NOTE = (
    "Source: IMOS National Reef Monitoring Network (Reef Life Survey), downloaded via the "
    "Australian Ocean Data Network Portal (portal.aodn.org.au)."
)


def main():
    engine = get_engine()
    df = pd.read_sql(
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
    print(f"{len(df)} site-year sighting records, {df['yr'].nunique()} distinct years "
          f"({df['yr'].min()}-{df['yr'].max()}), {df['site_code'].nunique()} distinct sites")

    # Every year in range needs at least a placeholder so the slider has a
    # frame for it even if animation_frame would otherwise skip a gap year.
    all_years = pd.DataFrame({"yr": range(int(df["yr"].min()), int(df["yr"].max()) + 1)})
    df["yr"] = df["yr"].astype(int)

    fig = px.scatter_mapbox(
        df, lat="latitude", lon="longitude", size="count", color="count",
        color_continuous_scale=REDS, range_color=(df["count"].min(), df["count"].max()),
        animation_frame="yr", hover_name="site_code",
        hover_data={"latitude": False, "longitude": False, "count": True, "yr": True},
        size_max=28, zoom=6.6,
        center=dict(lat=float(df["latitude"].mean()), lon=float(df["longitude"].mean())),
        mapbox_style="open-street-map",
        title="Invasive urchin sightings by year (drag the slider, or press play)",
    )
    fig.update_layout(
        height=850, margin=dict(l=10, r=10, t=60, b=200),
        font=dict(color="#000000"),
        coloraxis_colorbar=dict(title="Count", tickfont=dict(color="#000000")),
        annotations=[dict(
            text=f"{len(df)} site-year sighting records, {df['site_code'].nunique()} distinct sites, "
                 f"{df['yr'].min()}-{df['yr'].max()}.<br>{SPECIES_NOTE}<br>{SOURCE_NOTE}",
            xref="paper", yref="paper", x=0, y=-0.26, showarrow=False,
            font=dict(size=11, color="#000000"), align="left", xanchor="left", yanchor="top",
        )],
    )
    # The slider Plotly Express auto-generates defaults to sitting right at
    # the bottom of the plot area, which collided with the footnote below
    # it -- nudge just its y position (attribute access, not update_layout
    # with a new list, which would wipe out the auto-generated frame
    # steps) so there's clear air between the year labels and the footnote.
    fig.layout.sliders[0].y = 0.02
    out_path = OUT_DIR / "urchin_sightings_animated.html"
    fig.write_html(str(out_path), include_plotlyjs=True, full_html=True)
    print(f"Wrote {out_path} -- open directly in a browser, no server needed.")


if __name__ == "__main__":
    main()
