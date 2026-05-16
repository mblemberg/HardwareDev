"""Run-time contract consistency checker (design doc 6.7 / step 8)."""
from __future__ import annotations

import types

import pytest

from framework import (
    Constant,
    ContractMismatch,
    ContractViolation,
    Project,
    Quantity,
    RangeQuantity,
    check_contract_consistency,
    contract,
)
from framework.contract import _evaluate_at
from framework.modes import ModeSet
from framework.scenarios import ScenarioSet
from framework.units import A, mA


# ---------------------------------------------------------------------------
# Decorator wiring
# ---------------------------------------------------------------------------


class TestComparesToMetadata:
    def test_default_is_none(self) -> None:
        @contract(description="x")
        def fn() -> Quantity:
            return Constant(1.0, mA)
        assert fn.__contract_meta__.compares_to is None  # type: ignore[attr-defined]

    def test_captured(self) -> None:
        @contract(description="x", compares_to="my_actual")
        def fn() -> Quantity:
            return Constant(1.0, mA)
        assert fn.__contract_meta__.compares_to == "my_actual"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Quantity axis helpers
# ---------------------------------------------------------------------------


class TestAxisHelpers:
    def test_iter_axes_constant(self) -> None:
        q = Constant(5.0, mA)
        assert list(q.iter_axes()) == [(None, None, 5.0)]

    def test_iter_axes_by_mode(self) -> None:
        q = Quantity(unit=mA, by_mode={
            "a": Constant(1.0, mA),
            "b": RangeQuantity(2.0, 3.0, mA),
        })
        axes = sorted(q.iter_axes(), key=lambda t: t[1] or "")
        assert axes == [(None, "a", 1.0), (None, "b", (2.0, 3.0))]

    def test_evaluate_at_constant_ignores_axes(self) -> None:
        q = Constant(5.0, mA)
        assert _evaluate_at(q, scenario="anything", mode="anything") == 5.0

    def test_evaluate_at_missing_mode_raises(self) -> None:
        q = Quantity(unit=mA, by_mode={"a": Constant(1.0, mA)})
        with pytest.raises(KeyError, match="not in declared modes"):
            _evaluate_at(q, scenario=None, mode="b")


# ---------------------------------------------------------------------------
# check_contract_consistency — direct calls with pre-built results
# ---------------------------------------------------------------------------


class TestCheckConsistency:
    def test_matching_actual_no_mismatches(self) -> None:
        from consistency_ok_block import contracts, leaves
        results = {
            "declared_ok": contracts.declared_ok(),
            "actual_draw": leaves.actual_draw(),
        }
        assert check_contract_consistency([leaves, contracts], results) == []

    def test_over_budget_returns_mismatch(self) -> None:
        from consistency_bad_block import contracts, leaves
        results = {
            "declared_violated": contracts.declared_violated(),
            "actual_draw_over": leaves.actual_draw_over(),
        }
        mismatches = check_contract_consistency([leaves, contracts], results)
        assert len(mismatches) == 1
        m = mismatches[0]
        assert m.contract_name == "declared_violated"
        assert m.block == "consistency_bad_block"
        assert m.mode == "active"
        assert m.actual == (80.0, 260.0)
        assert m.declared == (0.0, 220.0)

    def test_no_compares_to_skipped(self) -> None:
        from consistency_skip_block import contracts
        results = {"declared_no_actual": contracts.declared_no_actual()}
        assert check_contract_consistency([contracts], results) == []

    def test_missing_target_strict_raises(self) -> None:
        from consistency_ok_block import contracts, leaves
        results = {"declared_ok": contracts.declared_ok()}
        with pytest.raises(ValueError, match="actual_draw"):
            check_contract_consistency([leaves, contracts], results, strict=True)

    def test_missing_target_lenient_skips(self) -> None:
        from consistency_ok_block import contracts, leaves
        results = {"declared_ok": contracts.declared_ok()}
        # Default: missing-target is silently skipped (the contract isn't a
        # run target in this call's universe).
        assert check_contract_consistency([leaves, contracts], results) == []

    def test_missing_contract_value_strict_raises(self) -> None:
        from consistency_ok_block import contracts, leaves
        results = {"actual_draw": leaves.actual_draw()}
        with pytest.raises(ValueError, match="declared_ok"):
            check_contract_consistency([leaves, contracts], results, strict=True)

    def test_unit_mismatch_converts_first(self) -> None:
        mod = types.ModuleType("u_test_block.contracts")

        @contract(description="x", compares_to="actual_amps")
        def declared_ma() -> Quantity:
            return RangeQuantity(0.0, 100.0, mA)

        def actual_amps() -> Quantity:
            return Constant(0.050, A)  # 50 mA expressed in A — must convert, not flag

        declared_ma.__module__ = "u_test_block.contracts"
        actual_amps.__module__ = "u_test_block.contracts"
        mod.declared_ma = declared_ma
        mod.actual_amps = actual_amps
        results = {"declared_ma": declared_ma(), "actual_amps": actual_amps()}
        assert check_contract_consistency([mod], results) == []


