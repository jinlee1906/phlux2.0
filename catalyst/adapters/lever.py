"""Lever ATS adapter.

Request shape confirmed against a live tenant: Shield AI's own careers page
(shield.ai/careers/) contains a literal ``<a href="https://jobs.lever.co/
shieldai">`` link — the company slug below was read directly off that page,
not guessed. See PROJECT_BRIEF.md Phase 3.

Unlike Greenhouse (a dict with a "jobs" key) and Workday (paginated), the
Lever postings endpoint returns a bare JSON array of every open posting in
one response.
"""
from __future__ import annotations

from datetime import date, datetime
import logging
from typing import List

import requests

from ..models import Employer, Level, Posting

logger = logging.getLogger(__name__)

_JOBS_URL = "https://api.lever.co/v0/postings/{company}"
_TIMEOUT_SECONDS = 30


def _parse_created_at(value) -> date | None:
    """Parse Lever's ``createdAt`` (epoch milliseconds) into a date, if present."""
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000).date()
    except (ValueError, OverflowError, OSError):
        return None


class LeverAdapter:
    """Fetches postings from a Lever job board.

    ``employer.ats_config`` must contain ``{"company": "<slug>"}`` — the
    slug used in ``https://jobs.lever.co/<slug>``.
    """

    def fetch(self, employer: Employer) -> List[Posting]:
        company = employer.ats_config.get("company")
        if not company:
            logger.error("No company slug configured for %s", employer.name)
            return []

        try:
            response = requests.get(
                _JOBS_URL.format(company=company),
                params={"mode": "json"},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            jobs = response.json()
        except requests.RequestException as exc:
            logger.error("Lever fetch failed for %s: %s", employer.name, exc)
            return []
        except ValueError as exc:  # malformed JSON
            logger.error("Lever response for %s was not valid JSON: %s", employer.name, exc)
            return []

        if not isinstance(jobs, list):
            logger.error("Lever response for %s was not a list: %r", employer.name, jobs)
            return []

        today = date.today()
        return [
            Posting(
                employer=employer.name,
                title=(job.get("text") or "").strip(),
                url=job.get("hostedUrl"),
                location=(job.get("categories") or {}).get("location"),
                posted_date=_parse_created_at(job.get("createdAt")),
                first_seen=today,
                sector=employer.sector,
                level=Level.UNKNOWN,
                score=0.0,
                tags=[],
                raw=job,
            )
            for job in jobs
        ]
