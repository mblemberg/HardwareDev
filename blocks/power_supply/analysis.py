"""Power supply block — derived analyses (design doc 6.6).

The interesting derivation here is the total-load math: the PSU consumes
``can_5v_draw`` and ``mcu_5v_draw`` (downstream blocks' published
Contracts) and rolls them into total current, which combined with the
Vin/Vout drop drives LDO dissipation and junction temperature.

The cross-block dependency is allowed because consumed nodes are
Contracts (cycle-cut rule, design doc 6.7). The PSU does NOT reach into
the CAN or MCU block's internals — only their published bounds.
"""
from __future__ import annotations

from framework import Quantity
from framework.units import A, K, degC, mW


def psu_v_drop(vbat: Quantity, psu_v_out_actual: Quantity) -> Quantity:
    """LDO voltage drop = V_in - V_out.

    ``vbat`` is the project-supplied scenario context input (9 / 12 / 16
    V across the three scenarios); ``psu_v_out_actual`` is the leaf-level
    output envelope. Subtraction propagates the scenario axis.
    """
    return vbat - psu_v_out_actual


def psu_total_5v_load(can_5v_draw: Quantity, mcu_5v_draw: Quantity) -> Quantity:
    """Sum of all downstream loads on the 5V rail.

    Both inputs are downstream blocks' published Contracts (mode-keyed
    upper bounds). The sum carries the mode axis automatically.
    """
    return (can_5v_draw + mcu_5v_draw).to(A)


def psu_power_dissipation(
    psu_v_drop: Quantity, psu_total_5v_load: Quantity
) -> Quantity:
    """LDO dissipation = V_drop × I_total.

    A linear regulator dissipates the entire (Vin − Vout) × I — that's
    the LDO's defining inefficiency. Carries both scenario (from V_drop)
    and mode (from total load) axes.
    """
    return (psu_v_drop * psu_total_5v_load).to(mW)


def psu_thermal_rise(
    psu_power_dissipation: Quantity, psu_r_theta_ja: Quantity
) -> Quantity:
    """Junction-to-ambient thermal rise (P · R_θJA), in K."""
    return (psu_power_dissipation * psu_r_theta_ja).to(K)


def psu_t_j(ambient_temp: Quantity, psu_thermal_rise: Quantity) -> Quantity:
    """LDO junction temperature.

    Ambient (degC) → K first so thermal rise is added as a delta;
    convert back to degC for display.
    """
    return (ambient_temp.to(K) + psu_thermal_rise).to(degC)
