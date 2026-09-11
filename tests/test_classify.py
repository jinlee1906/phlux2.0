"""Tests for catalyst/classify.py."""
import math
from datetime import date, timedelta

import pytest

from catalyst.classify import (
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_WEIGHTS,
    classify,
    detect_level,
    extract_cohort,
    normalize_location,
)
from catalyst.models import Level, Posting, Sector


def _make_posting(title, location=None, first_seen=None, **overrides):
    defaults = dict(
        employer="Acme",
        title=title,
        url="https://acme.com/jobs/1",
        location=location,
        posted_date=None,
        first_seen=first_seen or date.today(),
        sector=Sector.SPECIALTY_CHEM,
        level=Level.UNKNOWN,
        score=0.0,
        tags=[],
        raw={},
    )
    defaults.update(overrides)
    return Posting(**defaults)


# ── detect_level ──────────────────────────────────────────────────────────────

class TestDetectLevel:
    def test_intern_is_internship(self):
        assert detect_level("Process Engineering Intern") is Level.INTERNSHIP

    def test_internship_is_internship(self):
        assert detect_level("Internship - Summer 2027") is Level.INTERNSHIP

    def test_summer_analyst_is_internship(self):
        assert detect_level("Process Summer Analyst") is Level.INTERNSHIP

    def test_shipping_coordinator_is_not_internship(self):
        # The upstream bug: substring-matching "ship" caught this.
        assert detect_level("Shipping Coordinator") is not Level.INTERNSHIP

    def test_membership_is_not_internship(self):
        assert detect_level("Membership Coordinator") is not Level.INTERNSHIP

    def test_relationship_manager_is_not_internship(self):
        assert detect_level("Relationship Manager") is not Level.INTERNSHIP

    def test_co_op_hyphenated_is_co_op(self):
        assert detect_level("Process Engineering Co-Op") is Level.CO_OP

    def test_coop_fused_is_co_op(self):
        assert detect_level("Process Engineering Coop") is Level.CO_OP

    def test_co_op_with_space_is_co_op(self):
        assert detect_level("Process Engineering Co Op") is Level.CO_OP

    def test_rotational_is_new_grad(self):
        assert detect_level("Rotational Engineer Program") is Level.NEW_GRAD

    def test_development_program_is_new_grad(self):
        assert detect_level("Chemical Engineering Development Program") is Level.NEW_GRAD

    def test_new_grad_phrase_is_new_grad(self):
        assert detect_level("Process Engineer - New Grad") is Level.NEW_GRAD

    def test_entry_level_is_new_grad(self):
        assert detect_level("Entry Level Process Engineer") is Level.NEW_GRAD

    def test_campus_is_new_grad(self):
        assert detect_level("Campus Hire - Process Engineer") is Level.NEW_GRAD

    def test_engineer_i_is_new_grad(self):
        assert detect_level("Process Engineer I") is Level.NEW_GRAD

    def test_engineer_ii_is_not_new_grad_via_engineer_i(self):
        # "Engineer I" must not match inside "Engineer II".
        assert detect_level("Process Engineer II") is not Level.NEW_GRAD

    def test_associate_engineer_is_new_grad(self):
        assert detect_level("Associate Engineer") is Level.NEW_GRAD

    def test_internship_wins_over_new_grad_when_both_present(self):
        assert detect_level("Rotational Engineering Internship") is Level.INTERNSHIP

    def test_co_op_wins_over_new_grad_when_both_present(self):
        assert detect_level("Engineering Co-Op - Rotational Program") is Level.CO_OP

    def test_experienced_default_for_no_signal(self):
        assert detect_level("Senior Process Engineer") is Level.EXPERIENCED

    def test_unknown_for_empty_title(self):
        assert detect_level("") is Level.UNKNOWN


# ── extract_cohort ────────────────────────────────────────────────────────────

