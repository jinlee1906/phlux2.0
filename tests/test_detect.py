"""Tests for catalyst/detect.py."""
from unittest.mock import MagicMock, patch

import pytest
import requests
from selenium.common.exceptions import TimeoutException, WebDriverException

from catalyst.detect import Detection, count_postings, detect_ats, fetch_page, fetch_rendered_page
from catalyst.models import ATS


class TestDetectAts:
    def test_greenhouse_api_call_pattern(self):
        html = """<script>$.ajax({url: 'https://boards-api.greenhouse.io/v1/boards/agilityrobotics/departments', ...})</script>"""
        detection = detect_ats(html)
        assert detection.ats is ATS.GREENHOUSE
        assert detection.ats_config == {"board_token": "agilityrobotics"}

    def test_greenhouse_embed_widget_pattern(self):
        # Real case: Sila Nanotechnologies. The token is a "?for=" query
        # param, not the literal path segment "embed".
        html = '<script src="https://boards.greenhouse.io/embed/job_board/js?for=silananotechnologies"></script>'
        detection = detect_ats(html)
        assert detection.ats is ATS.GREENHOUSE
        assert detection.ats_config == {"board_token": "silananotechnologies"}

    def test_greenhouse_board_link_pattern(self):
        html = '<a href="https://job-boards.greenhouse.io/solidpower">Careers</a>'
        detection = detect_ats(html)
        assert detection.ats is ATS.GREENHOUSE
        assert detection.ats_config == {"board_token": "solidpower"}

    def test_workday_cxs_pattern(self):
        html = 'fetch("https://airproducts.wd5.myworkdayjobs.com/wday/cxs/airproducts/AP0001/jobs")'
        detection = detect_ats(html)
        assert detection.ats is ATS.WORKDAY
        assert detection.ats_config == {"tenant": "airproducts", "wd_host": "wd5", "site": "AP0001"}

    def test_workday_board_link_pattern(self):
        html = '<a href="https://airproducts.wd5.myworkdayjobs.com/en-US/AP0001">Search Jobs</a>'
        detection = detect_ats(html)
        assert detection.ats is ATS.WORKDAY
        assert detection.ats_config == {"tenant": "airproducts", "wd_host": "wd5", "site": "AP0001"}

    def test_workday_board_link_with_no_locale_prefix(self):
        # Real case: Pfizer's link has no locale segment before the site name
        # ("PfizerCareers"), just a sub-path ("page/<job-id>") after it. The
        # optional locale group must not swallow "PfizerCareers" and capture
        # "page" as if it were the site.
        html = '<a href="https://pfizer.wd1.myworkdayjobs.com/PfizerCareers/page/61cd8c39">Job</a>'
        detection = detect_ats(html)
        assert detection.ats is ATS.WORKDAY
        assert detection.ats_config == {"tenant": "pfizer", "wd_host": "wd1", "site": "PfizerCareers"}

    def test_workday_board_link_locale_must_look_like_a_locale(self):
        # A locale-shaped segment ("en-US") is still consumed correctly.
        html = '<a href="https://amgen.wd1.myworkdayjobs.com/en-US/Careers">Jobs</a>'
        detection = detect_ats(html)
        assert detection.ats_config == {"tenant": "amgen", "wd_host": "wd1", "site": "Careers"}

    def test_workday_site_name_with_hyphen(self):
        # Real case: Xylem's site is "xylem-careers" — the site capture group
        # must allow hyphens or it truncates to "xylem".
        html = '<a href="https://xylem.wd5.myworkdayjobs.com/xylem-careers">Search Jobs</a>'
        detection = detect_ats(html)
        assert detection.ats_config == {"tenant": "xylem", "wd_host": "wd5", "site": "xylem-careers"}

    def test_lever_pattern(self):
        html = '<iframe src="https://jobs.lever.co/redwoodmaterials"></iframe>'
        detection = detect_ats(html)
        assert detection.ats is ATS.LEVER
        assert detection.ats_config == {"company": "redwoodmaterials"}

    def test_lever_api_pattern(self):
        html = 'fetch("https://api.lever.co/v0/postings/example?mode=json")'
        detection = detect_ats(html)
        assert detection.ats is ATS.LEVER
        assert detection.ats_config == {"company": "example"}

    def test_successfactors_career_link_with_company_param(self):
        html = '<a href="https://career5.successfactors.com/career?company=BASF">Jobs</a>'
        detection = detect_ats(html)
        assert detection.ats is ATS.SUCCESSFACTORS
        assert detection.ats_config == {"company": "BASF"}

    def test_successfactors_sfcareer_path(self):
        html = '<a href="https://career18.successfactors.com/sfcareer/jobreqcareer?company=Linde">Jobs</a>'
        detection = detect_ats(html)
        assert detection.ats is ATS.SUCCESSFACTORS
        assert detection.ats_config == {"company": "Linde"}

    def test_successfactors_bare_asset_reference_is_not_a_detection(self):
        # Real false positive: Colgate-Palmolive's page loads jQuery FROM a
        # successfactors.com subdomain — that's shared SAP platform
        # infrastructure, not proof Colgate's own career site uses it.
        html = (
            '<script src="https://performancemanager4.successfactors.com/'
            'verp/vmod_v1/ui/extlib/jquery_3.5.1/jquery.js"></script>'
        )
        assert detect_ats(html) is None

    def test_successfactors_cdn_asset_reference_is_not_a_detection(self):
        # Real false positive: Oak Ridge National Lab's page loads a CSS file
        # from a successfactors.com CDN subdomain — same problem.
        html = '<link rel="stylesheet" href="//rmkcdn.successfactors.com/bc9eb071/style.css" />'
        assert detect_ats(html) is None

    def test_ashby_is_not_a_recognized_detection(self):
        # Ashby isn't one of the brief's five ATSes — must not be returned as
        # a usable Detection even though it's recognized in the source.
        html = '<a href="https://jobs.ashbyhq.com/formenergy">Careers</a>'
        assert detect_ats(html) is None

    def test_no_match_returns_none(self):
        assert detect_ats("<html><body>Nothing here</body></html>") is None

    def test_prefers_greenhouse_over_later_patterns_when_multiple_present(self):
        html = (
            '<a href="https://job-boards.greenhouse.io/acme">Jobs</a>'
            '<a href="https://jobs.lever.co/other">Other</a>'
        )
        detection = detect_ats(html)
        assert detection.ats is ATS.GREENHOUSE


