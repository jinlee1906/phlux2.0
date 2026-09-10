"""Entry point: scrape companies, persist results, and send internship email alerts."""
from __future__ import annotations

import json
import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable, Dict, List

from phlux.config import load_config, load_email_config
from phlux.scraping import ScrapeManager, load_company_data
from phlux.utils import is_full_time, is_internship

logger = logging.getLogger(__name__)

# ── Email ─────────────────────────────────────────────────────────────────────

def _format_email_html(message: Dict[str, Any], filter_fn: Callable[[str], bool], heading: str) -> str:
    """Build an HTML email body, keeping only jobs that satisfy *filter_fn*."""
    lines = [f'<h1 style="font-family: monospace;">{heading}</h1>']
    lines.append('<hr style="margin-top: 30px; margin-bottom: 20px;">')

    for company, jobs_data in message.get("companies", {}).items():
        filtered = [
            job["title"].strip().replace("\n", " ")
            for job in jobs_data["jobs"]
            if filter_fn(job["title"])
        ]
        if not filtered:
            continue

        lines.append('<div style="margin-bottom: 30px;">')
        lines.append(
            f'<h2 style="margin-bottom: 5px; font-family: monospace;">{company}</h2>'
        )
        lines.append("<ul style='margin-top: 5px;'>")
        for title in filtered:
            lines.append(f"<li style='margin-bottom: 4px; font-family: monospace;'>{title}</li>")
        lines.append("</ul>")
        lines.append(
            f'<p><strong>🔗 <a style="font-family: monospace;" '
            f'href="{jobs_data["link"]}" target="_blank">Apply Here</a></strong></p>'
        )
        lines.append("</div>")
        lines.append('<hr style="margin-top: 20px; margin-bottom: 20px;">')

    lines.append(
        '<p style="font-family: monospace;">💻 View all companies at '
        '<a href="https://github.com/Ph1so/phlux2.0" target="_blank">'
        "github.com/Ph1so/phlux2.0</a></p>"
    )
    return "\n".join(lines)


def format_message_html(message: Dict[str, Any]) -> str:
    """Return the HTML body for the internship-alert email."""
    return _format_email_html(message, is_internship, "Internships from Phi")


def format_message_html_fulltime(message: Dict[str, Any]) -> str:
    """Return the HTML body for the full-time-role alert email."""
    return _format_email_html(message, is_full_time, "Full-Time Roles from Phi")


def _send_email_impl(
    message: Dict[str, Any],
    subject: str,
    bcc: List[str],
    format_fn: Callable[[Dict[str, Any]], str],
    test: bool,
    email_cfg: Dict[str, Any],
) -> None:
    """Build and send an email via Gmail SMTP."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_cfg["from"]
    msg["To"] = email_cfg["to"]
    if not test and bcc:
        msg["Bcc"] = ", ".join(bcc)

    msg.set_content("This email contains HTML. Please view it in an HTML-compatible client.")
    msg.add_alternative(format_fn(message), subtype="html")

    password = os.environ["GMAIL_APP_PASSWORD"]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_cfg["login"], password)
        smtp.send_message(msg)


def send_email(message: Dict[str, Any], test: bool = False) -> None:
    """Send the internship-alert email via Gmail SMTP."""
    email_cfg = load_email_config()
    _send_email_impl(
        message,
        subject="🚀 New Internship Alerts!",
        bcc=email_cfg["internship_bcc"],
        format_fn=format_message_html,
        test=test,
        email_cfg=email_cfg,
    )


def send_email_fulltime(message: Dict[str, Any], test: bool = False) -> None:
    """Send the full-time-role alert email via Gmail SMTP."""
    email_cfg = load_email_config()
    _send_email_impl(
        message,
        subject="💼 New Full-Time Role Alerts!",
        bcc=email_cfg["fulltime_bcc"],
        format_fn=format_message_html_fulltime,
        test=test,
        email_cfg=email_cfg,
    )


def has_internships(message: dict) -> bool:
    """Return True if any job in *message* matches internship / co-op keywords.

    Args:
        message: Same structured dict as accepted by :func:`send_email`.
    """
    return any(
        is_internship(job["title"])
        for company_data in message.get("companies", {}).values()
        for job in company_data.get("jobs", [])
    )


def has_full_time_roles(message: dict) -> bool:
    """Return True if any job in *message* is a full-time (non-internship) role."""
    return any(
        is_full_time(job["title"])
        for company_data in message.get("companies", {}).values()
        for job in company_data.get("jobs", [])
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the full scrape → store → alert pipeline."""
    load_config()
    manager = ScrapeManager()
    companies = load_company_data()
    result = manager.scrape_companies(companies=companies)

    Path("storage.json").write_text(json.dumps(result["data"], indent=2), encoding="utf-8")

    new_jobs = result["new_jobs"]
    if new_jobs.get("companies"):
        if has_internships(new_jobs):
            send_email(new_jobs, test=False)
        else:
            print("Scrape complete: no new internship/co-op positions found.")
        if not load_email_config()["fulltime_enabled"]:
            print("Full-time emails are disabled in config; skipping.")
        elif has_full_time_roles(new_jobs):
            send_email_fulltime(new_jobs, test=False)
        else:
            print("Scrape complete: no new full-time positions found.")
    else:
        print("Scrape complete: no new positions found.")


if __name__ == "__main__":
    main()
