"""Tests for catalyst/adapters/selenium_adapter.py.

No live browser or network involved — ``get_driver`` and ``WebDriverWait``
are mocked throughout. The ``TestActions`` cases are carried over from the
pre-conversion ``phlux``/``catalyst`` test suite (recovered from git history
at commit ``0909128a^``) since the ``Actions`` class itself was ported
unchanged.
"""
from unittest.mock import MagicMock, call, patch

import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from catalyst.adapters.selenium_adapter import Actions, SeleniumAdapter
from catalyst.models import ATS, Employer, Sector


def _make_employer(**overrides):
    defaults = dict(
        name="Acme Corp",
        sector=Sector.SPECIALTY_CHEM,
        ats=ATS.SELENIUM,
        careers_url="https://acme.example.com/careers",
        ats_config={"urls": "https://acme.example.com/careers", "instructions": "CSS:.job-title"},
        hq_region=None,
    )
    defaults.update(overrides)
    return Employer(**defaults)


def _mock_element(text):
    el = MagicMock()
    el.text = text
    return el


# ── Actions ─────────────────────────────────────────────────────────────────

class TestActions:
    def test_get_type_css(self):
        assert Actions([]).get_type("CSS:.job-title") == "CSS"

    def test_get_type_click(self):
        assert Actions([]).get_type("CLICK:#load-more") == "CLICK"

    def test_get_type_filter(self):
        assert Actions([]).get_type("FILTER:intern") == "FILTER"

    def test_get_selector_basic(self):
        assert Actions([]).get_selector("CSS:.job-title") == ".job-title"

    def test_get_selector_filter_keyword(self):
        assert Actions([]).get_selector("FILTER:intern") == "intern"

    def test_get_selector_strips_pointer_flag(self):
        assert Actions([]).get_selector("CLICK:#btn:pointer") == "#btn"

    def test_has_flag_true(self):
        assert Actions([]).has_flag("CLICK:#btn:pointer", "pointer") is True

    def test_has_flag_false(self):
        assert Actions([]).has_flag("CLICK:#btn", "pointer") is False

    def test_is_iterable(self):
        actions = Actions(["CSS:.x", "CLICK:#y", "FILTER:intern"])
        assert list(actions) == ["CSS:.x", "CLICK:#y", "FILTER:intern"]

    def test_empty_actions_iterable(self):
        assert list(Actions([])) == []


# ── SeleniumAdapter ───────────────────────────────────────────────────────────

