"""Quantity arithmetic — design doc section 16 calls for 100% coverage here."""
from __future__ import annotations

import math

import pint
import pytest

from framework import units
from framework.quantity import (
    INVARIANT,
    Constant,
    Quantity,
    RangeQuantity,
)
from framework.units import A, K, Ohm, V, degC, kOhm, mA, mV, registry

# ---------- construction ----------


class TestConstruction:
    def test_constant_scalar(self) -> None:
        q = Constant(3.3, V)
        assert q.at() == 3.3
        assert q.unit == V

    def test_constant_from_pint_expression(self) -> None:
        q = Constant(3.3 * V)
        assert q.at() == 3.3

    def test_constant_from_pint_in_different_unit_is_converted(self) -> None:
        q = Constant(3300 * mV, V)
        assert math.isclose(q.at(), 3.3)

    def test_constant_requires_unit_when_value_is_plain_number(self) -> None:
        with pytest.raises(TypeError):
            Constant(5.0)  # type: ignore[call-arg]

    def test_range_quantity(self) -> None:
        q = RangeQuantity(3.0, 3.6, V)
        assert q.at() == (3.0, 3.6)

    def test_range_collapses_when_lo_eq_hi(self) -> None:
        q = RangeQuantity(3.3, 3.3, V)
        assert q.at() == 3.3

    def test_range_lo_gt_hi_raises(self) -> None:
        with pytest.raises(ValueError):
            RangeQuantity(3.6, 3.0, V)

    def test_range_from_pint_with_explicit_unit(self) -> None:
        q = RangeQuantity(3000 * mV, 3.6 * V, V)
        lo, hi = q.at()
        assert math.isclose(lo, 3.0)
        assert math.isclose(hi, 3.6)

    def test_range_from_pint_infers_unit_from_lo(self) -> None:
        q = RangeQuantity(3000 * mV, 3.6 * V)
        lo, hi = q.at()
        # Inferred unit is mV (lo's unit); hi is converted to mV
        assert q.unit == mV
        assert math.isclose(lo, 3000.0)
        assert math.isclose(hi, 3600.0)

    def test_range_requires_unit_when_lo_is_plain(self) -> None:
        with pytest.raises(TypeError):
            RangeQuantity(3.0, 3.6)  # type: ignore[call-arg]

    def test_unit_must_be_pint_unit(self) -> None:
        with pytest.raises(TypeError):
            Quantity(unit="V", value=3.3)  # type: ignore[arg-type]

    def test_must_specify_at_least_one_axis(self) -> None:
        with pytest.raises(ValueError):
            Quantity(unit=V)

    def test_empty_by_scenario_rejected(self) -> None:
        with pytest.raises(ValueError):
            Quantity(unit=V, by_scenario={})

    def test_empty_by_mode_rejected(self) -> None:
        with pytest.raises(ValueError):
            Quantity(unit=V, by_mode={})

    def test_by_mode_child_must_be_quantity(self) -> None:
        with pytest.raises(TypeError):
            Quantity(unit=V, by_mode={"active": 3.3})  # type: ignore[dict-item]

    def test_by_mode_child_must_share_unit(self) -> None:
        with pytest.raises(ValueError):
            Quantity(unit=V, by_mode={"active": Constant(3.3, mV)})

    def test_by_scenario_and_by_mode_both_set_rejected(self) -> None:
        # The axes nest; scenario variation belongs *inside* each mode child,
        # not alongside by_mode. Setting both silently dropped the scenario data
        # before this guard — see C-6.
        with pytest.raises(ValueError, match="more than one"):
            Quantity(
                unit=V,
                by_mode={INVARIANT: Constant(75.0, V)},
                by_scenario={"hot": 100.0, "cold": 50.0},
            )

    def test_by_scenario_and_value_both_set_rejected(self) -> None:
        with pytest.raises(ValueError, match="more than one"):
            Quantity(unit=V, by_scenario={"hot": 100.0}, value=75.0)

    def test_by_mode_and_value_both_set_rejected(self) -> None:
        with pytest.raises(ValueError, match="more than one"):
            Quantity(unit=V, by_mode={INVARIANT: Constant(75.0, V)}, value=75.0)

    def test_by_mode_children_with_disjoint_scenario_keys_rejected(self) -> None:
        with pytest.raises(ValueError, match="scenario keys"):
            Quantity(
                unit=A,
                by_mode={
                    "active": Quantity(unit=A, by_scenario={"cold": 0.15}),
                    "sleep": Quantity(unit=A, by_scenario={"hot": 10e-6}),
                },
            )

    def test_by_mode_children_with_matching_scenario_keys_ok(self) -> None:
        q = Quantity(
            unit=A,
            by_mode={
                "active": Quantity(unit=A, by_scenario={"cold": 0.15, "hot": 0.18}),
                "sleep": Quantity(unit=A, by_scenario={"cold": 10e-6, "hot": 12e-6}),
            },
        )
        assert math.isclose(q.at(scenario="cold", mode="active"), 0.15)

    def test_by_mode_scenario_varying_mode_alongside_invariant_mode_ok(self) -> None:
        # The legitimate mixed case: active varies by scenario, sleep is flat.
        q = Quantity(
            unit=A,
            by_mode={
                "active": Quantity(unit=A, by_scenario={"cold": 0.15, "hot": 0.18}),
                "sleep": Constant(10e-6, A),
            },
        )
        assert math.isclose(q.at(scenario="hot", mode="sleep"), 10e-6)

    def test_by_mode_invariant_scenario_key_does_not_trigger_mismatch(self) -> None:
        # A child keyed only by INVARIANT opts out of the cross-mode check.
        q = Quantity(
            unit=A,
            by_mode={
                "active": Quantity(unit=A, by_scenario={"cold": 0.15, "hot": 0.18}),
                "sleep": Quantity(unit=A, by_scenario={INVARIANT: 10e-6}),
            },
        )
        assert math.isclose(q.at(scenario="cold", mode="sleep"), 10e-6)

    def test_by_scenario_pint_values_coerced(self) -> None:
        q = Quantity(unit=V, by_scenario={"nom": 3300 * mV, "max": 3.6 * V})
        assert math.isclose(q.at(scenario="nom"), 3.3)
        assert math.isclose(q.at(scenario="max"), 3.6)

    def test_range_tuple_wrong_length_rejected(self) -> None:
        with pytest.raises(ValueError):
            Quantity(unit=V, by_scenario={"nom": (3.0, 3.3, 3.6)})  # type: ignore[dict-item]

    def test_range_in_scenario_lo_gt_hi_rejected(self) -> None:
        with pytest.raises(ValueError):
            Quantity(unit=V, by_scenario={"nom": (3.6, 3.0)})

    def test_frozen(self) -> None:
        q = Constant(3.3, V)
        with pytest.raises((AttributeError, TypeError)):
            q.unit = mV  # type: ignore[misc]


