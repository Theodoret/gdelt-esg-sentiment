"""GDELT GKG raw data downloader (plan.txt Section 3.1).

Downloads GDELT 2.0 GKG batches from the official GDELT server, unzips them,
and stores the raw ``.gkg.csv`` files in ``config.raw_data_dir`` so the rest of
the pipeline (``fetch_raw``) can load them.

GDELT 2.0 GKG file naming: ``<YYYYMMDDHHMMSS>.gkg.csv.zip``
URL pattern: ``https://data.gdeltproject.org/gdeltv2/<timestamp>.gkg.csv.zip``
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import requests

import config

# Official GDELT 2.0 GKG server base URL.
GDELT_BASE_URL = "https://data.gdeltproject.org/gdeltv2"

# 15-minute GDELT batch interval.
_BATCH_MINUTES = 15

# Separator used to make missing-batch warnings visually prominent in the
# notebook output.
_WARN_BAR = "!" * 70


def _warn_missing(timestamp: str, url: str) -> None:
    """Print a prominent warning that a GDELT batch is unavailable.

    GDELT occasionally has gaps in its archive (e.g. server outages). When a
    batch is missing we skip it and continue, but the user must be able to
    notice the gap so they know the resulting dataset is incomplete.
    """
    print(f"\n{_WARN_BAR}")
    print(f"WARNING: GDELT batch not available on the server: {timestamp}")
    print(f"  URL: {url}")
    print("  This batch was SKIPPED. The downloaded dataset will have a gap")
    print("  for this timestamp. Check the GDELT archive if you need this data.")
    print(f"{_WARN_BAR}\n")


def gkg_url(timestamp: str) -> str:
    """Return the download URL for a GKG batch timestamp (YYYYMMDDHHMMSS)."""
    return f"{GDELT_BASE_URL}/{timestamp}.gkg.csv.zip"


def download_batch(
    timestamp: str,
    dest_dir: Path | None = None,
    timeout: int = 120,
    force: bool = False,
) -> Path:
    """Download and unzip one GDELT GKG batch into ``dest_dir``.

    Args:
        timestamp: GDELT batch timestamp in ``YYYYMMDDHHMMSS`` format
            (e.g. ``"20261117200000"``).
        dest_dir: Directory to store the unzipped ``.gkg.csv``. Defaults to
            ``config.raw_data_dir``.
        timeout: HTTP request timeout in seconds.
        force: If True, re-download even when the file already exists
            (overwrites the local copy). Defaults to False (skip existing).

    Returns:
        Path to the downloaded ``.gkg.csv`` file.

    Raises:
        FileNotFoundError: If the batch already exists locally and ``force``
            is False (no download).
        requests.HTTPError: If the server returns an error (e.g. batch not
            available for that timestamp).
    """
    if dest_dir is None:
        dest_dir = config.raw_data_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    out_path = dest_dir / f"{timestamp}.gkg.csv"
    if out_path.exists() and not force:
        print(f"download: {out_path.name} already exists, skipping")
        return out_path

    url = gkg_url(timestamp)
    print(f"download: fetching {url}")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # The zip contains a single <timestamp>.gkg.csv entry.
        member = zf.namelist()[0]
        with zf.open(member) as src, open(out_path, "wb") as dst:
            dst.write(src.read())

    print(f"download: saved {out_path}")
    return out_path


def download_date_range(
    start: str,
    end: str,
    dest_dir: Path | None = None,
    timeout: int = 120,
    force: bool = False,
    skip_missing: bool = True,
) -> list[Path]:
    """Download all GDELT GKG batches between two dates (inclusive).

    Args:
        start: Start date, ISO (``"2026-11-17"``) or GDELT timestamp.
        end: End date, ISO (``"2026-11-17"``) or GDELT timestamp.
        dest_dir: Directory to store the unzipped ``.gkg.csv`` files.
        timeout: HTTP request timeout in seconds.
        force: If True, re-download existing files (overwrite). Defaults to
            False (skip existing).
        skip_missing: If True (default), skip batches the server does not have
            (404) with a prominent warning and continue. If False, raise on
            the first missing batch.

    Returns:
        List of paths to the downloaded ``.gkg.csv`` files.

    Raises:
        requests.HTTPError: If a batch is unavailable and ``skip_missing`` is
            False.
    """
    if dest_dir is None:
        dest_dir = config.raw_data_dir

    # Normalize to date objects.
    def _to_date(s: str) -> datetime:
        s = s.strip()
        if s.isdigit() and len(s) == 14:
            return datetime.strptime(s[:8], "%Y%m%d")
        return datetime.strptime(s, "%Y-%m-%d")

    d_start = _to_date(start)
    d_end = _to_date(end)
    if d_end < d_start:
        raise ValueError(f"end ({end}) is before start ({start})")

    paths: list[Path] = []
    day = d_start
    while day <= d_end:
        # GDELT publishes one batch per 15 minutes; fetch the last batch of
        # the day (23:45) as the day's representative GKG file.
        ts = day.strftime("%Y%m%d") + "234500"
        try:
            paths.append(download_batch(ts, dest_dir=dest_dir, timeout=timeout, force=force))
        except requests.HTTPError as exc:
            if not skip_missing or exc.response is None or exc.response.status_code != 404:
                raise
            _warn_missing(ts, gkg_url(ts))
        day += timedelta(days=1)
    return paths


def download_all_batches(
    start: str,
    end: str,
    dest_dir: Path | None = None,
    timeout: int = 120,
    force: bool = False,
    skip_missing: bool = True,
) -> list[Path]:
    """Download ALL 15-minute GDELT GKG batches between two dates (inclusive).

    GDELT publishes one GKG batch every 15 minutes, so a full day has 96
    batches. This downloads every batch in [start, end]. Use
    ``download_date_range`` instead if you only want one representative batch
    per day.

    Args:
        start: Start date, ISO (``"2026-11-17"``) or GDELT timestamp.
        end: End date, ISO (``"2026-11-17"``) or GDELT timestamp.
        dest_dir: Directory to store the unzipped ``.gkg.csv`` files.
        timeout: HTTP request timeout in seconds.
        force: If True, re-download existing files (overwrite). Defaults to
            False (skip existing).
        skip_missing: If True (default), skip batches the server does not have
            (404) with a prominent warning and continue. If False, raise on
            the first missing batch.

    Returns:
        List of paths to the downloaded ``.gkg.csv`` files.

    Raises:
        requests.HTTPError: If a batch is unavailable and ``skip_missing`` is
            False.
    """
    if dest_dir is None:
        dest_dir = config.raw_data_dir

    def _to_date(s: str) -> datetime:
        s = s.strip()
        if s.isdigit() and len(s) == 14:
            return datetime.strptime(s[:8], "%Y%m%d")
        return datetime.strptime(s, "%Y-%m-%d")

    d_start = _to_date(start)
    d_end = _to_date(end)
    if d_end < d_start:
        raise ValueError(f"end ({end}) is before start ({start})")

    paths: list[Path] = []
    ts = d_start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_ts = d_end.replace(hour=23, minute=45, second=0, microsecond=0)
    while ts <= end_ts:
        ts_str = ts.strftime("%Y%m%d%H%M%S")
        try:
            paths.append(download_batch(ts_str, dest_dir=dest_dir, timeout=timeout, force=force))
        except requests.HTTPError as exc:
            if not skip_missing or exc.response is None or exc.response.status_code != 404:
                raise
            _warn_missing(ts_str, gkg_url(ts_str))
        ts += timedelta(minutes=_BATCH_MINUTES)
    return paths


def download_latest_batch(dest_dir: Path | None = None, timeout: int = 120, force: bool = False) -> Path:
    """Download the most recent available GDELT GKG batch.

    Walks back from the current 15-minute boundary until a batch is found on
    the server (GDELT publishes with a delay).

    Args:
        dest_dir: Directory to store the unzipped ``.gkg.csv`` file.
        timeout: HTTP request timeout in seconds.
        force: If True, re-download existing files (overwrite). Defaults to
            False (skip existing).

    Returns:
        Path to the downloaded ``.gkg.csv`` file.
    """
    if dest_dir is None:
        dest_dir = config.raw_data_dir

    now = datetime.utcnow()
    # Round down to the nearest 15-minute boundary.
    boundary = now.replace(minute=(now.minute // _BATCH_MINUTES) * _BATCH_MINUTES, second=0, microsecond=0)

    for back in range(0, 24 * 4):  # try up to 24 hours back
        ts = (boundary - timedelta(minutes=_BATCH_MINUTES * back)).strftime("%Y%m%d%H%M%S")
        try:
            return download_batch(ts, dest_dir=dest_dir, timeout=timeout, force=force)
        except requests.HTTPError:
            continue
    raise FileNotFoundError("No recent GDELT GKG batch found on the server")