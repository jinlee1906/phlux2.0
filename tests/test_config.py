"""Tests for catalyst/config.py."""
import json

import pytest

from catalyst.config import (
    DEFAULT_SCORING_CONFIG,
    DEFAULT_TARGET_LEVELS,
    load_config,
    load_scoring_config,
    load_target_levels,
    load_target_regions,
)


def test_load_config_returns_dict(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"EMAIL": {}}', encoding="utf-8")
    result = load_config(cfg)
    assert isinstance(result, dict)


def test_load_config_returns_expected_keys(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"EMAIL": {"to": "a@b.com"}}),
        encoding="utf-8",
    )
    result = load_config(cfg)
    assert "EMAIL" in result


def test_load_config_accepts_string_path(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"key": "value"}', encoding="utf-8")
    result = load_config(str(cfg))
    assert result == {"key": "value"}


def test_load_config_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.json")


def test_load_config_raises_for_invalid_json(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("not valid json {{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_config(cfg)


# ── load_target_levels ──────────────────────────────────────────────────────────

def test_load_target_levels_reads_config(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"targets": {"levels": ["INTERNSHIP"]}}), encoding="utf-8")
    assert load_target_levels(cfg) == ["INTERNSHIP"]


def test_load_target_levels_defaults_to_internship_and_co_op(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    assert load_target_levels(cfg) == DEFAULT_TARGET_LEVELS
    assert load_target_levels(cfg) == ["INTERNSHIP", "CO_OP"]


def test_load_target_levels_defaults_when_targets_present_but_no_levels(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"targets": {}}), encoding="utf-8")
    assert load_target_levels(cfg) == DEFAULT_TARGET_LEVELS


def test_real_config_json_defaults_to_internship_and_co_op():
    # The shipped config.json must not silently widen to NEW_GRAD/EXPERIENCED.
    assert load_target_levels() == ["INTERNSHIP", "CO_OP"]


# ── load_target_regions ─────────────────────────────────────────────────────────

def test_load_target_regions_reads_config(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"targets": {"regions": ["Gulf Coast"]}}), encoding="utf-8")
    assert load_target_regions(cfg) == ["Gulf Coast"]


def test_load_target_regions_defaults_to_empty(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    assert load_target_regions(cfg) == []


# ── load_scoring_config ──────────────────────────────────────────────────────────

def test_load_scoring_config_defaults(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    assert load_scoring_config(cfg) == DEFAULT_SCORING_CONFIG


def test_load_scoring_config_overrides_half_life(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"scoring": {"half_life_days": 30}}), encoding="utf-8")
    result = load_scoring_config(cfg)
    assert result["half_life_days"] == 30
    assert result["weights"] == DEFAULT_SCORING_CONFIG["weights"]  # untouched keys still default


def test_load_scoring_config_merges_partial_weights(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"scoring": {"weights": {"core": 5}}}), encoding="utf-8")
    result = load_scoring_config(cfg)
    assert result["weights"]["core"] == 5
    assert result["weights"]["veto"] == -5  # unspecified weight still defaults


def test_real_config_json_has_expected_scoring_defaults():
    assert load_scoring_config() == DEFAULT_SCORING_CONFIG
