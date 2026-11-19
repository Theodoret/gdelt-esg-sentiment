"""Preprocessing for raw GDELT GKG data.

Implements the missing-value handling matrix (plan.txt Section 3.2) and
deduplication + persistence (plan.txt Section 3.3). Input is expected to come
from ``fetch_raw`` (all values as strings, empty string = missing).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import config


def _is_missing(series: pd.Series) -> pd.Series:
    """Return True where a value is NaN or an empty/whitespace-only string."""
    return series.isna() | series.astype(str).str.strip().eq("")


def handle_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the NA handling matrix from plan.txt Section 3.2.

    - ``DATE`` missing -> drop observation.
    - ``SourceCommonName`` missing -> retain, mark as ``config.UNKNOWN_SOURCE``.
    - ``Themes`` / ``V2Themes`` missing -> retain (classification fallback later).
    - ``Locations`` / ``V2Locations`` missing -> retain, no country assigned.
    - ``V2Tone`` missing -> retain for coverage volume, excluded from sentiment
      in the aggregation stage.
    - ``DocumentIdentifier`` missing -> retain if other identifiers exist;
      otherwise flag via a ``missing_identifier`` column for investigation.
    """
    df = df.copy()

    n_before = len(df)
    df = df[~_is_missing(df["DATE"])]
    n_dropped_date = n_before - len(df)

    df.loc[_is_missing(df["SourceCommonName"]), "SourceCommonName"] = config.UNKNOWN_SOURCE

    # Flag records with no usable identifier (no URL and no GKG record ID).
    df["missing_identifier"] = _is_missing(df["DocumentIdentifier"]) & _is_missing(
        df["GKGRecordID"]
    )

    n_missing_tone = int(_is_missing(df["V2Tone"]).sum())
    n_missing_identifier = int(df["missing_identifier"].sum())

    print(f"preprocess: dropped {n_dropped_date} rows with missing DATE")
    print(f"preprocess: {n_missing_tone} rows without V2Tone (kept for volume stats)")
    print(f"preprocess: {n_missing_identifier} rows flagged missing_identifier")
    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate records on ``config.DEDUP_COLUMNS`` (plan.txt Section 3.3)."""
    n_before = len(df)
    df = df.drop_duplicates(subset=config.DEDUP_COLUMNS, keep="first")
    n_dupes = n_before - len(df)
    print(f"preprocess: dropped {n_dupes} duplicate rows on {config.DEDUP_COLUMNS}")
    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full preprocessing pipeline: NA handling, then deduplication."""
    return deduplicate(handle_missing(df))


def save_processed(
    df: pd.DataFrame,
    path: Path | None = None,
    columns: list[str] | None = None,
) -> Path:
    """Persist the cleaned dataset to ``config.processed_data_dir``.

    Args:
        df: Cleaned DataFrame.
        path: Target file. Defaults to ``processed_data_dir / "gkg_clean.csv"``.
        columns: Columns to write. Defaults to ``config.RETAINED_COLUMNS``.

    Returns:
        The path the file was written to.
    """
    if path is None:
        path = config.processed_data_dir / "gkg_clean.csv"
    if columns is None:
        columns = config.RETAINED_COLUMNS

    path.parent.mkdir(parents=True, exist_ok=True)
    df[columns].to_csv(path, index=False)
    print(f"preprocess: saved {len(df)} rows x {len(columns)} cols -> {path}")
    return path