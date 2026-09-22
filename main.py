"""Entry point: fetch every enabled employer, classify postings, and email a digest.

Run with --dry-run to see the scored digest printed to stdout without
sending mail or writing storage.json — safe to run repeatedly while testing.
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import smtplib
from email.message import EmailMessage
from typing import Dict, List

from dotenv import load_dotenv

from catalyst.config import load_email_config
from catalyst.models import Posting
from catalyst.pipeline import run

# Loads .env into the environment if present (see .env.example) — a no-op
# if it doesn't exist, so CI (which sets real env vars directly) is unaffected.
load_dotenv()

logger = logging.getLogger(__name__)

_MAX_DIGEST_POSTINGS = 40

# One is picked at random per send — every {n} still carries the real count
# and {s} the correct singular/plural suffix, so it's silly, not misleading.
_SUBJECT_TEMPLATES = [
    "🍌 Your minions have found {n} new job{s}",
    "🕵️ {n} job{s} just surfaced from the depths",
    "🎯 {n} fresh target{s} acquired",
    "🚨 {n} new posting{s} spotted in the wild",
    "🧪 {n} new experiment{s}... I mean job{s}",
    "🛰️ Incoming transmission: {n} new job{s}",
    "🐿️ Your squirrel scouts found {n} new job{s}",
    "🔥 {n} hot new job{s} just dropped",
    "🎉 {n} new job{s} to obsess over",
    "🧫 {n} job{s} cultured fresh this morning",
]

# A different accent color each send, applied to headers/links/rule in the
# HTML digest — purely cosmetic, picked from a curated palette so it stays
# readable on a white background (not a random RGB roll).
_ACCENT_COLORS = [
    "#2563eb",  # blue
    "#dc2626",  # red
    "#16a34a",  # green
    "#9333ea",  # purple
    "#ea580c",  # orange
    "#0d9488",  # teal
    "#db2777",  # pink
    "#ca8a04",  # gold
]


def _group_by_sector(postings: List[Posting]) -> Dict[str, List[Posting]]:
    """Group *postings* by sector, each group sorted by score descending."""
    by_sector: Dict[str, List[Posting]] = {}
    for posting in postings:
        by_sector.setdefault(posting.sector.value, []).append(posting)
    for group in by_sector.values():
        group.sort(key=lambda p: p.score, reverse=True)
    return by_sector


def format_digest_html(postings: List[Posting], accent_color: str = "#111827") -> str:
    """Build the HTML digest body: grouped by sector, capped, deep-linked.

    *accent_color* tints the headers/rule/links — send_digest() picks a
    different one at random each send, purely for fun.
    """
    if not postings:
        return '<p style="font-family: monospace;">No new postings today.</p>'

    total = len(postings)
    by_sector = _group_by_sector(postings[:_MAX_DIGEST_POSTINGS])

    lines = [
        f'<h1 style="font-family: monospace; color: {accent_color};">'
        f'{total} New Posting{"s" if total != 1 else ""}</h1>'
    ]
    lines.append(f'<hr style="margin-top: 20px; margin-bottom: 20px; border-color: {accent_color};">')

    for sector in sorted(by_sector):
        lines.append(f'<h2 style="font-family: monospace; color: {accent_color};">{sector}</h2>')
        lines.append("<ul style='margin-top: 5px;'>")
        for posting in by_sector[sector]:
            tags = ", ".join(posting.tags) if posting.tags else "—"
            location = posting.location or "Location unknown"
            lines.append(
                "<li style='margin-bottom: 8px; font-family: monospace;'>"
                f'<a href="{posting.url}" target="_blank" style="color: {accent_color};">{posting.title}</a>'
                f" — {posting.employer}"
                f"<br>{location} · score {posting.score:.1f} · {tags}</li>"
            )
        lines.append("</ul>")

    if total > _MAX_DIGEST_POSTINGS:
        lines.append(f'<p style="font-family: monospace;">+{total - _MAX_DIGEST_POSTINGS} more</p>')

    return "\n".join(lines)


def format_digest_text(postings: List[Posting]) -> str:
    """Build a plain-text digest — used for --dry-run, where HTML isn't readable."""
    if not postings:
        return "No new postings today."

    total = len(postings)
    by_sector = _group_by_sector(postings[:_MAX_DIGEST_POSTINGS])

    lines = [f"{total} New Posting{'s' if total != 1 else ''}", "=" * 40]
    for sector in sorted(by_sector):
        lines.append(f"\n{sector}")
        lines.append("-" * len(sector))
        for posting in by_sector[sector]:
            tags = ", ".join(posting.tags) if posting.tags else "—"
            location = posting.location or "Location unknown"
            lines.append(f"  {posting.score:5.1f}  {posting.title}  ({posting.employer})")
            lines.append(f"         {location} · tags: {tags}")
            lines.append(f"         {posting.url}")

    if total > _MAX_DIGEST_POSTINGS:
        lines.append(f"\n+{total - _MAX_DIGEST_POSTINGS} more")

    return "\n".join(lines)


def send_digest(postings: List[Posting]) -> None:
    """Send the digest email via Gmail SMTP — single recipient, no BCC list.

    The subject line and HTML accent color are both picked at random each
    send (see _SUBJECT_TEMPLATES / _ACCENT_COLORS) — cosmetic only, the
    actual count and content are never affected.
    """
    email_cfg = load_email_config()
    msg = EmailMessage()
    subject_template = random.choice(_SUBJECT_TEMPLATES)
    msg["Subject"] = subject_template.format(n=len(postings), s="s" if len(postings) != 1 else "")
    msg["From"] = email_cfg["from"]
    msg["To"] = email_cfg["to"]

    accent_color = random.choice(_ACCENT_COLORS)
    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(format_digest_html(postings, accent_color=accent_color), subtype="html")

    password = os.environ["GMAIL_APP_PASSWORD"]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_cfg["login"], password)
        smtp.send_message(msg)


def main(dry_run: bool = False) -> None:
    """Run the full fetch -> classify -> filter -> alert pipeline."""
    result = run(persist=not dry_run)

    if dry_run:
        print(format_digest_text(result.new))
        print(f"\n({len(result.active)} active posting(s) total pass the score/level filter)")
        return

    if result.new:
        send_digest(result.new)
        print(f"Sent digest: {len(result.new)} new posting(s).")
    else:
        print("Scrape complete: no new postings found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest instead of emailing it, and don't write storage.json",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