class TestExtractCohort:
    def test_summer_year(self):
        assert extract_cohort("Process Engineering Intern - Summer 2027") == "Summer 2027"

    def test_spring_year(self):
        assert extract_cohort("Co-Op - Spring 2026") == "Spring 2026"

    def test_fall_year(self):
        assert extract_cohort("Fall 2026 Internship") == "Fall 2026"

    def test_case_insensitive(self):
        assert extract_cohort("summer 2027 intern") == "Summer 2027"

    def test_hyphenated_separator_still_matches(self):
        assert extract_cohort("Intern-Summer-2027") == "Summer 2027"

    def test_no_cohort_returns_none(self):
        assert extract_cohort("Process Engineer") is None

    def test_empty_title_returns_none(self):
        assert extract_cohort("") is None

    # ── non-adjacent season + plain calendar year ──────────────────────────────

    def test_non_adjacent_plain_year_in_parens(self):
        # Real Air Products title — season and year separated by other words.
        assert extract_cohort("Summer Intern-Finance, Corporate (2027)") == "Summer 2027"

    def test_non_adjacent_plain_year_no_parens(self):
        assert extract_cohort("Summer Co-op Chemical Engineering 2027 Class") == "Summer 2027"

    # ── FY-labeled year: requires a verified fiscal_year_end_month ─────────────

    def test_fy_year_without_fiscal_year_end_is_not_guessed(self):
        # No fiscal_year_end_month supplied — must not assume anything.
        assert extract_cohort("SUMMER CO-OP/INTERN – Chemical Engineering (FY 2027)") is None

    def test_fy_year_converts_when_fiscal_year_end_is_september_or_later(self):
        title = "SUMMER CO-OP/INTERN – Chemical Engineering (FY 2027)"
        assert extract_cohort(title, fiscal_year_end_month=9) == "Summer 2027"

    def test_fy_two_digit_year_converts(self):
        assert extract_cohort("Summer Intern (FY27)", fiscal_year_end_month=9) == "Summer 2027"

    def test_fy_year_not_converted_for_early_fiscal_close(self):
        # FYE in June: summer wouldn't reliably fall in the same-numbered FY.
        title = "Summer Co-op (FY 2027)"
        assert extract_cohort(title, fiscal_year_end_month=6) is None

    def test_fy_year_not_converted_for_non_summer_season(self):
        # Only the summer/Sept-or-later relationship has been verified.
        title = "Fall Co-op (FY 2027)"
        assert extract_cohort(title, fiscal_year_end_month=9) is None

    def test_plain_year_still_wins_when_no_fy_label_present(self):
        assert extract_cohort("Summer Intern (2027)", fiscal_year_end_month=9) == "Summer 2027"


# ── classify: taxonomy / scoring ──────────────────────────────────────────────

class TestClassifyScoring:
    def test_core_match_scores_positive(self):
        posting = _make_posting("Process Engineer")
        classify(posting)
        assert posting.score == 3.0
        assert posting.tags == ["process engineer"]

    def test_multiple_core_matches_add(self):
        posting = _make_posting("Chemical Engineer - Distillation Reactor Specialist")
        classify(posting)
        assert posting.score == 9.0  # chemical engineer + distillation + reactor

    def test_sector_match_scores_one(self):
        posting = _make_posting("Refinery Technician")
        classify(posting)
        assert posting.score == 1.0

    def test_veto_beats_core(self):
        # The brief's own example: must not pass on the word "process".
        posting = _make_posting("Software Engineer, Process Control")
        classify(posting)
        assert posting.score < 0

    def test_software_engineer_intern_scores_below_zero(self):
        posting = _make_posting("Software Engineer Intern")
        classify(posting)
        assert posting.score < 0

    def test_scale_up_matches_after_hyphen_normalization(self):
        posting = _make_posting("Scale-Up Engineer")
        classify(posting)
        assert "scale up" in posting.tags

    def test_unrelated_title_scores_zero(self):
        posting = _make_posting("Retail Store Manager")
        classify(posting)
        assert posting.score < 0  # veto match on "retail"

    def test_no_match_title_scores_zero_when_fresh(self):
        posting = _make_posting("Executive Assistant", first_seen=date.today())
        classify(posting)
        assert posting.score == 0.0


