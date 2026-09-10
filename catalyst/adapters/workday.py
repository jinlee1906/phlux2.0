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
from datetime import date, timedelta
from typing import List

import requests

from ..models import Employer, Level, Posting

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20
_MAX_PAGES = 100  # safety net against a pathological/incorrect "total"
_TIMEOUT_SECONDS = 30

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

        today = date.today()
        postings: List[Posting] = []

        try:
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
        except requests.RequestException as exc:
            logger.error("Workday fetch failed for %s: %s", employer.name, exc)
            return []
        except ValueError as exc:  # malformed JSON
            logger.error("Workday response for %s was not valid JSON: %s", employer.name, exc)
            return []

        return postings
