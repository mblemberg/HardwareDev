"""Requirement types + registry — coverage of construction, validation, and the registry API."""
from __future__ import annotations

import math
from collections.abc import Iterator

import pydantic
import pytest

from framework import (
    Constant,
    CurrentBudget,
    Performance,
    Quantity,
    RangeQuantity,
    SupplyEnvelope,
    TempRange,
    requirements,
)
from framework.units import A, Hz, V, degC, mA, ms, mV, percent, uA


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Every test starts with an empty registry."""
    requirements.clear()
    yield
    requirements.clear()


# ---------------------------------------------------------------------------
# TempRange
# ---------------------------------------------------------------------------


class TestTempRange:
    def test_basic_construction_via_constant(self) -> None:
        # Offset-unit friendly path: Constant(value, degC).
        t = TempRange(
            min=Constant(-40.0, degC),
            max=Constant(85.0, degC),
            req="REQ-ENV-001",
            description="Vehicle operating envelope",
        )
        assert math.isclose(t.min.to(degC).magnitude, -40.0)
        assert math.isclose(t.max.to(degC).magnitude, 85.0)
        assert t.req == "REQ-ENV-001"

    def test_string_input(self) -> None:
        t = TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-002")
        assert math.isclose(t.min.to(degC).magnitude, -40.0)
        assert math.isclose(t.max.to(degC).magnitude, 85.0)

    def test_kelvin_input(self) -> None:
        from framework.units import K
        # Mixing K and degC: dimensionality matches, conversion handled.
        t = TempRange(min=233.15 * K, max="85 degC", req="REQ-ENV-003")
        assert math.isclose(t.min.to(degC).magnitude, -40.0, abs_tol=1e-6)

    def test_min_gt_max_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            TempRange(min=Constant(85.0, degC), max=Constant(-40.0, degC), req="REQ-X")
        assert "min" in str(exc_info.value) and "max" in str(exc_info.value)

    def test_wrong_dimensionality_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            TempRange(min=12 * V, max=15 * V, req="REQ-X")
        assert "dimensionality" in str(exc_info.value).lower()

    def test_axed_quantity_rejected(self) -> None:
        bad = Quantity(unit=degC, by_scenario={"hot": 85.0, "cold": -40.0})
        with pytest.raises(pydantic.ValidationError) as exc_info:
            TempRange(min=bad, max=Constant(85.0, degC), req="REQ-X")
        assert "scalar" in str(exc_info.value).lower()

    def test_range_quantity_rejected_as_bound(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            TempRange(min=RangeQuantity(-40.0, -35.0, degC), max=Constant(85.0, degC), req="REQ-X")
        assert "scalar" in str(exc_info.value).lower()

    def test_unparseable_string_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            TempRange(min="-40 fahrennn", max="85 degC", req="REQ-X")


# ---------------------------------------------------------------------------
# SupplyEnvelope
# ---------------------------------------------------------------------------


class TestSupplyEnvelope:
    def test_basic_construction(self) -> None:
        s = SupplyEnvelope(
            nominal=12 * V, min=9 * V, max=16 * V,
            transient_min=6 * V, transient_max=40 * V,
            req="REQ-PWR-001",
            description="Vehicle 12V system",
        )
        assert math.isclose(s.nominal.to(V).magnitude, 12.0)
        assert s.transient_min is not None
        assert math.isclose(s.transient_min.to(V).magnitude, 6.0)
        assert s.transient_max is not None
        assert math.isclose(s.transient_max.to(V).magnitude, 40.0)

    def test_no_transients(self) -> None:
        s = SupplyEnvelope(nominal=3.3 * V, min=3.0 * V, max=3.6 * V, req="REQ-PWR-002")
        assert s.transient_min is None
        assert s.transient_max is None

    def test_string_input(self) -> None:
        s = SupplyEnvelope(nominal="12 V", min="9 V", max="16 V", req="REQ-PWR-003")
        assert math.isclose(s.nominal.to(V).magnitude, 12.0)

    def test_mixed_units_converted(self) -> None:
        # min in mV, others in V — dimensionality matches.
        s = SupplyEnvelope(nominal=3.3 * V, min=3000 * mV, max=3.6 * V, req="REQ-PWR-004")
        assert math.isclose(s.min.to(V).magnitude, 3.0)

    def test_nominal_outside_range_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            SupplyEnvelope(nominal=2.5 * V, min=3.0 * V, max=3.6 * V, req="REQ-X")
        assert "nominal" in str(exc_info.value).lower()

    def test_transient_min_above_min_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            SupplyEnvelope(
                nominal=12 * V, min=9 * V, max=16 * V,
                transient_min=10 * V,
                req="REQ-X",
            )
        assert "transient_min" in str(exc_info.value)

    def test_transient_max_below_max_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            SupplyEnvelope(
                nominal=12 * V, min=9 * V, max=16 * V,
                transient_max=14 * V,
                req="REQ-X",
            )
        assert "transient_max" in str(exc_info.value)

    def test_wrong_dimensionality_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            SupplyEnvelope(nominal=12 * A, min=9 * V, max=16 * V, req="REQ-X")


# ---------------------------------------------------------------------------
# CurrentBudget
# ---------------------------------------------------------------------------


class TestCurrentBudget:
    def test_basic(self) -> None:
        b = CurrentBudget(max=2 * mA, applies_to_mode="sleep", req="REQ-PWR-014")
        assert math.isclose(b.max.to(mA).magnitude, 2.0)
        assert b.applies_to_mode == "sleep"

    def test_without_mode(self) -> None:
        b = CurrentBudget(max=500 * mA, req="REQ-PWR-015")
        assert b.applies_to_mode is None

    def test_max_must_be_positive(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            CurrentBudget(max=0 * mA, req="REQ-X")
        assert "> 0" in str(exc_info.value)

    def test_string_input(self) -> None:
        b = CurrentBudget(max="2 mA", applies_to_mode="sleep", req="REQ-PWR-016")
        assert math.isclose(b.max.to(uA).magnitude, 2000.0)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_basic_construction(self) -> None:
        p = Performance(
            target=200 * ms,
            req="REQ-SYS-008",
            description="Boot time from cold start",
        )
        assert math.isclose(p.target.to(ms).magnitude, 200.0)
        assert p.tolerance is None

    def test_with_tolerance(self) -> None:
        p = Performance(target=2.5 * V, tolerance=25 * mV, req="REQ-AN-014")
        assert math.isclose(p.tolerance.to(mV).magnitude, 25.0)

    def test_tolerance_dimension_mismatch(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            Performance(target=2.5 * V, tolerance=25 * mA, req="REQ-X")
        assert "dimensionality" in str(exc_info.value).lower()

    def test_negative_tolerance_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            Performance(target=2.5 * V, tolerance=-25 * mV, req="REQ-X")
        assert "non-negative" in str(exc_info.value)

    def test_accepts_any_dimensionality(self) -> None:
        # Performance is the escape hatch — Hz, ms, percent, anything goes.
        Performance(target=100 * Hz, req="REQ-EMI-001")
        Performance(target=0.5 * percent, req="REQ-PERF-001a")

    def test_string_input(self) -> None:
        p = Performance(target="200 ms", req="REQ-SYS-009")
        assert math.isclose(p.target.to(ms).magnitude, 200.0)

    def test_scoped_to_scenario(self) -> None:
        p = Performance(
            target=0.5 * percent,
            req="REQ-PERF-001a",
            applies_to_scenario="nominal",
            description="ADC accuracy at 25 C",
        )
        assert p.applies_to_scenario == "nominal"
        assert p.applies_to_mode is None

    def test_scoped_to_mode_and_scenario(self) -> None:
        p = Performance(
            target=10 * uA,
            req="REQ-PWR-022",
            applies_to_mode="sleep",
            applies_to_scenario="cold_low_vin",
        )
        assert p.applies_to_mode == "sleep"
        assert p.applies_to_scenario == "cold_low_vin"

    def test_three_scenario_scoped_reqs_form_a_set(self) -> None:
        # The pattern: one Jama row per derate corner, each scoped to a scenario.
        a = Performance(target=0.5 * percent, req="REQ-PERF-001a", applies_to_scenario="nominal")
        b = Performance(target=1.0 * percent, req="REQ-PERF-001b", applies_to_scenario="hot_high_vin")
        c = Performance(target=0.8 * percent, req="REQ-PERF-001c", applies_to_scenario="cold_low_vin")
        # Three separate registrations; verifications can iterate by prefix.
        accuracy_reqs = [r for r in requirements.list_all() if r.req.startswith("REQ-PERF-001")]
        assert accuracy_reqs == [a, b, c]
        by_scenario = {r.applies_to_scenario: r.target.to(percent).magnitude for r in accuracy_reqs}
        assert by_scenario == {"nominal": 0.5, "hot_high_vin": 1.0, "cold_low_vin": 0.8}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_auto_register_on_construction(self) -> None:
        t = TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
        assert requirements.show("REQ-ENV-001") is t

    def test_list_all_sorted(self) -> None:
        TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-002")
        SupplyEnvelope(nominal=12 * V, min=9 * V, max=16 * V, req="REQ-PWR-001")
        CurrentBudget(max=2 * mA, req="REQ-PWR-014")
        ids = [r.req for r in requirements.list_all()]
        assert ids == ["REQ-ENV-002", "REQ-PWR-001", "REQ-PWR-014"]

    def test_show_missing_with_prefix_suggestions(self) -> None:
        SupplyEnvelope(nominal=12 * V, min=9 * V, max=16 * V, req="REQ-PWR-001")
        CurrentBudget(max=2 * mA, req="REQ-PWR-014")
        with pytest.raises(KeyError) as exc_info:
            requirements.show("REQ-PWR-999")
        msg = str(exc_info.value)
        assert "REQ-PWR-001" in msg
        assert "REQ-PWR-014" in msg

    def test_show_missing_no_prefix_match(self) -> None:
        TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
        with pytest.raises(KeyError) as exc_info:
            requirements.show("REQ-XXX-001")
        msg = str(exc_info.value)
        # No "REQ-XXX-*" exists, but we still surface the full list as fallback.
        assert "REQ-ENV-001" in msg

    def test_re_registration_with_same_content_is_idempotent(self) -> None:
        TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
        # Re-import (or re-eval) of the module produces the same instance values.
        TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
        assert len(requirements.list_all()) == 1

    def test_re_registration_with_different_content_rejected(self) -> None:
        TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
        with pytest.raises(ValueError, match="already registered"):
            TempRange(min="-40 degC", max="125 degC", req="REQ-ENV-001")

    def test_unregister(self) -> None:
        TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
        requirements.unregister("REQ-ENV-001")
        with pytest.raises(KeyError):
            requirements.show("REQ-ENV-001")

    def test_unregister_unknown_is_noop(self) -> None:
        requirements.unregister("REQ-NOPE-000")  # no exception

    def test_clear(self) -> None:
        TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
        SupplyEnvelope(nominal=12 * V, min=9 * V, max=16 * V, req="REQ-PWR-001")
        requirements.clear()
        assert requirements.list_all() == []


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def test_requirement_is_frozen() -> None:
    t = TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
    with pytest.raises(pydantic.ValidationError):
        t.req = "REQ-X"  # type: ignore[misc]


def test_unsupported_input_type_rejected() -> None:
    with pytest.raises(pydantic.ValidationError) as exc_info:
        TempRange(min=42, max="85 degC", req="REQ-X")  # bare int — no unit
    assert "must be a pint.Quantity" in str(exc_info.value)


def test_empty_req_id_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        TempRange(min="-40 degC", max="85 degC", req="")
