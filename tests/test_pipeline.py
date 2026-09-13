"""Tests for catalyst/pipeline.py."""
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from catalyst.models import ATS, Employer, Level, Posting, Sector, posting_key
from catalyst.pipeline import fetch_all, load_storage, run, save_storage


def _make_employer(**overrides):
    defaults = dict(
        name="Acme",
        sector=Sector.SPECIALTY_CHEM,
        ats=ATS.WORKDAY,
        careers_url="https://acme.com/careers",
        ats_config={"tenant": "acme", "wd_host": "wd1", "site": "External"},
        hq_region=None,
    )
    defaults.update(overrides)
    return Employer(**defaults)


def _make_posting(**overrides):
    defaults = dict(
        employer="Acme",
        title="Process Engineer",
        url="https://acme.com/jobs/1",
        location="Midland, MI",
        posted_date=None,
        first_seen=date.today(),
        sector=Sector.SPECIALTY_CHEM,
        level=Level.UNKNOWN,
        score=0.0,
        tags=[],
        raw={},
    )
    defaults.update(overrides)
    return Posting(**defaults)


class TestFetchAll:
    def test_fetches_only_enabled_employers(self):
        enabled = _make_employer(name="Enabled")
        disabled = _make_employer(name="Disabled", enabled=False)
        mock_adapter = MagicMock()
        mock_adapter.fetch.return_value = [_make_posting(employer="Enabled")]
        with patch("catalyst.pipeline._ADAPTERS", {ATS.WORKDAY: mock_adapter}):
            postings = fetch_all([enabled, disabled])
        assert len(postings) == 1
        mock_adapter.fetch.assert_called_once_with(enabled)

    def test_skips_employer_with_no_adapter(self):
        employer = _make_employer(ats=ATS.LEVER, ats_config={"company": "acme"})
        with patch("catalyst.pipeline._ADAPTERS", {}):
            postings = fetch_all([employer])
        assert postings == []

    def test_one_employer_failing_does_not_block_others(self):
        good = _make_employer(name="Good")
        bad = _make_employer(name="Bad")
        mock_adapter = MagicMock()

        def fetch_side_effect(employer):
            if employer.name == "Bad":
                raise RuntimeError("boom")
            return [_make_posting(employer="Good")]

        mock_adapter.fetch.side_effect = fetch_side_effect
        with patch("catalyst.pipeline._ADAPTERS", {ATS.WORKDAY: mock_adapter}):
            postings = fetch_all([good, bad])
        assert len(postings) == 1
        assert postings[0].employer == "Good"

    def test_aggregates_across_employers(self):
        e1 = _make_employer(name="E1")
        e2 = _make_employer(name="E2")
        mock_adapter = MagicMock()
        mock_adapter.fetch.side_effect = lambda e: [_make_posting(employer=e.name)]
        with patch("catalyst.pipeline._ADAPTERS", {ATS.WORKDAY: mock_adapter}):
            postings = fetch_all([e1, e2])
        assert {p.employer for p in postings} == {"E1", "E2"}


class TestStorage:
    def test_save_and_load_round_trip(self, tmp_path):
        path = tmp_path / "storage.json"
        data = {"abc123": {"employer": "Acme", "title": "X", "first_seen": "2026-01-01"}}
        save_storage(data, path)
        assert load_storage(path) == data

    def test_load_missing_file_returns_empty(self, tmp_path):
        assert load_storage(tmp_path / "nonexistent.json") == {}

    def test_load_corrupted_file_returns_empty(self, tmp_path):
        path = tmp_path / "storage.json"
        path.write_text("not valid json {{", encoding="utf-8")
        assert load_storage(path) == {}

    def test_load_empty_companies_style_file_returns_empty(self, tmp_path):
        # Old schema / freshly-truncated file — no "postings" key.
        path = tmp_path / "storage.json"
        path.write_text(json.dumps({"companies": {}}), encoding="utf-8")
        assert load_storage(path) == {}


