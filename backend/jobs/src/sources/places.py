"""Find cities and states (first-level divisions) in free text, offline, for one country.

The relocation filter uses this to place a posting's location, the user's home address and the
places they will not relocate to. Data: ``src/data/cities.tsv.gz``, every GeoNames place of at
least 1,000 people (CC BY 4.0, https://www.geonames.org; rebuilt by ``scripts/build_cities.py``).

Location text has no fixed format ("Austin, TX", "United States-Texas-Austin", "USA.VA.Reston",
"US-AZ-TUCSON-805 ~ 1151 E Hermans Rd"), so it is scanned for known names instead of parsed:

- A division is named in full ("Texas") or, written in capitals, by its code ("TX").
- A city counts when its division is also named in the text. When the text names no division
  at all, only a city of at least ``MIN_LONE_CITY_POPULATION`` counts ("San Francisco"), so
  ordinary words that happen to be small towns are ignored.
- When several cities share a name, the most populous in a named division wins.
"""

import gzip
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.sources.locations import CANADIAN_PROVINCES, US_STATES

CITIES_FILE = Path(__file__).resolve().parent.parent / "data" / "cities.tsv.gz"
MIN_LONE_CITY_POPULATION = 100_000
EARTH_RADIUS_MILES = 3958.8

# Division codes people write instead of the name; GeoNames itself stores names.
DIVISION_CODES: dict[str, dict[str, str]] = {"US": US_STATES, "CA": CANADIAN_PROVINCES}
# Short forms normalised on both sides, so "Ft. Collins" finds "Fort Collins".
_WORD_FORMS = {"saint": "st", "fort": "ft", "mount": "mt"}
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
# Postal codes written after the state on an address line.
_POSTAL_CODES = {
    "US": re.compile(r"(?<!\d)\d{5}(?:-\d{4})?(?!\d)"),
    "CA": re.compile(r"\b[A-Z]\d[A-Z] ?\d[A-Z]\d\b"),
}
# Resume contact details sit at the top; later lines are job history.
RESUME_HEADER_LINES = 8
# "New York City" is how GeoNames names it; these are other common spellings.
_CITY_ALIASES = {"nyc": "new york city", "new york": "new york city"}


