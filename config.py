"""Centralized parameter configuration for the ESG Media Sentiment Analysis Pipeline.

All pipeline stages read their settings from this module so that filtering,
paths, and aggregation behavior can be controlled from a single place without
refactoring downstream code. See plan.txt Section 2 for the parameter spec.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Directory layout (plan.txt Section 2)
# ---------------------------------------------------------------------------
# Base directory of the project (parent of this config module).
BASE_DIR = Path(__file__).resolve().parent

raw_data_dir = BASE_DIR / "data" / "raw"
processed_data_dir = BASE_DIR / "data" / "processed"
output_data_dir = BASE_DIR / "data" / "output"

# ---------------------------------------------------------------------------
# Data filtering parameters
# ---------------------------------------------------------------------------
# Inclusive start and end dates in GDELT timestamp format (YYYYMMDDHHMMSS)
# or ISO date format (YYYY-MM-DD). Use None to disable a bound.
date_range: tuple[str | None, str | None] = (None, None)

# Target continent filters, e.g. ["North America", "Europe", "Asia"] or ["ALL"].
continents: list[str] = ["ALL"]

# Target ISO country codes / names for source media, e.g. ["US", "GB", "ID"]
# or ["ALL"].
countries: list[str] = ["ALL"]

# ---------------------------------------------------------------------------
# ESG classification parameters
# ---------------------------------------------------------------------------
# ESG pillars to track.
esg_categories: list[str] = ["Environmental", "Social", "Governance"]

# ---------------------------------------------------------------------------
# Aggregation parameters
# ---------------------------------------------------------------------------
# Time aggregation window: "1D" (daily), "1W" (weekly), "1M" (monthly).
# Defaults to "1W": weekly buckets collect more articles per country, so the
# sentiment signal is less noisy than daily and the map reads as a trend
# rather than strobe-like single-article flicker.
aggregation_freq: str = "1W"

# ---------------------------------------------------------------------------
# Map visualization parameters
# ---------------------------------------------------------------------------
# Minimum number of articles (n_articles) required for a (date, country)
# bucket to be colored on the map / shown in the aggregation surface. Buckets
# below this threshold are considered too noisy to represent sentiment and are
# hidden. Tune to the coverage in your data; a lone article's tone is rarely
# a meaningful signal.
MIN_ARTICLES: int = 3

# ---------------------------------------------------------------------------
# GDELT schema / column handling
# ---------------------------------------------------------------------------
# Standard GDELT 2.0 GKG column headers (assigned on ingestion).
# GKG files are tab-separated with NO header row; this list is applied in order.
GDELT_COLUMNS: list[str] = [
    "GKGRecordID",
    "DATE",
    "NumArticles",
    "SourceCommonName",
    "DocumentIdentifier",
    "V1Counts",
    "V2Counts",
    "V1Themes",
    "V2Themes",
    "V1Locations",
    "V2Locations",
    "V1Persons",
    "V2Persons",
    "V1Organizations",
    "V2Organizations",
    "V1Tone",
    "V2Tone",
    "V1Dates",
    "V2Dates",
    "V1Sources",
    "V2Sources",
    "V1SocialImage",
    "V2SocialImage",
    "V1Quotations",
    "V2Quotations",
    "V1AllNames",
    "V2AllNames",
]

# Core columns retained for the pipeline (plan.txt Section 3.1).
CORE_COLUMNS: list[str] = [
    "DATE",
    "DocumentIdentifier",
    "V2Themes",
    "V2Locations",
    "V2Tone",
]

# Secondary / metadata columns.
SECONDARY_COLUMNS: list[str] = [
    "SourceCommonName",
    "V1Themes",
    "V1Locations",
]

# All retained columns.
RETAINED_COLUMNS: list[str] = CORE_COLUMNS + SECONDARY_COLUMNS

# ---------------------------------------------------------------------------
# Missing value handling (plan.txt Section 3.2)
# ---------------------------------------------------------------------------
# Sentinel used when a news source name is unknown.
UNKNOWN_SOURCE: str = "UNKNOWN"

# ---------------------------------------------------------------------------
# Deduplication (plan.txt Section 3.3)
# ---------------------------------------------------------------------------
# Columns used to identify duplicate records.
DEDUP_COLUMNS: list[str] = ["DocumentIdentifier", "DATE"]

# ---------------------------------------------------------------------------
# Paths helper
# ---------------------------------------------------------------------------


def ensure_dirs() -> None:
    """Create the data directories if they do not already exist."""
    for d in (raw_data_dir, processed_data_dir, output_data_dir):
        d.mkdir(parents=True, exist_ok=True)
