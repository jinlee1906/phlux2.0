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


# Levels included by default when config.json has no "targets.levels" —
# internships/co-ops only. Widen this list (add "NEW_GRAD") by editing
# config.json; nothing else needs to change.
DEFAULT_TARGET_LEVELS = ["INTERNSHIP", "CO_OP"]


def load_target_levels(path: Path | str = DEFAULT_CONFIG_PATH) -> list[str]:
    """Return the ``Level`` names to keep, from ``config.json``'s ``targets.levels``."""
    return load_config(path).get("targets", {}).get("levels", DEFAULT_TARGET_LEVELS)


def load_target_regions(path: Path | str = DEFAULT_CONFIG_PATH) -> list[str]:
    """Return target regions for the scoring +2 location bonus (Phase 4d).

    Empty by default — the location bonus is a no-op until regions are set.
    """
    return load_config(path).get("targets", {}).get("regions", [])


# Countries a posting's location must match (or be ambiguous) to be kept.
# Defaults to US-only — widen by editing config.json's targets.countries.
DEFAULT_TARGET_COUNTRIES = ["US"]


def load_target_countries(path: Path | str = DEFAULT_CONFIG_PATH) -> list[str]:
    """Return allowed countries from ``config.json``'s ``targets.countries``."""
    return load_config(path).get("targets", {}).get("countries", DEFAULT_TARGET_COUNTRIES)


# Defaults for the Phase 4a scoring formula. half_life_days controls the
# recency decay; weights are the per-category multipliers in the S formula.
DEFAULT_SCORING_CONFIG: Dict[str, Any] = {
    "half_life_days": 14,
    "min_score": 0.0,
    "weights": {"core": 3, "sector": 1, "veto": -5, "location": 2},
}


def load_scoring_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Return scoring parameters from ``config.json``'s ``scoring`` section, defaulted."""
    scoring = load_config(path).get("scoring", {})
    merged = {**DEFAULT_SCORING_CONFIG, **scoring}
    merged["weights"] = {**DEFAULT_SCORING_CONFIG["weights"], **scoring.get("weights", {})}
    return merged


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

