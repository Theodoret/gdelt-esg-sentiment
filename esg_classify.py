"""ESG classification of GDELT GKG records (plan.txt Section 4.1).

Classifies each article into Environmental (E), Social (S), and/or Governance
(G) pillars based on GDELT ``V2Themes`` matching domain-specific ESG taxonomies,
plus keyword/phrase matching. Multi-label tagging is supported: an article can
be tagged with more than one pillar.
"""

from __future__ import annotations

import re

import pandas as pd

import config

# ---------------------------------------------------------------------------
# ESG taxonomies
# ---------------------------------------------------------------------------
# Each pillar maps a set of GDELT theme substrings (matched case-insensitively
# against V2Themes) and a set of free-text keywords/phrases. A record is tagged
# with a pillar if any theme substring OR any keyword appears.
#
# GDELT theme prefixes used below (see GDELT GKG 2.0 theme documentation):
#   ENV_*        environmental / climate / energy
#   DISASTER_*   natural & manmade disasters
#   TAX_DISEASE  health / disease
#   SOC_*        social issues
#   UNGP_*       UN Guiding Principles (human rights, labour, environment)
#   GOV_*        governance / government
#   EPU_*        economic policy uncertainty
#   TAX_FNCACT   functional actors (officials, regulators, judiciary)
#   WB_*         World Bank sectors
#   CRISISLEX_*  crisis lexicon
#   MAR_*        maritime
#   ECO_*        economic
#   LABOUR_*     labour
#   HUMAN_RIGHT* human rights
#   CORRUPTION*  corruption
#   TAX_*        taxonomies (disease, crime, etc.)

ESG_TAXONOMY: dict[str, dict[str, list[str]]] = {
    "Environmental": {
        "themes": [
            "ENV_",
            "DISASTER_",
            "CLIMATE",
            "POLLUTION",
            "CARBON",
            "EMISSION",
            "RENEWABLE",
            "SOLAR",
            "WIND",
            "ENERGY",
            "WATER",
            "DEFORESTATION",
            "BIODIVERSITY",
            "WILDLIFE",
            "RECYCL",
            "WASTE",
            "MAR_",
            "OIL",
            "GAS",
            "MINING",
            "NUCLEAR",
            "FLOOD",
            "DROUGHT",
            "EARTHQUAKE",
            "HURRICANE",
            "WILDFIRE",
            "EXTREME_WEATHER",
        ],
        "keywords": [
            "climate change",
            "global warming",
            "carbon emission",
            "greenhouse gas",
            "renewable energy",
            "solar power",
            "wind power",
            "air pollution",
            "water pollution",
            "deforestation",
            "biodiversity",
            "endangered species",
            "recycling",
            "waste management",
            "oil spill",
            "natural disaster",
            "environmental",
            "sustainability",
        ],
    },
    "Social": {
        "themes": [
            "SOC_",
            "UNGP_",
            "TAX_DISEASE",
            "HUMAN_RIGHT",
            "LABOUR",
            "LABOR",
            "CHILD",
            "WOMEN",
            "GENDER",
            "EDUCATION",
            "HEALTH",
            "POVERTY",
            "HUNGER",
            "REFUGEE",
            "MIGRANT",
            "DISCRIMINATION",
            "INEQUALITY",
            "EMPLOYMENT",
            "UNEMPLOYMENT",
            "WAGES",
            "WORKER",
            "WORKPLACE",
            "SAFETY",
            "COMMUNITY",
            "PROTEST",
            "STRIKE",
            "CRIME",
            "VIOLENCE",
            "TERROR",
            "HUMANITARIAN",
            "FOOD_SECURITY",
            "ACCESS_TO",
        ],
        "keywords": [
            "human rights",
            "child labor",
            "child labour",
            "forced labor",
            "forced labour",
            "gender equality",
            "women's rights",
            "workers' rights",
            "labor rights",
            "labour rights",
            "working conditions",
            "minimum wage",
            "employee safety",
            "workplace safety",
            "occupational health",
            "community engagement",
            "social responsibility",
            "public health",
            "health care",
            "healthcare",
            "education access",
            "poverty",
            "hunger",
            "refugee",
            "migrant",
            "discrimination",
            "inequality",
            "diversity",
            "inclusion",
        ],
    },
    "Governance": {
        "themes": [
            "GOV_",
            "EPU_",
            "TAX_FNCACT",
            "CORRUPTION",
            "BRIBERY",
            "FRAUD",
            "REGULAT",
            "COMPLIANCE",
            "ANTITRUST",
            "MONOPOL",
            "TAX_",
            "LEGAL",
            "JUDICIAL",
            "COURT",
            "LAWSUIT",
            "LITIGATION",
            "SANCTION",
            "EMBARGO",
            "POLICY",
            "LEGISLAT",
            "PARLIAMENT",
            "ELECTION",
            "GOVERNMENT",
            "BOARD",
            "EXECUTIVE",
            "MANAGEMENT",
            "AUDIT",
            "TRANSPARENCY",
            "ACCOUNTABILITY",
            "WHISTLEBLOW",
            "ETHICS",
            "CONFLICT_OF_INTEREST",
            "SHAREHOLDER",
            "CORPORATE_GOVERNANCE",
        ],
        "keywords": [
            "corporate governance",
            "board of directors",
            "executive compensation",
            "shareholder rights",
            "shareholder activism",
            "conflict of interest",
            "bribery",
            "corruption",
            "fraud",
            "money laundering",
            "tax evasion",
            "regulatory compliance",
            "regulatory fine",
            "antitrust",
            "monopoly",
            "sanctions",
            "embargo",
            "lawsuit",
            "litigation",
            "legal dispute",
            "audit",
            "transparency",
            "accountability",
            "whistleblower",
            "business ethics",
            "political lobbying",
            "government policy",
            "election",
            "legislation",
        ],
    },
}