class TestGating:
    def test_bare_zinc_does_not_count(self):
        posting = _make_posting("Zinc Trading Analyst", first_seen=date.today())
        classify(posting)
        assert "zinc" not in posting.tags
        assert posting.score == 0.0

    def test_bare_lithium_does_not_count(self):
        posting = _make_posting("Lithium Logistics Coordinator", first_seen=date.today())
        classify(posting)
        assert "lithium" not in posting.tags

    def test_bare_battery_does_not_count(self):
        posting = _make_posting("Battery Sales Representative", first_seen=date.today())
        classify(posting)
        # "sales" is a veto match, "battery" should not additionally count.
        assert "battery" not in posting.tags

    def test_zinc_counts_with_a_co_occurring_match(self):
        posting = _make_posting("Zinc Electrode Process Engineer", first_seen=date.today())
        classify(posting)
        assert "zinc" in posting.tags

    def test_battery_counts_with_a_co_occurring_match(self):
        posting = _make_posting("Battery Cell Engineering Technician", first_seen=date.today())
        classify(posting)
        assert "battery" in posting.tags


class TestDecay:
    def test_no_decay_when_seen_today(self):
        posting = _make_posting("Process Engineer", first_seen=date.today())
        classify(posting)
        assert posting.score == 3.0

    def test_decay_reduces_score_over_time(self):
        posting = _make_posting("Process Engineer", first_seen=date.today() - timedelta(days=14))
        classify(posting)
        # One half-life at the default 14-day half-life: score should roughly halve.
        assert posting.score == pytest.approx(3.0 - math.log(2), abs=1e-9)

    def test_custom_half_life_changes_decay(self):
        posting = _make_posting("Process Engineer", first_seen=date.today() - timedelta(days=10))
        classify(posting, half_life_days=5)
        expected = 3.0 - (math.log(2) / 5) * 10
        assert posting.score == pytest.approx(expected, abs=1e-9)


