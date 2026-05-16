"""Project + Hamilton integration tests."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from framework import (
    Constant,
    Project,
    Quantity,
    RangeQuantity,
)
from framework.scenarios import Scenario, ScenarioSet
from framework.modes import Mode, ModeSet
from framework.units import K, V, degC, mA, mW

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Project.load
# ---------------------------------------------------------------------------


class TestLoad:
    def test_from_paths(self) -> None:
        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        assert p.scenarios.names() == ["nominal", "cold_low_vin", "hot_high_vin", "rf_carrier_drift"]
        assert "active" in p.modes

    def test_from_already_loaded_sets(self) -> None:
        ss = ScenarioSet(scenarios=[Scenario(name="nom", context={"vbat": "12 V"})])
        ms = ModeSet(modes=[Mode(name="active")])
        p = Project.load(scenarios=ss, modes=ms)
        assert p.scenarios is ss
        assert p.modes is ms


# ---------------------------------------------------------------------------
# Standard inputs derived from scenarios
# ---------------------------------------------------------------------------


class TestStandardInputs:
    def test_includes_scenarios_and_modes(self) -> None:
        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        inputs = p.standard_inputs()
        assert inputs["scenarios"] is p.scenarios
        assert inputs["modes"] is p.modes

    def test_common_keys_extracted_as_quantities(self) -> None:
        # The fixture's three project-global scenarios all carry ambient_temp + vbat.
        # rf_carrier_drift also has those plus xtal_drift, so the intersection is
        # {ambient_temp, vbat}.
        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        inputs = p.standard_inputs()
        assert isinstance(inputs["ambient_temp"], Quantity)
        assert isinstance(inputs["vbat"], Quantity)
        # xtal_drift is only on rf_carrier_drift — not common, not extracted.
        assert "xtal_drift" not in inputs
        # Each extracted Quantity carries every scenario in by_scenario.
        assert set((inputs["vbat"].by_scenario or {}).keys()) == set(p.scenarios.names())

    def test_empty_scenarios_just_yields_pass_through(self) -> None:
        p = Project.load(
            scenarios=ScenarioSet(scenarios=[]),
            modes=ModeSet(modes=[]),
        )
        inputs = p.standard_inputs()
        assert set(inputs) == {"scenarios", "modes"}


# ---------------------------------------------------------------------------
# DAG execution against the sample block fixture
# ---------------------------------------------------------------------------


class TestRun:
    def test_simple_dag_executes_and_returns_quantities(self) -> None:
        from sample_block import analysis, leaves

        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        results = p.run(modules=[leaves, analysis], targets=["power", "t_j"])

        assert isinstance(results["power"], Quantity)
        assert isinstance(results["t_j"], Quantity)

        # power = 100 mA * (4.75 .. 5.25 V) -> (475 .. 525) mW
        lo, hi = results["power"].at()
        assert math.isclose(lo, 475.0, abs_tol=1e-6)
        assert math.isclose(hi, 525.0, abs_tol=1e-6)

    def test_t_j_carries_scenario_axis_from_project_input(self) -> None:
        # Verifies ambient_temp auto-extracted from scenarios flows through the DAG.
        from sample_block import analysis, leaves

        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        results = p.run(modules=[leaves, analysis], targets=["t_j"])

        t_j = results["t_j"]
        # t_j is in degC; ambient is in degC from scenarios.toml.
        # Worst-case rise = 525 mW * 80 K/W = 42 K, added to scenario ambient.
        hot_lo, hot_hi = t_j.at(scenario="hot_high_vin")
        # 85 + 38 = 123; 85 + 42 = 127
        assert math.isclose(hot_lo, 123.0, abs_tol=0.5)
        assert math.isclose(hot_hi, 127.0, abs_tol=0.5)

    def test_explicit_inputs_override_standard_inputs(self) -> None:
        from sample_block import analysis, leaves

        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        results = p.run(
            modules=[leaves, analysis],
            targets=["t_j"],
            inputs={"ambient_temp": Constant(0.0, degC)},
        )
        # 0 degC + (38..42) K rise = 38..42 degC, regardless of scenario.
        # With no scenario axis on ambient_temp, t_j has no scenario axis either.
        val = results["t_j"].at()
        assert isinstance(val, tuple)
        lo, hi = val
        assert math.isclose(lo, 38.0, abs_tol=0.5)
        assert math.isclose(hi, 42.0, abs_tol=0.5)

    def test_missing_target_raises_at_build_time(self) -> None:
        from sample_block import analysis, leaves

        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        with pytest.raises(Exception):
            # Hamilton wraps the missing-target error in its own exception type;
            # we just want to confirm something useful is raised.
            p.run(modules=[leaves, analysis], targets=["nonexistent_node"])

    def test_run_requires_modules(self) -> None:
        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        with pytest.raises(ValueError, match="at least one module"):
            p.run(modules=[], targets=["x"])

    def test_run_requires_targets(self) -> None:
        from sample_block import analysis, leaves

        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        with pytest.raises(ValueError, match="at least one target"):
            p.run(modules=[leaves, analysis], targets=[])

    def test_return_all_computed_includes_auto_augmented_contract_nodes(self) -> None:
        # Project.run auto-adds Contracts + compares_to + Quantity-valued
        # assumed_inputs to the execute set for the consistency checks, then
        # filters them out of the return. return_all_computed=True preserves
        # them so the design-review renderers see the full surface.
        from consistency_ok_block import contracts, leaves

        p = Project(
            scenarios=ScenarioSet(scenarios=[]),
            modes=ModeSet(modes=[]),
            cache_dir=None,
        )
        # Caller only asks for the Contract; compares_to actual was implicit.
        default_result = p.run(
            modules=[contracts, leaves],
            targets=["declared_ok"],
        )
        full_result = p.run(
            modules=[contracts, leaves],
            targets=["declared_ok"],
            return_all_computed=True,
        )
        assert set(default_result) == {"declared_ok"}
        assert "actual_draw" in full_result
        assert "declared_ok" in full_result


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


class TestListNodes:
    def test_lists_function_nodes(self) -> None:
        from sample_block import analysis, leaves

        p = Project.load(
            scenarios=FIXTURES / "scenarios.toml",
            modes=FIXTURES / "modes.toml",
        )
        nodes = p.list_nodes([leaves, analysis])
        # Function names from the two modules show up; sorted.
        for expected in ("i_supply", "v_supply", "r_theta", "power", "thermal_rise", "t_j"):
            assert expected in nodes