# Precompile keyword regexes (word-boundary, case-insensitive) once.
_KEYWORD_RE: dict[str, list[re.Pattern[str]]] = {
    pillar: [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in tax["keywords"]]
    for pillar, tax in ESG_TAXONOMY.items()
}


def classify_themes(themes: str) -> set[str]:
    """Return the set of ESG pillars matched by a V2Themes string."""
    if not themes:
        return set()
    hits: set[str] = set()
    for pillar, tax in ESG_TAXONOMY.items():
        if any(sub.lower() in themes.lower() for sub in tax["themes"]):
            hits.add(pillar)
    return hits


def classify_text(text: str) -> set[str]:
    """Return the set of ESG pillars matched by free-text keywords."""
    if not text:
        return set()
    hits: set[str] = set()
    for pillar, regexes in _KEYWORD_RE.items():
        if any(rx.search(text) for rx in regexes):
            hits.add(pillar)
    return hits


def classify_row(themes: str, text: str | None = None) -> set[str]:
    """Classify a single record, combining theme and keyword matches."""
    hits = classify_themes(themes)
    if text:
        hits |= classify_text(text)
    return hits


def classify(df: pd.DataFrame, themes_col: str = "V2Themes") -> pd.DataFrame:
    """Add ESG pillar columns to ``df``.

    Adds one boolean column per pillar (``is_Environmental``, ``is_Social``,
    ``is_Governance``) plus a combined ``esg_pillars`` column listing the
    matched pillars (empty string if none). Multi-label is supported.

    Args:
        df: DataFrame with a ``V2Themes`` column (from fetch/preprocess).
        themes_col: Column holding GDELT themes.

    Returns:
        A new DataFrame with the ESG tag columns appended.
    """
    out = df.copy()
    themes = out[themes_col].fillna("").astype(str)

    for pillar in config.esg_categories:
        out[f"is_{pillar}"] = themes.apply(
            lambda t: pillar in classify_themes(t)
        )

    out["esg_pillars"] = themes.apply(
        lambda t: ";".join(sorted(classify_themes(t)))
    )
    return out