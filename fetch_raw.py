"""Raw GDELT GKG ingestion.

Locates the raw GKG batches stored in ``config.raw_data_dir`` and loads them
into a DataFrame with the standard GDELT 2.0 GKG column headers assigned.
See plan.txt Section 3.1.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import config


def find_raw_gkg_files(glob: str = "*.gkg.csv") -> list[Path]:
    """Return the raw GKG files in ``config.raw_data_dir``, sorted by name."""
    return sorted(config.raw_data_dir.glob(glob))


def load_raw_gkg(path: Path | None = None, columns: list[str] | None = None) -> pd.DataFrame:
    """Load one raw GKG file (tab-separated, no header row).

    Args:
        path: File to load. Defaults to the first raw GKG file found.
        columns: Column headers to assign. Defaults to ``config.GDELT_COLUMNS``.

    Returns:
        DataFrame with the GDELT column headers applied, all values as strings.
    """
    if path is None:
        raw_files = find_raw_gkg_files()
        if not raw_files:
            raise FileNotFoundError(f"No *.gkg.csv files found in {config.raw_data_dir}")
        path = raw_files[0]

    if columns is None:
        columns = config.GDELT_COLUMNS

    try:
        return pd.read_csv(
            path,
            sep="\t",
            header=None,
            names=columns,
            dtype=str,
            keep_default_na=False,
        )
    except UnicodeDecodeError:
        # Some GDELT batches contain latin-1 bytes; fall back so the row is kept.
        return pd.read_csv(
            path,
            sep="\t",
            header=None,
            names=columns,
            dtype=str,
            keep_default_na=False,
            encoding="latin-1",
        )


def fetch_raw_gkg(
    glob: str = "*.gkg.csv",
    date_range: tuple[str | None, str | None] | None = None,
) -> tuple[pd.DataFrame, list[Path]]:
    """Locate the raw GKG files and load them all, concatenated.

    Args:
        glob: Glob pattern for raw GKG files.
        date_range: Optional (start, end) filter applied to the ``DATE``
            column (GDELT timestamp YYYYMMDDHHMMSS or ISO date). ``None``
            disables the filter. Defaults to ``config.date_range``.

    Returns:
        Tuple of (concatenated DataFrame, list of loaded file paths).
    """
    raw_files = find_raw_gkg_files(glob)
    if not raw_files:
        raise FileNotFoundError(f"No {glob} files found in {config.raw_data_dir}")

    if date_range is None:
        date_range = config.date_range
    start, end = date_range

    frames: list[pd.DataFrame] = []
    loaded: list[Path] = []
    for raw_path in raw_files:
        df = load_raw_gkg(raw_path)
        if start or end:
            df = filter_by_date(df, start, end)
        if not df.empty:
            frames.append(df)
            loaded.append(raw_path)

    if not frames:
        raise ValueError(
            f"No rows match date_range {date_range} in {len(raw_files)} raw files"
        )

    return pd.concat(frames, ignore_index=True), loaded


def filter_by_date(
    df: pd.DataFrame,
    start: str | None = None,
    end: str | None = None,
    date_col: str = "DATE",
) -> pd.DataFrame:
    """Filter rows to an inclusive [start, end] date range.

    Dates are compared as GDELT timestamps (YYYYMMDDHHMMSS) or ISO dates.
    Rows with an unparseable DATE are dropped.

    Args:
        df: DataFrame with a DATE column.
        start: Inclusive start date (None = no lower bound).
        end: Inclusive end date (None = no upper bound).
        date_col: Column holding the date.

    Returns:
        Filtered DataFrame.
    """
    if not start and not end:
        return df

    def _norm(s: object) -> str:
        """Normalize a date to YYYYMMDD for comparison."""
        s = str(s).strip()
        # GDELT timestamp (14 digits) -> YYYYMMDD.
        if s.isdigit() and len(s) == 14:
            return s[:8]
        # ISO date YYYY-MM-DD -> YYYYMMDD.
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return s[:4] + s[5:7] + s[8:10]
        return s

    out = df.copy()
    dates = out[date_col].astype(str).str.strip().apply(_norm)
    if start:
        out = out[dates >= _norm(start)]
        dates = out[date_col].astype(str).str.strip().apply(_norm)
    if end:
        out = out[dates <= _norm(end)]
    return out