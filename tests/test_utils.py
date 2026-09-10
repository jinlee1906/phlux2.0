"""Tests for catalyst/utils.py."""
from catalyst.utils import is_full_time, is_internship


# ── is_internship / is_full_time ──────────────────────────────────────────────

class TestIsInternship:
    def test_matches_intern_substring(self):
        assert is_internship("Software Engineer Intern") is True

    def test_matches_internship_full_word(self):
        assert is_internship("internship program") is True

    def test_matches_ship_as_substring_of_internship(self):
        # "ship" is a substring of "internship" — intentional keyword
        assert is_internship("Internship Summer 2026") is True

    def test_matches_coop_with_hyphen(self):
        assert is_internship("Co-op Position") is True

    def test_matches_coop_no_hyphen(self):
        assert is_internship("Coop Rotation") is True

    def test_matches_coop_with_space(self):
        assert is_internship("Co Op Role") is True

    def test_case_insensitive(self):
        assert is_internship("INTERN") is True

    def test_false_for_fulltime_role(self):
        assert is_internship("Software Engineer") is False

    def test_false_for_senior_manager(self):
        assert is_internship("Senior Manager") is False


class TestIsFullTime:
    def test_is_exact_negation_of_is_internship(self):
        titles = [
            "Software Engineer",
            "Software Engineer Intern",
            "Co-op Role",
            "Manager",
            "Internship Program",
        ]
        for title in titles:
            assert is_full_time(title) == (not is_internship(title)), title

    def test_true_for_regular_role(self):
        assert is_full_time("Data Scientist") is True

    def test_false_for_intern_role(self):
        assert is_full_time("Software Engineer Intern") is False