# ---------- at() ----------


class TestAt:
    def test_invariant_scenario_falls_back(self) -> None:
        q = Quantity(unit=V, by_scenario={INVARIANT: 3.3})
        assert q.at(scenario="any") == 3.3
        assert q.at() == 3.3

    def test_named_scenario(self) -> None:
        q = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        assert q.at(scenario="hot") == 3.0
        assert q.at(scenario="cold") == 3.6

    def test_missing_scenario_raises(self) -> None:
        q = Quantity(unit=V, by_scenario={"hot": 3.0})
        with pytest.raises(KeyError):
            q.at(scenario="cold")

    def test_scenario_required_when_dependent(self) -> None:
        q = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        with pytest.raises(KeyError):
            q.at()

    def test_mode_evaluation(self) -> None:
        q = Quantity(
            unit=A,
            by_mode={
                "sleep": Constant(10e-6, A),
                "active": Constant(150e-3, A),
            },
        )
        assert q.at(mode="sleep") == 10e-6
        assert q.at(mode="active") == 150e-3

    def test_mode_required_when_dependent(self) -> None:
        q = Quantity(unit=A, by_mode={"sleep": Constant(10e-6, A)})
        with pytest.raises(KeyError):
            q.at()

    def test_missing_mode_raises(self) -> None:
        q = Quantity(unit=A, by_mode={"sleep": Constant(10e-6, A)})
        with pytest.raises(KeyError):
            q.at(mode="active")

    def test_mode_and_scenario_combined(self) -> None:
        q = Quantity(
            unit=A,
            by_mode={
                "sleep": Quantity(unit=A, by_scenario={"hot": 12e-6, "cold": 5e-6}),
                "active": Quantity(unit=A, by_scenario={"hot": 0.22, "cold": 0.08}),
            },
        )
        assert q.at(mode="sleep", scenario="hot") == 12e-6
        assert q.at(mode="active", scenario="cold") == 0.08


