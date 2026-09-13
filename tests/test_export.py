"""Tests for scripts/export.py."""
import csv
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from export import COLUMNS, export  # noqa: E402


def _posting(**overrides):
    defaults = dict(
        employer="Acme",
        title="Process Engineer",
        location="Midland, MI",
        sector="SPECIALTY_CHEM",
        level="EXPERIENCED",
        score=3.0,
        url="https://acme.com/jobs/1",
        first_seen="2026-01-01",
    )
    defaults.update(overrides)
    return defaults


def test_writes_header_and_rows(tmp_path):
    output_path = tmp_path / "postings.csv"
    with patch("export.load_active_postings", return_value=[_posting()]):
        count = export(output_path)

    assert count == 1
    with output_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["employer"] == "Acme"
    assert rows[0]["title"] == "Process Engineer"
    assert rows[0]["score"] == "3.0"


def test_columns_match_expected_order(tmp_path):
    output_path = tmp_path / "postings.csv"
    with patch("export.load_active_postings", return_value=[_posting()]):
        export(output_path)
    with output_path.open(encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert header == COLUMNS


def test_creates_parent_directory(tmp_path):
    output_path = tmp_path / "nested" / "postings.csv"
    with patch("export.load_active_postings", return_value=[]):
        export(output_path)
    assert output_path.exists()


def test_empty_postings_writes_header_only(tmp_path):
    output_path = tmp_path / "postings.csv"
    with patch("export.load_active_postings", return_value=[]):
        count = export(output_path)
    assert count == 0
    with output_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows == []


def test_missing_field_defaults_to_empty_string(tmp_path):
    output_path = tmp_path / "postings.csv"
    incomplete = {"employer": "Acme", "title": "Process Engineer"}
    with patch("export.load_active_postings", return_value=[incomplete]):
        export(output_path)
    with output_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["location"] == ""
