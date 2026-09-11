"""Employer registry: read/write ``employers.yaml``.

Replaces ``companies.csv`` (PROJECT_BRIEF.md Phase 5) — a CSV can't hold the
nested ``ats_config`` cleanly, and careers URLs with commas/quotes already
made the CSV fragile. Every entry here has been verified against the
employer's real careers page; anything that couldn't be verified goes in
``unverified.md`` instead (see CLAUDE.md's verification rule).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import yaml

from .models import ATS, Employer, Sector

DEFAULT_EMPLOYERS_PATH = Path(__file__).resolve().parent.parent / "employers.yaml"


def load_employers(path: Path | str = DEFAULT_EMPLOYERS_PATH) -> List[Employer]:
    """Load and parse ``employers.yaml`` into a list of :class:`Employer`."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []

    return [
        Employer(
            name=entry["name"],
            sector=Sector(entry["sector"]),
            ats=ATS(entry["ats"]),
            careers_url=entry["careers_url"],
            ats_config=entry.get("ats_config") or {},
            hq_region=entry.get("hq_region"),
            enabled=entry.get("enabled", True),
        )
        for entry in raw
    ]


def _employer_to_dict(employer: Employer) -> dict:
    return {
        "name": employer.name,
        "sector": employer.sector.value,
        "ats": employer.ats.value,
        "careers_url": employer.careers_url,
        "ats_config": employer.ats_config,
        "hq_region": employer.hq_region,
        "enabled": employer.enabled,
    }


def save_employers(employers: List[Employer], path: Path | str = DEFAULT_EMPLOYERS_PATH) -> None:
    """Write *employers* to *path* as YAML, sorted by name for stable diffs."""
    path = Path(path)
    data = [_employer_to_dict(e) for e in sorted(employers, key=lambda e: e.name.lower())]
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)


def append_employer(employer: Employer, path: Path | str = DEFAULT_EMPLOYERS_PATH) -> None:
    """Append *employer* to the registry at *path*.

    Raises ValueError if an employer with the same name (case-insensitive)
    is already present, so the same verified entry can't be duplicated.
    """
    path = Path(path)
    existing = load_employers(path) if path.exists() else []
    if any(e.name.lower() == employer.name.lower() for e in existing):
        raise ValueError(f"{employer.name!r} is already in {path}")
    existing.append(employer)
    save_employers(existing, path)
