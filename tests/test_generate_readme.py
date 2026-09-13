"""Tests for generate_readme.py."""
import json
from unittest.mock import patch

from generate_readme import generate_readme, load_active_postings, write_history


def _posting(**overrides):
    defaults = dict(
        employer="Acme",
        title="Process Engineer",
        url="https://acme.com/jobs/1",
        location="Midland, MI",
        sector="SPECIALTY_CHEM",
        level="EXPERIENCED",
        score=3.0,
        tags=["process engineer"],
        first_seen="2026-01-01",
    )
    defaults.update(overrides)
    return defaults


class TestLoadActivePostings:
    def test_filters_below_min_score(self, tmp_path):
        storage_path = tmp_path / "storage.json"
        storage_path.write_text(
            json.dumps(
                {
                    "postings": {
                        "a": _posting(title="Good", score=3.0),
                        "b": _posting(title="Bad", score=-5.0),
                    }
                }
            ),
            encoding="utf-8",
        )
        scoring = {"min_score": 0.0, "half_life_days": 14, "weights": {}}
        with patch("generate_readme.load_scoring_config", return_value=scoring), \
             patch("generate_readme.load_target_levels", return_value=["EXPERIENCED"]):
            active = load_active_postings(storage_path)
        assert [p["title"] for p in active] == ["Good"]

    def test_filters_by_target_level(self, tmp_path):
        storage_path = tmp_path / "storage.json"
        storage_path.write_text(
            json.dumps(
                {
                    "postings": {
                        "a": _posting(title="Wanted", level="INTERNSHIP"),
                        "b": _posting(title="Unwanted", level="EXPERIENCED"),
                    }
                }
            ),
            encoding="utf-8",
        )
        scoring = {"min_score": 0.0, "half_life_days": 14, "weights": {}}
        with patch("generate_readme.load_scoring_config", return_value=scoring), \
             patch("generate_readme.load_target_levels", return_value=["INTERNSHIP"]):
            active = load_active_postings(storage_path)
        assert [p["title"] for p in active] == ["Wanted"]

    def test_filters_by_target_country(self, tmp_path):
        storage_path = tmp_path / "storage.json"
        storage_path.write_text(
            json.dumps(
                {
                    "postings": {
                        "a": _posting(title="Wanted", location="Pittsburgh, PA"),
                        "b": _posting(title="Unwanted", location="IRL - Carlow - Carlow"),
                    }
                }
            ),
            encoding="utf-8",
        )
        scoring = {"min_score": 0.0, "half_life_days": 14, "weights": {}}
        with patch("generate_readme.load_scoring_config", return_value=scoring), \
             patch("generate_readme.load_target_levels", return_value=["EXPERIENCED"]), \
             patch("generate_readme.load_target_countries", return_value=["US"]):
            active = load_active_postings(storage_path)
        assert [p["title"] for p in active] == ["Wanted"]

    def test_sorted_by_score_descending(self, tmp_path):
        storage_path = tmp_path / "storage.json"
        storage_path.write_text(
            json.dumps(
                {
                    "postings": {
                        "a": _posting(title="Low", score=1.0),
                        "b": _posting(title="High", score=5.0),
                    }
                }
            ),
            encoding="utf-8",
        )
        scoring = {"min_score": 0.0, "half_life_days": 14, "weights": {}}
        with patch("generate_readme.load_scoring_config", return_value=scoring), \
             patch("generate_readme.load_target_levels", return_value=["EXPERIENCED"]):
            active = load_active_postings(storage_path)
        assert [p["title"] for p in active] == ["High", "Low"]


class TestWriteHistory:
    def test_writes_one_json_object_per_line(self, tmp_path):
        path = tmp_path / "data" / "postings.ndjson"
        postings = [_posting(title="A"), _posting(title="B")]
        write_history(postings, path)
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["title"] == "A"
        assert json.loads(lines[1])["title"] == "B"

    def test_creates_parent_directory(self, tmp_path):
        path = tmp_path / "nested" / "data" / "postings.ndjson"
        write_history([_posting()], path)
        assert path.exists()


class TestGenerateReadme:
    def test_contains_posting_count(self):
        postings = [_posting(title="A"), _posting(title="B")]
        readme = generate_readme(postings)
        assert "2 highest-scoring of 2" in readme

    def test_contains_title_and_employer(self):
        readme = generate_readme([_posting(title="Process Engineer", employer="Dow")])
        assert "Process Engineer" in readme
        assert "Dow" in readme

    def test_deep_links_to_posting_url(self):
        readme = generate_readme([_posting(url="https://acme.com/jobs/42")])
        assert 'href="https://acme.com/jobs/42"' in readme

    def test_escapes_pipe_in_title(self):
        readme = generate_readme([_posting(title="Software | Hardware Engineer")])
        assert "\\|" in readme

    def test_uses_hash_link_when_url_missing(self):
        readme = generate_readme([_posting(url=None)])
        assert 'href="#"' in readme

    def test_caps_at_200_postings(self):
        postings = [_posting(title=f"Job {i}", score=float(i)) for i in range(210)]
        readme = generate_readme(postings)
        assert "200 highest-scoring of 210" in readme

    def test_empty_list_does_not_raise(self):
        readme = generate_readme([])
        assert "0 highest-scoring of 0" in readme
