"""CLI: verify an employer's ATS from their real careers page and append it
to employers.yaml.

Usage:
    python scripts/add_employer.py <careers_url> --name "Air Products" \\
        --sector SPECIALTY_CHEM [--hq-region "Allentown, PA"] [--disabled]

Fetches *careers_url*, looks for a literal ATS reference in the page itself
(never guesses a tenant/board token — see CLAUDE.md), and for Greenhouse or
Workday also confirms the detected config actually returns postings before
appending. An ATS detected but not confirmable this way (Lever,
SuccessFactors — no adapter yet) is still appended, flagged as unconfirmed,
per the project's Phase 5 decision to record those ahead of their adapters.
Nothing could be detected at all: reports it and suggests unverified.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalyst.detect import count_postings, detect_ats, fetch_page  # noqa: E402
from catalyst.models import Employer, Sector  # noqa: E402
from catalyst.registry import append_employer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("careers_url", help="The employer's real, public careers page URL")
    parser.add_argument("--name", required=True, help="Employer name")
    parser.add_argument("--sector", required=True, choices=[s.value for s in Sector], help="Sector enum value")
    parser.add_argument("--hq-region", default=None, help='HQ region, e.g. "Allentown, PA"')
    parser.add_argument("--disabled", action="store_true", help="Add with enabled: false")
    args = parser.parse_args()

    print(f"Fetching {args.careers_url} ...")
    html = fetch_page(args.careers_url)
    if html is None:
        print(f"Could not fetch {args.careers_url} (blocked, 404, or a network error).")
        print("Log this employer in unverified.md with what was tried.")
        return 1

    detection = detect_ats(html)
    if detection is None:
        print("No known ATS reference (Greenhouse/Workday/Lever/SuccessFactors) found on this page.")
        print("Log this employer in unverified.md with what was tried.")
        return 1

    print(f"Detected {detection.ats.value}: {detection.ats_config}")
    print(f"  evidence: {detection.evidence}")

    sector = Sector(args.sector)
    count = count_postings(detection, name=args.name, sector=sector)
    if count is None:
        print(f"No adapter exists yet to confirm postings for {detection.ats.value} — recording unconfirmed.")
    elif count == 0:
        print(f"{detection.ats.value} config returned zero postings — not confirmed. Not adding.")
        print("Log this employer in unverified.md with what was tried.")
        return 1
    else:
        print(f"Confirmed: {count} real postings returned.")

    employer = Employer(
        name=args.name,
        sector=sector,
        ats=detection.ats,
        careers_url=args.careers_url,
        ats_config=detection.ats_config,
        hq_region=args.hq_region,
        enabled=not args.disabled,
    )
    append_employer(employer)
    print(f"Added {args.name!r} to employers.yaml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
