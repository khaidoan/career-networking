"""The relocation filter: places the user will not move to, and their commute limit.

Built from the Profile page's relocation answers. A posting passes when it is remote, when its
location cannot be placed, or when at least one place it names is allowed:

- A place is not allowed when it, or its state, is on the user's list of places they will not
  relocate to.
- When the user is not willing to relocate and has a commute limit, a place must also be within
  that many miles of the city of their home address. Without a recognisable home city, the
  commute limit is not applied.
- A posting that names states but no city is dropped only when every state named is excluded.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from src.models import Preferences
from src.sources.locations import is_remote
from src.sources.places import Place, division_named, find_places, home_place


@dataclass(frozen=True)
class ExcludedPlaces:
    divisions: frozenset[str] = frozenset()
    cities: frozenset[Place] = frozenset()
    # Entries that name no known city or state; shown on the Profile page.
    unrecognized: tuple[str, ...] = ()


def parse_excluded_places(entries: Iterable[str], country: str) -> ExcludedPlaces:
    """Each entry is a state ("Texas", "TX") or a city ("Austin, TX", "Seattle")."""
    divisions: set[str] = set()
    cities: set[Place] = set()
    unrecognized: list[str] = []
    for entry in entries:
        if not entry.strip():
            continue
        division = division_named(entry, country)
        if division is not None:
            divisions.add(division)
            continue
        found = find_places(entry, country)
        if found.cities:
            cities.update(found.cities)
        elif found.divisions:
            divisions.update(found.divisions)
        else:
            unrecognized.append(entry.strip())
    return ExcludedPlaces(frozenset(divisions), frozenset(cities), tuple(unrecognized))


@dataclass(frozen=True)
class RelocationRules:
    country: str
    excluded: ExcludedPlaces = ExcludedPlaces()
    home: Place | None = None
    # Set only when it applies: not willing to relocate, a limit saved and a home city found.
    max_commute_miles: int | None = None

    def allows_place(self, place: Place) -> bool:
        if place.division in self.excluded.divisions or place in self.excluded.cities:
            return False
        if self.max_commute_miles is not None and self.home is not None:
            return self.home.miles_to(place) <= self.max_commute_miles
        return True

    def allows(self, location: str) -> bool:
        if is_remote(location or ""):
            return True
        found = find_places(location or "", self.country)
        if found.cities:
            return any(self.allows_place(place) for place in found.cities)
        return not (found.divisions and found.divisions <= self.excluded.divisions)


def relocation_rules(preferences: Preferences) -> RelocationRules | None:
    """The rules to apply, or ``None`` when the answers leave nothing to filter."""
    country = preferences.country
    if not country:
        return None
    excluded = parse_excluded_places(preferences.excluded_relocation_places or (), country)
    home = home_place(preferences.address, country)
    commute = None
    if preferences.willing_to_relocate is False and preferences.max_commute_miles and home:
        commute = preferences.max_commute_miles
    if not excluded.divisions and not excluded.cities and commute is None:
        return None
    return RelocationRules(country, excluded, home, commute)
