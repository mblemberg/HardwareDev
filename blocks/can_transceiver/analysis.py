"""CAN transceiver — derived analyses (design doc 6.6).

Hamilton wires these by parameter name: ``power(v_supply, i_supply)`` pulls
the ``v_supply`` and ``i_supply`` nodes (defined in ``leaves.py``); ``t_j``
pulls the framework-supplied ``ambient_temp`` plus our local ``thermal_rise``.
"""
from __future__ import annotations

from framework import Quantity
from framework.units import K, degC, mW


def power(v_supply: Quantity, i_supply: Quantity) -> Quantity:
    """Block supply power (V * I), in mW."""
    return (v_supply * i_supply).to(mW)


def thermal_rise(power: Quantity, r_theta_ja: Quantity) -> Quantity:
    """Junction-to-ambient thermal rise (P * R_theta), in K."""
    return (power * r_theta_ja).to(K)


def t_j(ambient_temp: Quantity, thermal_rise: Quantity) -> Quantity:
    """Junction temperature.

    Converts ambient (in degC, from project scenarios) to K first so the
    additive thermal math treats the rise as a delta — Pint's offset-unit
    semantics say ``degC + K`` adds as two absolutes, which is wrong for
    thermal rise. Returns degC for display.
    """
    return (ambient_temp.to(K) + thermal_rise).to(degC)
