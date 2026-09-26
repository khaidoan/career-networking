"""Detect which countries a free-text posting location refers to.

Country names, ISO codes and aliases come from ``src.vocabularies``. This module adds what the
vocabularies deliberately leave out: US states and Canadian provinces (their two-letter codes
clash with country codes such as CA and IN), a few multi-country regions and major cities that
postings often list without a country. Ambiguous terms map to every country they may mean
("CA" is Canada or California), and a posting matches when the preferred country is among them.
"""

import re
from functools import lru_cache

from src.vocabularies import COUNTRIES

# fmt: off
US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

CANADIAN_PROVINCES: dict[str, str] = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories",
    "NU": "Nunavut", "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon",
}

_EUROPE = (
    "AD", "AL", "AT", "BA", "BE", "BG", "BY", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MC", "MD", "ME",
    "MK", "MT", "NL", "NO", "PL", "PT", "RO", "RS", "SE", "SI", "SK", "SM", "UA", "VA",
)
_EUROPEAN_UNION = (
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE",
    "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
)
_MIDDLE_EAST_AFRICA = (
    "AE", "BH", "EG", "IL", "JO", "KE", "KW", "LB", "MA", "NG", "OM", "QA", "SA", "TN", "TR",
    "ZA",
)
_APAC = (
    "AU", "BD", "CN", "HK", "ID", "IN", "JP", "KR", "LK", "MY", "NZ", "PH", "PK", "SG", "TH",
    "TW", "VN",
)
_LATIN_AMERICA = (
    "AR", "BO", "BR", "CL", "CO", "CR", "DO", "EC", "GT", "HN", "MX", "PA", "PE", "PR", "PY",
    "SV", "UY", "VE",
)

REGIONS: dict[str, tuple[str, ...]] = {
    "europe": _EUROPE, "european union": _EUROPEAN_UNION, "eu": _EUROPEAN_UNION,
    "eea": (*_EUROPEAN_UNION, "IS", "LI", "NO"), "dach": ("DE", "AT", "CH"),
    "nordics": ("DK", "FI", "IS", "NO", "SE"), "benelux": ("BE", "NL", "LU"),
    "emea": (*_EUROPE, *_MIDDLE_EAST_AFRICA), "middle east": _MIDDLE_EAST_AFRICA,
    "apac": _APAC, "asia": _APAC, "asia pacific": _APAC, "anz": ("AU", "NZ"),
    "latam": _LATIN_AMERICA, "latin america": _LATIN_AMERICA, "south america": _LATIN_AMERICA,
    "central america": _LATIN_AMERICA, "north america": ("US", "CA", "MX"),
    "americas": ("US", "CA", *_LATIN_AMERICA),
}

CITIES: dict[str, str] = {
    "san francisco": "US", "sf bay area": "US", "bay area": "US", "silicon valley": "US",
    "new york city": "US", "nyc": "US", "los angeles": "US", "seattle": "US", "boston": "US",
    "chicago": "US", "austin": "US", "denver": "US", "atlanta": "US", "miami": "US",
    "palo alto": "US", "mountain view": "US", "san jose": "US", "san diego": "US",
    "toronto": "CA", "vancouver": "CA", "montreal": "CA", "montréal": "CA", "ottawa": "CA",
    "calgary": "CA", "waterloo": "CA",
    "london": "GB", "manchester": "GB", "edinburgh": "GB", "cambridge": "GB",
    "dublin": "IE", "berlin": "DE", "munich": "DE", "münchen": "DE", "hamburg": "DE",
    "frankfurt": "DE", "paris": "FR", "amsterdam": "NL", "rotterdam": "NL", "madrid": "ES",
    "barcelona": "ES", "lisbon": "PT", "milan": "IT", "zurich": "CH", "zürich": "CH",
    "geneva": "CH", "vienna": "AT", "stockholm": "SE", "copenhagen": "DK", "oslo": "NO",
    "helsinki": "FI", "warsaw": "PL", "prague": "CZ", "tel aviv": "IL", "bangalore": "IN",
    "bengaluru": "IN", "hyderabad": "IN", "mumbai": "IN", "pune": "IN", "tokyo": "JP",
    "seoul": "KR", "sydney": "AU", "melbourne": "AU", "auckland": "NZ", "são paulo": "BR",
    "sao paulo": "BR", "mexico city": "MX", "buenos aires": "AR", "bogotá": "CO",
    "bogota": "CO",
}
# fmt: on

REMOTE_PATTERN = re.compile(
    r"(?<!\w)(remote|anywhere|worldwide|global|distributed|work from home|wfh)(?!\w)",
    re.IGNORECASE,
)
_UPPERCASE_CODE = re.compile(r"(?<![A-Za-z])[A-Z]{2}(?![A-Za-z])")


@lru_cache
def _term_countries() -> dict[str, frozenset[str]]:
    """Lower-cased place names mapped to every country code they may refer to."""
    terms: dict[str, set[str]] = {}

    def add(term: str, codes: tuple[str, ...] | str) -> None:
        terms.setdefault(term.casefold(), set()).update(
            (codes,) if isinstance(codes, str) else codes
        )

    for country in COUNTRIES.values():
        for term in country.match_terms:
            add(term, country.code)
    for name in US_STATES.values():
        add(name, "US")
    for name in CANADIAN_PROVINCES.values():
        add(name, "CA")
    for region, codes in REGIONS.items():
        add(region, codes)
    for city, code in CITIES.items():
        add(city, code)
    return {term: frozenset(codes) for term, codes in terms.items()}


@lru_cache
def _term_pattern() -> re.Pattern[str]:
    # Longest first, so "new jersey" wins over "jersey" and "papua new guinea" over "guinea".
    alternatives = sorted(_term_countries(), key=len, reverse=True)
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(term) for term in alternatives) + r")(?!\w)")


def _code_countries(code: str) -> set[str]:
    countries: set[str] = set()
    if code in COUNTRIES:
        countries.add(code)
    if code in US_STATES:
        countries.add("US")
    if code in CANADIAN_PROVINCES:
        countries.add("CA")
    return countries


def countries_in(location: str) -> set[str]:
    """Every ISO country code the location may refer to (empty when none is recognised)."""
    countries: set[str] = set()
    for match in _term_pattern().finditer(location.casefold()):
        countries |= _term_countries()[match.group(1)]
    for code in _UPPERCASE_CODE.findall(location):
        countries |= _code_countries(code)
    return countries


def is_remote(location: str) -> bool:
    return bool(REMOTE_PATTERN.search(location))