class TestRun:
    def _run_with_postings(
        self, tmp_path, postings, *,
        scoring=None, target_regions=None, target_levels=None, target_countries=None,
        persist=True, today=None,
    ):
        scoring = scoring or {
            "half_life_days": 14,
            "min_score": 0.0,
            "weights": {"core": 3, "sector": 1, "veto": -5, "location": 2},
        }
        target_regions = target_regions if target_regions is not None else []
        target_levels = target_levels if target_levels is not None else ["INTERNSHIP", "CO_OP", "EXPERIENCED", "UNKNOWN"]
        target_countries = target_countries if target_countries is not None else ["US"]
        storage_path = tmp_path / "storage.json"
        with patch("catalyst.pipeline.fetch_all", return_value=postings), \
             patch("catalyst.pipeline.load_scoring_config", return_value=scoring), \
             patch("catalyst.pipeline.load_target_regions", return_value=target_regions), \
             patch("catalyst.pipeline.load_target_levels", return_value=target_levels), \
             patch("catalyst.pipeline.load_target_countries", return_value=target_countries):
            return run(employers=[], storage_path=storage_path, persist=persist, today=today)

    def test_new_posting_gets_todays_date_as_first_seen(self, tmp_path):
        today = date(2026, 6, 1)
        posting = _make_posting(title="Process Engineer", first_seen=today)
        result = self._run_with_postings(tmp_path, [posting], today=today)
        assert result.active[0].first_seen == today

    def test_previously_seen_posting_preserves_stored_first_seen(self, tmp_path):
        storage_path = tmp_path / "storage.json"
        old_first_seen = date(2026, 1, 1)
        posting = _make_posting(title="Process Engineer", location="Midland, MI")
        key = posting_key(posting.employer, posting.title, posting.location)
        save_storage({key: {"first_seen": old_first_seen.isoformat()}}, storage_path)

        today = date(2026, 1, 15)  # 14 days later = 1 half-life of decay
        fresh_posting = _make_posting(title="Process Engineer", location="Midland, MI", first_seen=today)
        result = self._run_with_postings(tmp_path, [fresh_posting], today=today)

        assert result.active[0].first_seen == old_first_seen
        assert result.active[0] not in result.new  # not new — already known

    def test_genuinely_new_posting_appears_in_new_and_active(self, tmp_path):
        posting = _make_posting(title="Process Engineer", first_seen=date.today())
        result = self._run_with_postings(tmp_path, [posting])
        assert len(result.new) == 1
        assert len(result.active) == 1

    def test_filters_out_below_min_score(self, tmp_path):
        posting = _make_posting(title="Retail Sales Associate")  # veto match, scores negative
        result = self._run_with_postings(tmp_path, [posting])
        assert result.active == []
        assert result.new == []

    def test_filters_by_target_level(self, tmp_path):
        posting = _make_posting(title="Senior Process Engineer")  # classifies as EXPERIENCED
        result = self._run_with_postings(tmp_path, [posting], target_levels=["INTERNSHIP", "CO_OP"])
        assert result.active == []

    def test_filters_by_target_country(self, tmp_path):
        posting = _make_posting(
            title="Process Engineer", location="IRL - Carlow - Carlow", first_seen=date.today()
        )
        result = self._run_with_postings(tmp_path, [posting], target_countries=["US"])
        assert result.active == []

    def test_ambiguous_location_not_excluded_by_country_filter(self, tmp_path):
        posting = _make_posting(title="Process Engineer", location="2 Locations", first_seen=date.today())
        result = self._run_with_postings(tmp_path, [posting], target_countries=["US"])
        assert len(result.active) == 1

    def test_active_sorted_by_score_descending(self, tmp_path):
        low = _make_posting(title="Refinery Technician", first_seen=date.today())  # sector match, score 1
        high = _make_posting(title="Process Engineer", first_seen=date.today())  # core match, score 3
        result = self._run_with_postings(tmp_path, [low, high])
        assert [p.score for p in result.active] == sorted((p.score for p in result.active), reverse=True)

    def test_persist_false_does_not_write_storage(self, tmp_path):
        posting = _make_posting(first_seen=date.today())
        storage_path = tmp_path / "storage.json"
        self._run_with_postings(tmp_path, [posting], persist=False)
        assert not storage_path.exists()

    def test_persist_true_writes_storage(self, tmp_path):
        posting = _make_posting(first_seen=date.today())
        storage_path = tmp_path / "storage.json"
        self._run_with_postings(tmp_path, [posting], persist=True)
        assert storage_path.exists()
        stored = load_storage(storage_path)
        assert len(stored) == 1

    def test_persisted_storage_includes_postings_that_fail_filters(self, tmp_path):
        # Storage should track everything fetched (for accurate first_seen next
        # run), not just what currently passes the score/level filter.
        posting = _make_posting(title="Retail Sales Associate", first_seen=date.today())
        storage_path = tmp_path / "storage.json"
        self._run_with_postings(tmp_path, [posting], persist=True)
        assert len(load_storage(storage_path)) == 1

    def test_posting_with_normalizable_location_is_still_recognized_as_new(self, tmp_path):
        # Regression: classify() mutates posting.location via
        # normalize_location() ("Hybrid- Fremont, CA" -> "Fremont, CA"). The
        # dedupe key must be computed once, before that mutation — otherwise
        # a genuinely new posting silently drops out of `new` because the
        # key recomputed after classify() no longer matches.
        posting = _make_posting(
            title="Process Engineer", location="Hybrid- Fremont, CA", first_seen=date.today()
        )
        result = self._run_with_postings(tmp_path, [posting])
        assert len(result.new) == 1
        assert len(result.active) == 1

    def test_posting_with_normalizable_location_dedupes_on_second_run(self, tmp_path):
        # Same regression, checked the way it would actually bite: run once
        # (persisted), then run again with an identically-shaped fresh
        # posting (as a real re-fetch would produce) — it must NOT show up
        # as new the second time.
        storage_path = tmp_path / "storage.json"
        first = _make_posting(
            title="Process Engineer", location="Hybrid- Fremont, CA", first_seen=date.today()
        )
        self._run_with_postings(tmp_path, [first], persist=True)

        second = _make_posting(
            title="Process Engineer", location="Hybrid- Fremont, CA", first_seen=date.today()
        )
        with patch("catalyst.pipeline.fetch_all", return_value=[second]), \
             patch("catalyst.pipeline.load_scoring_config", return_value={
                 "half_life_days": 14, "min_score": 0.0,
                 "weights": {"core": 3, "sector": 1, "veto": -5, "location": 2},
             }), \
             patch("catalyst.pipeline.load_target_regions", return_value=[]), \
             patch("catalyst.pipeline.load_target_levels", return_value=["EXPERIENCED"]), \
             patch("catalyst.pipeline.load_target_countries", return_value=["US"]):
            result = run(employers=[], storage_path=storage_path, persist=True)

        assert result.new == []
        assert len(result.active) == 1
