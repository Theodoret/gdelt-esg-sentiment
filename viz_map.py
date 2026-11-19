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

# Plotly's choropleth uses ISO-3 country codes internally; we pass country
# names and let Plotly match them. Names not in Plotly's geometry are dropped
# from the map (they remain in the underlying data).
_COLOR_SCALE = "RdBu_r"  # red = negative, blue = positive (tone scale)


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to rows with a valid tone and a map-mappable country."""
    out = df.copy()
    out = out[out["tone_mean"].notna()]
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
        geo=dict(showframe=False, showcoastlines=True),
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
        geo=dict(showframe=False, showcoastlines=True),
    )
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
        geo=dict(showframe=False, showcoastlines=True),
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

    # Date slider steps.
    slider_steps = [
        dict(
            method="animate",
            label=str(d),
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
                currentvalue=dict(prefix="Date: ", visible=True),
            )
        ],
        coloraxis=dict(
            colorscale=_COLOR_SCALE,
            cmin=-5,
            cmax=5,
            colorbar=dict(title="Mean tone"),
        ),
        geo=dict(showframe=False, showcoastlines=True),
    )
    return fig


def save_figure(fig: go.Figure, name: str) -> str:
    """Save a figure as a self-contained HTML file in ``config.output_data_dir``."""
    path = config.output_data_dir / f"{name}.html"
    fig.write_html(path)
    print(f"viz: saved {path}")
    return str(path)