# ---------- str / repr ----------


class TestStr:
    def test_scalar(self) -> None:
        assert str(Constant(3.3, V)) == "3.3 V"

    def test_range(self) -> None:
        assert str(Quantity(unit=V, value=(3.0, 3.6))) == "[3.0, 3.6] V"

    def test_by_scenario(self) -> None:
        s = str(Quantity(unit=V, by_scenario={"cold": 3.0, "hot": 3.6}))
        assert s == "{cold: 3.0, hot: 3.6} V"

    def test_by_mode_nested(self) -> None:
        q = Quantity(unit=A, by_mode={
            "sleep":  Constant(7.5e-5, A),
            "active": Quantity(unit=A, by_scenario={"hot": 0.1, "cold": 0.05}),
        })
        assert str(q) == "{sleep: 7.5e-05, active: {hot: 0.1, cold: 0.05}} A"

    def test_repr_still_verbose_for_debugging(self) -> None:
        # __str__ is the human form; __repr__ stays the full dataclass form.
        r = repr(Constant(3.3, V))
        assert "Quantity(" in r and "unit=" in r and "provenance=" in r


# ---------- within / predicates ----------


class TestWithin:
    def test_scalar_inside(self) -> None:
        assert Constant(3.3, V).within(3.0 * V, 3.6 * V) is True

    def test_scalar_outside(self) -> None:
        assert Constant(3.8, V).within(3.0 * V, 3.6 * V) is False

    def test_range_fully_inside(self) -> None:
        assert RangeQuantity(3.1, 3.5, V).within(3.0 * V, 3.6 * V) is True

    def test_range_partially_outside(self) -> None:
        assert RangeQuantity(3.1, 3.7, V).within(3.0 * V, 3.6 * V) is False

    def test_within_across_scenarios(self) -> None:
        q = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        assert q.within(3.0 * V, 3.6 * V) is True
        assert q.within(3.0 * V, 3.5 * V) is False

    def test_within_across_modes_and_scenarios(self) -> None:
        q = Quantity(
            unit=V,
            by_mode={
                "active": Quantity(unit=V, by_scenario={"hot": 3.1, "cold": 3.5}),
                "diagnostic": Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6}),
            },
        )
        assert q.within(3.0 * V, 3.6 * V) is True
        assert q.within(3.1 * V, 3.6 * V) is False

    def test_within_accepts_framework_quantity_bound(self) -> None:
        # Useful for offset units (degC) where `125 * degC` raises in Pint.
        q = Quantity(unit=degC, by_scenario={"cold": -20.0, "hot": 110.0})
        assert q.within(Constant(-40.0, degC), Constant(125.0, degC)) is True
        assert q.within(Constant(-40.0, degC), Constant(100.0, degC)) is False

    def test_within_rejects_axed_bound(self) -> None:
        q = Constant(25.0, degC)
        bound_with_scenarios = Quantity(unit=degC, by_scenario={"a": 1.0, "b": 2.0})
        with pytest.raises(TypeError, match="scalar Quantity"):
            q.within(bound_with_scenarios, Constant(100.0, degC))

    def test_within_rejects_range_bound(self) -> None:
        q = Constant(25.0, degC)
        with pytest.raises(TypeError, match="not a range"):
            q.within(RangeQuantity(-5.0, 5.0, degC), Constant(100.0, degC))


# ---------- arithmetic: scalars ----------


