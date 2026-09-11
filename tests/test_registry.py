"""Tests for catalyst/registry.py."""
import pytest
import yaml

from catalyst.models import ATS, Employer, Sector
from catalyst.registry import append_employer, load_employers, save_employers


def _dow(**overrides):
    defaults = dict(
        name="Dow",
        sector=Sector.SPECIALTY_CHEM,
        ats=ATS.WORKDAY,
        careers_url="https://corporate.dow.com/en-us/careers.html",
        ats_config={"tenant": "dow", "wd_host": "wd5", "site": "External"},
        hq_region="Midland, MI",
    )
    defaults.update(overrides)
    return Employer(**defaults)


def _basf(**overrides):
    defaults = dict(
        name="BASF",
        sector=Sector.SPECIALTY_CHEM,
        ats=ATS.SUCCESSFACTORS,
        careers_url="https://www.basf.com/us/en/careers.html",
        ats_config={},
        hq_region="Florham Park, NJ",
        enabled=False,
    )
    defaults.update(overrides)
    return Employer(**defaults)


class TestLoadEmployers:
    def test_parses_full_entry(self, tmp_path):
        path = tmp_path / "employers.yaml"
        path.write_text(
            yaml.safe_dump([
                {
                    "name": "Dow",
                    "sector": "SPECIALTY_CHEM",
                    "ats": "WORKDAY",
                    "careers_url": "https://corporate.dow.com/en-us/careers.html",
                    "ats_config": {"tenant": "dow", "wd_host": "wd5", "site": "External"},
                    "hq_region": "Midland, MI",
                    "enabled": True,
                }
            ]),
            encoding="utf-8",
        )
        employers = load_employers(path)
        assert len(employers) == 1
        employer = employers[0]
        assert employer.name == "Dow"
        assert employer.sector is Sector.SPECIALTY_CHEM
        assert employer.ats is ATS.WORKDAY
        assert employer.ats_config == {"tenant": "dow", "wd_host": "wd5", "site": "External"}
        assert employer.hq_region == "Midland, MI"
        assert employer.enabled is True

    def test_defaults_missing_ats_config_to_empty_dict(self, tmp_path):
        path = tmp_path / "employers.yaml"
        path.write_text(
            yaml.safe_dump([
                {
                    "name": "BASF",
                    "sector": "SPECIALTY_CHEM",
                    "ats": "SUCCESSFACTORS",
                    "careers_url": "https://www.basf.com/us/en/careers.html",
                }
            ]),
            encoding="utf-8",
        )
        employers = load_employers(path)
        assert employers[0].ats_config == {}
        assert employers[0].hq_region is None
        assert employers[0].enabled is True  # defaults to True when omitted

    def test_empty_file_returns_empty_list(self, tmp_path):
        path = tmp_path / "employers.yaml"
        path.write_text("", encoding="utf-8")
        assert load_employers(path) == []

    def test_raises_for_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_employers(tmp_path / "nonexistent.yaml")

    def test_raises_for_invalid_sector(self, tmp_path):
        path = tmp_path / "employers.yaml"
        path.write_text(
            yaml.safe_dump([{"name": "X", "sector": "NOT_A_SECTOR", "ats": "WORKDAY", "careers_url": "https://x.com"}]),
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            load_employers(path)


class TestSaveEmployers:
    def test_round_trips_through_load(self, tmp_path):
        path = tmp_path / "employers.yaml"
        save_employers([_dow(), _basf()], path)
        loaded = load_employers(path)
        assert {e.name for e in loaded} == {"Dow", "BASF"}

    def test_sorts_by_name(self, tmp_path):
        path = tmp_path / "employers.yaml"
        save_employers([_dow(name="Zinc Co"), _dow(name="Acme")], path)
        loaded = load_employers(path)
        assert [e.name for e in loaded] == ["Acme", "Zinc Co"]

    def test_preserves_disabled_flag(self, tmp_path):
        path = tmp_path / "employers.yaml"
        save_employers([_basf(enabled=False)], path)
        loaded = load_employers(path)
        assert loaded[0].enabled is False

    def test_writes_human_readable_yaml(self, tmp_path):
        path = tmp_path / "employers.yaml"
        save_employers([_dow()], path)
        text = path.read_text(encoding="utf-8")
        assert "name: Dow" in text
        assert "tenant: dow" in text


class TestAppendEmployer:
    def test_creates_file_when_missing(self, tmp_path):
        path = tmp_path / "employers.yaml"
        append_employer(_dow(), path)
        assert load_employers(path)[0].name == "Dow"

    def test_appends_to_existing_entries(self, tmp_path):
        path = tmp_path / "employers.yaml"
        save_employers([_dow()], path)
        append_employer(_basf(), path)
        names = {e.name for e in load_employers(path)}
        assert names == {"Dow", "BASF"}

    def test_raises_for_duplicate_name(self, tmp_path):
        path = tmp_path / "employers.yaml"
        save_employers([_dow()], path)
        with pytest.raises(ValueError, match="Dow"):
            append_employer(_dow(), path)

    def test_duplicate_check_is_case_insensitive(self, tmp_path):
        path = tmp_path / "employers.yaml"
        save_employers([_dow(name="Dow")], path)
        with pytest.raises(ValueError):
            append_employer(_dow(name="DOW"), path)
