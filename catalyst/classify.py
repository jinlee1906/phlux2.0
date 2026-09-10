"""Posting classification and relevance scoring — the domain heart of the tracker.

Implements PROJECT_BRIEF.md Phase 4: level detection (4c), the keyword
taxonomy and additive log-odds score (4a/4b/4b-ii), and recruiting-cohort
extraction. The taxonomy below was drafted from the brief and corrected by
the user before being wired in here — don't add or remove keywords without
that same review.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Dict, List, Optional

from .models import Level, Posting

# ── Matching ─────────────────────────────────────────────────────────────────

# Hyphens and slashes are normalized to spaces before matching, so every
# keyword below is written in canonical space-separated form (e.g. "scale up"
# rather than "scale-up") — that's the form it will actually appear in after
# normalization, on both sides of the comparison.
_SEPARATOR_RE = re.compile(r"[-/]")


def _normalize_for_matching(text: str) -> str:
    normalized = _SEPARATOR_RE.sub(" ", text.lower())
    return " ".join(normalized.split())


def _find_matches(normalized_text: str, keywords: List[str]) -> List[str]:
    return [kw for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", normalized_text)]


# ── Keyword taxonomy (PROJECT_BRIEF.md Phase 4b/4b-ii, user-reviewed) ───────────

CORE_KEYWORDS: List[str] = [
    # General
    "process engineer", "chemical engineer", "distillation", "reactor", "catalysis",
    "separations", "unit operations", "heat transfer", "mass transfer", "hazop",
    "process safety", "psm", "scale up", "pilot plant", "bioprocess", "fermentation",
    "downstream processing", "upstream processing", "drug substance", "formulation",
    "polymer", "refining", "petrochemical", "process development", "process control",
    "dcs", "plant engineer", "production engineer", "manufacturing engineer", "tech service",
    # Profile-specific (battery/electrochemistry, fragrance)
    "electrochemistry", "electrochemical", "cell engineering", "electrode", "anode",
    "cathode", "electrolyte", "cell design", "cell manufacturing", "battery engineer",
    # NOTE: "coating engineer" also matches paint/coatings roles at PPG and
    # Sherwin-Williams (MATERIALS sector, not battery electrode coating) — an
    # expected, accepted false-positive source, not a bug.
    "coating engineer",
    "calendering", "slurry", "failure analysis", "materials engineer", "aromachemical",
    "flavor and fragrance", "perfumer", "fragrance development", "flavor chemist",
]

SECTOR_KEYWORDS: List[str] = [
    # General
    "refinery", "gmp", "cgmp", "cleanroom", "fab", "wafer", "etch", "deposition", "cvd",
    "ald", "battery", "electrolyzer", "carbon capture", "wastewater", "emissions", "fda",
    "validation", "six sigma", "lean",
    # Profile-specific (battery/electrochemistry, soft robotics materials, fragrance)
    "eis", "impedance", "galvanostatic", "cycling", "dendrite", "separator", "pouch cell",
    "coin cell", "solid state", "sodium ion", "zinc", "lithium", "elastomer", "silicone",
    "liquid metal", "actuator", "hydrogel", "encapsulation", "adhesive", "thin film",
    "compounding", "emulsion", "surfactant", "rheology", "stability testing", "ifra",
    "gc ms", "hplc", "aspen", "comsol",
    # Moved from core: too generic on its own (also common in software/lab-sales titles).
    "application scientist",
]

VETO_KEYWORDS: List[str] = [
    "software engineer", "frontend", "backend", "full stack", "data scientist",
    "machine learning", "sales", "account executive", "accounting", "recruiter", "hr",
    "marketing", "paralegal", "truck driver", "warehouse associate", "retail",
]

# These only count as a match when at least one OTHER core/sector keyword also
# matched — otherwise a mining, logistics, or lab-instrument posting about the
# raw material/component scores just from the element/product name.
GATED_KEYWORDS = frozenset({"zinc", "lithium", "battery"})


def _apply_gating(core_matches: List[str], sector_matches: List[str]) -> tuple[List[str], List[str]]:
    non_gated = [m for m in core_matches + sector_matches if m not in GATED_KEYWORDS]
    if non_gated:
        return core_matches, sector_matches
    return core_matches, [m for m in sector_matches if m not in GATED_KEYWORDS]


# ── Level detection (4c) ─────────────────────────────────────────────────────

# Word-boundary matched, same as the taxonomy above — not the upstream's
# "ship" substring bug (which also matched "Shipping Coordinator").
_INTERNSHIP_KEYWORDS = ["intern", "internship", "summer analyst"]
# Weighted as heavily as internship detection — most Gulf Coast plants (Air
# Products, Eastman, and similar) run co-op programs, not 12-week internships.
_CO_OP_KEYWORDS = ["co op", "coop", "cooperative education"]
_NEW_GRAD_KEYWORDS = [
    "new grad", "entry level", "university", "campus", "rotational",
    "graduate program", "development program", "eit", "engineer i", "associate engineer",
]


def detect_level(title: str) -> Level:
    """Classify *title* by career stage. Internship/co-op checked before new-grad
    so e.g. "Rotational Engineering Internship" still comes out INTERNSHIP."""
    if not title:
        return Level.UNKNOWN
    normalized = _normalize_for_matching(title)
    if _find_matches(normalized, _INTERNSHIP_KEYWORDS):
        return Level.INTERNSHIP
    if _find_matches(normalized, _CO_OP_KEYWORDS):
        return Level.CO_OP
    if _find_matches(normalized, _NEW_GRAD_KEYWORDS):
        return Level.NEW_GRAD
    return Level.EXPERIENCED


# ── Recruiting cohort extraction ─────────────────────────────────────────────

_ADJACENT_COHORT_RE = re.compile(r"\b(spring|summer|fall|winter)\s+(20\d{2})\b", re.IGNORECASE)
_SEASON_RE = re.compile(r"\b(spring|summer|fall|winter)\b", re.IGNORECASE)
_FY_YEAR_RE = re.compile(r"\bfy\s*'?(\d{4}|\d{2})\b", re.IGNORECASE)
_BARE_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def extract_cohort(title: str, fiscal_year_end_month: Optional[int] = None) -> Optional[str]:
    """Extract a "Season YYYY" recruiting cohort from *title*, if present.

    Lets postings from cycles that have already closed be filtered out later
    (e.g. keep "Summer 2027", drop "Fall 2025") without discarding the year
    during title normalization — see normalize_title()'s cohort-year tests.

    Handles three cases, in order:

    1. Season and year adjacent ("Summer 2027") — always a calendar year.
    2. Season anywhere in the title plus a plain 4-digit year anywhere else
       ("Summer Intern-Finance, Corporate (2027)") — still a calendar year,
       no conversion needed, just not required to be adjacent to the season.
    3. Season anywhere plus a fiscal-year-labeled year ("FY 2027", "FY27")
       anywhere else — a fiscal year only equals the same-numbered calendar
       summer when the employer's fiscal year closes in September or later
       (its Q4 then overlaps that calendar summer). This is never assumed:
       it only converts when the caller passes a verified
       *fiscal_year_end_month* (1-12) for that specific employer, and only
       for "summer" (the only season/FYE relationship actually verified so
       far — see PROJECT_BRIEF.md Phase 4 history for the Air Products case
       this was built against). Anything else returns None rather than
       guess at an unverified fiscal calendar.
    """
    if not title:
        return None
    normalized = _normalize_for_matching(title)

    adjacent = _ADJACENT_COHORT_RE.search(normalized)
    if adjacent:
        season, year = adjacent.groups()
        return f"{season.capitalize()} {year}"

    season_match = _SEASON_RE.search(normalized)
    if not season_match:
        return None
    season = season_match.group(1)

    fy_match = _FY_YEAR_RE.search(normalized)
    if fy_match:
        if season.lower() == "summer" and fiscal_year_end_month is not None and fiscal_year_end_month >= 9:
            digits = fy_match.group(1)
            year = f"20{digits}" if len(digits) == 2 else digits
            return f"{season.capitalize()} {year}"
        return None  # FY-labeled year we can't safely convert — don't guess

    bare_year_match = _BARE_YEAR_RE.search(normalized)
    if bare_year_match:
        return f"{season.capitalize()} {bare_year_match.group(1)}"

    return None


# ── Location bonus (4d) ──────────────────────────────────────────────────────

def _matches_target_region(location: Optional[str], target_regions: List[str]) -> bool:
    """Placeholder region match: case-insensitive substring against *location*.

    Refined once target regions are actually configured (Phase 4d) — currently
    a no-op since config.json's targets.regions defaults to empty.
    """
    if not location or not target_regions:
        return False
    lowered_location = location.lower()
    return any(region.lower() in lowered_location for region in target_regions)


# ── Scoring (4a) ──────────────────────────────────────────────────────────────

DEFAULT_WEIGHTS: Dict[str, float] = {"core": 3, "sector": 1, "veto": -5, "location": 2}
DEFAULT_HALF_LIFE_DAYS = 14


def classify(
    posting: Posting,
    *,
    weights: Optional[Dict[str, float]] = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    target_regions: Optional[List[str]] = None,
    fiscal_year_end_month: Optional[int] = None,
    today: Optional[date] = None,
) -> Posting:
    """Classify and score *posting* in place, and return it for chaining.

    Sets ``level``, ``cohort``, ``score``, and ``tags``. Does not decide
    whether to drop the posting — compare the resulting score against a
    configured ``min_score`` separately (S < 0 should be dropped, per 4a).

    *fiscal_year_end_month* is this specific employer's verified fiscal year
    end (1-12), used only to interpret an FY-labeled cohort like "FY 2027" —
    see :func:`extract_cohort`. There's no employer registry to source this
    from yet (that's Phase 5), so callers pass it explicitly per employer.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    target_regions = target_regions if target_regions is not None else []
    today = today or date.today()

    posting.level = detect_level(posting.title)
    posting.cohort = extract_cohort(posting.title, fiscal_year_end_month=fiscal_year_end_month)

    normalized_title = _normalize_for_matching(posting.title)
    core_matches = _find_matches(normalized_title, CORE_KEYWORDS)
    sector_matches = _find_matches(normalized_title, SECTOR_KEYWORDS)
    veto_matches = _find_matches(normalized_title, VETO_KEYWORDS)
    core_matches, sector_matches = _apply_gating(core_matches, sector_matches)

    location_bonus = 1 if _matches_target_region(posting.location, target_regions) else 0
    days_since_seen = max(0, (today - posting.first_seen).days)
    decay = (math.log(2) / half_life_days) * days_since_seen

    posting.score = (
        weights["core"] * len(core_matches)
        + weights["sector"] * len(sector_matches)
        + weights["veto"] * len(veto_matches)
        + weights["location"] * location_bonus
        - decay
    )
    posting.tags = core_matches + sector_matches + veto_matches

    return posting
