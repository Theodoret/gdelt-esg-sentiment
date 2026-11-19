"""Metric aggregation engine (plan.txt Section 4.4).

Computes aggregated sentiment time series across ESG category, media source
country, and time window:

    Sentiment_{c, s, t} = (1/N) * sum(Tone_i)

where:
    c = ESG category (Environmental / Social / Governance / composite)
    s = media source country (``attributed_country``)
    t = time interval (daily / weekly / monthly, from ``config.aggregation_freq``)
    N = article count in that bucket (retained as coverage volume)

Rows without a parseable tone are excluded from the sentiment mean but still
counted in the coverage volume ``N`` (plan.txt Section 3.2).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import config

# Tone column produced by the tone module.
_TONE_COL = "tone"

# Pillar boolean columns produced by the esg_classify module.
_PILLAR_COLS = [f"is_{p}" for p in config.esg_categories]


def _parse_date(date_val: object) -> pd.Timestamp | None:
    """Parse a GDELT DATE (YYYYMMDDHHMMSS) or ISO date into a Timestamp."""
    if date_val is None or (isinstance(date_val, float) and pd.isna(date_val)):
        return None
    s = str(date_val).strip()
    if not s:
        return None
    # GDELT timestamp: YYYYMMDDHHMMSS (14 digits) or YYYYMMDD (8 digits).
    if s.isdigit() and len(s) in (8, 14):
        fmt = "%Y%m%d%H%M%S" if len(s) == 14 else "%Y%m%d"
        try:
            return pd.to_datetime(s, format=fmt)
        except ValueError:
            return None
    try:
        return pd.to_datetime(s)
    except (ValueError, TypeError):
        return None


def _freq_alias(freq: str) -> str:
    """Map config aggregation_freq to a pandas offset alias."""
    return {"1D": "D", "1W": "W", "1M": "ME"}.get(freq, freq)


def aggregate(
    df: pd.DataFrame,
    freq: str | None = None,
    date_col: str = "DATE",
    country_col: str = "attributed_country",
) -> pd.DataFrame:
    """Aggregate sentiment by ESG category x source country x time window.

    Args:
        df: DataFrame with DATE, attributed_country, is_* pillar columns, and
            a numeric ``tone`` column (output of tone.extract_tone).
        freq: Aggregation frequency ("1D", "1W", "1M"). Defaults to
            ``config.aggregation_freq``.
        date_col: Column holding the publication date.
        country_col: Column holding the attributed source country.

    Returns:
        Long-format DataFrame with columns:
            date, country, esg_category, tone_mean, tone_median, tone_std,
            n_with_tone, n_articles
        ``esg_category`` is one of Environmental / Social / Governance /
        Composite. ``n_articles`` is the coverage volume (all rows in the
        bucket, including those without tone); ``n_with_tone`` is the count
        used for the mean.
    """
    if freq is None:
        freq = config.aggregation_freq

    out = df.copy()
    out["_date"] = out[date_col].apply(_parse_date)
    # Rows with an unparseable date are dropped from aggregation.
    out = out[out["_date"].notna()].copy()

    # Empty input (e.g. date/country filters removed all rows): return an
    # empty result with the expected schema instead of crashing on .dt.
    if out.empty:
        return pd.DataFrame(
            columns=[
                "date", "country", "esg_category",
                "tone_mean", "tone_median", "tone_std",
                "n_with_tone", "n_articles",
            ]
        )

    out["_period"] = out["_date"].dt.to_period(_freq_alias(freq)).dt.start_time

    # Composite bucket: all rows (any ESG tag or none).
    out["is_Composite"] = True

    frames: list[pd.DataFrame] = []
    for pillar in config.esg_categories + ["Composite"]:
        mask = out[f"is_{pillar}"]
        sub = out[mask]
        if sub.empty:
            continue
        g = (
            sub.groupby(["_period", country_col])
            .agg(
                tone_mean=pd.NamedAgg(column=_TONE_COL, aggfunc="mean"),
                tone_median=pd.NamedAgg(column=_TONE_COL, aggfunc="median"),
                tone_std=pd.NamedAgg(column=_TONE_COL, aggfunc="std"),
                n_with_tone=pd.NamedAgg(column=_TONE_COL, aggfunc="count"),
                n_articles=pd.NamedAgg(column=_TONE_COL, aggfunc="size"),
            )
            .reset_index()
        )
        g["esg_category"] = pillar
        frames.append(g)

    result = pd.concat(frames, ignore_index=True)
    result = result.rename(columns={"_period": "date", country_col: "country"})
    result = result[["date", "country", "esg_category", "tone_mean", "tone_median", "tone_std", "n_with_tone", "n_articles"]]
    return result.sort_values(["date", "country", "esg_category"]).reset_index(drop=True)


def save_aggregated(
    df: pd.DataFrame,
    path: Path | None = None,
) -> Path:
    """Persist the aggregated table to ``config.output_data_dir``.

    Defaults to ``output_data_dir / "aggregated_sentiment.csv"``.
    """
    if path is None:
        path = config.output_data_dir / "aggregated_sentiment.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"aggregate: saved {len(df)} rows -> {path}")
    return path