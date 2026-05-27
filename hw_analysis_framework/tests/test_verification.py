"""@verification_test + TestResult + VerificationContext + runner (step 9a)."""
from __future__ import annotations

import types
from typing import Callable

import pytest

from framework import (
    INVARIANT,
    Constant,
    Quantity,
    RangeQuantity,
    ScenarioMode,
    Severity,
    TestResult,
    VerificationContext,
    collect_verification_tests,
    format_results,
    get_verification_meta,
    is_verification_test,
    run_verification_for_pytest,
    run_verifications,
    verification_test,
)
from framework.units import K, V, degC, mA


# ---------------------------------------------------------------------------
# Decorator wiring
# ---------------------------------------------------------------------------


class TestDecorator:
    def test_marks_function(self) -> None:
        @verification_test(name="dummy")
        def t(ctx) -> TestResult:
            return TestResult(name="dummy", passed=True)

        assert is_verification_test(t) is True
        meta = get_verification_meta(t)
        assert meta is not None
        assert meta.name == "dummy"
        assert meta.severity is Severity.CRITICAL  # default

    def test_undecorated_is_not_a_test(self) -> None:
        def t(ctx) -> TestResult:
            return TestResult(name="x", passed=True)

        assert is_verification_test(t) is False
        assert get_verification_meta(t) is None

    def test_metadata_captured(self) -> None:
        @verification_test(
            name="thermal",
            requirement="REQ-ENV-001",
            severity=Severity.WARNING,
            modes=["active", "diagnostic"],
            scenarios=["hot_high_vin"],
        )
        def t(ctx) -> TestResult:
            return TestResult(name="thermal", passed=True)

        meta = get_verification_meta(t)
        assert meta is not None
        assert meta.requirement == "REQ-ENV-001"
        assert meta.severity is Severity.WARNING
        assert meta.modes == ("active", "diagnostic")
        assert meta.scenarios == ("hot_high_vin",)

    def test_block_inferred_from_module(self) -> None:
        @verification_test(name="x")
        def t(ctx) -> TestResult:
            return TestResult(name="x", passed=True)

        # Force module to look like blocks.can_transceiver.verifications
        t.__module__ = "blocks.can_transceiver.verifications"
        # Re-decorate to capture the corrected block
        re_decorated = verification_test(name="x")(t)
        meta = get_verification_meta(re_decorated)
        assert meta is not None
        assert meta.block == "can_transceiver"


# ---------------------------------------------------------------------------
# TestResult / ScenarioMode
# ---------------------------------------------------------------------------


class TestResultShape:  # noqa: D101 — pytest class group
    __test__ = True  # explicit (overrides TestResult's __test__=False inheritance heuristic)

    def test_summary_pass(self) -> None:
        r = TestResult(name="x", passed=True)
        assert r.summary().startswith("PASS")
        assert "x" in r.summary()

    def test_summary_fail_lists_corners(self) -> None:
        r = TestResult(
            name="thermal",
            passed=False,
            failed_at=(ScenarioMode(scenario="hot_high_vin", mode="diagnostic"),),
        )
        s = r.summary()
        assert s.startswith("FAIL")
        assert "hot_high_vin" in s
        assert "diagnostic" in s

    def test_scenario_mode_str(self) -> None:
        assert str(ScenarioMode(scenario=None, mode=None)) == "(no axes)"
        assert "mode='active'" in str(ScenarioMode(mode="active"))
        # INVARIANT scenario is hidden in str output
        assert str(ScenarioMode(scenario=INVARIANT, mode="active")) == "mode='active'"


# ---------------------------------------------------------------------------
# VerificationContext
# ---------------------------------------------------------------------------