class TestScalarArithmetic:
    def test_add(self) -> None:
        assert (Constant(1.0, V) + Constant(2.0, V)).at() == 3.0

    def test_sub(self) -> None:
        assert (Constant(3.0, V) - Constant(1.0, V)).at() == 2.0

    def test_mul(self) -> None:
        q = Constant(3.3, V) * Constant(2.0, mA)
        assert math.isclose(q.to(units.mW).at(), 6.6)

    def test_div(self) -> None:
        q = Constant(3.3, V) / Constant(1.5, mA)
        assert math.isclose(q.to(kOhm).at(), 2.2)

    def test_mul_by_plain_number_keeps_unit(self) -> None:
        # Regression for the 2026-05-16 _binop fix: Q(5 V) * 2 should be 10 V,
        # not 10 V² (the old code lifted bare numbers to left.unit for both
        # additive and multiplicative ops, squaring the dimension).
        q = Constant(5.0, V) * 2
        assert math.isclose(q.at(), 10.0)
        assert q.unit == V

    def test_div_by_plain_number_keeps_unit(self) -> None:
        q = Constant(10.0, V) / 2
        assert math.isclose(q.at(), 5.0)
        assert q.unit == V

    def test_mul_by_float_in_chain(self) -> None:
        # The original bug surface: a multi-step expression where a float
        # appears mid-chain.
        q = Constant(1.0, A) ** 2 * Constant(0.1, Ohm) * 1.0
        # I²·R = power in watts. 1² · 0.1 = 0.1 W.
        assert math.isclose(q.to(units.mW).at(), 100.0)

    def test_pow_int(self) -> None:
        q = Constant(2.0, V) ** 2
        assert math.isclose(q.at(), 4.0)
        assert q.unit == (registry.Quantity(1, V) ** 2).units

    def test_pow_negative(self) -> None:
        q = Constant(2.0, V) ** -1
        assert math.isclose(q.at(), 0.5)

    def test_pow_non_int_rejected(self) -> None:
        with pytest.raises(TypeError):
            Constant(2.0, V) ** 0.5  # type: ignore[operator]

    def test_neg(self) -> None:
        assert (-Constant(3.3, V)).at() == -3.3

    def test_add_incompatible_units(self) -> None:
        with pytest.raises(pint.DimensionalityError):
            Constant(1.0, V) + Constant(1.0, A)

    def test_add_with_unit_conversion(self) -> None:
        q = Constant(1.0, V) + Constant(500.0, mV)
        assert math.isclose(q.at(), 1.5)

    def test_rmul_dimensionless(self) -> None:
        q = 2 * Constant(3.3, V)
        assert math.isclose(q.at(), 6.6)

    def test_rtruediv_dimensionless(self) -> None:
        q = 6.6 / Constant(3.3, V)
        assert math.isclose(q.to(registry.parse_units("1/V")).at(), 2.0)

    def test_pint_on_left_raises_helpful_error(self) -> None:
        # pint.Quantity.__add__ does not honor NotImplemented for our type,
        # so `pint_q + framework_q` is not supported. Users should wrap the
        # pint value in Constant() first. The framework.units auto-lift sugar
        # (design doc 6.1) that would make `5 * V` return a Quantity directly
        # is deferred to a follow-on step.
        with pytest.raises(pint.DimensionalityError):
            (1.0 * V) + Constant(2.0, V)

    def test_constant_plus_pint_works_via_radd(self) -> None:
        # The supported direction: framework.Quantity is on one side and
        # plain numbers go through __radd__ / __rmul__ etc.
        q = Constant(2.0, V) + 1.0  # plain float lifted into V
        assert math.isclose(q.at(), 3.0)


# ---------- arithmetic: ranges (interval) ----------


