"""Standard analyses library (step 11 v1)."""
from __future__ import annotations

import math

import pint
import pytest

from framework import Constant, Quantity, RangeQuantity
from framework.analyses import (
    mosfet_thermal_rise,
    parallel_capacitance,
    parallel_resistance,
    rc_filter_cutoff,
    series_capacitance,
    series_resistance,
    voltage_divider,
)
from framework.units import A, V, W, K, Hz, kHz, mA, Ohm, kOhm, nF, uF


def _close(actual: float, expected: float, tol: float = 1e-9) -> bool:
    return math.isclose(actual, expected, rel_tol=tol, abs_tol=tol)


# ---------------------------------------------------------------------------
# parallel_resistance / series_resistance
# ---------------------------------------------------------------------------


class TestCombinationHelpers:
    def test_parallel_two_equal(self) -> None:
        r = parallel_resistance([Constant(10_000, Ohm), Constant(10_000, Ohm)])
        assert _close(float(r.at()), 5_000.0)

    def test_parallel_three_unequal(self) -> None:
        r = parallel_resistance([
            Constant(100.0, Ohm),
            Constant(200.0, Ohm),
            Constant(300.0, Ohm),
        ])
        # 1/(1/100 + 1/200 + 1/300) = 600 / 11 ≈ 54.545
        assert _close(float(r.at()), 600.0 / 11.0)

    def test_parallel_single_passthrough(self) -> None:
        r = parallel_resistance([Constant(47.0, Ohm)])
        assert r.at() == 47.0

    def test_parallel_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            parallel_resistance([])

    def test_series_sums(self) -> None:
        r = series_resistance([
            Constant(100.0, Ohm),
            Constant(200.0, Ohm),
            Constant(50.0, Ohm),
        ])
        assert _close(float(r.at()), 350.0)

    def test_series_propagates_ranges(self) -> None:
        # ±5% on each → ranges add per interval arithmetic
        r = series_resistance([
            RangeQuantity(95.0, 105.0, Ohm),
            RangeQuantity(95.0, 105.0, Ohm),
        ])
        lo, hi = r.at()
        assert _close(lo, 190.0)
        assert _close(hi, 210.0)

    def test_parallel_dimensional_check(self) -> None:
        with pytest.raises(pint.DimensionalityError):
            parallel_resistance([Constant(1.0, Ohm), Constant(1.0, V)])


# ---------------------------------------------------------------------------
# voltage_divider
# ---------------------------------------------------------------------------


class TestVoltageDivider:
    def test_scalar_inputs(self) -> None:
        # 5 V divided 10k / (10k + 10k) → 2.5 V
        v_out = voltage_divider(
            Constant(5.0, V), Constant(10_000.0, Ohm), Constant(10_000.0, Ohm)
        )
        assert _close(float(v_out.at()), 2.5)

    def test_unequal_legs(self) -> None:
        # 12 V across 30k top / 10k bot → 12 * 10k / 40k = 3 V
        v_out = voltage_divider(
            Constant(12.0, V), Constant(30_000.0, Ohm), Constant(10_000.0, Ohm)
        )
        assert _close(float(v_out.at()), 3.0)

    def test_top_list_parallels(self) -> None:
        # Two 20k in parallel = 10k → divider becomes 10k / 20k → 0.5
        v_out = voltage_divider(
            Constant(5.0, V),
            [Constant(20_000.0, Ohm), Constant(20_000.0, Ohm)],
            Constant(10_000.0, Ohm),
        )
        assert _close(float(v_out.at()), 2.5)

    def test_bottom_list_parallels(self) -> None:
        # Bottom: two 20k parallel = 10k. Same outcome as the scalar version.
        v_out = voltage_divider(
            Constant(5.0, V),
            Constant(10_000.0, Ohm),
            [Constant(20_000.0, Ohm), Constant(20_000.0, Ohm)],
        )
        assert _close(float(v_out.at()), 2.5)

    def test_both_legs_lists(self) -> None:
        # top: 2x 20k parallel = 10k; bottom: 3x 30k parallel = 10k → 0.5 ratio
        v_out = voltage_divider(
            Constant(5.0, V),
            [Constant(20_000.0, Ohm), Constant(20_000.0, Ohm)],
            [Constant(30_000.0, Ohm), Constant(30_000.0, Ohm), Constant(30_000.0, Ohm)],
        )
        assert _close(float(v_out.at()), 2.5)

    def test_propagates_input_range(self) -> None:
        v_out = voltage_divider(
            RangeQuantity(4.75, 5.25, V),
            Constant(10_000.0, Ohm),
            Constant(10_000.0, Ohm),
        )
        lo, hi = v_out.at()
        assert _close(lo, 2.375)
        assert _close(hi, 2.625)

    def test_dimensional_mismatch_raises(self) -> None:
        with pytest.raises(pint.DimensionalityError):
            voltage_divider(
                Constant(5.0, V),
                Constant(10_000.0, Ohm),
                Constant(10_000.0, V),  # wrong dimension
            )