@dataclass(frozen=True)
class Place:
    name: str
    division: str
    latitude: float
    longitude: float
    population: int

    @property
    def label(self) -> str:
        return f"{self.name}, {self.division}" if self.division else self.name

    def miles_to(self, other: "Place") -> float:
        """Great-circle distance in miles."""
        lat1, lon1, lat2, lon2 = map(
            math.radians, (self.latitude, self.longitude, other.latitude, other.longitude)
        )
        a = (
            math.sin((lat2 - lat1) / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        )
        return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class PlacesFound:
    cities: tuple[Place, ...]
    # Every division named in the text, with or without a city.
    divisions: frozenset[str]


@dataclass(frozen=True)
class _Index:
    # Normalised city name -> places with that name, most populous first.
    cities: dict[str, tuple[Place, ...]]
    # Normalised division name -> division name as stored.
    division_names: dict[str, str]
    # Upper-case code ("TX") -> division name.
    division_codes: dict[str, str]
    max_words: int


@dataclass(frozen=True)
class _Word:
    key: str
    raw: str


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.replace("’", "'"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _words(text: str) -> list[_Word]:
    words = []
    for match in _WORD.finditer(_fold(text)):
        key = match.group().casefold()
        words.append(_Word(key=_WORD_FORMS.get(key, key), raw=match.group()))
    return words


def _key(text: str) -> str:
    return " ".join(word.key for word in _words(text))


@lru_cache(maxsize=4)
def _index(country: str) -> _Index:
    by_name: dict[str, list[Place]] = {}
    division_names: dict[str, str] = {}
    prefix = f"{country}\t"
    with gzip.open(CITIES_FILE, "rt", encoding="utf-8") as rows:
        next(rows)
        for row in rows:
            if not row.startswith(prefix):
                continue
            _country, division, name, latitude, longitude, population = row.rstrip("\n").split("\t")
            place = Place(name, division, float(latitude), float(longitude), int(population))
            by_name.setdefault(_key(name), []).append(place)
            if division:
                division_names.setdefault(_key(division), division)
    codes = {
        code: division_names.get(_key(name), name)
        for code, name in DIVISION_CODES.get(country, {}).items()
    }
    for division in codes.values():
        division_names.setdefault(_key(division), division)
    cities = {
        name: tuple(sorted(places, key=lambda place: -place.population))
        for name, places in by_name.items()
    }
    for alias, name in _CITY_ALIASES.items():
        if name in cities:
            cities.setdefault(alias, cities[name])
    max_words = max((len(name.split()) for name in cities), default=1)
    return _Index(cities, division_names, codes, max_words)


def _division_spans(words: list[_Word], index: _Index) -> dict[tuple[int, int], str]:
    """Each named division by its word span, longest names first."""
    spans: dict[tuple[int, int], str] = {}
    start = 0
    while start < len(words):
        for length in range(min(4, len(words) - start), 0, -1):
            key = " ".join(word.key for word in words[start : start + length])
            division = index.division_names.get(key)
            raw = words[start].raw
            if division is None and length == 1 and len(raw) == 2 and raw.isupper():
                division = index.division_codes.get(raw)
            if division is not None:
                spans[(start, start + length)] = division
                start += length
                break
        else:
            start += 1
    return spans


def find_places(text: str, country: str) -> PlacesFound:
    """The cities and divisions of ``country`` that ``text`` names (see the module rules)."""
    index = _index(country)
    words = _words(text)
    division_spans = _division_spans(words, index)
    divisions = frozenset(division_spans.values())
    cities: list[Place] = []
    start = 0
    while start < len(words):
        for length in range(min(index.max_words, len(words) - start), 0, -1):
            span = (start, start + length)
            candidates = index.cities.get(" ".join(word.key for word in words[start : span[1]]))
            if not candidates:
                continue
            if span in division_spans:
                # A division's name is that division ("Liberty Lake, Washington") unless the
                # text names the city's division elsewhere ("Washington, DC", "New York, NY").
                others = frozenset(
                    division for other, division in division_spans.items() if other != span
                )
                place = _choose(candidates, others) if others else None
            else:
                place = _choose(candidates, divisions)
            if place is not None:
                if place not in cities:
                    cities.append(place)
                start += length
                break
        else:
            start += 1
    return PlacesFound(tuple(cities), divisions)


def _choose(candidates: tuple[Place, ...], divisions: frozenset[str]) -> Place | None:
    if divisions:
        return next((place for place in candidates if place.division in divisions), None)
    top = candidates[0]
    return top if top.population >= MIN_LONE_CITY_POPULATION else None


def division_named(text: str, country: str) -> str | None:
    """The division ``text`` is exactly, by name or code ("Texas", "TX"), else ``None``."""
    index = _index(country)
    stripped = text.strip()
    return index.division_names.get(_key(stripped)) or index.division_codes.get(stripped.upper())


def address_from_resume(resume_text: str, country: str) -> str | None:
    """ "City, ST 12345" from the first header line of a resume that names a city, else ``None``.

    Used when the AI resume reader finds no address. The state is written as its code where
    there is one, and the ZIP or postal code is kept when it is on the same line.
    """
    lines = [line for line in resume_text.splitlines() if line.strip()][:RESUME_HEADER_LINES]
    codes = {name: code for code, name in _index(country).division_codes.items()}
    for line in lines:
        cities = find_places(line, country).cities
        if not cities:
            continue
        # Addresses end "street, city, state": a street named like a town comes first.
        place = cities[-1]
        address = f"{place.name}, {codes.get(place.division, place.division)}"
        postal = _POSTAL_CODES.get(country)
        match = postal.search(line) if postal else None
        return f"{address} {match.group()}" if match else address
    return None


def home_place(address: str | None, country: str | None) -> Place | None:
    """The city of a home address: the last city named, as addresses end "City, ST 12345"."""
    if not address or not country:
        return None
    cities = find_places(address, country).cities
    return cities[-1] if cities else None
