"""The relocation filter: excluded places and the commute limit."""

import pytest

from src.models import Preferences
from src.sources.relocation import RelocationRules, parse_excluded_places, relocation_rules


def _rules(**values: object) -> RelocationRules:
    preferences = Preferences(country="US", address="1 Congress Ave, Austin, TX 78701", **values)
    rules = relocation_rules(preferences)
    assert rules is not None
    return rules


def test_excluded_places_are_states_or_cities_and_unknown_entries_are_reported() -> None:
    excluded = parse_excluded_places(["California", "tx", "Seattle, WA", "Bay Area", " "], "US")

    assert excluded.divisions == {"California", "Texas"}
    assert [place.label for place in excluded.cities] == ["Seattle, Washington"]
    assert excluded.unrecognized == ("Bay Area",)


@pytest.mark.parametrize(
    ("location", "allowed"),
    [
        ("San Jose, CA", False),
        ("Seattle, Washington", False),
        ("Tacoma, WA", True),
        ("Denver, CO", True),
        # Remote, unplaceable, or one allowed office among several: kept.
        ("Remote - San Francisco, CA", True),
        ("Multiple Locations", True),
        ("San Jose, CA · Denver, CO", True),
        # States only: dropped when every state named is excluded.
        ("California · United States", False),
        ("California or Colorado", True),
    ],
)
def test_excluded_places_drop_postings_located_only_there(location: str, allowed: bool) -> None:
    rules = _rules(excluded_relocation_places=["California", "Seattle, WA"])

    assert rules.allows(location) is allowed


@pytest.mark.parametrize(
    ("location", "allowed"),
    [
        ("Round Rock, TX", True),  # about 17 miles
        ("San Antonio, TX", False),  # about 75 miles
        ("Remote, US", True),
        ("Texas", True),  # no city to measure; kept
    ],
)
def test_commute_limit_applies_only_when_not_willing_to_relocate(
    location: str, allowed: bool
) -> None:
    assert _rules(willing_to_relocate=False, max_commute_miles=30).allows(location) is allowed


def test_nothing_to_filter_means_no_rules() -> None:
    def rules(**values: object) -> RelocationRules | None:
        return relocation_rules(Preferences(country="US", address="Austin, TX", **values))

    assert rules() is None
    # Willing to relocate, or no limit saved: the commute limit is off.
    assert rules(willing_to_relocate=True, max_commute_miles=30) is None
    assert rules(willing_to_relocate=False) is None
    # No home city in the address: the commute limit cannot be measured.
    no_home = Preferences(
        country="US", address="PO Box 12", willing_to_relocate=False, max_commute_miles=30
    )
    assert relocation_rules(no_home) is None
