"""Tests for catalyst/adapters/lever.py.

Uses a recorded fixture of a real response from Shield AI's Lever board
(tests/fixtures/lever_shieldai.json) — never hits the live endpoint.
"""
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from catalyst.adapters.lever import LeverAdapter
from catalyst.models import ATS, Employer, Level, Sector

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "lever_shieldai.json"


def _load_fixture():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _make_employer(**overrides):
    defaults = dict(
        name="Shield AI",
        sector=Sector.AEROSPACE,
        ats=ATS.LEVER,
        careers_url="https://shield.ai/careers/",
        ats_config={"company": "shieldai"},
        hq_region="San Diego, CA",
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


class TestLeverAdapter:
    def test_returns_a_posting_per_job(self):
        with patch("catalyst.adapters.lever.requests.get", return_value=_mock_response(_load_fixture())):
            postings = LeverAdapter().fetch(_make_employer())
        assert len(postings) == 2

    def test_parses_title_and_url(self):
        with patch("catalyst.adapters.lever.requests.get", return_value=_mock_response(_load_fixture())):
            postings = LeverAdapter().fetch(_make_employer())
        first = postings[0]
        assert first.title == "Aerodynamics & Performance Engineer (R5732)"
        assert first.url == "https://jobs.lever.co/shieldai/938a7ddf-521f-4581-b5ba-c3ba29f9308a"

    def test_parses_location(self):
        with patch("catalyst.adapters.lever.requests.get", return_value=_mock_response(_load_fixture())):
            postings = LeverAdapter().fetch(_make_employer())
        assert postings[0].location == "Dallas, Texas"
        assert postings[1].location == "Seattle, Washington"

    def test_parses_posted_date_from_created_at(self):
        with patch("catalyst.adapters.lever.requests.get", return_value=_mock_response(_load_fixture())):
            postings = LeverAdapter().fetch(_make_employer())
        assert postings[0].posted_date == date(2026, 8, 26)
        assert postings[1].posted_date == date(2026, 5, 27)

    def test_sets_employer_and_sector_from_employer(self):
        employer = _make_employer(name="Shield AI", sector=Sector.AEROSPACE)
        with patch("catalyst.adapters.lever.requests.get", return_value=_mock_response(_load_fixture())):
            postings = LeverAdapter().fetch(employer)
        assert all(p.employer == "Shield AI" for p in postings)
        assert all(p.sector is Sector.AEROSPACE for p in postings)

    def test_level_and_score_are_unclassified_placeholders(self):
        with patch("catalyst.adapters.lever.requests.get", return_value=_mock_response(_load_fixture())):
            postings = LeverAdapter().fetch(_make_employer())
        assert all(p.level is Level.UNKNOWN for p in postings)
        assert all(p.score == 0.0 for p in postings)
        assert all(p.tags == [] for p in postings)

    def test_raw_holds_untouched_payload(self):
        fixture = _load_fixture()
        with patch("catalyst.adapters.lever.requests.get", return_value=_mock_response(fixture)):
            postings = LeverAdapter().fetch(_make_employer())
        assert postings[0].raw == fixture[0]

    def test_missing_company_returns_empty_without_request(self):
        with patch("catalyst.adapters.lever.requests.get") as mock_get:
            postings = LeverAdapter().fetch(_make_employer(ats_config={}))
        assert postings == []
        mock_get.assert_not_called()

    def test_http_error_degrades_to_empty_list(self):
        with patch(
            "catalyst.adapters.lever.requests.get",
            return_value=_mock_response({}, status_code=404),
        ):
            postings = LeverAdapter().fetch(_make_employer())
        assert postings == []

    def test_connection_error_degrades_to_empty_list(self):
        with patch(
            "catalyst.adapters.lever.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            postings = LeverAdapter().fetch(_make_employer())
        assert postings == []

    def test_malformed_json_degrades_to_empty_list(self):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.side_effect = ValueError("not json")
        with patch("catalyst.adapters.lever.requests.get", return_value=response):
            postings = LeverAdapter().fetch(_make_employer())
        assert postings == []

    def test_non_list_response_degrades_to_empty_list(self):
        with patch(
            "catalyst.adapters.lever.requests.get",
            return_value=_mock_response({"ok": False, "error": "Document not found"}),
        ):
            postings = LeverAdapter().fetch(_make_employer())
        assert postings == []

    def test_empty_jobs_list_returns_empty(self):
        with patch("catalyst.adapters.lever.requests.get", return_value=_mock_response([])):
            postings = LeverAdapter().fetch(_make_employer())
        assert postings == []

    def test_requests_mode_json(self):
        mock_get = MagicMock(return_value=_mock_response(_load_fixture()))
        with patch("catalyst.adapters.lever.requests.get", mock_get):
            LeverAdapter().fetch(_make_employer())
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"mode": "json"}

    def test_requests_correct_postings_url(self):
        mock_get = MagicMock(return_value=_mock_response(_load_fixture()))
        with patch("catalyst.adapters.lever.requests.get", mock_get):
            LeverAdapter().fetch(_make_employer())
        args, _ = mock_get.call_args
        assert args[0] == "https://api.lever.co/v0/postings/shieldai"
