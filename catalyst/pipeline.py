"""Orchestration: fetch every enabled employer, classify postings, dedupe
against storage.json.

Connects the pieces built in Phases 2-5 — registry, adapters, classify —
into one pipeline. Nothing here existed before Phase 6; the adapters and
classify() were previously only ever exercised from ad-hoc scratch scripts.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List

from .adapters import Adapter
from .adapters.greenhouse import GreenhouseAdapter
from .adapters.workday import WorkdayAdapter
from .classify import classify, matches_target_country
from .config import (
    load_scoring_config,
    load_target_countries,
    load_target_levels,
    load_target_regions,
)
from .models import ATS, Employer, Posting, posting_key
from .registry import load_employers

logger = logging.getLogger(__name__)

# CLAUDE.md: never more than 4 concurrent workers.
_MAX_WORKERS = 4

DEFAULT_STORAGE_PATH = Path(__file__).resolve().parent.parent / "storage.json"

_ADAPTERS: Dict[ATS, Adapter] = {
    ATS.GREENHOUSE: GreenhouseAdapter(),
    ATS.WORKDAY: WorkdayAdapter(),
}


@dataclass
class PipelineResult:
    new: List[Posting] = field(default_factory=list)
    """Postings that weren't in storage before this run and pass the score/level filters —
    what the email digest should alert on."""
    active: List[Posting] = field(default_factory=list)
    """Every currently-open posting that passes the score/level filters (new or not) —
    what the README/CSV export should show."""


def fetch_all(employers: List[Employer]) -> List[Posting]:
    """Fetch postings for every enabled employer with a built adapter.

    Runs up to 4 employers concurrently (CLAUDE.md's worker cap). One
    employer's fetch failing (an adapter already degrades to [] internally,
    but this also guards against an unexpected exception) never blocks the
    others.
    """
    to_fetch = [e for e in employers if e.enabled]
    postings: List[Posting] = []

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        future_to_employer = {}
        for employer in to_fetch:
            adapter = _ADAPTERS.get(employer.ats)
            if adapter is None:
                logger.warning("No adapter for %s (%s) — skipping", employer.name, employer.ats.value)
                continue
            future_to_employer[executor.submit(adapter.fetch, employer)] = employer

        for future in as_completed(future_to_employer):
            employer = future_to_employer[future]
            try:
                postings.extend(future.result())
            except Exception:
                logger.exception("Fetch failed for %s", employer.name)

    return postings


def _posting_to_dict(posting: Posting) -> dict:
    return {
        "employer": posting.employer,
        "title": posting.title,
        "url": posting.url,
        "location": posting.location,
        "posted_date": posting.posted_date.isoformat() if posting.posted_date else None,
        "first_seen": posting.first_seen.isoformat(),
        "sector": posting.sector.value,
        "level": posting.level.value,
        "score": posting.score,
        "tags": posting.tags,
        "cohort": posting.cohort,
    }


def load_storage(path: Path | str = DEFAULT_STORAGE_PATH) -> Dict[str, dict]:
    """Load storage.json's postings dict (key -> serialized posting), or {} if missing/empty."""
    path = Path(path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            logger.warning("%s is corrupted — starting fresh.", path)
            return {}
    return data.get("postings", {})


def save_storage(postings_by_key: Dict[str, dict], path: Path | str = DEFAULT_STORAGE_PATH) -> None:
    """Write *postings_by_key* to storage.json."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"postings": postings_by_key}, f, indent=2)


def run(
    *,
    employers: List[Employer] | None = None,
    today: date | None = None,
    storage_path: Path | str = DEFAULT_STORAGE_PATH,
    persist: bool = True,
) -> PipelineResult:
    """Run the full fetch -> classify -> dedupe -> filter pipeline.

    *persist* controls whether storage.json is overwritten — pass False for
    a dry run that shouldn't have side effects.
    """
    today = today or date.today()
    employers = employers if employers is not None else load_employers()
    raw_postings = fetch_all(employers)

    # Compute each posting's key exactly once, before classify() runs — it
    # mutates posting.location (normalize_location()), and recomputing the
    # key afterward would silently change it for any posting whose location
    # string actually gets normalized, breaking both the new/active match
    # below and dedup on every subsequent run (the persisted key would never
    # match what a fresh fetch recomputes pre-classify).
    keyed = [(p, posting_key(p.employer, p.title, p.location)) for p in raw_postings]

    stored = load_storage(storage_path)
    new_keys = {key for _, key in keyed if key not in stored}
    for posting, key in keyed:
        if key in stored:
            posting.first_seen = date.fromisoformat(stored[key]["first_seen"])

    scoring = load_scoring_config()
    target_regions = load_target_regions()
    target_levels = set(load_target_levels())
    target_countries = load_target_countries()

    for posting, _ in keyed:
        classify(
            posting,
            weights=scoring["weights"],
            half_life_days=scoring["half_life_days"],
            target_regions=target_regions,
            today=today,
        )

    min_score = scoring["min_score"]
    active_keyed = [
        (p, key)
        for p, key in keyed
        if p.score >= min_score
        and p.level.value in target_levels
        and matches_target_country(p.location, target_countries)
    ]
    active_keyed.sort(key=lambda pk: pk[0].score, reverse=True)

    active = [p for p, _ in active_keyed]
    new_active = [p for p, key in active_keyed if key in new_keys]

    if persist:
        new_storage = {key: _posting_to_dict(p) for p, key in keyed}
        save_storage(new_storage, storage_path)

    return PipelineResult(new=new_active, active=active)