class TestFetchPage:
    def test_returns_text_on_success(self):
        mock_response = MagicMock(status_code=200, text="<html>ok</html>")
        with patch("catalyst.detect.requests.get", return_value=mock_response) as mock_get:
            result = fetch_page("https://example.com/careers")
        assert result == "<html>ok</html>"
        assert "User-Agent" in mock_get.call_args.kwargs["headers"]

    def test_returns_none_on_http_error_status(self):
        mock_response = MagicMock(status_code=403, text="blocked")
        with patch("catalyst.detect.requests.get", return_value=mock_response):
            assert fetch_page("https://example.com/careers") is None

    def test_returns_none_on_request_exception(self):
        with patch("catalyst.detect.requests.get", side_effect=requests.ConnectionError("boom")):
            assert fetch_page("https://example.com/careers") is None


class TestCountPostings:
    def test_greenhouse_uses_greenhouse_adapter(self):
        detection = Detection(ATS.GREENHOUSE, {"board_token": "acme"}, "evidence")
        with patch("catalyst.detect.GreenhouseAdapter") as mock_cls:
            mock_cls.return_value.fetch.return_value = [object(), object()]
            count = count_postings(detection)
        assert count == 2

    def test_workday_uses_workday_adapter(self):
        detection = Detection(ATS.WORKDAY, {"tenant": "acme", "wd_host": "wd5", "site": "External"}, "evidence")
        with patch("catalyst.detect.WorkdayAdapter") as mock_cls:
            mock_cls.return_value.fetch.return_value = [object()]
            count = count_postings(detection)
        assert count == 1

    def test_lever_uses_lever_adapter(self):
        detection = Detection(ATS.LEVER, {"company": "acme"}, "evidence")
        with patch("catalyst.detect.LeverAdapter") as mock_cls:
            mock_cls.return_value.fetch.return_value = [object(), object()]
            count = count_postings(detection)
        assert count == 2

    def test_successfactors_returns_none_no_adapter_yet(self):
        detection = Detection(ATS.SUCCESSFACTORS, {"company": "acme"}, "evidence")
        assert count_postings(detection) is None


class TestFetchRenderedPage:
    def test_returns_rendered_page_source(self):
        mock_driver = MagicMock()
        mock_driver.page_source = "<html>rendered</html>"
        with patch("catalyst.utils.get_driver", return_value=mock_driver), \
             patch("catalyst.detect.time.sleep"):
            result = fetch_rendered_page("https://example.com/careers")
        assert result == "<html>rendered</html>"
        mock_driver.get.assert_called_once_with("https://example.com/careers")
        mock_driver.quit.assert_called_once()

    def test_returns_none_when_driver_cannot_be_created(self):
        with patch("catalyst.utils.get_driver", side_effect=WebDriverException("no browser")):
            assert fetch_rendered_page("https://example.com/careers") is None

    def test_returns_none_on_page_load_timeout(self):
        mock_driver = MagicMock()
        mock_driver.get.side_effect = TimeoutException("timed out")
        with patch("catalyst.utils.get_driver", return_value=mock_driver):
            assert fetch_rendered_page("https://example.com/careers") is None
        mock_driver.quit.assert_called_once()

    def test_quits_driver_even_if_get_raises(self):
        mock_driver = MagicMock()
        mock_driver.get.side_effect = WebDriverException("boom")
        with patch("catalyst.utils.get_driver", return_value=mock_driver):
            fetch_rendered_page("https://example.com/careers")
        mock_driver.quit.assert_called_once()