# ---------------------------------------------------------------------------
# mosfet_thermal_rise
# ---------------------------------------------------------------------------


class TestMosfetThermalRise:
    def test_basic_conduction_loss(self) -> None:
        # 1 A through 100 mΩ → 0.1 W. 0.1 W * 100 K/W = 10 K rise.
        rise = mosfet_thermal_rise(
            i_drain=Constant(1.0, A),
            r_ds_on=Constant(0.1, Ohm),
            r_theta_ja=Constant(100.0, K / W),
        )
        assert _close(float(rise.at()), 10.0)

    def test_returns_kelvin(self) -> None:
        rise = mosfet_thermal_rise(
            i_drain=Constant(0.5, A),
            r_ds_on=Constant(0.05, Ohm),
            r_theta_ja=Constant(80.0, K / W),
        )
        assert rise.unit == K

    def test_duty_cycle_scales(self) -> None:
        # At 50% duty cycle the rise is half (linear in average power).
        full = mosfet_thermal_rise(
            i_drain=Constant(1.0, A),
            r_ds_on=Constant(0.1, Ohm),
            r_theta_ja=Constant(100.0, K / W),
        )
        half = mosfet_thermal_rise(
            i_drain=Constant(1.0, A),
            r_ds_on=Constant(0.1, Ohm),
            r_theta_ja=Constant(100.0, K / W),
            duty_cycle=0.5,
        )
        assert _close(float(half.at()), float(full.at()) / 2.0)

    def test_mode_axis_propagates(self) -> None:
        # I_D varies by mode → rise varies by mode.
        i_d = Quantity(unit=A, by_mode={
            "idle":   Constant(0.1, A),
            "active": Constant(1.0, A),
        })
        rise = mosfet_thermal_rise(
            i_drain=i_d,
            r_ds_on=Constant(0.1, Ohm),
            r_theta_ja=Constant(100.0, K / W),
        )
        # idle: 0.1^2 * 0.1 * 100 = 0.1 K; active: 1^2 * 0.1 * 100 = 10 K.
        assert _close(float(rise.at(mode="idle")), 0.1)
        assert _close(float(rise.at(mode="active")), 10.0)

    def test_range_propagates(self) -> None:
        # I_D in a range produces a range result via interval squaring.
        rise = mosfet_thermal_rise(
            i_drain=RangeQuantity(0.5, 1.5, A),
            r_ds_on=Constant(0.1, Ohm),
            r_theta_ja=Constant(100.0, K / W),
        )
        lo, hi = rise.at()
        # 0.5^2 * 0.1 * 100 = 2.5 K; 1.5^2 * 0.1 * 100 = 22.5 K.
        assert _close(lo, 2.5)
        assert _close(hi, 22.5)

    def test_dimensional_check(self) -> None:
        # Wrong R_DS_on unit (V instead of ohm) should error.
        with pytest.raises(pint.DimensionalityError):
            mosfet_thermal_rise(
                i_drain=Constant(1.0, A),
                r_ds_on=Constant(0.1, V),
                r_theta_ja=Constant(100.0, K / W),
            )


# ---------------------------------------------------------------------------
# framework.analyses as a submodule
# ---------------------------------------------------------------------------


class TestFrameworkSubmodule:
    def test_importable_as_submodule(self) -> None:
        from framework import analyses
        assert hasattr(analyses, "voltage_divider")
        assert hasattr(analyses, "mosfet_thermal_rise")
        assert hasattr(analyses, "rc_filter_cutoff")
        assert hasattr(analyses, "parallel_resistance")
        assert hasattr(analyses, "series_resistance")
        assert hasattr(analyses, "parallel_capacitance")
        assert hasattr(analyses, "series_capacitance")


