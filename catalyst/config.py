"""Configuration loader for catalyst."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

# Fallback email settings used when config.json omits an "EMAIL" key (or a field
# within it). BCC lists default to empty so the email only goes to "to".
# "from"/"to"/"login" are never hardcoded here — they come from ALERT_EMAIL.
DEFAULT_EMAIL_CONFIG: Dict[str, Any] = {
    "internship_bcc_enabled": True,
    "internship_bcc": [],
    "fulltime_enabled": True,
    "fulltime_bcc": [],
}


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load JSON configuration from *path*."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_email_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Return email settings from the ``EMAIL`` section, filled with defaults.

    ``from``, ``to``, and ``login`` always come from the ``ALERT_EMAIL``
    environment variable — never from a tracked file. Missing fields in
    ``config.json`` otherwise fall back to :data:`DEFAULT_EMAIL_CONFIG`.
    ``internship_bcc`` and ``fulltime_bcc`` may be given as a list of
    addresses or a single comma-separated string.

    Raises:
        RuntimeError: If ``ALERT_EMAIL`` is not set in the environment.
    """
    alert_email = os.environ.get("ALERT_EMAIL")
    if not alert_email:
        raise RuntimeError("ALERT_EMAIL environment variable must be set")

    email = {
        "from": alert_email,
        "to": alert_email,
        "login": alert_email,
        **DEFAULT_EMAIL_CONFIG,
        **load_config(path).get("EMAIL", {}),
    }
    for key in ("internship_bcc", "fulltime_bcc"):
        value = email[key]
        if isinstance(value, str):
            email[key] = [addr.strip() for addr in value.split(",") if addr.strip()]
    # When disabled, keep the saved addresses in config but don't BCC them, so the
    # internship email only reaches "to". Flip the flag back to re-enable them.
    if not email["internship_bcc_enabled"]:
        email["internship_bcc"] = []
    return email

