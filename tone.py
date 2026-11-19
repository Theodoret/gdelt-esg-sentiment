"""Tone / sentiment extraction from GDELT ``V2Tone`` (plan.txt Section 4.2).

``V2Tone`` is a semicolon-separated list of tone records, each ``#``-separated.
When a record has multiple tone entries, the first is used as the
article-level value.

NOTE ON ACTUAL DATA FORMAT (verified 2026-11-17 batch):
    The standard GDELT 2.0 ``V2Tone`` layout is a 12-field record
    (tone#positive#negative#polarity#activity#self_group#self_positive#...).
    The batch used in this project does NOT follow that layout. Every record
    here has exactly 5 fields::

        tone#positive#negative#year#word_count

    where ``tone`` is a small integer level (1-4), ``positive`` and
    ``negative`` are counts, ``year`` is a publication year (1830-2014), and
    ``word_count`` is a large integer. There is no explicit polarity field, so
    ``polarity`` is derived as ``positive - negative``.

    FORMAT DETECTION: The parser is layout-aware. It inspects the field count
    of each record:
      - 12-field (standard GDELT 2.0): ``polarity`` is read directly from
        field 3.
      - 5-field (this batch): ``polarity`` is derived as ``positive - negative``.
      - any other count: ``polarity`` is derived as a fallback.
    This keeps the module correct if a later batch uses the standard 12-field
    layout.
"""

from __future__ import annotations

import pandas as pd

import config

# Field positions within a single '#'-separated V2Tone record.
# Standard GDELT 2.0 12-field layout:
#   tone#positive#negative#polarity#activity#self_group#self_positive#...
# This project's 5-field layout:
#   tone#positive#negative#year#word_count
_TONE_IDX = 0
_POSITIVE_IDX = 1
_NEGATIVE_IDX = 2
_POLARITY_IDX = 3

# A record carries an explicit polarity field only in the standard GDELT
# 12-field layout; any other field count (e.g. this batch's 5-field layout)
# has no polarity field and it must be derived.
_STANDARD_N_FIELDS = 12


def parse_v2tone(v2tone: str) -> dict[str, float | None]:
    """Parse a single ``V2Tone`` string into numeric tone metrics.

    Returns a dict with keys ``tone``, ``positive``, ``negative``, ``polarity``.
    ``polarity`` is read from field 3 when the record has the standard
    12-field layout; otherwise it is derived as ``positive - negative``
    (5-field layout / fallback). Values are ``None`` when a field is missing
    or non-numeric.
    """
    result: dict[str, float | None] = {
        "tone": None,
        "positive": None,
        "negative": None,
        "polarity": None,
    }
    if not v2tone or not isinstance(v2tone, str):
        return result

    # Take the first tone record as the article-level value.
    first = v2tone.split(";")[0].strip()
    if not first:
        return result

    fields = first.split("#")
    if len(fields) < 3:
        return result

    def _num(idx: int) -> float | None:
        try:
            return float(fields[idx])
        except (ValueError, IndexError):
            return None

    tone = _num(_TONE_IDX)
    positive = _num(_POSITIVE_IDX)
    negative = _num(_NEGATIVE_IDX)

    result["tone"] = tone
    result["positive"] = positive
    result["negative"] = negative

    # Explicit polarity field present (standard 12-field layout).
    if len(fields) == _STANDARD_N_FIELDS:
        result["polarity"] = _num(_POLARITY_IDX)
    # No explicit polarity field (5-field layout / fallback): derive it.
    elif positive is not None and negative is not None:
        result["polarity"] = positive - negative
    return result


def extract_tone(df: pd.DataFrame, v2tone_col: str = "V2Tone") -> pd.DataFrame:
    """Add numeric tone columns to ``df``.

    Adds ``tone``, ``positive``, ``negative``, ``polarity`` (float, ``NaN``
    when missing). Rows without a parseable ``V2Tone`` get ``NaN`` and are
    excluded from sentiment aggregation but retained for volume statistics
    (plan.txt Section 3.2).
    """
    out = df.copy()
    parsed = out[v2tone_col].fillna("").astype(str).apply(parse_v2tone)
    for key in ("tone", "positive", "negative", "polarity"):
        out[key] = parsed.apply(lambda d: d[key])
    return out