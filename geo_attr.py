"""Media source geographic attribution (plan.txt Section 4.3).

Identifies the source country / jurisdiction of each article using
``SourceCommonName`` (media domain) and ``V2Locations`` (locations mentioned
in the article):

- ``source_country``: country inferred from the domain's ccTLD (e.g.
  ``leadership.ng`` -> Nigeria). Generic TLDs (``.com``, ``.org``, ``.net``,
  ``.edu``, ``.tv``, ``.fm``) carry no country signal and yield ``None``.
- ``location_country``: most frequent country code in ``V2Locations``
  (field index 2 of each ``#``-separated location record).
- ``attributed_country``: ``source_country`` when available, otherwise
  ``location_country``, otherwise ``config.UNKNOWN_SOURCE``.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

import config

# ---------------------------------------------------------------------------
# Country code mappings
# ---------------------------------------------------------------------------
# ccTLD -> country name (ISO 3166-1 alpha-2 country-code TLDs).
TLD_TO_COUNTRY: dict[str, str] = {
    "ac": "Ascension Island",
    "ad": "Andorra",
    "ae": "United Arab Emirates",
    "af": "Afghanistan",
    "ag": "Antigua and Barbuda",
    "ai": "Anguilla",
    "al": "Albania",
    "am": "Armenia",
    "ao": "Angola",
    "aq": "Antarctica",
    "ar": "Argentina",
    "as": "American Samoa",
    "at": "Austria",
    "au": "Australia",
    "aw": "Aruba",
    "ax": "Aland Islands",
    "az": "Azerbaijan",
    "ba": "Bosnia and Herzegovina",
    "bb": "Barbados",
    "bd": "Bangladesh",
    "be": "Belgium",
    "bf": "Burkina Faso",
    "bg": "Bulgaria",
    "bh": "Bahrain",
    "bi": "Burundi",
    "bj": "Benin",
    "bl": "Saint Barthelemy",
    "bm": "Bermuda",
    "bn": "Brunei",
    "bo": "Bolivia",
    "bq": "Bonaire, Sint Eustatius and Saba",
    "br": "Brazil",
    "bs": "Bahamas",
    "bt": "Bhutan",
    "bv": "Bouvet Island",
    "bw": "Botswana",
    "by": "Belarus",
    "bz": "Belize",
    "ca": "Canada",
    "cc": "Cocos Islands",
    "cd": "Democratic Republic of the Congo",
    "cf": "Central African Republic",
    "cg": "Republic of the Congo",
    "ch": "Switzerland",
    "ci": "Ivory Coast",
    "ck": "Cook Islands",
    "cl": "Chile",
    "cm": "Cameroon",
    "cn": "China",
    "co": "Colombia",
    "cr": "Costa Rica",
    "cu": "Cuba",
    "cv": "Cape Verde",
    "cw": "Curacao",
    "cx": "Christmas Island",
    "cy": "Cyprus",
    "cz": "Czechia",
    "de": "Germany",
    "dj": "Djibouti",
    "dk": "Denmark",
    "dm": "Dominica",
    "do": "Dominican Republic",
    "dz": "Algeria",
    "ec": "Ecuador",
    "ee": "Estonia",
    "eg": "Egypt",
    "eh": "Western Sahara",
    "er": "Eritrea",
    "es": "Spain",
    "et": "Ethiopia",
    "eu": "European Union",
    "fi": "Finland",
    "fj": "Fiji",
    "fk": "Falkland Islands",
    "fm": "Micronesia",
    "fo": "Faroe Islands",
    "fr": "France",
    "ga": "Gabon",
    "gb": "United Kingdom",
    "gd": "Grenada",
    "ge": "Georgia",
    "gf": "French Guiana",
    "gg": "Guernsey",
    "gh": "Ghana",
    "gi": "Gibraltar",
    "gl": "Greenland",
    "gm": "Gambia",
    "gn": "Guinea",
    "gp": "Guadeloupe",
    "gq": "Equatorial Guinea",
    "gr": "Greece",
    "gs": "South Georgia and the South Sandwich Islands",
    "gt": "Guatemala",
    "gu": "Guam",
    "gw": "Guinea-Bissau",
    "gy": "Guyana",
    "hk": "Hong Kong",
    "hm": "Heard Island and McDonald Islands",
    "hn": "Honduras",
    "hr": "Croatia",
    "ht": "Haiti",
    "hu": "Hungary",
    "id": "Indonesia",
    "ie": "Ireland",
    "il": "Israel",
    "im": "Isle of Man",
    "in": "India",
    "io": "British Indian Ocean Territory",
    "iq": "Iraq",
    "ir": "Iran",
    "is": "Iceland",
    "it": "Italy",
    "je": "Jersey",
    "jm": "Jamaica",
    "jo": "Jordan",
    "jp": "Japan",
    "ke": "Kenya",
    "kg": "Kyrgyzstan",
    "kh": "Cambodia",
    "ki": "Kiribati",
    "km": "Comoros",
    "kn": "Saint Kitts and Nevis",
    "kp": "North Korea",
    "kr": "South Korea",
    "kw": "Kuwait",
    "ky": "Cayman Islands",
    "kz": "Kazakhstan",
    "la": "Laos",
    "lb": "Lebanon",
    "lc": "Saint Lucia",
    "li": "Liechtenstein",
    "lk": "Sri Lanka",
    "lr": "Liberia",
    "ls": "Lesotho",
    "lt": "Lithuania",
    "lu": "Luxembourg",
    "lv": "Latvia",
    "ly": "Libya",
    "ma": "Morocco",
    "mc": "Monaco",
    "md": "Moldova",
    "me": "Montenegro",
    "mf": "Saint Martin",
    "mg": "Madagascar",
    "mh": "Marshall Islands",
    "mk": "North Macedonia",
    "ml": "Mali",
    "mm": "Myanmar",
    "mn": "Mongolia",
    "mo": "Macau",
    "mp": "Northern Mariana Islands",
    "mq": "Martinique",
    "mr": "Mauritania",
    "ms": "Montserrat",
    "mt": "Malta",
    "mu": "Mauritius",
    "mv": "Maldives",
    "mw": "Malawi",
    "mx": "Mexico",
    "my": "Malaysia",
    "mz": "Mozambique",
    "na": "Namibia",
    "nc": "New Caledonia",
    "ne": "Niger",
    "nf": "Norfolk Island",
    "ng": "Nigeria",
    "ni": "Nicaragua",
    "nl": "Netherlands",
    "no": "Norway",
    "np": "Nepal",
    "nr": "Nauru",
    "nu": "Niue",
    "nz": "New Zealand",
    "om": "Oman",
    "pa": "Panama",
    "pe": "Peru",
    "pf": "French Polynesia",
    "pg": "Papua New Guinea",
    "ph": "Philippines",
    "pk": "Pakistan",
    "pl": "Poland",
    "pm": "Saint Pierre and Miquelon",
    "pn": "Pitcairn Islands",
    "pr": "Puerto Rico",
    "ps": "Palestine",
    "pt": "Portugal",
    "pw": "Palau",
    "py": "Paraguay",
    "qa": "Qatar",
    "re": "Reunion",
    "ro": "Romania",
    "rs": "Serbia",
    "ru": "Russia",
    "rw": "Rwanda",
    "sa": "Saudi Arabia",
    "sb": "Solomon Islands",
    "sc": "Seychelles",
    "sd": "Sudan",
    "se": "Sweden",
    "sg": "Singapore",
    "sh": "Saint Helena",
    "si": "Slovenia",
    "sj": "Svalbard and Jan Mayen",
    "sk": "Slovakia",
    "sl": "Sierra Leone",
    "sm": "San Marino",
    "sn": "Senegal",
    "so": "Somalia",
    "sr": "Suriname",
    "ss": "South Sudan",
    "st": "Sao Tome and Principe",
    "sv": "El Salvador",
    "sx": "Sint Maarten",
    "sy": "Syria",
    "sz": "Eswatini",
    "tc": "Turks and Caicos Islands",
    "td": "Chad",
    "tf": "French Southern Territories",
    "tg": "Togo",
    "th": "Thailand",
    "tj": "Tajikistan",
    "tk": "Tokelau",
    "tl": "Timor-Leste",
    "tm": "Turkmenistan",
    "tn": "Tunisia",
    "to": "Tonga",
    "tr": "Turkey",
    "tt": "Trinidad and Tobago",
    "tv": "Tuvalu",
    "tw": "Taiwan",
    "tz": "Tanzania",
    "ua": "Ukraine",
    "ug": "Uganda",
    "uk": "United Kingdom",
    "um": "United States Minor Outlying Islands",
    "us": "United States",
    "uy": "Uruguay",
    "uz": "Uzbekistan",
    "va": "Vatican City",
    "vc": "Saint Vincent and the Grenadines",
    "ve": "Venezuela",
    "vg": "British Virgin Islands",
    "vi": "United States Virgin Islands",
    "vn": "Vietnam",
    "vu": "Vanuatu",
    "wf": "Wallis and Futuna",
    "ws": "Samoa",
    "ye": "Yemen",
    "yt": "Mayotte",
    "za": "South Africa",
    "zm": "Zambia",
    "zw": "Zimbabwe",
}

# FIPS 10-4 country codes -> country name (used by GDELT V2Locations).
# NOTE: GDELT uses FIPS 10-4 codes, NOT ISO 3166-1. This is why e.g. Nigeria
# is "NI", Bolivia is "BL", Spain is "SP", China is "CH", and the United
# Kingdom is "UK". Mapping verified against the codes present in the
# 2026-11-17 batch.
FIPS_TO_COUNTRY: dict[str, str] = {
    "AA": "Aruba", "AC": "Antigua and Barbuda", "AE": "United Arab Emirates",
    "AF": "Afghanistan", "AG": "Algeria", "AJ": "Azerbaijan", "AL": "Albania",
    "AM": "Armenia", "AN": "Andorra", "AO": "Angola", "AQ": "American Samoa",
    "AR": "Argentina", "AS": "Australia", "AT": "Ashmore and Cartier Islands",
    "AU": "Austria", "AV": "Anguilla", "AY": "Antarctica", "BA": "Bahrain",
    "BB": "Barbados", "BC": "Botswana", "BD": "Bermuda", "BE": "Belgium",
    "BF": "Bahamas", "BG": "Bangladesh", "BH": "Belize", "BK": "Bosnia and Herzegovina",
    "BL": "Bolivia", "BM": "Burma", "BN": "Benin", "BO": "Belarus",
    "BP": "Solomon Islands", "BR": "Brazil", "BS": "Bassas da India",
    "BT": "Bhutan", "BU": "Bulgaria", "BV": "Bouvet Island", "BX": "Brunei",
    "BY": "Burundi", "CA": "Cambodia", "CB": "Cambodia", "CD": "Chad",
    "CE": "Sri Lanka", "CF": "Republic of the Congo", "CG": "Democratic Republic of the Congo",
    "CH": "China", "CI": "Chile", "CJ": "Cayman Islands", "CK": "Cocos Islands",
    "CM": "Cameroon", "CN": "Comoros", "CO": "Colombia", "CQ": "Northern Mariana Islands",
    "CR": "Coral Sea Islands", "CS": "Costa Rica", "CT": "Central African Republic",
    "CU": "Cuba", "CV": "Cape Verde", "CW": "Cook Islands", "CY": "Cyprus",
    "DA": "Denmark", "DJ": "Djibouti", "DO": "Dominica", "DQ": "Jarvis Island",
    "DR": "Dominican Republic", "DX": "Dhekelia", "EC": "Ecuador", "EG": "Egypt",
    "EI": "Ireland", "EK": "Equatorial Guinea", "EN": "Estonia", "ER": "Eritrea",
    "ES": "El Salvador", "ET": "Ethiopia", "EU": "Europa Island", "EZ": "Czechia",
    "FG": "French Guiana", "FI": "Finland", "FJ": "Fiji", "FK": "Falkland Islands",
    "FM": "Federated States of Micronesia", "FO": "Faroe Islands", "FP": "French Polynesia",
    "FQ": "Baker Island", "FR": "France", "FS": "French Southern and Antarctic Lands",
    "GA": "Gambia", "GB": "Gabon", "GG": "Georgia", "GH": "Ghana",
    "GI": "Gibraltar", "GJ": "Grenada", "GK": "Guernsey", "GL": "Greenland",
    "GM": "Germany", "GO": "Glorioso Islands", "GP": "Guadeloupe", "GQ": "Guam",
    "GR": "Greece", "GT": "Guatemala", "GV": "Guinea", "GY": "Guyana",
    "GZ": "Gaza Strip", "HA": "Haiti", "HK": "Hong Kong", "HM": "Heard Island and McDonald Islands",
    "HO": "Honduras", "HQ": "Howland Island", "HR": "Croatia", "HU": "Hungary",
    "IC": "Iceland", "ID": "Indonesia", "IM": "Man (Isle of)", "IN": "India",
    "IO": "British Indian Ocean Territory", "IQ": "Iraq", "IR": "Iran",
    "IS": "Israel", "IT": "Italy", "IV": "Ivory Coast", "IZ": "Iraq",
    "JA": "Japan", "JE": "Jersey", "JM": "Jamaica", "JN": "Jan Mayen",
    "JO": "Jordan", "JQ": "Johnston Atoll", "JU": "Juan de Nova Island",
    "KE": "Kenya", "KG": "Kyrgyzstan", "KH": "Kiribati", "KM": "Comoros",
    "KN": "North Korea", "KQ": "Kingman Reef", "KR": "Kiribati", "KS": "South Korea",
    "KT": "Christmas Island", "KU": "Kuwait", "KV": "Kosovo", "KY": "Cayman Islands",
    "KZ": "Kazakhstan", "LA": "Laos", "LE": "Lebanon", "LG": "Latvia",
    "LH": "Lithuania", "LI": "Liberia", "LO": "Slovakia", "LQ": "Palmyra Atoll",
    "LS": "Liechtenstein", "LT": "Lesotho", "LU": "Luxembourg", "LY": "Libya",
    "MA": "Madagascar", "MB": "Martinique", "MC": "Macau", "MD": "Moldova",
    "MF": "Mayotte", "MG": "Mongolia", "MH": "Montserrat", "MI": "Midway Islands",
    "MJ": "Montenegro", "MK": "North Macedonia", "ML": "Mali", "MN": "Monaco",
    "MO": "Morocco", "MP": "Mauritius", "MQ": "Midway Islands", "MR": "Mauritania",
    "MT": "Malta", "MU": "Oman", "MV": "Maldives", "MW": "Montenegro",
    "MX": "Mexico", "MY": "Malaysia", "MZ": "Mozambique", "NC": "New Caledonia",
    "NE": "Niue", "NF": "Norfolk Island", "NG": "Niger", "NH": "Vanuatu",
    "NI": "Nigeria", "NL": "Netherlands", "NM": "No Man's Land", "NO": "Norway",
    "NP": "Nepal", "NQ": "Navassa Island", "NR": "Nauru", "NS": "Suriname",
    "NT": "Netherlands Antilles", "NU": "Nicaragua", "NZ": "New Zealand",
    "OD": "South Sudan", "OS": "Kosovo", "PA": "Paraguay", "PC": "Pitcairn Islands",
    "PE": "Peru", "PF": "Paracel Islands", "PG": "Spratly Islands", "PI": "Philippines",
    "PK": "Pakistan", "PL": "Poland", "PM": "Panama", "PO": "Portugal",
    "PP": "Papua New Guinea", "PS": "Palau", "PU": "Guinea-Bissau", "QA": "Qatar",
    "RE": "Reunion", "RI": "Serbia", "RM": "Marshall Islands", "RN": "Saint Martin",
    "RO": "Romania", "RP": "Philippines", "RQ": "Puerto Rico", "RS": "Russia",
    "RW": "Rwanda", "SA": "Saudi Arabia", "SB": "Saint Barthelemy", "SC": "Saint Kitts and Nevis",
    "SE": "Seychelles", "SF": "South Africa", "SG": "Senegal", "SH": "Saint Helena",
    "SI": "Slovenia", "SL": "Sierra Leone", "SM": "San Marino", "SN": "Singapore",
    "SO": "Somalia", "SP": "Spain", "ST": "Saint Lucia", "SU": "Sudan",
    "SV": "Svalbard", "SW": "Sweden", "SY": "Syria", "SZ": "Switzerland",
    "TC": "United Arab Emirates", "TD": "Trinidad and Tobago", "TE": "Tromelin Island",
    "TH": "Thailand", "TI": "Tajikistan", "TK": "Turks and Caicos Islands", "TL": "Tokelau",
    "TM": "Timor-Leste", "TN": "Tonga", "TO": "Togo", "TP": "Sao Tome and Principe",
    "TS": "Tunisia", "TT": "Taiwan", "TU": "Turkey", "TV": "Tuvalu",
    "TW": "Taiwan", "TX": "Turkmenistan", "TZ": "Tanzania", "UG": "Uganda",
    "UK": "United Kingdom", "UP": "Ukraine", "UR": "Uruguay", "US": "United States",
    "UV": "Burkina Faso", "UY": "Uruguay", "UZ": "Uzbekistan", "VC": "Vatican City",
    "VE": "Venezuela", "VI": "British Virgin Islands", "VM": "Vietnam", "VQ": "United States Virgin Islands",
    "VT": "Vietnam", "WA": "Namibia", "WB": "Wallis and Futuna", "WE": "West Bank",
    "WF": "Wallis and Futuna", "WI": "Western Sahara", "WQ": "Wake Island", "WS": "Samoa",
    "WZ": "Eswatini", "YM": "Yemen", "ZA": "Zambia", "ZI": "Zimbabwe",
}

# Generic TLDs that carry no country signal.
_GENERIC_TLDS = {"com", "org", "net", "edu", "gov", "mil", "int", "info", "biz", "tv", "fm", "io", "co", "me"}


def country_from_domain(domain: str) -> str | None:
    """Infer the source country from a media domain's ccTLD.

    Returns ``None`` for generic TLDs or unparseable domains.
    """
    if not domain or not isinstance(domain, str):
        return None
    parts = domain.strip().lower().split(".")
    if len(parts) < 2:
        return None
    tld = parts[-1]
    if tld in _GENERIC_TLDS:
        return None
    return TLD_TO_COUNTRY.get(tld)


def parse_v2locations(v2locations: str) -> list[tuple[str, str, int]]:
    """Parse a ``V2Locations`` string into (country_code, country_name, word_count).

    Each location record is ``#``-separated; the country code is field index 2
    and the word count is the last field. Records without a recognizable
    country code are skipped.
    """
    out: list[tuple[str, str, int]] = []
    if not v2locations or not isinstance(v2locations, str):
        return out
    for rec in v2locations.split(";"):
        fields = rec.split("#")
        if len(fields) < 3:
            continue
        code = fields[2].strip().upper()
        name = FIPS_TO_COUNTRY.get(code)
        if name is None:
            continue
        try:
            wc = int(fields[-1]) if fields[-1].strip() else 0
        except ValueError:
            wc = 0
        out.append((code, name, wc))
    return out


def most_frequent_country(locations: list[tuple[str, str, int]]) -> str | None:
    """Return the country name appearing most often in parsed locations."""
    if not locations:
        return None
    counts = Counter(name for _, name, _ in locations)
    return counts.most_common(1)[0][0]


# Continent mapping for the ``continents`` filter (country name -> continent).
# Covers the countries present in the dataset; extend as needed.
COUNTRY_TO_CONTINENT: dict[str, str] = {
    "Afghanistan": "Asia", "Albania": "Europe", "Algeria": "Africa",
    "American Samoa": "Oceania", "Andorra": "Europe", "Angola": "Africa",
    "Antigua and Barbuda": "North America", "Argentina": "South America",
    "Armenia": "Asia", "Australia": "Oceania", "Austria": "Europe",
    "Azerbaijan": "Asia", "Bahamas": "North America", "Bahrain": "Asia",
    "Bangladesh": "Asia", "Barbados": "North America", "Belarus": "Europe",
    "Belgium": "Europe", "Belize": "North America", "Benin": "Africa",
    "Bermuda": "North America", "Bhutan": "Asia", "Bolivia": "South America",
    "Bosnia and Herzegovina": "Europe", "Botswana": "Africa", "Brazil": "South America",
    "Brunei": "Asia", "Bulgaria": "Europe", "Burkina Faso": "Africa",
    "Burundi": "Africa", "Cambodia": "Asia", "Cameroon": "Africa",
    "Canada": "North America", "Cape Verde": "Africa", "Central African Republic": "Africa",
    "Chad": "Africa", "Chile": "South America", "China": "Asia",
    "Colombia": "South America", "Comoros": "Africa", "Costa Rica": "North America",
    "Croatia": "Europe", "Cuba": "North America", "Cyprus": "Asia",
    "Czechia": "Europe", "Democratic Republic of the Congo": "Africa",
    "Denmark": "Europe", "Djibouti": "Africa", "Dominica": "North America",
    "Dominican Republic": "North America", "Ecuador": "South America",
    "Egypt": "Africa", "El Salvador": "North America", "Equatorial Guinea": "Africa",
    "Eritrea": "Africa", "Estonia": "Europe", "Eswatini": "Africa",
    "Ethiopia": "Africa", "Fiji": "Oceania", "Finland": "Europe",
    "France": "Europe", "Gabon": "Africa", "Gambia": "Africa",
    "Georgia": "Asia", "Germany": "Europe", "Ghana": "Africa",
    "Greece": "Europe", "Grenada": "North America", "Guam": "Oceania",
    "Guatemala": "North America", "Guinea": "Africa", "Guinea-Bissau": "Africa",
    "Guyana": "South America", "Haiti": "North America", "Honduras": "North America",
    "Hong Kong": "Asia", "Hungary": "Europe", "Iceland": "Europe",
    "India": "Asia", "Indonesia": "Asia", "Iran": "Asia", "Iraq": "Asia",
    "Ireland": "Europe", "Israel": "Asia", "Italy": "Europe",
    "Ivory Coast": "Africa", "Jamaica": "North America", "Japan": "Asia",
    "Jersey": "Europe", "Jordan": "Asia", "Kazakhstan": "Asia",
    "Kenya": "Africa", "Kosovo": "Europe", "Kuwait": "Asia",
    "Kyrgyzstan": "Asia", "Laos": "Asia", "Latvia": "Europe",
    "Lebanon": "Asia", "Lesotho": "Africa", "Liberia": "Africa",
    "Libya": "Africa", "Liechtenstein": "Europe", "Lithuania": "Europe",
    "Luxembourg": "Europe", "Macau": "Asia", "Madagascar": "Africa",
    "Malawi": "Africa", "Malaysia": "Asia", "Maldives": "Asia",
    "Mali": "Africa", "Malta": "Europe", "Mauritania": "Africa",
    "Mauritius": "Africa", "Mexico": "North America", "Micronesia": "Oceania",
    "Moldova": "Europe", "Monaco": "Europe", "Mongolia": "Asia",
    "Montenegro": "Europe", "Morocco": "Africa", "Mozambique": "Africa",
    "Myanmar": "Asia", "Namibia": "Africa", "Nepal": "Asia",
    "Netherlands": "Europe", "New Caledonia": "Oceania", "New Zealand": "Oceania",
    "Nicaragua": "North America", "Niger": "Africa", "Nigeria": "Africa",
    "North Korea": "Asia", "North Macedonia": "Europe", "Norway": "Europe",
    "Oman": "Asia", "Pakistan": "Asia", "Palestine": "Asia", "Panama": "North America",
    "Papua New Guinea": "Oceania", "Paraguay": "South America", "Peru": "South America",
    "Philippines": "Asia", "Poland": "Europe", "Portugal": "Europe",
    "Puerto Rico": "North America", "Qatar": "Asia", "Republic of the Congo": "Africa",
    "Romania": "Europe", "Russia": "Europe", "Rwanda": "Africa",
    "Saint Barthelemy": "North America", "Saint Kitts and Nevis": "North America",
    "Saint Lucia": "North America", "Saint Vincent and the Grenadines": "North America",
    "Samoa": "Oceania", "San Marino": "Europe", "Sao Tome and Principe": "Africa",
    "Saudi Arabia": "Asia", "Senegal": "Africa", "Serbia": "Europe",
    "Seychelles": "Africa", "Sierra Leone": "Africa", "Singapore": "Asia",
    "Slovakia": "Europe", "Slovenia": "Europe", "Solomon Islands": "Oceania",
    "Somalia": "Africa", "South Africa": "Africa", "South Korea": "Asia",
    "South Sudan": "Africa", "Spain": "Europe", "Sri Lanka": "Asia",
    "Sudan": "Africa", "Suriname": "South America", "Sweden": "Europe",
    "Switzerland": "Europe", "Syria": "Asia", "Taiwan": "Asia",
    "Tajikistan": "Asia", "Tanzania": "Africa", "Thailand": "Asia",
    "Timor-Leste": "Asia", "Togo": "Africa", "Trinidad and Tobago": "North America",
    "Tunisia": "Africa", "Turkey": "Asia", "Turkmenistan": "Asia",
    "Uganda": "Africa", "Ukraine": "Europe", "United Arab Emirates": "Asia",
    "United Kingdom": "Europe", "United States": "North America",
    "Uruguay": "South America", "Uzbekistan": "Asia", "Vanuatu": "Oceania",
    "Vatican City": "Europe", "Venezuela": "South America", "Vietnam": "Asia",
    "Yemen": "Asia", "Zambia": "Africa", "Zimbabwe": "Africa",
}


def filter_by_countries(
    df: pd.DataFrame,
    countries: list[str] | None = None,
    continents: list[str] | None = None,
    country_col: str = "attributed_country",
) -> pd.DataFrame:
    """Filter rows by target countries and/or continents.

    Args:
        df: DataFrame with an ``attributed_country`` column.
        countries: Target country names, or ["ALL"] for no country filter.
        continents: Target continents, or ["ALL"] for no continent filter.
        country_col: Column holding the attributed country.

    Returns:
        Filtered DataFrame. Rows whose country is ``UNKNOWN`` are kept only
        when no country/continent filter is applied.
    """
    out = df.copy()
    if countries and countries != ["ALL"]:
        out = out[out[country_col].isin(countries)]
    if continents and continents != ["ALL"]:
        cont = out[country_col].map(COUNTRY_TO_CONTINENT)
        out = out[cont.isin(continents)]
    return out


def attribute(df: pd.DataFrame) -> pd.DataFrame:
    """Add geographic attribution columns to ``df``.

    Adds:
    - ``source_country``: country from domain ccTLD (``None`` if generic TLD).
    - ``location_countries``: semicolon-joined country names from V2Locations.
    - ``location_country``: most frequent country in V2Locations.
    - ``attributed_country``: source_country, else location_country, else
      ``config.UNKNOWN_SOURCE``.
    """
    out = df.copy()

    out["source_country"] = out["SourceCommonName"].apply(country_from_domain)

    parsed = out["V2Locations"].fillna("").astype(str).apply(parse_v2locations)
    out["location_countries"] = parsed.apply(
        lambda locs: ";".join(dict.fromkeys(name for _, name, _ in locs))
    )
    out["location_country"] = parsed.apply(most_frequent_country)

    out["attributed_country"] = out["source_country"].fillna(
        out["location_country"]
    ).fillna(config.UNKNOWN_SOURCE)

    return out