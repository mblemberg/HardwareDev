"""Mode + TOML loader tests."""
from __future__ import annotations

from pathlib import Path

import pydantic
import pytest

from framework import INVARIANT, Mode, ModeSet, TomlError, load_modes

FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadFixture:
    def test_loads_all_modes(self) -> None:
        ms = load_modes(FIXTURES / "modes.toml")
        assert ms.names() == ["off", "sleep", "active", "diagnostic", "calibration"]

    def test_descriptions_present(self) -> None:
        ms = load_modes(FIXTURES / "modes.toml")
        assert "RTC" in ms.by_name("sleep").description


class TestModeSet:
    def test_by_name(self) -> None:
        ms = load_modes(FIXTURES / "modes.toml")
        assert ms.by_name("active").name == "active"

    def test_by_name_missing(self) -> None:
        ms = load_modes(FIXTURES / "modes.toml")
        with pytest.raises(KeyError) as exc_info:
            ms.by_name("nope")
        assert "nope" in str(exc_info.value)
        assert "available" in str(exc_info.value)

    def test_contains(self) -> None:
        ms = load_modes(FIXTURES / "modes.toml")
        assert "active" in ms
        assert "nope" not in ms
        assert 42 not in ms

    def test_iteration_and_len(self) -> None:
        ms = load_modes(FIXTURES / "modes.toml")
        assert len(ms) == 5
        assert [m.name for m in ms] == ms.names()

    def test_empty_modeset(self) -> None:
        ms = ModeSet(modes=[])
        assert len(ms) == 0

    def test_duplicate_names_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ModeSet(modes=[Mode(name="sleep"), Mode(name="sleep")])
        assert "duplicate" in str(exc_info.value).lower()


class TestModeValidation:
    def test_reserved_invariant_name_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Mode(name=INVARIANT)

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Mode(name="")

    def test_mode_is_frozen(self) -> None:
        m = Mode(name="active")
        with pytest.raises(pydantic.ValidationError):
            m.name = "other"  # type: ignore[misc]


class TestLoadErrors:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(TomlError) as exc_info:
            load_modes(tmp_path / "nope.toml")
        assert "not found" in str(exc_info.value)

    def test_invalid_toml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text("not = = toml", encoding="utf-8")
        with pytest.raises(TomlError):
            load_modes(bad)

    def test_no_mode_table_returns_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.toml"
        empty.write_text("# nothing here\n", encoding="utf-8")
        ms = load_modes(empty)
        assert len(ms) == 0

    def test_mode_not_a_table_array(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text('mode = "wrong shape"\n', encoding="utf-8")
        with pytest.raises(TomlError) as exc_info:
            load_modes(bad)
        assert "[[mode]]" in str(exc_info.value)

    def test_mode_missing_name(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text("[[mode]]\ndescription = \"x\"\n", encoding="utf-8")
        with pytest.raises(TomlError) as exc_info:
            load_modes(bad)
        assert "name" in str(exc_info.value).lower()

    def test_mode_unknown_keys_rejected(self, tmp_path: Path) -> None:
        # Modes are simple (name + description). A stray key probably means
        # the engineer is trying to declare scenario-style context here.
        bad = tmp_path / "bad.toml"
        bad.write_text(
            "[[mode]]\nname = \"sleep\"\nvbat = \"9 V\"\n", encoding="utf-8"
        )
        with pytest.raises(TomlError) as exc_info:
            load_modes(bad)
        assert "unknown" in str(exc_info.value).lower()
        assert "vbat" in str(exc_info.value)

    def test_mode_duplicate_names_in_file(self, tmp_path: Path) -> None:
        bad = tmp_path / "dup.toml"
        bad.write_text(
            "[[mode]]\nname = \"sleep\"\n\n[[mode]]\nname = \"sleep\"\n",
            encoding="utf-8",
        )
        with pytest.raises(TomlError) as exc_info:
            load_modes(bad)
        assert "duplicate" in str(exc_info.value).lower()
