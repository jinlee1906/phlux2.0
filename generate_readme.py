"""Generate README.md from storage.json — the top-scoring active postings.

The upstream wrote every posting ever seen into the README, reaching 9 MB.
This caps the rendered table at MAX_README_POSTINGS and writes the full
history to data/postings.ndjson (newline-delimited JSON) instead —
greppable, diffable, and it doesn't bloat the page.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from catalyst.classify import matches_target_country
from catalyst.config import load_scoring_config, load_target_countries, load_target_levels
from catalyst.pipeline import DEFAULT_STORAGE_PATH, load_storage

MAX_README_POSTINGS = 200
DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORY_PATH = DATA_DIR / "postings.ndjson"


def load_active_postings(storage_path: Path | str = DEFAULT_STORAGE_PATH) -> List[Dict[str, Any]]:
    """Load postings from storage.json that currently pass the score/level
    filter (storage.json itself holds everything ever fetched), sorted by
    score descending.
    """
    stored = load_storage(storage_path)
    min_score = load_scoring_config()["min_score"]
    target_levels = set(load_target_levels())
    target_countries = load_target_countries()

    active = [
        posting
        for posting in stored.values()
        if posting.get("score", 0) >= min_score
        and posting.get("level") in target_levels
        and matches_target_country(posting.get("location"), target_countries)
    ]
    active.sort(key=lambda p: p.get("score", 0), reverse=True)
    return active


def write_history(postings: List[Dict[str, Any]], path: Path = HISTORY_PATH) -> None:
    """Write *postings* as newline-delimited JSON, one posting per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for posting in postings:
            f.write(json.dumps(posting) + "\n")


def generate_readme(postings: List[Dict[str, Any]]) -> str:
    """Build the README Markdown/HTML string from the top-scoring postings."""
    total = len(postings)
    shown = postings[:MAX_README_POSTINGS]

    lines = [
        "# 🌀 Catalyst: Chemical Engineering Job Tracker\n",
        "A personal job tracker for chemical engineering roles — process engineering, "
        "manufacturing, R&D, bioprocess, refining, and adjacent work.\n",
        f"\n---\n\n## 🔍 Top Postings\n"
        f"*Showing the {len(shown)} highest-scoring of {total} active postings — "
        f"full history in `data/postings.ndjson`*\n",
        """
<table>
  <thead>
    <tr>
      <th style="white-space: nowrap;">Employer</th>
      <th style="width: 100%;">Role</th>
      <th>Sector</th>
      <th>Location</th>
      <th>Score</th>
    </tr>
  </thead>
  <tbody>
""",
    ]

    for posting in shown:
        title = (posting.get("title") or "").replace("\n", " ").replace("|", "\\|").strip()
        url = posting.get("url") or "#"
        location = posting.get("location") or "—"
        sector = posting.get("sector") or "—"
        score = posting.get("score", 0.0)
        lines.append(
            f"""  <tr>
  <td>{posting.get("employer", "—")}</td>
  <td><a href="{url}">{title}</a></td>
  <td>{sector}</td>
  <td>{location}</td>
  <td>{score:.1f}</td>
</tr>"""
        )

    lines.append("""
  </tbody>
</table>
\n---
""")

    return "\n".join(lines)


if __name__ == "__main__":
    _postings = load_active_postings()
    write_history(_postings)
    readme = generate_readme(_postings)
    Path("README.md").write_text(readme, encoding="utf-8")
    print(
        f"README.md updated: {min(len(_postings), MAX_README_POSTINGS)} of "
        f"{len(_postings)} active postings shown; full history in {HISTORY_PATH}."
    )
