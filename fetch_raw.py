"""Raw GDELT GKG ingestion.

Locates the raw GKG batches stored in ``config.raw_data_dir`` and loads them
into a DataFrame with the standard GDELT 2.0 GKG column headers assigned.
See plan.txt Section 3.1.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

import config

# Separator used to make missing-day warnings visually prominent in the
# notebook output.
_WARN_BAR = "!" * 70


def _warn_missing_days(missing_days: list[str]) -> None:
    """Print a prominent warning listing days with no raw GKG file.

    GDELT has occasional archive gaps (e.g. server outages). When the
    requested date range includes days for which no raw batch was downloaded,
    the user must be able to notice the gap so they know the dataset is
    incomplete.
    """
    print(f"\n{_WARN_BAR}")
    print(f"WARNING: {len(missing_days)} day(s) in the requested date range have no raw GKG file:")
    for d in missing_days:
        print(f"  - {d}")
    print("  These days are MISSING from the dataset (GDELT archive gap or")
    print("  the batch was skipped during download).")
    print(f"{_WARN_BAR}\n")


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


def _missing_days(
    raw_files: list[Path],
    start: str | None,
    end: str | None,
) -> list[str]:
    """Return the days in [start, end] that have no raw GKG file.

    GDELT daily batches are named ``<YYYYMMDD>234500.gkg.csv``. Days whose
    batch file is absent (e.g. archive gap or skipped download) are returned
    as ``YYYY-MM-DD`` strings. Returns [] when no date bounds are given.
    """
    if not start and not end:
        return []

    def _to_date(s: str) -> datetime:
        s = s.strip()
        if s.isdigit() and len(s) == 14:
            return datetime.strptime(s[:8], "%Y%m%d")
        return datetime.strptime(s, "%Y-%m-%d")

    d_start = _to_date(start) if start else None
    d_end = _to_date(end) if end else None

    # Collect the dates covered by the raw files present.
    have: set[str] = set()
    for p in raw_files:
        name = p.stem  # e.g. 20250613234500.gkg.csv -> 20250613234500
        if len(name) >= 8 and name[:8].isdigit():
            have.add(name[:8])

    missing: list[str] = []
    day = d_start or (d_end - timedelta(days=365))
    while d_end is None or day <= d_end:
        if day.strftime("%Y%m%d") not in have:
            missing.append(day.strftime("%Y-%m-%d"))
        if d_end is None:
            break
        day += timedelta(days=1)
    return missing


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

    # Warn about days in the requested range that have no raw file (GDELT
    # archive gaps or batches skipped during download).
    missing = _missing_days(raw_files, start, end)
    if missing:
        _warn_missing_days(missing)

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