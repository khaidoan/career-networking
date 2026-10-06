"""The free pre-LLM filters: titles, seniority from titles and bare-"Remote" postings."""

import pytest

from src.models import Preferences
from src.sources.filters import (
    SearchCriteria,
    bare_remote_allowed,
    location_matches,
    seniority_matches,
    title_matches,
    title_seniority_levels,
)

DESIRED = ("Software Engineer", "AI Engineer")
EXCLUDED = ("Test", "QA", "Security", "Site Reliability")


@pytest.mark.parametrize(
    ("title", "kept"),
    [
        ("Senior Software Engineer, Payments", True),
        ("Lead Engineer - AI Payments App", True),
        # Every word of an excluded entry, in any order and case: skipped.
        ("Software Development Engineer in Test (SDET)", False),
        ("Senior Software Engineer, qa Automation", False),
        ("Staff Software Security Engineer", False),
        ("Site Reliability Engineer, AI Observability", False),
        # Only part of a multi-word entry: kept. Excluded words never add a match.
        ("Reliability Engineer, AI Platform", True),
        ("Test Automation Lead", False),
    ],
)
def test_title_matches_skips_titles_with_an_excluded_entry(title: str, kept: bool) -> None:
    assert title_matches(title, DESIRED, EXCLUDED) is kept


def test_search_criteria_carry_the_excluded_title_words() -> None:
    preferences = Preferences(
        desired_titles=["Backend Engineer"], country="US", excluded_title_words=["QA", "  "]
    )

    criteria = SearchCriteria.from_preferences(preferences)

    assert criteria is not None and criteria.excluded_title_words == ("QA",)


@pytest.mark.parametrize(
    ("title", "levels"),
    [
        ("Senior Backend Engineer", {"senior"}),
        ("Sr. Data Scientist", {"senior"}),
        ("Software Engineering Intern", {"intern"}),
        ("Internal Tools Engineer", set()),
        ("Junior Developer", {"entry"}),
        ("Principal Engineer", {"staff_principal"}),
        ("Director of Engineering", {"director"}),
        ("VP, Engineering", {"vp_plus"}),
        ("Chief Technology Officer", {"vp_plus"}),
        ("MVP Product Engineer", set()),
        # Ambiguous words never name a level.
        ("Product Manager", set()),
        ("Staff Accountant", set()),
        ("Engineering Lead", set()),
        ("Head of Data", set()),
        ("Associate Consultant", set()),
        ("Software Engineer II", set()),
    ],
)
def test_title_seniority_levels_only_reads_unambiguous_words(title: str, levels: set[str]) -> None:
    assert title_seniority_levels(title) == levels


@pytest.mark.parametrize(
    ("title", "selected", "kept"),
    [
        ("Backend Engineer", ("senior",), True),  # no level named: the evaluator decides
        ("Product Manager", ("entry",), True),  # ambiguous: kept
        ("Senior Backend Engineer", (), True),  # no seniority selected: no filtering
        ("Principal Engineer", ("senior",), True),  # adjacent level: kept
        ("Senior Engineer", ("mid",), True),  # adjacent level: kept
        ("Director of Engineering", ("lead_manager",), True),  # adjacent level: kept
        ("Senior Director, Engineering", ("senior",), True),  # any matching word keeps it
        ("Software Engineering Intern", ("senior",), False),
        ("Junior Developer", ("senior", "staff_principal"), False),
        ("VP of Engineering", ("mid", "senior"), False),
        ("Senior Engineer", ("intern", "entry"), False),
        ("Junior Developer", ("senior", "entry"), True),  # one of several selections matches
    ],
)
def test_seniority_matches_drops_only_clear_mismatches(
    title: str, selected: tuple[str, ...], kept: bool
) -> None:
    assert seniority_matches(title, selected) is kept


def test_bare_remote_is_rejected_only_when_the_board_names_other_countries_but_never_ours() -> None:
    german_board = ["Berlin, Germany", "Munich, Germany", "Remote"]
    mixed_board = ["Berlin, Germany", "New York, NY", "Remote"]
    unknown_board = ["Remote", "Anywhere"]

    assert not bare_remote_allowed(german_board, "US")
    assert bare_remote_allowed(mixed_board, "US")
    assert bare_remote_allowed(unknown_board, "US")

    assert not location_matches("Remote", "US", allow_bare_remote=False)
    assert location_matches("Remote - US", "US", allow_bare_remote=False)
    assert not location_matches("Remote - Germany", "US")
