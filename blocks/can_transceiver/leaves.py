"""CAN transceiver — mode-dependent leaf Quantities (design doc 6.6).

Leaves are the hand-coded inputs the block author owns: which part is used,
which mode-dependent state to consume from it, what the block-local derates
look like. The actual datasheet values live on the typed component instance
(``components.instances.semiconductors.tja1051t_3.TJA1051T_3``) — leaves
read from that, so a datasheet revision updates exactly one place.
"""
from __future__ import annotations

from framework import Constant, Quantity, RangeQuantity, SupplyEnvelope
from framework.units import A, degC

from components.instances.semiconductors.tja1051t_3 import TJA1051T_3


def i_supply() -> Quantity:
    """Supply current per system mode, sourced from the TJA1051T/3 datasheet."""
    return Quantity(unit=A, by_mode=TJA1051T_3.supply_current_by_mode)


def v_supply(can_5v_rail: SupplyEnvelope) -> Quantity:
    """Sourced from project requirement REQ-PWR-005 (passed as DAG input).

    The chip's own tolerated rail window (``TJA1051T_3.supply_voltage_range``)
    happens to coincide with REQ-PWR-005 in this project. In a future step we'll
    add a verification test that asserts the project rail is contained within
    the part's tolerated window for every block that consumes the rail.
    """
    return RangeQuantity(can_5v_rail.min, can_5v_rail.max)


def r_theta_ja() -> Quantity:
    """Junction-to-ambient thermal resistance — datasheet."""
    assert TJA1051T_3.r_thermal_ja is not None
    return TJA1051T_3.r_thermal_ja


def t_j_max() -> Quantity:
    """Block-local derate: 25 C below the part's 150 C absolute max."""
    return Constant(125.0, degC)
