"""CAN transceiver — mode-dependent leaf Quantities (design doc 6.6).

Leaves are the hand-coded inputs the block author owns: datasheet currents,
component choices, mode-dependent state. They become the entry points of the
Hamilton DAG.
"""
from __future__ import annotations

from framework import Constant, Quantity, RangeQuantity, SupplyEnvelope
from framework.units import A, K, W, degC


def i_supply() -> Quantity:
    """Supply current per system mode, datasheet min/max ranges."""
    return Quantity(unit=A, by_mode={
        "off":        Constant(0.0, A),
        "sleep":      RangeQuantity(8e-6,  15e-6, A),
        "active":     RangeQuantity(45e-3, 65e-3, A),
        "diagnostic": RangeQuantity(70e-3, 90e-3, A),
    })


def v_supply(can_5v_rail: SupplyEnvelope) -> Quantity:
    """Sourced from project requirement REQ-PWR-005 (passed as DAG input)."""
    return RangeQuantity(can_5v_rail.min, can_5v_rail.max)


def r_theta_ja() -> Quantity:
    """Junction-to-ambient thermal resistance, SO-8 in still air (datasheet)."""
    return Constant(120.0, K / W)


def t_j_max() -> Quantity:
    """Junction-temperature derate: 25 C below the 150 C datasheet absolute max."""
    return Constant(125.0, degC)
