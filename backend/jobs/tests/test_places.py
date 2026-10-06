"""Finding cities and states in free-text locations with the bundled GeoNames data."""

import pytest

from src.sources.places import address_from_resume, division_named, find_places, home_place


@pytest.mark.parametrize(
    ("text", "cities"),
    [
        ("El Segundo, California, United States", ["El Segundo, California"]),
        ("United States-Colorado-Colorado Springs", ["Colorado Springs, Colorado"]),
        ("USA.VA.Reston · United States of America", ["Reston, Virginia"]),
        ("US-AZ-TUCSON-805 ~ 1151 E Hermans Rd ~ BLDG 805", ["Tucson, Arizona"]),
        ("Ft. Collins, Colorado", ["Fort Collins, Colorado"]),
        ("St. Paul, MN", ["Saint Paul, Minnesota"]),
        ("New York, NY, USA", ["New York City, New York"]),
        ("New York City · New York · United States", ["New York City, New York"]),
        ("Washington, DC", ["Washington, District of Columbia"]),
        ("Liberty Lake, Washington", ["Liberty Lake, Washington"]),
        ("Houston, TX · Ann Arbor, Michigan", ["Houston, Texas", "Ann Arbor, Michigan"]),
        # A lone city counts only when it is large; a lone state is a state, not a city.
        ("San Francisco", ["San Francisco, California"]),
        ("Washington", []),
        ("Remote Massachusetts", []),
        ("United States of America", []),
    ],
)
def test_find_places_reads_common_location_formats(text: str, cities: list[str]) -> None:
    assert [place.label for place in find_places(text, "US").cities] == cities


def test_states_are_named_in_full_or_by_capitalised_code() -> None:
    assert find_places("Remote Massachusetts", "US").divisions == {"Massachusetts"}
    assert find_places("Chicago, IL", "US").divisions == {"Illinois"}
    # Lower-case two-letter words are ordinary words, not codes.
    assert find_places("work in or near me", "US").divisions == frozenset()
    assert division_named("tx", "US") == "Texas"
    assert division_named("Austin, TX", "US") is None


def test_home_place_takes_the_address_city_and_measures_miles() -> None:
    home = home_place("123 Main St, Austin, TX 78701", "US")
    round_rock = find_places("Round Rock, TX", "US").cities[0]

    assert home is not None and home.label == "Austin, Texas"
    assert 15 < home.miles_to(round_rock) < 20
    assert home_place("PO Box 12", "US") is None
    assert home_place(None, "US") is None


def test_other_countries_use_their_own_divisions() -> None:
    assert [place.label for place in find_places("Toronto, ON", "CA").cities] == [
        "Toronto, Ontario"
    ]
    assert [place.label for place in find_places("Montréal, QC", "CA").cities] == [
        "Montreal, Quebec"
    ]


@pytest.mark.parametrize(
    ("resume", "country", "address"),
    [
        ("Jane Doe\nSan Jose, CA 95112 | (408) 555-1234 | jane@x.com", "US", "San Jose, CA 95112"),
        ("Jane Doe\njane@x.com · 408-555-1234\nSan Jose, California", "US", "San Jose, CA"),
        ("Jane\n100 Lincoln Ave, Pflugerville, TX 78660-1234", "US", "Pflugerville, TX 78660-1234"),
        ("John\n12 King St W, Toronto, ON M5H 1A1", "CA", "Toronto, ON M5H 1A1"),
        ("Jane Doe\nNo location here", "US", None),
    ],
)
def test_address_from_resume_reads_the_header_city_state_and_postal_code(
    resume: str, country: str, address: str | None
) -> None:
    assert address_from_resume(resume, country) == address
