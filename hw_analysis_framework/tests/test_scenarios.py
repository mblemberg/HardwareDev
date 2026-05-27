"""Scenario + TOML loader tests — covers happy path, validation, and error locations."""
from __future__ import annotations

import math
from pathlib import Path

import pydantic
import pytest

from framework import INVARIANT, Scenario, ScenarioSet, TomlError, load_scenarios
from framework.units import V, degC, ppm

FIXTURES = Path(__file__).parent / "fixtures"


# ---------- happy path ----------


class TestLoadFixture:
    def test_loads_all_scenarios(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        assert len(ss) == 4
        assert ss.names() == ["nominal", "cold_low_vin", "hot_high_vin", "rf_carrier_drift"]

    def test_pint_values_parsed_with_units(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        cold = ss.by_name("cold_low_vin")
        assert math.isclose(cold.context["vbat"].to(V).magnitude, 9.0)
        assert math.isclose(cold.context["ambient_temp"].to(degC).magnitude, -40.0)

    def test_owner_block_carries_through(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        assert ss.by_name("rf_carrier_drift").owner_block == "rf"
        assert ss.by_name("nominal").owner_block is None

    def test_description_optional(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        assert "Cold start" in ss.by_name("cold_low_vin").description

    def test_block_specific_field_parsed(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        rf = ss.by_name("rf_carrier_drift")
        # xtal_drift = "20 ppm" — dimensionless ratio
        assert rf.context["xtal_drift"].dimensionless
        # 20 ppm = 20e-6
        assert math.isclose(rf.context["xtal_drift"].to(ppm).magnitude, 20.0)


# ---------- ScenarioSet collection API ----------


class TestScenarioSet:
    def test_by_name_lookup(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        assert ss.by_name("nominal").name == "nominal"

    def test_by_name_missing_raises_helpful_keyerror(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        with pytest.raises(KeyError) as exc_info:
            ss.by_name("nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert "available" in str(exc_info.value)

    def test_contains(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        assert "nominal" in ss
        assert "nope" not in ss
        assert 42 not in ss  # non-string

    def test_iteration(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        names = [s.name for s in ss]
        assert names == ["nominal", "cold_low_vin", "hot_high_vin", "rf_carrier_drift"]

    def test_empty_set_constructs(self) -> None:
        ss = ScenarioSet(scenarios=[])
        assert len(ss) == 0
        assert ss.names() == []

    def test_duplicate_names_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            ScenarioSet(scenarios=[
                Scenario(name="nominal"),
                Scenario(name="nominal"),
            ])
        assert "duplicate" in str(exc_info.value).lower()


# ---------- Scenario validation ----------


class TestScenarioValidation:
    def test_reserved_invariant_name_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            Scenario(name=INVARIANT)
        assert "reserved" in str(exc_info.value).lower()

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Scenario(name="")

    def test_context_accepts_pint_quantity_directly(self) -> None:
        scen = Scenario(name="custom", context={"vbat": 9.0 * V})
        assert math.isclose(scen.context["vbat"].to(V).magnitude, 9.0)

    def test_context_accepts_pint_string(self) -> None:
        scen = Scenario(name="custom", context={"vbat": "9.0 V"})
        assert math.isclose(scen.context["vbat"].to(V).magnitude, 9.0)

    def test_context_rejects_bare_number(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            Scenario(name="custom", context={"vbat": 9.0})
        msg = str(exc_info.value)
        assert "Pint-format string" in msg
        assert "vbat" in msg

    def test_context_rejects_garbage_string(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            Scenario(name="custom", context={"vbat": "9.0 vlts"})
        assert "vbat" in str(exc_info.value)

    def test_scenario_is_frozen(self) -> None:
        scen = Scenario(name="custom")
        with pytest.raises(pydantic.ValidationError):
            scen.name = "other"  # type: ignore[misc]


# ---------- TOML loader error paths ----------


class TestLoadErrors:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(TomlError) as exc_info:
            load_scenarios(tmp_path / "nope.toml")
        assert "not found" in str(exc_info.value)

    def test_invalid_toml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text("this = is = not toml", encoding="utf-8")
        with pytest.raises(TomlError):
            load_scenarios(bad)

    def test_no_scenario_table_returns_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.toml"
        empty.write_text("# just a comment\n", encoding="utf-8")
        ss = load_scenarios(empty)
        assert len(ss) == 0

    def test_scenario_not_a_table_array(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text('scenario = "should be a table array"\n', encoding="utf-8")
        with pytest.raises(TomlError) as exc_info:
            load_scenarios(bad)
        assert "[[scenario]]" in str(exc_info.value)

    def test_scenario_missing_name(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text(
            "[[scenario]]\nambient_temp = \"25 degC\"\n", encoding="utf-8"
        )
        with pytest.raises(TomlError) as exc_info:
            load_scenarios(bad)
        assert "name" in str(exc_info.value).lower()

    def test_scenario_bad_unit_string_locates_field(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text(
            "[[scenario]]\nname = \"hot\"\nvbat = \"9.0 vlts\"\n", encoding="utf-8"
        )
        with pytest.raises(TomlError) as exc_info:
            load_scenarios(bad)
        msg = str(exc_info.value)
        assert "hot" in msg
        assert "vbat" in msg

    def test_scenario_bare_number_rejected_at_load(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text(
            "[[scenario]]\nname = \"hot\"\nvbat = 9.0\n", encoding="utf-8"
        )
        with pytest.raises(TomlError) as exc_info:
            load_scenarios(bad)
        msg = str(exc_info.value)
        assert "vbat" in msg
        assert "Pint" in msg

    def test_scenario_duplicate_names_in_file(self, tmp_path: Path) -> None:
        bad = tmp_path / "dup.toml"
        bad.write_text(
            "[[scenario]]\nname = \"nominal\"\n\n[[scenario]]\nname = \"nominal\"\n",
            encoding="utf-8",
        )
        with pytest.raises(TomlError) as exc_info:
            load_scenarios(bad)
        assert "duplicate" in str(exc_info.value).lower()


# ---------- integration sanity ----------


def test_loaded_quantities_arithmetic_through_pint() -> None:
    ss = load_scenarios(FIXTURES / "scenarios.toml")
    cold = ss.by_name("cold_low_vin")
    hot = ss.by_name("hot_high_vin")
    span = hot.context["vbat"] - cold.context["vbat"]
    assert math.isclose(span.to(V).magnitude, 7.0)


# ---------- as_quantity helper ----------


class TestAsQuantity:
    def test_pulls_key_across_all_carriers(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        vbat = ss.as_quantity("vbat")
        assert math.isclose(vbat.at(scenario="nominal"), 12.0)
        assert math.isclose(vbat.at(scenario="cold_low_vin"), 9.0)
        assert math.isclose(vbat.at(scenario="hot_high_vin"), 16.0)

    def test_target_unit_explicit_conversion(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        from framework.units import mV
        vbat = ss.as_quantity("vbat", unit=mV)
        assert vbat.unit == mV
        assert math.isclose(vbat.at(scenario="nominal"), 12_000.0)

    def test_only_carrying_scenarios_included(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        # `xtal_drift` is only on rf_carrier_drift
        drift = ss.as_quantity("xtal_drift")
        # Only that one scenario appears in by_scenario
        assert set(drift.by_scenario or {}) == {"rf_carrier_drift"}

    def test_missing_key_everywhere_raises(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        with pytest.raises(KeyError) as exc_info:
            ss.as_quantity("nonexistent")
        msg = str(exc_info.value)
        assert "nonexistent" in msg
        assert "available context keys" in msg

    def test_returned_quantity_is_arithmetic_compatible(self) -> None:
        ss = load_scenarios(FIXTURES / "scenarios.toml")
        vbat = ss.as_quantity("vbat")
        from framework import Constant
        from framework.units import Ohm
        i = vbat / Constant(100.0, Ohm)
        # i = vbat / 100 Ohm, so 9V/100 = 90 mA, etc.
        assert math.isclose(i.at(scenario="cold_low_vin"), 9.0 / 100.0)
