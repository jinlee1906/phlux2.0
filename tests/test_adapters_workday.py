"""Tests for catalyst/adapters/workday.py.

Uses recorded fixtures of real responses from Air Products's Workday CXS
API (tests/fixtures/workday_airproducts_page*.json) — never hits the live
endpoint.
"""
import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from catalyst.adapters.workday import WorkdayAdapter
from catalyst.models import ATS, Employer, Level, Sector

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name):
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _make_employer(**overrides):
    defaults = dict(
        name="Air Products",
        sector=Sector.SPECIALTY_CHEM,
        ats=ATS.WORKDAY,
        careers_url="https://www.airproducts.com/careers",
        ats_config={"tenant": "airproducts", "wd_host": "wd5", "site": "AP0001"},
        hq_region="Allentown, PA",
    )
    defaults.update(overrides)
    return Employer(**defaults)


def _mock_response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status_code} error")
    return response


def _patched_session(*payloads):
    """Patch requests.Session so session.post() yields *payloads* in order."""
    session = MagicMock()
    session.post.side_effect = [_mock_response(p) for p in payloads]
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return patch("catalyst.adapters.workday.requests.Session", return_value=session)


class TestWorkdayAdapter:
    def test_paginates_across_pages(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        page2 = _load_fixture("workday_airproducts_page2.json")
        empty_page = {"total": 0, "jobPostings": []}

        with _patched_session(page1, page2, empty_page):
            postings = WorkdayAdapter().fetch(_make_employer())

        assert len(postings) == 6
        titles = {p.title for p in postings}
        assert "Sr Contract Administrator" in titles
        assert "Senior Turbomachinery Design Engineer" in titles

    def test_stops_when_a_page_has_no_postings(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        empty_page = {"total": 0, "jobPostings": []}

        with _patched_session({"total": 3, "jobPostings": page1["jobPostings"]}, empty_page):
            postings = WorkdayAdapter().fetch(_make_employer())

        assert len(postings) == 3

    def test_uses_total_from_first_page_only(self):
        # First page claims total=3 (matches its own postings); a bogus
        # total=0 on a later page must NOT stop pagination early.
        job = {"title": "A", "externalPath": "/job/a", "locationsText": "X", "postedOn": "Posted Today"}
        page1 = {"total": 23, "jobPostings": [job] * 20}  # a full page; more remain
        page2 = {"total": 0, "jobPostings": [job] * 3}  # the real total's remainder

        with _patched_session(page1, page2):
            postings = WorkdayAdapter().fetch(_make_employer())

        assert len(postings) == 23  # 20 from page1 + 3 from page2, page2's total=0 ignored

    def test_builds_absolute_deep_link_from_external_path(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        with _patched_session(page1, {"total": 0, "jobPostings": []}):
            postings = WorkdayAdapter().fetch(_make_employer())

        first = postings[0]
        assert first.url == (
            "https://airproducts.wd5.myworkdayjobs.com/en-US/AP0001"
            "/job/Duba-Saudi-Arabia/Sr-Contract-Administrator_JR-2026-22165"
        )

    def test_parses_location(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        with _patched_session(page1, {"total": 0, "jobPostings": []}):
            postings = WorkdayAdapter().fetch(_make_employer())
        assert postings[0].location == "Duba, Saudi Arabia"

    def test_parses_posted_today(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        with _patched_session(page1, {"total": 0, "jobPostings": []}):
            postings = WorkdayAdapter().fetch(_make_employer())
        assert postings[0].posted_date == date.today()

    def test_parses_posted_days_ago(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        with _patched_session(page1, {"total": 0, "jobPostings": []}):
            postings = WorkdayAdapter().fetch(_make_employer())
        # "Posted 8 Days Ago"
        assert postings[1].posted_date == date.today() - timedelta(days=8)

    def test_parses_posted_yesterday(self):
        page = {
            "total": 1,
            "jobPostings": [
                {"title": "X", "externalPath": "/job/x", "locationsText": "Y", "postedOn": "Posted Yesterday"}
            ],
        }
        with _patched_session(page):
            postings = WorkdayAdapter().fetch(_make_employer())
        assert postings[0].posted_date == date.today() - timedelta(days=1)

    def test_parses_posted_30_plus_days_ago_as_floor(self):
        page2 = _load_fixture("workday_airproducts_page2.json")
        with _patched_session(page2, {"total": 0, "jobPostings": []}):
            postings = WorkdayAdapter().fetch(_make_employer())
        # "Posted 30+ Days Ago" — treated as a 30-day floor, not exact precision.
        assert postings[0].posted_date == date.today() - timedelta(days=30)

    def test_sets_employer_and_sector_from_employer(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        employer = _make_employer(name="Air Products", sector=Sector.SPECIALTY_CHEM)
        with _patched_session(page1, {"total": 0, "jobPostings": []}):
            postings = WorkdayAdapter().fetch(employer)
        assert all(p.employer == "Air Products" for p in postings)
        assert all(p.sector is Sector.SPECIALTY_CHEM for p in postings)

    def test_level_and_score_are_unclassified_placeholders(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        with _patched_session(page1, {"total": 0, "jobPostings": []}):
            postings = WorkdayAdapter().fetch(_make_employer())
        assert all(p.level is Level.UNKNOWN for p in postings)
        assert all(p.score == 0.0 for p in postings)
        assert all(p.tags == [] for p in postings)

    def test_raw_holds_untouched_payload(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        with _patched_session(page1, {"total": 0, "jobPostings": []}):
            postings = WorkdayAdapter().fetch(_make_employer())
        assert postings[0].raw == page1["jobPostings"][0]

    def test_incomplete_ats_config_returns_empty_without_request(self):
        with patch("catalyst.adapters.workday.requests.Session") as mock_session_cls:
            postings = WorkdayAdapter().fetch(_make_employer(ats_config={"tenant": "airproducts"}))
        assert postings == []
        mock_session_cls.assert_not_called()

    def test_http_error_degrades_to_empty_list(self):
        session = MagicMock()
        session.post.return_value = _mock_response({}, status_code=500)
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        with patch("catalyst.adapters.workday.requests.Session", return_value=session):
            postings = WorkdayAdapter().fetch(_make_employer())
        assert postings == []

    def test_connection_error_degrades_to_empty_list(self):
        session = MagicMock()
        session.post.side_effect = requests.ConnectionError("boom")
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        with patch("catalyst.adapters.workday.requests.Session", return_value=session):
            postings = WorkdayAdapter().fetch(_make_employer())
        assert postings == []

    def test_malformed_json_degrades_to_empty_list(self):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.side_effect = ValueError("not json")
        session = MagicMock()
        session.post.return_value = response
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        with patch("catalyst.adapters.workday.requests.Session", return_value=session):
            postings = WorkdayAdapter().fetch(_make_employer())
        assert postings == []

    def test_requests_correct_jobs_url(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        session = MagicMock()
        session.post.side_effect = [_mock_response(page1), _mock_response({"total": 0, "jobPostings": []})]
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        with patch("catalyst.adapters.workday.requests.Session", return_value=session):
            WorkdayAdapter().fetch(_make_employer())
        args, _ = session.post.call_args_list[0]
        assert args[0] == "https://airproducts.wd5.myworkdayjobs.com/wday/cxs/airproducts/AP0001/jobs"

    def test_requests_body_shape(self):
        page1 = _load_fixture("workday_airproducts_page1.json")
        session = MagicMock()
        session.post.side_effect = [_mock_response(page1), _mock_response({"total": 0, "jobPostings": []})]
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        with patch("catalyst.adapters.workday.requests.Session", return_value=session):
            WorkdayAdapter().fetch(_make_employer())
        _, kwargs = session.post.call_args_list[0]
        assert kwargs["json"] == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
