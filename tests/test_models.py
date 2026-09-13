from datetime import date

import pytest

from catalyst.models import (
    ATS,
    Employer,
    Level,
    Posting,
    Sector,
    normalize_title,
    posting_key,
)


# ── Employer ──────────────────────────────────────────────────────────────────

class TestEmployer:
    def _make(self, **overrides):
        defaults = dict(
            name="Dow",
            sector=Sector.SPECIALTY_CHEM,
            ats=ATS.WORKDAY,
            careers_url="https://corporate.dow.com/en-us/careers.html",
            ats_config={"tenant": "dow", "site": "External"},
            hq_region="Midland, MI",
        )
        defaults.update(overrides)
        return Employer(**defaults)

    def test_construction(self):
        employer = self._make()
        assert employer.name == "Dow"
        assert employer.sector is Sector.SPECIALTY_CHEM
        assert employer.ats is ATS.WORKDAY
        assert employer.enabled is True

    def test_enabled_defaults_true(self):
        assert self._make().enabled is True

    def test_hq_region_optional(self):
        employer = self._make(hq_region=None)
        assert employer.hq_region is None

    def test_is_frozen(self):
        employer = self._make()
        with pytest.raises(AttributeError):
            employer.name = "BASF"


# ── Posting ───────────────────────────────────────────────────────────────────

class TestPosting:
    def test_construction(self):
        posting = Posting(
            employer="Dow",
            title="Process Engineer",
            url="https://dow.com/jobs/123",
            location="Midland, MI",
            posted_date=date(2026, 1, 1),
            first_seen=date(2026, 1, 2),
            sector=Sector.SPECIALTY_CHEM,
            level=Level.EXPERIENCED,
            score=5.0,
            tags=["process engineer"],
            raw={"id": "123"},
        )
        assert posting.title == "Process Engineer"
        assert posting.score == 5.0
        assert posting.tags == ["process engineer"]

    def test_optional_fields_accept_none(self):
        posting = Posting(
            employer="Dow",
            title="Process Engineer",
            url=None,
            location=None,
            posted_date=None,
            first_seen=date(2026, 1, 2),
            sector=Sector.SPECIALTY_CHEM,
            level=Level.UNKNOWN,
            score=0.0,
            tags=[],
            raw={},
        )
        assert posting.url is None
        assert posting.posted_date is None

    def test_is_mutable(self):
        posting = Posting(
            employer="Dow",
            title="Process Engineer",
            url=None,
            location=None,
            posted_date=None,
            first_seen=date(2026, 1, 2),
            sector=Sector.SPECIALTY_CHEM,
            level=Level.UNKNOWN,
            score=0.0,
            tags=[],
            raw={},
        )
        posting.score = 3.0  # must not raise — scoring mutates in place
        assert posting.score == 3.0


# ── normalize_title ───────────────────────────────────────────────────────────

class TestNormalizeTitle:
    def test_lowercases(self):
        assert normalize_title("Process Engineer") == "process engineer"

    def test_collapses_whitespace(self):
        assert normalize_title("Process   Engineer\n") == "process engineer"

    def test_strips_dash_req_id(self):
        assert normalize_title("Process Engineer - R123456") == "process engineer"

    def test_strips_parenthetical_req_id(self):
        assert normalize_title("Process Engineer (Req 123456)") == "process engineer"

    def test_strips_hash_req_id(self):
        assert normalize_title("Process Engineer #123456") == "process engineer"

    def test_strips_dashed_numeric_id(self):
        assert normalize_title("Process Engineer - 24-00123") == "process engineer"

    def test_preserves_trailing_level_digit(self):
        # A short trailing number is a level, not a req ID — must survive.
        assert normalize_title("Process Engineer 2") == "process engineer 2"

    def test_preserves_engineer_numeral(self):
        assert normalize_title("Associate Engineer I") == "associate engineer i"

    def test_no_id_unchanged(self):
        assert normalize_title("Process Engineer") == "process engineer"

    def test_preserves_cohort_year(self):
        # A 4-digit year must not be mistaken for a req ID — otherwise
        # "Summer 2026" and "Summer 2027" postings would collide into the
        # same dedupe key.
        assert normalize_title("Process Engineer - Summer 2026") == "process engineer - summer 2026"

    def test_preserves_class_of_year(self):
        assert (
            normalize_title("Chemical Engineer Intern, Class of 2027")
            == "chemical engineer intern, class of 2027"
        )


# ── posting_key ───────────────────────────────────────────────────────────────

class TestPostingKey:
    def test_stable_for_same_input(self):
        a = posting_key("Dow", "Process Engineer", "Midland, MI")
        b = posting_key("Dow", "Process Engineer", "Midland, MI")
        assert a == b

    def test_case_insensitive(self):
        a = posting_key("Dow", "Process Engineer", "Midland, MI")
        b = posting_key("dow", "process engineer", "midland, mi")
        assert a == b

    def test_ignores_req_id_changes(self):
        a = posting_key("Dow", "Process Engineer - R123456", "Midland, MI")
        b = posting_key("Dow", "Process Engineer - R999999", "Midland, MI")
        assert a == b

    def test_differs_for_different_title(self):
        a = posting_key("Dow", "Process Engineer", "Midland, MI")
        b = posting_key("Dow", "Process Chemist", "Midland, MI")
        assert a != b

    def test_differs_for_different_location(self):
        a = posting_key("Dow", "Process Engineer", "Midland, MI")
        b = posting_key("Dow", "Process Engineer", "Freeport, TX")
        assert a != b

    def test_differs_for_different_employer(self):
        a = posting_key("Dow", "Process Engineer", "Midland, MI")
        b = posting_key("BASF", "Process Engineer", "Midland, MI")
        assert a != b

    def test_handles_none_location(self):
        key = posting_key("Dow", "Process Engineer", None)
        assert isinstance(key, str) and key
