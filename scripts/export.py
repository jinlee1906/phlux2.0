"""CLI: export active postings to data/postings.csv.

Replaces the old hardcoded Google Sheets integration (main.py's
update_internship_tracker, removed in Phase 0) — import the CSV into
whatever tracker you actually use.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_readme import load_active_postings  # noqa: E402

DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "postings.csv"
COLUMNS = ["employer", "title", "location", "sector", "level", "score", "url", "first_seen"]


def export(path: Path = DEFAULT_OUTPUT_PATH) -> int:
    """Write active postings to *path* as CSV. Returns the row count."""
    postings = load_active_postings()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for posting in postings:
            writer.writerow({column: posting.get(column, "") for column in COLUMNS})
    return len(postings)


if __name__ == "__main__":
    count = export()
    print(f"Exported {count} posting(s) to {DEFAULT_OUTPUT_PATH}")
