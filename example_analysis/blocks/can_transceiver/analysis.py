"""CAN transceiver — derived analyses (design doc 6.6).

Hamilton wires by parameter name. ``can_power`` consumes ``rail_5v`` —
the power supply block's published Contract — directly: the cycle-cut
rule (design doc 6.7) allows a non-Contract node like ``can_power`` to
read from another block's Contract, just not from another block's
internals. Cross-block voltage assumption is captured on the CAN's own
Contract via ``assumed_inputs={"rail_5v": ...}``.
"""
from __future__ import annotations

from framework import Quantity
from framework.units import K, degC, mW


def can_power(rail_5v: Quantity, can_i_supply: Quantity) -> Quantity:
    """Block supply power (V * I), in mW. Consumes the PSU's rail_5v Contract."""
    return (rail_5v * can_i_supply).to(mW)


def can_thermal_rise(can_power: Quantity, can_r_theta_ja: Quantity) -> Quantity:
    """Junction-to-ambient thermal rise (P * R_theta), in K."""
    return (can_power * can_r_theta_ja).to(K)


def can_t_j(ambient_temp: Quantity, can_thermal_rise: Quantity) -> Quantity:
    """Junction temperature.

    Converts ambient (in degC, from project scenarios) to K first so the
    additive thermal math treats the rise as a delta — Pint's offset-unit
    semantics say ``degC + K`` adds as two absolutes, which is wrong for
    thermal rise. Returns degC for display.
    """
    return (ambient_temp.to(K) + can_thermal_rise).to(degC)
