"""Auto-detect which ATS an employer's careers page actually uses.

Never guesses a tenant/board token — only recognizes patterns that appear
literally in the page's own HTML (a script src, an embedded API call, a link
href). See CLAUDE.md's verification rule and PROJECT_BRIEF.md Phase 3's
history: brute-forcing candidate tokens against an ATS's API is explicitly
disallowed, even for "just checking."
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

import requests
from selenium.common.exceptions import TimeoutException, WebDriverException

from .adapters.greenhouse import GreenhouseAdapter
from .adapters.workday import WorkdayAdapter
from .models import ATS, Employer, Sector

# A browser UA, not a descriptive bot UA: this is a one-time research fetch
# of a public marketing page (equivalent to opening it in a browser), not
# part of the recurring production scrape — and several employer sites
# (confirmed: Air Products) 403 any non-browser UA outright, descriptive or
# not. The adapters that do the actual recurring scraping hit each ATS's own
# JSON API directly, which doesn't gate on User-Agent.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_TIMEOUT_SECONDS = 20

_GREENHOUSE_API_RE = re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9_-]+)", re.IGNORECASE)
# The embed-widget script (e.g. Sila Nanotechnologies) carries the real token
# as a "?for=" query param, not a path segment — must be checked before the
# generic board-link pattern below, which would otherwise wrongly capture
# the literal word "embed" from ".../embed/job_board/js?for=<token>".
_GREENHOUSE_EMBED_RE = re.compile(r"boards\.greenhouse\.io/embed/job_board/js\?for=([a-z0-9_-]+)", re.IGNORECASE)
_GREENHOUSE_BOARD_RE = re.compile(r"(?:job-boards|boards)\.greenhouse\.io/([a-z0-9_-]+)", re.IGNORECASE)
# The optional locale segment must look like an actual locale ("en-US"), not
# any old word — otherwise, for a tenant with no locale prefix at all (e.g.
# Pfizer's ".../PfizerCareers/page/<job-id>"), this group would greedily
# swallow the real site name ("PfizerCareers") and capture a sub-path
# segment ("page") as if it were the site instead.
_WORKDAY_BOARD_RE = re.compile(
    r"([a-z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-z]{2}-[a-z]{2})?/([A-Za-z0-9_-]+)", re.IGNORECASE
)
_WORKDAY_CXS_RE = re.compile(
    r"([a-z0-9_-]+)\.(wd\d+)\.myworkdayjobs\.com/wday/cxs/[a-z0-9_-]+/([A-Za-z0-9_-]+)/jobs", re.IGNORECASE
)
_LEVER_BOARD_RE = re.compile(r"jobs\.lever\.co/([a-z0-9_.-]+)", re.IGNORECASE)
_LEVER_API_RE = re.compile(r"api\.lever\.co/v0/postings/([a-z0-9_.-]+)", re.IGNORECASE)
# SuccessFactors applicant-facing career links look like
# ".../career?company=<tenant>" (the subdomain, e.g. "career5" or
# "performancemanager4", is a shared numbered SAP instance, NOT the
# employer's tenant). A bare "*.successfactors.com" reference with no
# "/career" path and no "company=" param is just shared platform
# infrastructure (an asset CDN, a jQuery include, a login widget) —
# confirmed false positives on exactly this for both Colgate-Palmolive and
# Oak Ridge National Laboratory, both loading unrelated static assets from
# a successfactors.com subdomain. Require both signals together.
_SUCCESSFACTORS_RE = re.compile(
    r"successfactors\.com/(?:career|sfcareer)[^\"'\s]*[?&]company=([a-zA-Z0-9_-]+)", re.IGNORECASE
)
_ASHBY_RE = re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_.-]+)", re.IGNORECASE)


@dataclass
class Detection:
    ats: ATS
    ats_config: dict
    evidence: str  # the literal matched substring — always double-check this by eye


def fetch_page(url: str) -> Optional[str]:
    """Fetch *url*'s HTML, or None if it can't be fetched (bot-blocked, 404, etc.)."""
    try:
        response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None
    if response.status_code >= 400:
        return None
    return response.text


_RENDER_PAGE_LOAD_TIMEOUT_SECONDS = 30


def fetch_rendered_page(url: str, wait_seconds: float = 4.0) -> Optional[str]:
    """Fetch *url* with a real headless browser, executing JS, and return the
    rendered HTML — or None if it can't be loaded.

    For a job board whose ATS reference only appears after client-side
    rendering (invisible to fetch_page's plain HTTP GET). This still doesn't
    guess anything: detect_ats() runs the same literal-evidence patterns
    against whatever HTML comes back.
    """
    from .utils import get_driver  # local import: avoids a hard Selenium dependency for callers that only use fetch_page

    try:
        driver = get_driver(headless=True)
    except WebDriverException:
        return None

    try:
        driver.set_page_load_timeout(_RENDER_PAGE_LOAD_TIMEOUT_SECONDS)
        driver.get(url)
        time.sleep(wait_seconds)
        return driver.page_source
    except (TimeoutException, WebDriverException):
        return None
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def detect_ats(html: str) -> Optional[Detection]:
    """Find a literal ATS reference in *html*. Returns None if none is found.

    Checks the two ATSes with working adapters first (Greenhouse, Workday),
    then Lever/SuccessFactors/Ashby, which are detected but may not be fully
    verifiable without an adapter — see count_postings().
    """
    match = (
        _GREENHOUSE_API_RE.search(html)
        or _GREENHOUSE_EMBED_RE.search(html)
        or _GREENHOUSE_BOARD_RE.search(html)
    )
    if match:
        return Detection(ATS.GREENHOUSE, {"board_token": match.group(1)}, match.group(0))

    match = _WORKDAY_CXS_RE.search(html)
    if match:
        tenant, wd_host, site = match.groups()
        return Detection(ATS.WORKDAY, {"tenant": tenant, "wd_host": wd_host, "site": site}, match.group(0))
    match = _WORKDAY_BOARD_RE.search(html)
    if match:
        tenant, wd_host, site = match.groups()
        return Detection(ATS.WORKDAY, {"tenant": tenant, "wd_host": wd_host, "site": site}, match.group(0))

    match = _LEVER_BOARD_RE.search(html) or _LEVER_API_RE.search(html)
    if match:
        return Detection(ATS.LEVER, {"company": match.group(1)}, match.group(0))

    match = _SUCCESSFACTORS_RE.search(html)
    if match:
        return Detection(ATS.SUCCESSFACTORS, {"company": match.group(1)}, match.group(0))

    match = _ASHBY_RE.search(html)
    # Ashby isn't in the brief's five-ATS list — surfaced as evidence only,
    # not a real Detection, so callers can log it (e.g. Form Energy).
    if match:
        return None

    return None


def count_postings(detection: Detection, name: str = "?", sector: Sector = Sector.OTHER) -> Optional[int]:
    """Confirm *detection* actually returns postings via a real adapter.

    Returns the posting count (0 included) when an adapter exists for this
    ATS, or None when there's no adapter yet to verify with (Lever,
    SuccessFactors, ...) — a None result doesn't mean verification failed,
    it means it couldn't be attempted this way.
    """
    probe = Employer(
        name=name,
        sector=sector,
        ats=detection.ats,
        careers_url="",
        ats_config=detection.ats_config,
        hq_region=None,
    )
    if detection.ats is ATS.GREENHOUSE:
        return len(GreenhouseAdapter().fetch(probe))
    if detection.ats is ATS.WORKDAY:
        return len(WorkdayAdapter().fetch(probe))
    return None
