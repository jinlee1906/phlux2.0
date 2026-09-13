"""Dataclasses used across the project."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import List


class Sector(str, Enum):
    """Industry sector an employer or posting belongs to."""

    OIL_GAS = "OIL_GAS"
    SPECIALTY_CHEM = "SPECIALTY_CHEM"
    PHARMA_BIOTECH = "PHARMA_BIOTECH"
    SEMICONDUCTOR = "SEMICONDUCTOR"
    ENERGY_STORAGE = "ENERGY_STORAGE"
    COSMETICS_FRAGRANCE = "COSMETICS_FRAGRANCE"
    ROBOTICS = "ROBOTICS"
    AEROSPACE = "AEROSPACE"
    FOOD_CPG = "FOOD_CPG"
    EPC = "EPC"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    NATIONAL_LAB = "NATIONAL_LAB"
    MATERIALS = "MATERIALS"
    OTHER = "OTHER"


class ATS(str, Enum):
    """Applicant tracking system an employer's careers page runs on."""

    WORKDAY = "WORKDAY"
    GREENHOUSE = "GREENHOUSE"
    LEVER = "LEVER"
    SUCCESSFACTORS = "SUCCESSFACTORS"
    SELENIUM = "SELENIUM"


class Level(str, Enum):
    """Seniority/experience level of a posting."""

    INTERNSHIP = "INTERNSHIP"
    CO_OP = "CO_OP"
    NEW_GRAD = "NEW_GRAD"
    EXPERIENCED = "EXPERIENCED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Employer:
    """A company we scrape, and how to scrape it."""

    name: str
    sector: Sector
    ats: ATS
    careers_url: str
    ats_config: dict
    hq_region: str | None
    enabled: bool = True


@dataclass
class Posting:
    """A single job posting, scored and tagged for relevance."""

    employer: str
    title: str
    url: str | None
    location: str | None
    posted_date: date | None
    first_seen: date
    sector: Sector
    level: Level
    score: float
    tags: List[str]
    raw: dict
    # Recruiting cycle parsed from the title (e.g. "Summer 2027"), when present.
    # Added in Phase 4 so cycles that have already closed can be filtered out;
    # defaults to None so adapters (which don't classify) don't need updating.
    cohort: str | None = None


# A trailing requisition ID. Four ways a code can be recognizable as an ID
# rather than meaningful title text (a cohort year, a level number, ...):
#   - explicitly labeled: "Req 12345", "Job ID 12345"
#   - hash-prefixed: "#12345"
#   - R-prefixed (the common Workday convention): "R123456"
#   - a long bare number with no label at all: 5+ digits/dashes
# A short bare number (e.g. a 4-digit cohort year like "Summer 2026", or a
# level like "Engineer 2") is deliberately NOT stripped — only a labeled or
# R-prefixed code, or an unusually long bare number, is assumed to be an ID.
_TRAILING_REQ_ID_RE = re.compile(
    r"""
    [\s\-–—|,(]+                                            # separator introducing the code
    (?:
        (?:req(?:uisition)?\.?|job\s*id|job)\s*\#?\s*\d[\d-]{2,}   # labeled: 3+ digits
        | \#\s*\d[\d-]{2,}                                          # "#12345": 3+ digits
        | r-?\d[\d-]{3,}                                            # "R123456": 4+ digits
        | \d[\d-]{4,}                                               # bare number: 5+ digits
    )
    \)?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace, and strip a trailing requisition ID.

    Used to build a stable dedupe key so a posting whose title gets reworded
    slightly (or gains/loses a req ID across scrapes) doesn't show up as new.
    """
    normalized = " ".join(title.lower().split())
    return _TRAILING_REQ_ID_RE.sub("", normalized).strip()


def posting_key(employer: str, title: str, location: str | None) -> str:
    """Return a stable id for a posting, keyed on (employer, title, location).

    Deliberately excludes url/posted_date/score/tags/raw so a reworded title
    or a re-scored posting still dedupes against what we've already seen.
    """
    normalized_location = " ".join((location or "").lower().split())
    raw = f"{employer.strip().lower()}|{normalize_title(title)}|{normalized_location}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