# ---------------------------------------------------------------------------
# parallel_capacitance / series_capacitance
# ---------------------------------------------------------------------------


class TestCapacitanceHelpers:
    def test_parallel_caps_sum(self) -> None:
        # Caps in parallel: C = C1 + C2 + C3
        c = parallel_capacitance([
            Constant(10.0, uF),
            Constant(0.1, uF),    # bulk + bypass pattern
            Constant(0.01, uF),
        ])
        assert _close(float(c.at()), 10.11)

    def test_series_caps_reciprocal_sum(self) -> None:
        # 1/(1/10 + 1/10) = 5 uF for two 10 uF in series
        c = series_capacitance([Constant(10.0, uF), Constant(10.0, uF)])
        assert _close(float(c.at()), 5.0)

    def test_single_passthrough(self) -> None:
        assert parallel_capacitance([Constant(47.0, nF)]).at() == 47.0
        assert series_capacitance([Constant(47.0, nF)]).at() == 47.0

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            parallel_capacitance([])
        with pytest.raises(ValueError, match="at least one"):
            series_capacitance([])


# ---------------------------------------------------------------------------
# rc_filter_cutoff
# ---------------------------------------------------------------------------


class TestRcFilterCutoff:
    def test_scalar_inputs(self) -> None:
        # R = 1 kΩ, C = 1 µF → f_c = 1 / (2π · 1e3 · 1e-6) ≈ 159.155 Hz
        f = rc_filter_cutoff(Constant(1.0, kOhm), Constant(1.0, uF))
        assert _close(float(f.at()), 1 / (2 * math.pi * 1e3 * 1e-6))

    def test_returns_hz(self) -> None:
        f = rc_filter_cutoff(Constant(10.0, kOhm), Constant(10.0, nF))
        assert f.unit == Hz

    def test_higher_r_lowers_cutoff(self) -> None:
        # f ∝ 1/R: doubling R halves f_c
        f1 = rc_filter_cutoff(Constant(1.0, kOhm), Constant(1.0, uF))
        f2 = rc_filter_cutoff(Constant(2.0, kOhm), Constant(1.0, uF))
        assert _close(float(f2.at()), float(f1.at()) / 2.0)

    def test_caps_paralleled_when_list(self) -> None:
        # Three 1 µF in parallel = 3 µF; same as a single 3 µF cap.
        f_list = rc_filter_cutoff(
            Constant(1.0, kOhm),
            [Constant(1.0, uF), Constant(1.0, uF), Constant(1.0, uF)],
        )
        f_one = rc_filter_cutoff(Constant(1.0, kOhm), Constant(3.0, uF))
        assert _close(float(f_list.at()), float(f_one.at()))

    def test_resistors_paralleled_when_list(self) -> None:
        # Two 2 kΩ in parallel = 1 kΩ; same as single 1 kΩ
        f_list = rc_filter_cutoff(
            [Constant(2.0, kOhm), Constant(2.0, kOhm)],
            Constant(1.0, uF),
        )
        f_one = rc_filter_cutoff(Constant(1.0, kOhm), Constant(1.0, uF))
        assert _close(float(f_list.at()), float(f_one.at()))

    def test_propagates_tolerance_range(self) -> None:
        # R ±5%, C ±20% → f_c carries the propagated range.
        f = rc_filter_cutoff(
            RangeQuantity(950.0, 1050.0, Ohm),
            RangeQuantity(0.8, 1.2, uF),
        )
        lo, hi = f.at()
        # f_lo = 1/(2π · 1050 · 1.2e-6); f_hi = 1/(2π · 950 · 0.8e-6)
        expected_lo = 1 / (2 * math.pi * 1050.0 * 1.2e-6)
        expected_hi = 1 / (2 * math.pi * 950.0 * 0.8e-6)
        assert _close(lo, expected_lo, tol=1e-6)
        assert _close(hi, expected_hi, tol=1e-6)

    def test_dimensional_mismatch_raises(self) -> None:
        with pytest.raises(pint.DimensionalityError):
            rc_filter_cutoff(Constant(1.0, V), Constant(1.0, uF))
