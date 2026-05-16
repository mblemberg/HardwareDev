"""Standard analyses library — design doc §14 step 11 (v1, very basic).

Reusable analytic forms an engineer would otherwise rewrite in every block.
Each function operates on framework Quantities and propagates scenario/mode
axes automatically via the existing arithmetic. Unit checks fire through
Pint as a free side effect.

v1 scope (deliberately small — extend on demand):
- :func:`voltage_divider` — classic R-divider, with list inputs for parallel
  resistor stacks.
- :func:`rc_filter_cutoff` — ``f_c = 1 / (2π RC)`` for a first-order RC filter.
- :func:`mosfet_thermal_rise` — junction temperature rise from a MOSFET's
  conduction losses (no switching losses; add those separately if needed).
- :func:`parallel_resistance` / :func:`series_resistance` — resistor
  combination helpers (used internally by :func:`voltage_divider`).
- :func:`parallel_capacitance` / :func:`series_capacitance` — capacitor
  combination helpers. Capacitors combine *opposite* to resistors:
  capacitors in parallel sum, capacitors in series reciprocal-sum.

Out of v1: ``worst_case_droop``, ``current_limit_check``,
``power_dissipation``, generic ``thermal_rise`` — land when a real project
needs them.
"""
from __future__ import annotations

import math
from typing import Sequence

from framework.quantity import Quantity
from framework.units import K, Hz


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


def parallel_capacitance(caps: Sequence[Quantity]) -> Quantity:
    """Equivalent capacitance of capacitors connected in parallel. ``C = sum(C_i)``.

    Caps combine *opposite* to resistors — parallel caps sum (more plate area),
    series caps reciprocal-sum (charge has to traverse both dielectrics).
    """
    if not caps:
        raise ValueError("parallel_capacitance requires at least one capacitor")
    if len(caps) == 1:
        return caps[0]
    total = caps[0]
    for c in caps[1:]:
        total = total + c
    return total


def series_capacitance(caps: Sequence[Quantity]) -> Quantity:
    """Equivalent capacitance in series. ``C = 1 / sum(1 / C_i)``."""
    if not caps:
        raise ValueError("series_capacitance requires at least one capacitor")
    if len(caps) == 1:
        return caps[0]
    inv = 1 / caps[0]
    for c in caps[1:]:
        inv = inv + 1 / c
    return 1 / inv


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


def rc_filter_cutoff(
    r: Quantity | Sequence[Quantity],
    c: Quantity | Sequence[Quantity],
) -> Quantity:
    """First-order RC filter cutoff: ``f_c = 1 / (2π R C)``.

    Applies to both the canonical low-pass (R in series, C to ground) and
    its high-pass dual (C in series, R to ground) — the cutoff frequency is
    the same. Returns Hz.

    ``r`` may be a single resistance Quantity or a list (combined in
    **parallel** — same convention as :func:`voltage_divider`). ``c`` may be
    a single capacitance or a list (combined in **parallel**, i.e. summed —
    the canonical "bulk + bypass" pattern).

    For unusual series stacks, pre-compose with :func:`series_resistance`
    or :func:`series_capacitance` and pass the result.
    """
    r_eq = parallel_resistance(list(r)) if isinstance(r, (list, tuple)) else r
    c_eq = parallel_capacitance(list(c)) if isinstance(c, (list, tuple)) else c
    return (1.0 / (2.0 * math.pi * r_eq * c_eq)).to(Hz)


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
    "parallel_capacitance",
    "parallel_resistance",
    "rc_filter_cutoff",
    "series_capacitance",
    "series_resistance",
    "voltage_divider",
]
