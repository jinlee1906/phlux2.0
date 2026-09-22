"""Selenium fallback ATS adapter.

The fallback for job boards not covered by the Workday/Greenhouse/Lever JSON
adapters — iCIMS, Phenom, Ashby-less SPAs, and other bespoke in-house
portals whose job search only exists as a dynamic browser-rendered call.
See PROJECT_BRIEF.md Phase 3, item 5.

The ``Actions`` DSL and the scraping loop below are ported near-verbatim
from the pre-conversion ``phlux``/``catalyst`` scraping stack (recovered
from git history at commit ``0909128a^`` — it was deleted during the Phase 6
cleanup when the old CSS-selector-registry approach was superseded, then
resurrected here as the explicit fallback Phase 3 always called for). The
one intentional behavior change from the original: the retry is now scoped
to genuine WebDriver-level transient failures instead of retrying blindly
on any exception, matching the narrowing already applied to the Workday
adapter's retry after a live incident — see ``catalyst/adapters/workday.py``.

Known limitation, unlike the JSON adapters: this DSL only ever extracts
job TITLE text via CSS selectors — there is no per-posting deep link,
location, or posted date available from it. Every ``Posting`` this adapter
returns links back to the employer's careers page as a whole, not the
specific listing. Onboarding an employer here also means hand-writing a
CSS-selector action string against their live DOM — the same manual,
per-company process Phase 3's JSON adapters exist to move away from. Use
this only when a JSON adapter genuinely isn't available.
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import List

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from ..models import Employer, Level, Posting
from ..utils import get_driver

logger = logging.getLogger(__name__)

CSS = "CSS"
CLICK = "CLICK"
FILTER = "FILTER"
UNDETECTED = "UNDETECTED"
_ACTION_TYPES = {CSS, CLICK, FILTER, UNDETECTED}

_PAGE_LOAD_WAIT_SECONDS = 3
_ELEMENT_WAIT_SECONDS = 15
_CLICK_SETTLE_SECONDS = 2
_RETRY_WAIT_SECONDS = 5


class Actions:
    """Parses and iterates over a ``->``-delimited action string.

    Each action has the form ``TYPE:selector[:flag]``, e.g.
    ``CSS:.job-title``, ``CLICK:#load-more:pointer``, or simply
    ``UNDETECTED``.
    """

    def __init__(self, actions: List[str]) -> None:
        self.actions = actions

    def __iter__(self):
        return iter(self.actions)

    def get_type(self, action: str) -> str:
        """Return the action type (the part before the first ``:``)."""
        return action[: action.index(":")].strip()

    def get_selector(self, action: str) -> str:
        """Return the CSS/XPath selector, stripping any trailing ``:pointer`` flag."""
        raw = action[action.index(":") + 1 :].strip()
        return raw.replace(":pointer", "").strip()

    def has_flag(self, action: str, flag: str) -> bool:
        """Return True if *flag* is appended to *action*."""
        return f":{flag}" in action


@retry(
    # Scoped to WebDriver-level transient failures only, not any exception —
    # a bad selector or a real markup change would fail identically on
    # retry and shouldn't cost 3x the wait. See the module docstring.
    retry=retry_if_exception_type((TimeoutException, WebDriverException)),
    stop=stop_after_attempt(3),
    wait=wait_fixed(_RETRY_WAIT_SECONDS),
    reraise=True,
)
def _scrape_titles(urls: str, instructions: str, name: str) -> List[str]:
    """Run the Actions DSL against *urls* and return matched job titles.

    Args:
        name: Employer name (used for logging).
        urls: One or more career-page URLs separated by ``->``.
        instructions: Action string describing how to extract jobs.

    Returns:
        List of raw job title strings (whitespace-stripped, undecorated —
        level detection and any other classification happens downstream in
        ``catalyst.classify``, not here).
    """
    if instructions.startswith('"') and instructions.endswith('"'):
        instructions = instructions[1:-1]

    actions = Actions(instructions.split("->"))
    use_undetected = any(a.strip() == UNDETECTED for a in actions)
    driver = get_driver(headless=True, use_undetected=use_undetected)
    jobs: List[str] = []

    try:
        for url in urls.split("->"):
            try:
                driver.get(url.strip())
                time.sleep(_PAGE_LOAD_WAIT_SECONDS)

                for action in actions:
                    action = action.strip()
                    if action == UNDETECTED:
                        continue

                    if ":" not in action:
                        logger.warning("Invalid action format for %s: %s", name, action)
                        continue

                    action_type = actions.get_type(action)
                    selector = actions.get_selector(action)
                    use_pointer = actions.has_flag(action, "pointer")

                    if action_type not in _ACTION_TYPES:
                        logger.warning("Unknown action type '%s' for %s", action_type, name)
                        continue

                    if action_type == CSS:
                        if ">>" in selector:
                            parent_sel, child_sel = map(str.strip, selector.split(">>", 1))
                            WebDriverWait(driver, _ELEMENT_WAIT_SECONDS).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, parent_sel))
                            )
                            for parent in driver.find_elements(By.CSS_SELECTOR, parent_sel):
                                try:
                                    text = parent.find_element(By.CSS_SELECTOR, child_sel).text.strip()
                                    if text:
                                        jobs.append(text)
                                except Exception:
                                    continue
                        else:
                            WebDriverWait(driver, _ELEMENT_WAIT_SECONDS).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                            )
                            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                                text = el.text.strip()
                                if text:
                                    jobs.append(text)

                    elif action_type == CLICK:
                        try:
                            if selector.startswith("'") and selector.endswith("'"):
                                element = WebDriverWait(driver, _ELEMENT_WAIT_SECONDS).until(
                                    EC.presence_of_element_located((By.XPATH, selector[1:-1]))
                                )
                            else:
                                element = WebDriverWait(driver, _ELEMENT_WAIT_SECONDS).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                )
                            if use_pointer:
                                driver.execute_script(
                                    """
                                    const el = arguments[0];
                                    el.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                    """,
                                    element,
                                )
                            else:
                                driver.execute_script("arguments[0].click();", element)
                            time.sleep(_CLICK_SETTLE_SECONDS)
                        except Exception as exc:
                            logger.error("Failed clicking for %s: %s", name, exc)

                    elif action_type == FILTER:
                        jobs = [j for j in jobs if selector.lower() in j.lower()]

            except TimeoutException:
                logger.warning("Timeout for %s at %s", name, url)
                continue

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return jobs


class SeleniumAdapter:
    """Fallback adapter for job boards with no JSON API — runs a
    per-employer CSS-selector ``Actions`` DSL against a real headless
    browser.

    ``employer.ats_config`` must contain ``urls`` (one or more careers-page
    URLs, ``->``-delimited) and ``instructions`` (the DSL action string —
    see the ``Actions`` class above for syntax).
    """

    def fetch(self, employer: Employer) -> List[Posting]:
        urls = employer.ats_config.get("urls")
        instructions = employer.ats_config.get("instructions")
        if not urls or not instructions:
            logger.error("Incomplete Selenium ats_config for %s", employer.name)
            return []

        try:
            titles = _scrape_titles(urls, instructions, employer.name)
        except (TimeoutException, WebDriverException) as exc:
            logger.error("Selenium fetch failed for %s (after retry): %s", employer.name, exc)
            return []

        today = date.today()
        # No structured JSON payload to attach as `raw` here, unlike the
        # other adapters — the DSL only ever extracts title text.
        return [
            Posting(
                employer=employer.name,
                title=title,
                url=employer.careers_url,
                location=None,
                posted_date=None,
                first_seen=today,
                sector=employer.sector,
                level=Level.UNKNOWN,
                score=0.0,
                tags=[],
                raw={"title": title},
            )
            for title in titles
        ]
