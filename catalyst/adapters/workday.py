"""Workday ATS adapter.

Request shape confirmed against a live tenant: Air Products's own careers
page (airproducts.com/careers) contains a literal reference to
``airproducts.wd5.myworkdayjobs.com/en-US/AP0001`` — the tenant/host/site
below were read directly off that page, not guessed. See PROJECT_BRIEF.md
Phase 3.

Two quirks discovered empirically, not documented anywhere official:

- Only the FIRST page's "total" is reliable. Every later page (any request
  with offset > 0) reports "total": 0 even though it still returns real,
  distinct postings — confirmed by comparing titles across pages (zero
  overlap between offset=0 and offset=20 against Air Products). So "total"
  must be captured once, from the first response, and never overwritten.
- "postedOn" is relative text ("Posted Today", "Posted 8 Days Ago",
  "Posted 30+ Days Ago"), never an absolute date. "30+" is a floor, not an
  exact count.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import date, timedelta
from typing import List

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from ..models import Employer, Level, Posting

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20
_MAX_PAGES = 100  # safety net against a pathological/incorrect "total"
_TIMEOUT_SECONDS = 30
# CLAUDE.md: minimum 2s between requests to the same host. A large employer
# (e.g. Amgen, ~1774 postings / 20 per page = ~89 requests) would otherwise
# hammer their API back-to-back across a whole pagination run.
_PER_HOST_DELAY_SECONDS = 2.0
_RETRY_WAIT_SECONDS = 5

# Every Workday tenant is a different subdomain (*.myworkdayjobs.com), but
# they share Workday's backend infrastructure — pipeline.fetch_all() runs up
# to 4 employers concurrently, and 4 simultaneous Workday tenants (each
# individually well-paced) can still add up to an aggregate request rate
# against that shared infrastructure well above what per-page pacing alone
# accounts for. Confirmed live: 8 of 17 Workday employers hit connection
# resets/timeouts in one run. This lock serializes ALL Workday fetches
# process-wide — other ATSes (Greenhouse, ...) are untouched and still run
# concurrently via the thread pool.
_WORKDAY_HOST_LOCK = threading.Lock()

_RELATIVE_DAYS_RE = re.compile(r"(\d+)\+?\s*days?", re.IGNORECASE)


def _parse_posted_on(value: str | None, today: date) -> date | None:
    """Parse Workday's relative 'postedOn' text into a date, if possible."""
    if not value:
        return None
    lowered = value.lower()
    if "today" in lowered:
        return today
    if "yesterday" in lowered:
        return today - timedelta(days=1)
    match = _RELATIVE_DAYS_RE.search(lowered)
    if match:
        return today - timedelta(days=int(match.group(1)))
    return None


class WorkdayAdapter:
    """Fetches postings from a Workday CXS job board.

    ``employer.ats_config`` must contain ``tenant``, ``wd_host`` (e.g.
    ``"wd5"``), and ``site`` — read off the employer's own careers page as
    ``https://{tenant}.{wd_host}.myworkdayjobs.com/en-US/{site}``.
    """

    def fetch(self, employer: Employer) -> List[Posting]:
        tenant = employer.ats_config.get("tenant")
        wd_host = employer.ats_config.get("wd_host")
        site = employer.ats_config.get("site")
        if not tenant or not wd_host or not site:
            logger.error("Incomplete Workday ats_config for %s", employer.name)
            return []

        base = f"https://{tenant}.{wd_host}.myworkdayjobs.com"
        jobs_url = f"{base}/wday/cxs/{tenant}/{site}/jobs"
        board_url = f"{base}/en-US/{site}"

        with _WORKDAY_HOST_LOCK:
            try:
                return self._fetch_all_pages(employer, jobs_url, board_url)
            except requests.RequestException as exc:
                logger.error("Workday fetch failed for %s (after retry): %s", employer.name, exc)
                return []
            except ValueError as exc:  # malformed JSON — not worth retrying
                logger.error("Workday response for %s was not valid JSON: %s", employer.name, exc)
                return []

    @retry(
        # Connection resets/timeouts only — not requests.RequestException
        # broadly, so a real HTTP error status (a config problem that will
        # just fail the same way again) doesn't waste a 5s wait retrying it.
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        stop=stop_after_attempt(2),
        wait=wait_fixed(_RETRY_WAIT_SECONDS),
        reraise=True,
    )
    def _fetch_all_pages(self, employer: Employer, jobs_url: str, board_url: str) -> List[Posting]:
        """Fetch every page for *employer*. Retried once (from the start —
        pagination state isn't resumable) on a connection reset or timeout."""
        today = date.today()
        postings: List[Posting] = []

        with requests.Session() as session:
            total = None
            offset = 0
            for _ in range(_MAX_PAGES):
                body = {
                    "appliedFacets": {},
                    "limit": _PAGE_SIZE,
                    "offset": offset,
                    "searchText": "",
                }
                response = session.post(jobs_url, json=body, timeout=_TIMEOUT_SECONDS)
                response.raise_for_status()
                data = response.json()

                if total is None:
                    total = data.get("total", 0)

                job_postings = data.get("jobPostings", [])
                if not job_postings:
                    break

                for job in job_postings:
                    external_path = job.get("externalPath")
                    postings.append(
                        Posting(
                            employer=employer.name,
                            title=(job.get("title") or "").strip(),
                            url=(board_url + external_path) if external_path else None,
                            location=job.get("locationsText"),
                            posted_date=_parse_posted_on(job.get("postedOn"), today),
                            first_seen=today,
                            sector=employer.sector,
                            level=Level.UNKNOWN,
                            score=0.0,
                            tags=[],
                            raw=job,
                        )
                    )

                offset += _PAGE_SIZE
                if offset >= total:
                    break
                time.sleep(_PER_HOST_DELAY_SECONDS)

        return postings
