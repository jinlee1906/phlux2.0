"""Entry point: fetch every enabled employer, classify postings, and email a digest.

Run with --dry-run to see the scored digest printed to stdout without
sending mail or writing storage.json — safe to run repeatedly while testing.
"""
from __future__ import annotations

import argparse
import colorsys
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

# The user wants a "nothing new" email every day too, not silence — these
# make that email something worth opening instead of a dull null-result
# notice. One subject, one big-emoji "graphic", and one message line are
# each picked independently at random.
_EMPTY_SUBJECT_TEMPLATES = [
    "😴 Nothing new today, boss",
    "🦗 Crickets... zero new jobs today",
    "🕳️ Stared into the job void today. It stared back.",
    "🌵 Tumbleweeds rolling through job land",
    "😅 Your minions came back empty-handed",
    "🧊 Ice cold out there — nothing new today",
    "🎣 Went fishing for jobs, caught nothing",
    "🫠 A whole lot of nothing today",
]

_EMPTY_GRAPHICS = ["🦗🦗🦗", "🌵💨🌵", "🤷", "😴💤💤", "🕸️👻🕸️", "🎣🐟❌", "🫠", "🛸❓"]

_EMPTY_MESSAGES = [
    "Nothing new found today. The chemical engineering job market is taking a nap.",
    "Zero new postings. Even the minions are surprised.",
    "The scrape ran, the postings were checked, and... nothing. Try again tomorrow.",
    "No fresh jobs today. Go touch some grass (or a reactor).",
    "Quiet day out there. Nothing new to report.",
]


def _complementary_background(accent_hex: str) -> str:
    """Return a pale background tint whose hue is complementary (180°
    opposite) to *accent_hex* on the color wheel.

    The complement is computed at full saturation/lightness first (so the
    hue relationship is a true complementary pair), then lightened way up
    and desaturated down for background use — a raw, fully-saturated
    complementary color makes a fine accent but an unreadable full-page
    background behind default-black body text.
    """
    accent_hex = accent_hex.lstrip("#")
    r, g, b = (int(accent_hex[i : i + 2], 16) / 255 for i in (0, 2, 4))
    hue, _lightness, _saturation = colorsys.rgb_to_hls(r, g, b)

    complementary_hue = (hue + 0.5) % 1.0
    bg_r, bg_g, bg_b = colorsys.hls_to_rgb(complementary_hue, 0.93, 0.55)
    return "#{:02x}{:02x}{:02x}".format(round(bg_r * 255), round(bg_g * 255), round(bg_b * 255))


def _group_by_sector(postings: List[Posting]) -> Dict[str, List[Posting]]:
    """Group *postings* by sector, each group sorted by score descending."""
    by_sector: Dict[str, List[Posting]] = {}
    for posting in postings:
        by_sector.setdefault(posting.sector.value, []).append(posting)
    for group in by_sector.values():
        group.sort(key=lambda p: p.score, reverse=True)
    return by_sector


def format_digest_html(
    postings: List[Posting],
    accent_color: str = "#111827",
    background_color: str = "#ffffff",
) -> str:
    """Build the HTML digest body: grouped by sector, capped, deep-linked.

    *accent_color* tints the headers/rule/links; *background_color* fills
    the page behind everything — send_digest() picks a random accent color
    each send and derives background_color as its complement, purely for
    fun.
    """
    if not postings:
        graphic = random.choice(_EMPTY_GRAPHICS)
        message = random.choice(_EMPTY_MESSAGES)
        return (
            f'<div style="background-color: {background_color}; padding: 24px; text-align: center;">'
            f'<div style="font-size: 64px; margin-bottom: 16px;">{graphic}</div>'
            f'<h1 style="font-family: monospace; color: {accent_color};">No New Postings Today</h1>'
            f'<p style="font-family: monospace;">{message}</p>'
            "</div>"
        )

    total = len(postings)
    by_sector = _group_by_sector(postings[:_MAX_DIGEST_POSTINGS])

    lines = [f'<div style="background-color: {background_color}; padding: 24px;">']
    lines.append(
        f'<h1 style="font-family: monospace; color: {accent_color};">'
        f'{total} New Posting{"s" if total != 1 else ""}</h1>'
    )
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

    lines.append("</div>")
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
    Sends every day, even with zero new postings — see _EMPTY_SUBJECT_TEMPLATES
    / _EMPTY_GRAPHICS / _EMPTY_MESSAGES for that case.

    The subject line and HTML accent color are both picked at random each
    send (see _SUBJECT_TEMPLATES / _ACCENT_COLORS), and the background is
    derived as the accent color's complement — cosmetic only, the actual
    count and content are never affected.
    """
    email_cfg = load_email_config()
    msg = EmailMessage()
    if postings:
        subject_template = random.choice(_SUBJECT_TEMPLATES)
        msg["Subject"] = subject_template.format(n=len(postings), s="s" if len(postings) != 1 else "")
    else:
        msg["Subject"] = random.choice(_EMPTY_SUBJECT_TEMPLATES)
    msg["From"] = email_cfg["from"]
    msg["To"] = email_cfg["to"]

    accent_color = random.choice(_ACCENT_COLORS)
    background_color = _complementary_background(accent_color)
    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(
        format_digest_html(postings, accent_color=accent_color, background_color=background_color),
        subtype="html",
    )

    password = os.environ["GMAIL_APP_PASSWORD"]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_cfg["login"], password)
        smtp.send_message(msg)


def main(dry_run: bool = False) -> None:
    """Run the full fetch -> classify -> filter -> alert pipeline.

    Sends a digest every live run, even with zero new postings — the user
    wants a daily email regardless, not silence on quiet days.
    """
    result = run(persist=not dry_run)

    if dry_run:
        print(format_digest_text(result.new))
        print(f"\n({len(result.active)} active posting(s) total pass the score/level filter)")
        return

    send_digest(result.new)
    print(f"Sent digest: {len(result.new)} new posting(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the digest instead of emailing it, and don't write storage.json",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