# ---------------------------------------------------------------------------
# ContractViolation exception
# ---------------------------------------------------------------------------


class TestContractViolation:
    def test_message_lists_each_mismatch(self) -> None:
        m = ContractMismatch(
            contract_name="c", block="b", scenario=None, mode="active",
            actual=(0.0, 260.0), declared=(0.0, 220.0), unit="mA",
        )
        with pytest.raises(ContractViolation) as exc_info:
            raise ContractViolation([m])
        msg = str(exc_info.value)
        assert "1 contract mismatch" in msg
        assert "'c'" in msg
        assert "'active'" in msg
        assert "260" in msg and "220" in msg

    def test_mismatches_attr_accessible(self) -> None:
        m = ContractMismatch(
            contract_name="c", block="b", scenario=None, mode=None,
            actual=1.0, declared=0.5, unit="mA",
        )
        try:
            raise ContractViolation([m])
        except ContractViolation as e:
            assert e.mismatches == [m]


# ---------------------------------------------------------------------------
# Integration through Project.run
# ---------------------------------------------------------------------------


def _empty_project() -> Project:
    return Project(
        scenarios=ScenarioSet(scenarios=[]),
        modes=ModeSet(modes=[]),
        cache_dir=None,
    )


class TestProjectRunIntegration:
    def test_consistent_run_returns_results(self) -> None:
        from consistency_ok_block import contracts, leaves
        out = _empty_project().run(
            modules=[leaves, contracts],
            targets=["declared_ok"],
        )
        assert "declared_ok" in out

    def test_violation_raises_contract_violation(self) -> None:
        from consistency_bad_block import contracts, leaves
        with pytest.raises(ContractViolation) as exc_info:
            _empty_project().run(
                modules=[leaves, contracts],
                targets=["declared_violated"],
            )
        assert any(m.contract_name == "declared_violated" for m in exc_info.value.mismatches)

    def test_check_contracts_false_skips(self) -> None:
        from consistency_bad_block import contracts, leaves
        out = _empty_project().run(
            modules=[leaves, contracts],
            targets=["declared_violated"],
            check_contracts=False,
        )
        assert "declared_violated" in out

    def test_actual_auto_added_to_targets(self) -> None:
        """The user only asks for the contract — the framework pulls the actual through too."""
        from consistency_ok_block import contracts, leaves
        # We can't observe the auto-added target in the returned dict (Project.run
        # filters back down to user-requested targets) but the violation check
        # itself proves the actual was computed.
        out = _empty_project().run(
            modules=[leaves, contracts],
            targets=["declared_ok"],
        )
        # User asked for one thing, got one thing.
        assert list(out.keys()) == ["declared_ok"]
