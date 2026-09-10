"""Tests for catalyst/adapters/greenhouse.py.

Uses a recorded fixture of a real response from Agility Robotics's
Greenhouse board (tests/fixtures/greenhouse_agilityrobotics.json) —
never hits the live endpoint.
"""
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from catalyst.adapters.greenhouse import GreenhouseAdapter
from catalyst.models import ATS, Employer, Level, Sector

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "greenhouse_agilityrobotics.json"


def _load_fixture():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _make_employer(**overrides):
    defaults = dict(
        name="Agility Robotics",
        sector=Sector.ROBOTICS,
        ats=ATS.GREENHOUSE,
        careers_url="https://www.agilityrobotics.com/careers",
        ats_config={"board_token": "agilityrobotics"},
        hq_region="Corvallis, OR",
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


class TestGreenhouseAdapter:
    def test_returns_a_posting_per_job(self):
        with patch("catalyst.adapters.greenhouse.requests.get", return_value=_mock_response(_load_fixture())):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert len(postings) == 2

    def test_parses_title_and_url(self):
        with patch("catalyst.adapters.greenhouse.requests.get", return_value=_mock_response(_load_fixture())):
            postings = GreenhouseAdapter().fetch(_make_employer())
        first = postings[0]
        assert first.title == "Accountant III"
        assert first.url == "https://www.agilityrobotics.com/about/job-post?gh_jid=5986011004"

    def test_parses_location(self):
        with patch("catalyst.adapters.greenhouse.requests.get", return_value=_mock_response(_load_fixture())):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert postings[0].location == "Hybrid- Fremont, CA"
        assert postings[1].location == "Remote"

    def test_parses_posted_date_from_first_published(self):
        with patch("catalyst.adapters.greenhouse.requests.get", return_value=_mock_response(_load_fixture())):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert postings[0].posted_date == date(2026, 5, 1)

    def test_sets_employer_and_sector_from_employer(self):
        employer = _make_employer(name="Agility Robotics", sector=Sector.ROBOTICS)
        with patch("catalyst.adapters.greenhouse.requests.get", return_value=_mock_response(_load_fixture())):
            postings = GreenhouseAdapter().fetch(employer)
        assert all(p.employer == "Agility Robotics" for p in postings)
        assert all(p.sector is Sector.ROBOTICS for p in postings)

    def test_level_and_score_are_unclassified_placeholders(self):
        with patch("catalyst.adapters.greenhouse.requests.get", return_value=_mock_response(_load_fixture())):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert all(p.level is Level.UNKNOWN for p in postings)
        assert all(p.score == 0.0 for p in postings)
        assert all(p.tags == [] for p in postings)

    def test_raw_holds_untouched_payload(self):
        fixture = _load_fixture()
        with patch("catalyst.adapters.greenhouse.requests.get", return_value=_mock_response(fixture)):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert postings[0].raw == fixture["jobs"][0]

    def test_missing_board_token_returns_empty_without_request(self):
        with patch("catalyst.adapters.greenhouse.requests.get") as mock_get:
            postings = GreenhouseAdapter().fetch(_make_employer(ats_config={}))
        assert postings == []
        mock_get.assert_not_called()

    def test_http_error_degrades_to_empty_list(self):
        with patch(
            "catalyst.adapters.greenhouse.requests.get",
            return_value=_mock_response({}, status_code=404),
        ):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert postings == []

    def test_connection_error_degrades_to_empty_list(self):
        with patch(
            "catalyst.adapters.greenhouse.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert postings == []

    def test_malformed_json_degrades_to_empty_list(self):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.side_effect = ValueError("not json")
        with patch("catalyst.adapters.greenhouse.requests.get", return_value=response):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert postings == []

    def test_empty_jobs_list_returns_empty(self):
        with patch(
            "catalyst.adapters.greenhouse.requests.get",
            return_value=_mock_response({"jobs": [], "meta": {"total": 0}}),
        ):
            postings = GreenhouseAdapter().fetch(_make_employer())
        assert postings == []

    def test_requests_content_true(self):
        mock_get = MagicMock(return_value=_mock_response(_load_fixture()))
        with patch("catalyst.adapters.greenhouse.requests.get", mock_get):
            GreenhouseAdapter().fetch(_make_employer())
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"content": "true"}

    def test_requests_correct_board_url(self):
        mock_get = MagicMock(return_value=_mock_response(_load_fixture()))
        with patch("catalyst.adapters.greenhouse.requests.get", mock_get):
            GreenhouseAdapter().fetch(_make_employer())
        args, _ = mock_get.call_args
        assert args[0] == "https://boards-api.greenhouse.io/v1/boards/agilityrobotics/jobs"