class TestRangeArithmetic:
    def test_range_add(self) -> None:
        q = RangeQuantity(1.0, 2.0, V) + RangeQuantity(3.0, 4.0, V)
        assert q.at() == (4.0, 6.0)

    def test_range_sub_widens(self) -> None:
        # (a - d, b - c)  for [a,b] - [c,d]
        q = RangeQuantity(5.0, 10.0, V) - RangeQuantity(1.0, 2.0, V)
        assert q.at() == (3.0, 9.0)

    def test_range_mul_all_positive(self) -> None:
        q = RangeQuantity(2.0, 3.0, V) * RangeQuantity(4.0, 5.0, A)
        assert q.at() == (8.0, 15.0)

    def test_range_mul_straddles_zero(self) -> None:
        q = RangeQuantity(-1.0, 2.0, V) * RangeQuantity(-3.0, 4.0, A)
        # corners: -1*-3=3, -1*4=-4, 2*-3=-6, 2*4=8 -> (-6, 8)
        assert q.at() == (-6.0, 8.0)

    def test_range_div_positive(self) -> None:
        q = RangeQuantity(6.0, 12.0, V) / RangeQuantity(2.0, 3.0, A)
        # corners: 6/2=3, 6/3=2, 12/2=6, 12/3=4 -> (2, 6)
        assert q.at() == (2.0, 6.0)

    def test_range_div_by_zero_range_raises(self) -> None:
        with pytest.raises(ZeroDivisionError):
            RangeQuantity(1.0, 2.0, V) / RangeQuantity(-1.0, 1.0, A)

    def test_range_pow_squared(self) -> None:
        q = RangeQuantity(2.0, 3.0, V) ** 2
        assert q.at() == (4.0, 9.0)

    def test_scalar_plus_range(self) -> None:
        q = Constant(10.0, V) + RangeQuantity(1.0, 2.0, V)
        assert q.at() == (11.0, 12.0)


# ---------- arithmetic: scenarios ----------


class TestScenarioArithmetic:
    def test_add_aligned_scenarios(self) -> None:
        a = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        b = Quantity(unit=V, by_scenario={"hot": 0.1, "cold": 0.2})
        q = a + b
        assert q.at(scenario="hot") == 3.1
        assert math.isclose(q.at(scenario="cold"), 3.8)

    def test_scenario_plus_invariant(self) -> None:
        a = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        b = Quantity(unit=V, by_scenario={INVARIANT: 0.1})
        q = a + b
        assert q.at(scenario="hot") == 3.1
        assert math.isclose(q.at(scenario="cold"), 3.7)

    def test_scenario_plus_constant(self) -> None:
        a = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        q = a + Constant(0.1, V)
        assert q.at(scenario="hot") == 3.1
        assert math.isclose(q.at(scenario="cold"), 3.7)

    def test_disjoint_scenarios_rejected(self) -> None:
        a = Quantity(unit=V, by_scenario={"hot": 3.0})
        b = Quantity(unit=V, by_scenario={"cold": 3.6})
        with pytest.raises(ValueError):
            _ = a + b

    def test_subset_scenarios_with_invariant_fallback_aligns(self) -> None:
        # The narrower operand names only "cold" but carries an INVARIANT
        # fallback, so "hot" resolves to that fallback.
        a = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        b = Quantity(unit=V, by_scenario={"cold": 0.2, INVARIANT: 0.1})
        q = a + b
        assert math.isclose(q.at(scenario="cold"), 3.8)
        assert math.isclose(q.at(scenario="hot"), 3.1)  # uses INVARIANT

    def test_subset_scenarios_with_invariant_fallback_aligns_left_operand(self) -> None:
        # Same as above but with the narrower operand on the left, exercising
        # the a_keys <= b_keys branch of the alignment.
        a = Quantity(unit=V, by_scenario={"cold": 0.2, INVARIANT: 0.1})
        b = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        q = a + b
        assert math.isclose(q.at(scenario="cold"), 3.8)
        assert math.isclose(q.at(scenario="hot"), 3.1)  # uses INVARIANT

    def test_subset_scenarios_without_invariant_rejected(self) -> None:
        # Strict subset with no INVARIANT fallback: "hot" has no value. This
        # used to surface as a cryptic KeyError: '_ALL_' from `_pick`.
        a = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6})
        b = Quantity(unit=V, by_scenario={"cold": 0.2})
        with pytest.raises(ValueError, match="no value for scenario"):
            _ = a + b


# ---------- arithmetic: modes ----------


