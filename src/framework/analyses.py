"""Standard analyses library — design doc §14 step 11 (v1, very basic).

Reusable analytic forms an engineer would otherwise rewrite in every block.
Each function operates on framework Quantities and propagates scenario/mode
axes automatically via the existing arithmetic. Unit checks fire through
Pint as a free side effect.

v1 scope (deliberately small — extend on demand):
- :func:`voltage_divider` — classic R-divider, with list inputs for parallel
  resistor stacks.
- :func:`mosfet_thermal_rise` — junction temperature rise from a MOSFET's
  conduction losses (no switching losses; add those separately if needed).
- :func:`parallel_resistance` / :func:`series_resistance` — combination
  helpers, used internally by :func:`voltage_divider` and exposed for users
  who want to pre-compose stacks themselves.

Out of v1: ``rc_filter_cutoff``, ``worst_case_droop``, ``current_limit_check``,
``power_dissipation``, generic ``thermal_rise`` — land when a real project
needs them.
"""
from __future__ import annotations

from typing import Sequence

from framework.quantity import Quantity
from framework.units import K


def parallel_resistance(resistors: Sequence[Quantity]) -> Quantity:
    """Equivalent resistance of resistors connected in parallel.

    ``R = 1 / sum(1 / R_i)``. Pint enforces ohms throughout; mixing in a
    non-resistance Quantity raises ``DimensionalityError`` at the first
    division. Scenario/mode axes propagate per-Quantity.
    """
    if not resistors:
        raise ValueError("parallel_resistance requires at least one resistor")
    if len(resistors) == 1:
        return resistors[0]
    inv = 1 / resistors[0]
    for r in resistors[1:]:
        inv = inv + 1 / r
    return 1 / inv


def series_resistance(resistors: Sequence[Quantity]) -> Quantity:
    """Equivalent resistance of resistors connected in series. ``R = sum(R_i)``."""
    if not resistors:
        raise ValueError("series_resistance requires at least one resistor")
    if len(resistors) == 1:
        return resistors[0]
    total = resistors[0]
    for r in resistors[1:]:
        total = total + r
    return total


def voltage_divider(
    v_in: Quantity,
    r_top: Quantity | Sequence[Quantity],
    r_bottom: Quantity | Sequence[Quantity],
) -> Quantity:
    """Resistive voltage divider: ``V_out = V_in * R_bottom / (R_top + R_bottom)``.

    ``r_top`` and ``r_bottom`` may each be a single resistance Quantity or a
    list/tuple of resistance Quantities. Lists are combined in **parallel**
    — the common pattern when stacking resistors for power dissipation,
    tolerance averaging, or hitting non-standard values. For series stacks,
    pre-compose with :func:`series_resistance` and pass the result.

    Args:
        v_in: Source voltage at the top of the divider.
        r_top: Resistance from source to the divider tap (a Quantity or a
            list of Quantities to be paralleled).
        r_bottom: Resistance from the tap to ground (same shape).

    Returns:
        The divided voltage at the tap, in volts.
    """
    rt = parallel_resistance(list(r_top)) if isinstance(r_top, (list, tuple)) else r_top
    rb = parallel_resistance(list(r_bottom)) if isinstance(r_bottom, (list, tuple)) else r_bottom
    return v_in * rb / (rt + rb)


def mosfet_thermal_rise(
    i_drain: Quantity,
    r_ds_on: Quantity,
    r_theta_ja: Quantity,
    duty_cycle: Quantity | float = 1.0,
) -> Quantity:
    """Junction-temperature rise above ambient from MOSFET conduction losses.

    ``ΔT_JA = I_D² · R_DS(on) · D · R_θJA``. Switching losses are *not*
    modeled here — add a separate term for those when relevant (it dominates
    at high switching frequencies and isn't a one-line formula).

    Args:
        i_drain: Drain current (typically a Quantity carrying scenario/mode
            axes; the result inherits those).
        r_ds_on: On-state drain-source resistance from the datasheet
            (consider the temperature derating — pass an axed Quantity if
            you've modeled R_DS_on vs T_J).
        r_theta_ja: Junction-to-ambient thermal resistance (datasheet,
            possibly derated by PCB copper area).
        duty_cycle: Fraction of time the FET is conducting (0.0–1.0).
            Pass a Quantity carrying a mode axis for switched applications;
            defaults to 1.0 for always-on (e.g. low-side discrete switch).

    Returns:
        Temperature rise in kelvin (a delta — add to ambient to get T_J).
        Convert to ambient + this in your block; degC + K is misleading
        (see framework CLAUDE.md gotcha #2).
    """
    power = (i_drain ** 2) * r_ds_on * duty_cycle
    return (power * r_theta_ja).to(K)


__all__ = [
    "mosfet_thermal_rise",
    "parallel_resistance",
    "series_resistance",
    "voltage_divider",
]
