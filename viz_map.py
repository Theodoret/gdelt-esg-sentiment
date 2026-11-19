"""Interactive world map visualization (plan.txt Section 5.1).

Renders a choropleth of country-level aggregate ESG sentiment over time with:
- Filtering by ESG dimension (Environmental / Social / Governance / Composite)
- Date slider/selector
- Coverage volume (N) shown via tooltip
- Tooltips with source volume N and average tone breakdown

Uses Plotly Express ``choropleth``. Country names are matched to Plotly's
built-in country geometry; unmatched names (e.g. "UNKNOWN", territories not
in the geometry) are excluded from the map but still present in the data.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import config
from geo_attr import COUNTRY_TO_CONTINENT

# Plotly's choropleth uses ISO-3 country codes internally; we pass country
# names and let Plotly match them. Names not in Plotly's geometry are dropped
# from the map (they remain in the underlying data).
_COLOR_SCALE = "RdBu_r"  # red = negative, blue = positive (tone scale)

# Approximate bounding boxes per continent (lon / lat), used to clip the map
# view so that continents unrelated to the selected countries are removed.
_CONT_BOUNDS: dict[str, dict[str, tuple[float, float]]] = {
    "Africa": {"lon": (-20, 56), "lat": (-38, 40)},
    "Asia": {"lon": (25, 180), "lat": (-12, 80)},
    "Europe": {"lon": (-28, 60), "lat": (34, 72)},
    "North America": {"lon": (-170, -50), "lat": (5, 84)},
    "South America": {"lon": (-84, -32), "lat": (-58, 14)},
    "Oceania": {"lon": (108, 180), "lat": (-54, -4)},
}

# If the selected countries span a box wider than this, fall back to the whole
# globe (treat it as a global / multi-continent view).
_MAX_GEO_SPAN = (200.0, 130.0)


def _geo_clip(countries) -> dict:
    """Return geo layout ranges that focus the map on the given countries.

    Determines the set of continents implied by ``countries`` (via
    ``COUNTRY_TO_CONTINENT``) and returns an equirectangular layout whose
    lon/lat ranges bound the union of those continents. Falls back to an empty
    dict (full world) when no continent can be inferred or the span is global.
    """
    nations = set(countries)
    continents = {COUNTRY_TO_CONTINENT[c] for c in nations if c in COUNTRY_TO_CONTINENT}
    if not continents:
        return {}
    lon_min = min(_CONT_BOUNDS[c]["lon"][0] for c in continents)
    lon_max = max(_CONT_BOUNDS[c]["lon"][1] for c in continents)
    lat_min = min(_CONT_BOUNDS[c]["lat"][0] for c in continents)
    lat_max = max(_CONT_BOUNDS[c]["lat"][1] for c in continents)
    if (lon_max - lon_min) > _MAX_GEO_SPAN[0] or (lat_max - lat_min) > _MAX_GEO_SPAN[1]:
        return {}
    return {
        "projection": {"type": "equirectangular"},
        "lonaxis": {"range": [lon_min, lon_max]},
        "lataxis": {"range": [lat_min, lat_max]},
    }


def _base_geo(countries) -> dict:
    """Full geo layout: base styling plus continent clipping for ``countries``."""
    geo = {"showframe": False, "showcoastlines": True}
    geo.update(_geo_clip(countries))
    return geo


def _prepare(df: pd.DataFrame, min_articles: int | None = None) -> pd.DataFrame:
    """Filter to rows with a valid tone and a map-mappable country.

    Rows whose bucket holds fewer than ``min_articles`` articles (default
    ``config.MIN_ARTICLES``) are dropped: with too small a sample the tone
    mean is dominated by a single article and reads as noise, which makes
    animated maps flicker. Setting ``min_articles=0`` disables the mask.
    """
    if min_articles is None:
        min_articles = config.MIN_ARTICLES
    out = df.copy()
    out = out[out["tone_mean"].notna()]
    if min_articles > 0:
        out = out[out["n_articles"] >= min_articles]
    # Exclude the UNKNOWN bucket and any country Plotly cannot geolocate.
    out = out[out["country"] != config.UNKNOWN_SOURCE]
    return out


def build_choropleth(
    df: pd.DataFrame,
    category: str = "Composite",
    date: str | None = None,
    color_col: str = "tone_mean",
) -> go.Figure:
    """Build an interactive choropleth for one ESG category and date.

    Args:
        df: Aggregated table (output of aggregate.aggregate).
        category: ESG category to display ("Environmental", "Social",
            "Governance", "Composite").
        date: Optional ISO date string to filter to. If None, uses the latest
            date present in the data.
        color_col: Column to color by (default "tone_mean").

    Returns:
        A Plotly Figure with hover tooltips showing N and tone breakdown.
    """
    data = _prepare(df)
    data = data[data["esg_category"] == category]

    if date is None:
        date = data["date"].max()
    data = data[data["date"] == date]

    fig = px.choropleth(
        data,
        locations="country",
        locationmode="country names",
        color=color_col,
        color_continuous_scale=_COLOR_SCALE,
        range_color=(-5, 5),
        hover_name="country",
        hover_data={
            "country": False,
            "tone_mean": ":.2f",
            "tone_median": ":.2f",
            "n_with_tone": True,
            "n_articles": True,
        },
        title=f"{category} sentiment by country ({date})",
    )
    fig.update_layout(
        coloraxis_colorbar=dict(title="Mean tone"),
        geo=_base_geo(data["country"]),
    )
    return fig


def build_date_slider_figure(
    df: pd.DataFrame,
    category: str = "Composite",
) -> go.Figure:
    """Build a choropleth with a date slider (one frame per date)."""
    data = _prepare(df)
    data = data[data["esg_category"] == category]
    data = data.sort_values("date")

    fig = px.choropleth(
        data,
        locations="country",
        locationmode="country names",
        color="tone_mean",
        color_continuous_scale=_COLOR_SCALE,
        range_color=(-5, 5),
        hover_name="country",
        hover_data={
            "country": False,
            "tone_mean": ":.2f",
            "tone_median": ":.2f",
            "n_with_tone": True,
            "n_articles": True,
        },
        animation_frame="date",
        title=f"{category} sentiment by country over time",
    )
    fig.update_layout(
        coloraxis_colorbar=dict(title="Mean tone"),
        geo=_base_geo(data["country"]),
    )
    # Remove the auto-added play/pause buttons (autoplay) so the map does not
    # animate on its own; the user steps through frames with the slider.
    fig.layout.updatemenus = ()
    # Hide the per-tick date labels and the above-slider "date=..." readout so
    # the slider shows no timestamp; the thumb position is the only cue.
    for slider in fig.layout.sliders or []:
        for step in slider.steps:
            step.label = ""
        slider.currentvalue.visible = False
    return fig


def build_category_selector_figure(
    df: pd.DataFrame,
    date: str | None = None,
    color_col: str = "tone_mean",
) -> go.Figure:
    """Build a choropleth with a dropdown to switch ESG category.

    Renders one choropleth trace per category (Environmental / Social /
    Governance / Composite) for a single date and adds a dropdown menu to
    toggle which trace is visible. Defaults to the latest date in the data.

    Args:
        df: Aggregated table (output of aggregate.aggregate).
        date: Optional ISO date string to filter to. If None, uses the latest
            date present in the data.
        color_col: Column to color by (default "tone_mean").

    Returns:
        A Plotly Figure with a category dropdown and hover tooltips showing
        N and tone breakdown.
    """
    data = _prepare(df)
    if date is None:
        date = data["date"].max()
    data = data[data["date"] == date]

    categories = config.esg_categories + ["Composite"]
    traces: list[go.Choropleth] = []
    for cat in categories:
        sub = data[data["esg_category"] == cat]
        traces.append(
            go.Choropleth(
                locations=sub["country"],
                locationmode="country names",
                z=sub[color_col],
                customdata=sub[["tone_median", "n_with_tone", "n_articles"]].to_numpy(),
                hovertemplate=(
                    "<b>%{location}</b><br>"
                    "Mean tone: %{z:.2f}<br>"
                    "Median: %{customdata[0]:.2f}<br>"
                    "N with tone: %{customdata[1]}<br>"
                    "N articles: %{customdata[2]}<extra></extra>"
                ),
                coloraxis="coloraxis",
                visible=(cat == "Composite"),
                name=cat,
            )
        )

    buttons = [
        dict(
            label=cat,
            method="update",
            args=[{"visible": [i == idx for i in range(len(categories))]}],
        )
        for idx, cat in enumerate(categories)
    ]

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=f"ESG sentiment by country ({date})",
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                showactive=True,
                x=0.02,
                y=1.12,
                buttons=buttons,
            )
        ],
        coloraxis=dict(
            colorscale=_COLOR_SCALE,
            cmin=-5,
            cmax=5,
            colorbar=dict(title="Mean tone"),
        ),
        geo=_base_geo(data["country"]),
    )
    return fig


def build_time_series_figure(
    df: pd.DataFrame,
    color_col: str = "tone_mean",
) -> go.Figure:
    """Build a choropleth with BOTH a category dropdown and a date slider.

    Renders one choropleth trace per ESG category per date. A dropdown toggles
    which category is visible; a slider (with play/pause) animates through the
    dates, showing how sentiment changes over time.

    Args:
        df: Aggregated table (output of aggregate.aggregate).
        color_col: Column to color by (default "tone_mean").

    Returns:
        A Plotly Figure with a category dropdown, date slider, and hover
        tooltips showing N and tone breakdown.
    """
    data = _prepare(df)
    dates = sorted(data["date"].unique())
    categories = config.esg_categories + ["Composite"]

    # Empty data (e.g. filters removed all rows): return an empty figure.
    if not dates:
        fig = go.Figure()
        fig.update_layout(title="No data for the selected filters")
        return fig

    def _trace(sub: pd.DataFrame, cat: str) -> go.Choropleth:
        return go.Choropleth(
            locations=sub["country"],
            locationmode="country names",
            z=sub[color_col],
            customdata=sub[["tone_median", "n_with_tone", "n_articles"]].to_numpy(),
            hovertemplate=(
                "<b>%{location}</b><br>"
                "Mean tone: %{z:.2f}<br>"
                "Median: %{customdata[0]:.2f}<br>"
                "N with tone: %{customdata[1]}<br>"
                "N articles: %{customdata[2]}<extra></extra>"
            ),
            coloraxis="coloraxis",
            visible=(cat == "Composite"),
            name=cat,
        )

    # Base traces: first date, one per category.
    first_date = dates[0]
    traces = [
        _trace(data[(data["date"] == first_date) & (data["esg_category"] == cat)], cat)
        for cat in categories
    ]

    # Frames: one per subsequent date, each with one trace per category.
    frames = []
    for d in dates[1:]:
        frame_traces = [
            _trace(data[(data["date"] == d) & (data["esg_category"] == cat)], cat)
            for cat in categories
        ]
        frames.append(go.Frame(data=frame_traces, name=str(d)))

    # Category dropdown: toggle visibility of the 4 traces in every frame.
    buttons = [
        dict(
            label=cat,
            method="update",
            args=[{"visible": [i == idx for i in range(len(categories))]}],
        )
        for idx, cat in enumerate(categories)
    ]

    # Date slider steps. Labels are blank and the current-value readout is
    # hidden so the slider shows no timestamp until a frame changes; the only
    # visual cue is the thumb position between ticks.
    slider_steps = [
        dict(
            method="animate",
            label="",
            args=[
                [str(d)],
                dict(mode="immediate", frame=dict(duration=500, redraw=True), transition=dict(duration=300)),
            ],
        )
        for d in dates
    ]

    fig = go.Figure(data=traces, frames=frames)
    fig.update_layout(
        title=f"ESG sentiment by country over time ({first_date} to {dates[-1]})",
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                showactive=True,
                x=0.02,
                y=1.12,
                buttons=buttons,
            ),
        ],
        sliders=[
            dict(
                active=0,
                steps=slider_steps,
                x=0.1,
                len=0.9,
                pad=dict(t=40),
                currentvalue=dict(visible=False),
            )
        ],
        coloraxis=dict(
            colorscale=_COLOR_SCALE,
            cmin=-5,
            cmax=5,
            colorbar=dict(title="Mean tone"),
        ),
        geo=_base_geo(data["country"]),
    )
    return fig


def save_figure(fig: go.Figure, name: str) -> str:
    """Save a figure as a self-contained HTML file in ``config.output_data_dir``."""
    path = config.output_data_dir / f"{name}.html"
    fig.write_html(path)
    print(f"viz: saved {path}")
    return str(path)