class TestModeArithmetic:
    def test_add_aligned_modes(self) -> None:
        a = Quantity(unit=A, by_mode={"sleep": Constant(10e-6, A), "active": Constant(0.15, A)})
        b = Quantity(unit=A, by_mode={"sleep": Constant(2e-6, A), "active": Constant(0.05, A)})
        q = a + b
        assert math.isclose(q.at(mode="sleep"), 12e-6)
        assert math.isclose(q.at(mode="active"), 0.20)

    def test_mode_plus_constant_broadcasts(self) -> None:
        a = Quantity(unit=A, by_mode={"sleep": Constant(10e-6, A), "active": Constant(0.15, A)})
        q = a + Constant(1e-6, A)
        assert math.isclose(q.at(mode="sleep"), 11e-6)
        assert math.isclose(q.at(mode="active"), 0.150001)

    def test_mode_plus_scenario_broadcasts(self) -> None:
        a = Quantity(unit=A, by_mode={"sleep": Constant(10e-6, A), "active": Constant(0.15, A)})
        b = Quantity(unit=A, by_scenario={"hot": 1e-6, "cold": 2e-6})
        q = a + b
        assert math.isclose(q.at(mode="sleep", scenario="hot"), 11e-6)
        assert math.isclose(q.at(mode="active", scenario="cold"), 0.150002)

    def test_disjoint_modes_rejected(self) -> None:
        a = Quantity(unit=A, by_mode={"sleep": Constant(10e-6, A)})
        b = Quantity(unit=A, by_mode={"active": Constant(0.15, A)})
        with pytest.raises(ValueError):
            _ = a + b


# ---------- unit conversion ----------


class TestToConversion:
    def test_to_compatible_unit_scales(self) -> None:
        q = Constant(1.0, V).to(mV)
        assert math.isclose(q.at(), 1000.0)
        assert q.unit == mV

    def test_to_same_unit_is_noop(self) -> None:
        q = Constant(1.0, V)
        assert q.to(V) is q

    def test_to_preserves_scenario(self) -> None:
        a = Quantity(unit=V, by_scenario={"hot": 3.0, "cold": 3.6}).to(mV)
        assert math.isclose(a.at(scenario="hot"), 3000.0)

    def test_to_preserves_mode(self) -> None:
        a = Quantity(unit=A, by_mode={"sleep": Constant(10e-6, A)}).to(mA)
        assert math.isclose(a.at(mode="sleep"), 0.01)

    def test_to_handles_offset_units_kelvin_to_celsius(self) -> None:
        # 358.15 K = 85.0 °C ; a factor-based conversion would mangle this.
        q = Constant(358.15, K).to(degC)
        assert math.isclose(q.at(), 85.0, abs_tol=1e-9)

    def test_to_handles_offset_units_celsius_to_kelvin(self) -> None:
        q = Constant(25.0, degC).to(K)
        assert math.isclose(q.at(), 298.15, abs_tol=1e-9)

    def test_to_handles_offset_with_scenarios(self) -> None:
        q = Quantity(unit=degC, by_scenario={
            "cold": -40.0, "nominal": 25.0, "hot": 85.0
        }).to(K)
        assert math.isclose(q.at(scenario="cold"), 233.15, abs_tol=1e-9)
        assert math.isclose(q.at(scenario="nominal"), 298.15, abs_tol=1e-9)
        assert math.isclose(q.at(scenario="hot"), 358.15, abs_tol=1e-9)


# ---------- end-to-end: ohm's law sanity ----------


def test_ohms_law_scenario_propagation() -> None:
    vin = Quantity(unit=V, by_scenario={"hot": 12.0, "cold": 14.0})
    r_load = Constant(1.0, kOhm)
    i = (vin / r_load).to(mA)
    assert math.isclose(i.at(scenario="hot"), 12.0)
    assert math.isclose(i.at(scenario="cold"), 14.0)