class TestSeleniumAdapter:
    @pytest.fixture(autouse=True)
    def _no_real_sleep(self):
        with patch("catalyst.adapters.selenium_adapter.time.sleep"):
            yield

    def test_incomplete_ats_config_missing_instructions_returns_empty(self):
        employer = _make_employer(ats_config={"urls": "https://acme.example.com"})
        assert SeleniumAdapter().fetch(employer) == []

    def test_incomplete_ats_config_missing_urls_returns_empty(self):
        employer = _make_employer(ats_config={"instructions": "CSS:.job-title"})
        assert SeleniumAdapter().fetch(employer) == []

    def test_css_action_extracts_titles(self):
        driver = MagicMock()
        driver.find_elements.return_value = [_mock_element("Process Engineer"), _mock_element("Plant Manager")]

        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = True
            postings = SeleniumAdapter().fetch(_make_employer())

        assert [p.title for p in postings] == ["Process Engineer", "Plant Manager"]
        driver.quit.assert_called_once()

    def test_posting_fields_use_careers_url_not_deep_link(self):
        driver = MagicMock()
        driver.find_elements.return_value = [_mock_element("Process Engineer")]

        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = True
            postings = SeleniumAdapter().fetch(_make_employer())

        posting = postings[0]
        assert posting.url == "https://acme.example.com/careers"
        assert posting.location is None
        assert posting.posted_date is None
        assert posting.employer == "Acme Corp"

    def test_nested_parent_child_css_selector(self):
        child = _mock_element("Reactor Operator")
        parent = MagicMock()
        parent.find_element.return_value = child
        driver = MagicMock()
        driver.find_elements.return_value = [parent]

        employer = _make_employer(ats_config={"urls": "https://acme.example.com", "instructions": "CSS:.job >> .title"})
        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = True
            postings = SeleniumAdapter().fetch(employer)

        assert [p.title for p in postings] == ["Reactor Operator"]

    def test_filter_action_keeps_only_matching_titles(self):
        driver = MagicMock()
        driver.find_elements.return_value = [
            _mock_element("Process Engineering Intern"),
            _mock_element("Senior Process Engineer"),
        ]

        employer = _make_employer(
            ats_config={"urls": "https://acme.example.com", "instructions": "CSS:.job-title->FILTER:intern"}
        )
        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = True
            postings = SeleniumAdapter().fetch(employer)

        assert [p.title for p in postings] == ["Process Engineering Intern"]

    def test_click_action_dispatches_click_then_continues_to_css(self):
        driver = MagicMock()
        driver.find_elements.return_value = [_mock_element("Plant Engineer")]

        employer = _make_employer(
            ats_config={"urls": "https://acme.example.com", "instructions": "CLICK:#load-more->CSS:.job-title"}
        )
        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = MagicMock()
            postings = SeleniumAdapter().fetch(employer)

        driver.execute_script.assert_called_once()
        assert [p.title for p in postings] == ["Plant Engineer"]

    def test_undetected_flag_requests_undetected_driver(self):
        driver = MagicMock()
        driver.find_elements.return_value = []

        employer = _make_employer(
            ats_config={"urls": "https://acme.example.com", "instructions": "UNDETECTED->CSS:.job-title"}
        )
        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver) as mock_get_driver, \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = True
            SeleniumAdapter().fetch(employer)

        mock_get_driver.assert_called_once_with(headless=True, use_undetected=True)

    def test_multiple_urls_visits_each(self):
        driver = MagicMock()
        driver.find_elements.return_value = []

        employer = _make_employer(
            ats_config={
                "urls": "https://acme.example.com/a->https://acme.example.com/b",
                "instructions": "CSS:.job-title",
            }
        )
        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = True
            SeleniumAdapter().fetch(employer)

        driver.get.assert_has_calls([call("https://acme.example.com/a"), call("https://acme.example.com/b")])

    def test_quoted_instructions_are_unwrapped(self):
        driver = MagicMock()
        driver.find_elements.return_value = [_mock_element("Engineer")]

        employer = _make_employer(ats_config={"urls": "https://acme.example.com", "instructions": '"CSS:.job-title"'})
        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = True
            postings = SeleniumAdapter().fetch(employer)

        assert [p.title for p in postings] == ["Engineer"]

    def test_timeout_for_one_url_is_caught_and_does_not_trigger_retry(self):
        # A per-page timeout is caught and logged per-URL (ported behavior)
        # -- it never escapes _scrape_titles, so the outer retry (reserved
        # for WebDriverException failures not scoped to a single page)
        # never fires. Only one driver session is created.
        driver = MagicMock()

        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.side_effect = TimeoutException("no such element")
            postings = SeleniumAdapter().fetch(_make_employer())

        assert postings == []
        driver.quit.assert_called_once()

    def test_driver_quit_called_even_on_failure(self):
        driver = MagicMock()

        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.side_effect = WebDriverException("crashed")
            SeleniumAdapter().fetch(_make_employer())

        assert driver.quit.call_count == 3  # one call per retry attempt

    def test_unrelated_exception_is_not_swallowed_by_fetch(self):
        # A bug in the DSL itself (e.g. a bad selector raising something
        # other than a WebDriver error) should surface, not be silently
        # eaten — only genuine WebDriver-level failures are caught.
        driver = MagicMock()
        driver.find_elements.side_effect = ValueError("boom")

        with patch("catalyst.adapters.selenium_adapter.get_driver", return_value=driver), \
             patch("catalyst.adapters.selenium_adapter.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = True
            with pytest.raises(ValueError):
                SeleniumAdapter().fetch(_make_employer())
