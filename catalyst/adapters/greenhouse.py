"""Greenhouse ATS adapter.

Request shape confirmed against a live tenant: Agility Robotics's own
careers page (agilityrobotics.com/careers) embeds a script that calls
``https://boards-api.greenhouse.io/v1/boards/agilityrobotics/departments`` —
the board-token convention below was read directly off that page, not
guessed. See PROJECT_BRIEF.md Phase 3.

The jobs endpoint returns every open posting in a single response (no
offset/limit pagination, unlike Workday).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import List

import requests

from ..models import Employer, Level, Posting

logger = logging.getLogger(__name__)

_JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
_TIMEOUT_SECONDS = 30


def _parse_date(value: str | None) -> date | None:
    """Parse a Greenhouse ISO-8601 timestamp into a date, if present."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


class GreenhouseAdapter:
    """Fetches postings from a Greenhouse job board.

    ``employer.ats_config`` must contain ``{"board_token": "<token>"}`` —
    the slug used in ``https://boards-api.greenhouse.io/v1/boards/<token>``.
    """

    def fetch(self, employer: Employer) -> List[Posting]:
        token = employer.ats_config.get("board_token")
        if not token:
            logger.error("No board_token configured for %s", employer.name)
            return []

        try:
            response = requests.get(
                _JOBS_URL.format(token=token),
                params={"content": "true"},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            jobs = response.json().get("jobs", [])
        except requests.RequestException as exc:
            logger.error("Greenhouse fetch failed for %s: %s", employer.name, exc)
            return []
        except ValueError as exc:  # malformed JSON
            logger.error("Greenhouse response for %s was not valid JSON: %s", employer.name, exc)
            return []

        today = date.today()
        return [
            Posting(
                employer=employer.name,
                title=(job.get("title") or "").strip(),
                url=job.get("absolute_url"),
                location=(job.get("location") or {}).get("name"),
                posted_date=_parse_date(job.get("first_published") or job.get("updated_at")),
                first_seen=today,
                sector=employer.sector,
                level=Level.UNKNOWN,
                score=0.0,
                tags=[],
                raw=job,
            )
            for job in jobs
        ]