def test_power_dissipation_range_propagation() -> None:
    v_rds = RangeQuantity(0.02, 0.04, V)
    i = RangeQuantity(1.0, 2.0, A)
    p = (v_rds * i).to(units.mW)
    # corners: 0.02*1=0.02 V*A = 20 mW ; 0.04*2 = 0.08 V*A = 80 mW
    lo, hi = p.at()
    assert math.isclose(lo, 20.0)
    assert math.isclose(hi, 80.0)


# ---------- C-7: dimensionless-scaled auto-simplify ----------


class TestAutoSimplifyDimensionless:
    """Multiplicative ops auto-simplify dimensionless-scaled units (% / ppm) and
    dimensional ratios that cancel (m / cm). See _drop_scaled_dimensionless."""

    def test_v_times_percent_drops_percent(self) -> None:
        # 10 V × 120 % should be 12 V, not 1200 %·V.
        q = Constant(10.0, V) * Constant(120.0, units.percent)
        assert q.unit == V
        assert math.isclose(q.at(), 12.0)

    def test_percent_times_v_is_commutative(self) -> None:
        q = Constant(120.0, units.percent) * Constant(10.0, V)
        assert q.unit == V
        assert math.isclose(q.at(), 12.0)

    def test_range_times_percent(self) -> None:
        q = RangeQuantity(10.0, 16.0, V) * Constant(120.0, units.percent)
        assert q.unit == V
        lo, hi = q.at()
        assert math.isclose(lo, 12.0) and math.isclose(hi, 19.2)

    def test_percent_times_percent_is_plain_dimensionless(self) -> None:
        q = Constant(50.0, units.percent) * Constant(200.0, units.percent)
        assert q.unit == registry.dimensionless
        assert math.isclose(q.at(), 1.0)

    def test_by_scenario_times_percent(self) -> None:
        v = Quantity(unit=V, by_scenario={"cold": 3.0, "hot": 3.6})
        q = v * Constant(110.0, units.percent)
        assert q.unit == V
        assert math.isclose(q.at(scenario="cold"), 3.3)
        assert math.isclose(q.at(scenario="hot"), 3.96)

    def test_by_mode_times_percent_propagates_through_recursion(self) -> None:
        # Exercises the _simplify_output=False path through _combine_modes:
        # children must stay unit-consistent with the parent during recursion.
        v = Quantity(unit=V, by_mode={
            "sleep":  Constant(3.3, V),
            "active": Quantity(unit=V, by_scenario={"hot": 3.6, "cold": 3.0}),
        })
        q = v * Constant(90.0, units.percent)
        assert q.unit == V
        assert math.isclose(q.at(mode="sleep"), 2.97)
        assert math.isclose(q.at(mode="active", scenario="hot"), 3.24)

    def test_dimensional_ratio_collapses_to_dimensionless(self) -> None:
        # 2 m / 50 cm should be 4 (dimensionless), not 0.04 m/cm.
        q = Constant(2.0, registry.meter) / Constant(50.0, registry.centimeter)
        assert q.unit == registry.dimensionless
        assert math.isclose(q.at(), 4.0)

    def test_dimensional_ratio_collapse_propagates_through_by_mode(self) -> None:
        m_mode = Quantity(unit=registry.meter, by_mode={
            "x": Constant(1.0, registry.meter),
            "y": Constant(2.0, registry.meter),
        })
        q = m_mode / Constant(50.0, registry.centimeter)
        assert q.unit == registry.dimensionless
        assert math.isclose(q.at(mode="x"), 2.0)
        assert math.isclose(q.at(mode="y"), 4.0)

    def test_dimensional_product_NOT_simplified(self) -> None:
        # V × V is V², V × A is V·A — auto-simplify must not touch dimensional
        # products. Engineering convention on V·A vs W is the caller's call.
        q_vv = Constant(3.0, V) * Constant(2.0, V)
        assert q_vv.unit == V * V
        q_va = Constant(3.0, V) * Constant(2.0, A)
        assert q_va.unit == V * A

    def test_dimensionless_input_unchanged(self) -> None:
        # Plain dimensionless (not scaled) operand: just a multiplier, no
        # special path needed.
        q = Constant(5.0, V) * Constant(2.0, registry.dimensionless)
        assert q.unit == V
        assert math.isclose(q.at(), 10.0)