class TestVerificationContext:
    def test_quantity_lookup(self) -> None:
        results = {"foo": Constant(5.0, mA)}
        ctx = VerificationContext(results)
        q = ctx.quantity("foo")
        assert q.at() == 5.0

    def test_quantity_missing_raises(self) -> None:
        ctx = VerificationContext({})
        with pytest.raises(KeyError, match="foo"):
            ctx.quantity("foo")

    def test_quantity_wrong_type_raises(self) -> None:
        ctx = VerificationContext({"foo": 42})
        with pytest.raises(TypeError, match="expected Quantity"):
            ctx.quantity("foo")

    def test_assert_in_pass(self) -> None:
        ctx = VerificationContext({"x": Constant(50.0, mA)})
        r = ctx.assert_quantity_in(ctx.quantity("x"), 0.0, 100.0, name="x in [0,100]")
        assert r.passed is True
        assert r.failed_at == ()

    def test_assert_in_fail_records_corners(self) -> None:
        q = Quantity(unit=mA, by_mode={
            "sleep":  Constant(5.0, mA),
            "active": RangeQuantity(80.0, 260.0, mA),  # 260 > 220
        })
        ctx = VerificationContext({"x": q})
        r = ctx.assert_quantity_in(q, 0.0, 220.0, name="x ≤ 220 mA")
        assert r.passed is False
        assert len(r.failed_at) == 1
        assert r.failed_at[0].mode == "active"

    def test_assert_below_pass(self) -> None:
        ctx = VerificationContext({"x": Constant(100.0, degC)})
        r = ctx.assert_quantity_below(
            ctx.quantity("x"), Constant(125.0, degC), name="x ≤ 125 °C"
        )
        assert r.passed is True

    def test_assert_below_fail(self) -> None:
        q = Quantity(unit=degC, by_mode={
            "cold": Constant(25.0, degC),
            "hot":  Constant(141.7, degC),
        })
        ctx = VerificationContext({"x": q})
        r = ctx.assert_quantity_below(q, Constant(125.0, degC), name="x ≤ 125 °C")
        assert r.passed is False
        assert any(c.mode == "hot" for c in r.failed_at)

    def test_assert_above_fail(self) -> None:
        q = Quantity(unit=V, by_mode={"on": Constant(4.5, V)})
        ctx = VerificationContext({"x": q})
        r = ctx.assert_quantity_above(q, 4.75, name="x ≥ 4.75 V")
        assert r.passed is False
        assert r.failed_at[0].mode == "on"

    def test_severity_propagates_to_result(self) -> None:
        from framework.verification import VerificationMeta
        meta = VerificationMeta(name="x", severity=Severity.WARNING)
        ctx = VerificationContext({"x": Constant(5.0, mA)}, meta=meta)
        r = ctx.assert_quantity_below(ctx.quantity("x"), Constant(10.0, mA))
        assert r.severity is Severity.WARNING


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class TestRunner:
    def _mod(self, name: str) -> types.ModuleType:
        return types.ModuleType(name)

    def test_runs_all_tests(self) -> None:
        mod = self._mod("verif_mod")

        @verification_test(name="A")
        def test_a(ctx) -> TestResult:
            return ctx.assert_quantity_below(ctx.quantity("x"), 100.0)

        @verification_test(name="B")
        def test_b(ctx) -> TestResult:
            return ctx.assert_quantity_above(ctx.quantity("x"), 0.0)

        test_a.__module__ = "verif_mod"
        test_b.__module__ = "verif_mod"
        mod.test_a = test_a
        mod.test_b = test_b
        out = run_verifications([mod], {"x": Constant(50.0, mA)})
        assert set(out) == {"A", "B"}
        assert all(r.passed for r in out.values())

    def test_skips_non_tests(self) -> None:
        mod = self._mod("v2")

        def helper(ctx) -> TestResult:
            return TestResult(name="x", passed=True)

        helper.__module__ = "v2"
        mod.helper = helper
        out = run_verifications([mod], {})
        assert out == {}

    def test_duplicate_name_raises(self) -> None:
        mod = self._mod("v3")

        @verification_test(name="same")
        def a(ctx) -> TestResult:
            return TestResult(name="same", passed=True)

        @verification_test(name="same")
        def b(ctx) -> TestResult:
            return TestResult(name="same", passed=True)

        a.__module__ = "v3"
        b.__module__ = "v3"
        mod.a = a
        mod.b = b
        with pytest.raises(ValueError, match="Duplicate verification-test name"):
            run_verifications([mod], {})

    def test_wrong_return_raises(self) -> None:
        mod = self._mod("v4")

        @verification_test(name="bad")
        def t(ctx):  # type: ignore[no-untyped-def]
            return "not a TestResult"

        t.__module__ = "v4"
        mod.t = t
        with pytest.raises(TypeError, match="expected framework.TestResult"):
            run_verifications([mod], {})

    def test_skips_re_exports(self) -> None:
        # Function defined in another module but attached as an attribute
        # should not be picked up — only functions whose __module__ matches.
        mod_a = self._mod("v5a")
        mod_b = self._mod("v5b")

        @verification_test(name="lives_in_a")
        def t(ctx) -> TestResult:
            return TestResult(name="lives_in_a", passed=True)

        t.__module__ = "v5a"
        mod_a.t = t
        mod_b.t = t  # re-export
        # Only scan mod_b: t's __module__ != mod_b.__name__, so it's skipped.
        out = run_verifications([mod_b], {})
        assert out == {}