class TestNormalizeLocation:
    def test_strips_hybrid_prefix(self):
        assert normalize_location("Hybrid- Fremont, CA") == "Fremont, CA"

    def test_leaves_bare_remote_alone(self):
        assert normalize_location("Remote") == "Remote"

    def test_leaves_already_abbreviated_state(self):
        assert normalize_location("Midland, MI") == "Midland, MI"

    def test_spells_out_state_converted_to_abbreviation(self):
        assert normalize_location("Bethlehem, Pennsylvania") == "Bethlehem, PA"

    def test_international_location_left_as_is(self):
        assert normalize_location("Duba, Saudi Arabia") == "Duba, Saudi Arabia"

    def test_none_returns_none(self):
        assert normalize_location(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_location("") is None

    def test_no_comma_no_state_returned_trimmed(self):
        assert normalize_location("  Pittsburgh  ") == "Pittsburgh"


class TestLocationBonus:
    def test_no_bonus_with_no_target_regions(self):
        posting = _make_posting("Process Engineer", location="Midland, MI", first_seen=date.today())
        classify(posting, target_regions=[])
        assert posting.score == 3.0

    def test_no_bonus_when_location_missing(self):
        posting = _make_posting("Process Engineer", location=None, first_seen=date.today())
        classify(posting, target_regions=["Pittsburgh"])
        assert posting.score == 3.0

    def test_state_level_region_matches_any_city_in_state(self):
        posting = _make_posting("Process Engineer", location="Midland, MI", first_seen=date.today())
        classify(posting, target_regions=["Michigan"])
        assert posting.score == 5.0

    def test_state_level_region_matches_spelled_out_state_name(self):
        posting = _make_posting("Process Engineer", location="Fremont, California", first_seen=date.today())
        classify(posting, target_regions=["California"])
        assert posting.score == 5.0

    def test_california_matches_abbreviated_form(self):
        posting = _make_posting("Process Engineer", location="Hybrid- Fremont, CA", first_seen=date.today())
        classify(posting, target_regions=["California"])
        assert posting.score == 5.0

    def test_california_does_not_false_positive_on_casablanca(self):
        posting = _make_posting("Process Engineer", location="Casablanca, Morocco", first_seen=date.today())
        classify(posting, target_regions=["California"])
        assert posting.score == 3.0  # no bonus — "CA" must not substring-match "Casablanca"

    def test_new_york_city_matches_nyc_location(self):
        posting = _make_posting("Process Engineer", location="New York, NY", first_seen=date.today())
        classify(posting, target_regions=["New York City"])
        assert posting.score == 5.0

    def test_new_york_city_does_not_match_rest_of_state(self):
        posting = _make_posting("Process Engineer", location="Buffalo, NY", first_seen=date.today())
        classify(posting, target_regions=["New York City"])
        assert posting.score == 3.0  # NYC is a city target, not the whole state

    def test_pittsburgh_matches(self):
        posting = _make_posting("Process Engineer", location="Pittsburgh, PA", first_seen=date.today())
        classify(posting, target_regions=["Pittsburgh"])
        assert posting.score == 5.0

    def test_pittsburgh_does_not_match_other_pa_cities(self):
        posting = _make_posting("Process Engineer", location="Bethlehem, PA", first_seen=date.today())
        classify(posting, target_regions=["Pittsburgh"])
        assert posting.score == 3.0

    def test_configured_default_regions_all_work_together(self):
        regions = ["New York City", "California", "Pittsburgh"]
        for location in ("New York, NY", "Fremont, CA", "Pittsburgh, PA"):
            posting = _make_posting("Process Engineer", location=location, first_seen=date.today())
            classify(posting, target_regions=regions)
            assert posting.score == 5.0, location

    def test_location_normalized_as_a_side_effect(self):
        posting = _make_posting("Process Engineer", location="Hybrid- Fremont, CA", first_seen=date.today())
        classify(posting, target_regions=[])
        assert posting.location == "Fremont, CA"


class TestClassifySetsLevelAndCohort:
    def test_sets_level(self):
        posting = _make_posting("Process Engineering Intern")
        classify(posting)
        assert posting.level is Level.INTERNSHIP

    def test_sets_cohort(self):
        posting = _make_posting("Process Engineering Intern - Summer 2027")
        classify(posting)
        assert posting.cohort == "Summer 2027"

    def test_cohort_none_when_absent(self):
        posting = _make_posting("Process Engineer")
        classify(posting)
        assert posting.cohort is None

    def test_returns_same_posting_instance(self):
        posting = _make_posting("Process Engineer")
        result = classify(posting)
        assert result is posting

    def test_fiscal_year_end_month_passed_through_to_cohort(self):
        posting = _make_posting("Summer Co-op – Chemical Engineering (FY 2027)")
        classify(posting, fiscal_year_end_month=9)
        assert posting.cohort == "Summer 2027"

    def test_fiscal_year_end_month_not_supplied_leaves_cohort_none(self):
        posting = _make_posting("Summer Co-op – Chemical Engineering (FY 2027)")
        classify(posting)
        assert posting.cohort is None


class TestWeightsOverride:
    def test_custom_weights_change_score(self):
        posting = _make_posting("Process Engineer", first_seen=date.today())
        classify(posting, weights={"core": 10})
        assert posting.score == 10.0

    def test_default_weights_unaffected_by_override(self):
        posting = _make_posting("Refinery Technician", first_seen=date.today())
        classify(posting, weights={"core": 10})
        assert posting.score == DEFAULT_WEIGHTS["sector"]