# ---------------------------------------------------------------------------
# format_results
# ---------------------------------------------------------------------------


class TestFormatResults:
    def test_empty(self) -> None:
        assert format_results({}) == "(no verification tests run)"

    def test_failures_first(self) -> None:
        pass_r = TestResult(name="A", passed=True)
        fail_r = TestResult(
            name="B", passed=False, failed_at=(ScenarioMode(mode="active"),),
        )
        out = format_results({"A": pass_r, "B": fail_r})
        lines = out.splitlines()
        assert lines[0].startswith("FAIL")
        assert lines[1].startswith("PASS")


# ---------------------------------------------------------------------------
# 9b: pytest helpers — collect + run_for_pytest
# ---------------------------------------------------------------------------


class TestCollect:
    def _mod(self, name: str) -> types.ModuleType:
        return types.ModuleType(name)

    def test_collects_all_in_stable_order(self) -> None:
        mod = self._mod("collect_test")

        @verification_test(name="zebra")
        def z(ctx) -> TestResult:
            return TestResult(name="zebra", passed=True)

        @verification_test(name="alpha")
        def a(ctx) -> TestResult:
            return TestResult(name="alpha", passed=True)

        z.__module__ = "collect_test"
        a.__module__ = "collect_test"
        mod.z = z
        mod.a = a
        out = collect_verification_tests([mod])
        # Sorted by (block, name); both share block "collect_test", so by name.
        names = [t.__verification_meta__.name for t in out]
        assert names == ["alpha", "zebra"]

    def test_skips_re_exports(self) -> None:
        mod_owner = self._mod("c_owner")
        mod_borrower = self._mod("c_borrower")

        @verification_test(name="lives_in_owner")
        def t(ctx) -> TestResult:
            return TestResult(name="lives_in_owner", passed=True)

        t.__module__ = "c_owner"
        mod_owner.t = t
        mod_borrower.t = t
        assert collect_verification_tests([mod_borrower]) == []


class TestRunForPytest:
    def _passing(self) -> Callable:
        @verification_test(name="p")
        def t(ctx) -> TestResult:
            return TestResult(name="p", passed=True)
        t.__module__ = "rfp"
        return t

    def _failing(self, severity: Severity) -> Callable:
        @verification_test(name="f", severity=severity, requirement="REQ-X")
        def t(ctx) -> TestResult:
            return TestResult(
                name="f", passed=False, severity=severity,
                failed_at=(ScenarioMode(mode="hot"),),
            )
        t.__module__ = "rfp"
        return t

    def test_pass_returns_result(self) -> None:
        r = run_verification_for_pytest(self._passing(), {})
        assert r.passed

    def test_critical_failure_calls_pytest_fail(self) -> None:
        with pytest.raises(pytest.fail.Exception, match=r"REQ-X.*hot"):
            run_verification_for_pytest(self._failing(Severity.CRITICAL), {})

    def test_warning_failure_calls_xfail(self) -> None:
        with pytest.raises(pytest.xfail.Exception):
            run_verification_for_pytest(self._failing(Severity.WARNING), {})

    def test_info_failure_calls_skip(self) -> None:
        with pytest.raises(pytest.skip.Exception):
            run_verification_for_pytest(self._failing(Severity.INFO), {})

    def test_non_test_function_rejected(self) -> None:
        def not_decorated(ctx) -> TestResult:  # type: ignore[no-untyped-def]
            return TestResult(name="x", passed=True)
        with pytest.raises(TypeError, match="not a @verification_test"):
            run_verification_for_pytest(not_decorated, {})
