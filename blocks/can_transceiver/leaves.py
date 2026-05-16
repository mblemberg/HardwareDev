"""CAN transceiver — mode-dependent leaf Quantities (design doc 6.6).

Leaves are the hand-coded inputs the block author owns: which part is used,
which mode-dependent state to consume from it, what the block-local derates
look like. The actual datasheet values live on the typed component instance
(``components.instances.semiconductors.tja1051t_3.TJA1051T_3``) — leaves
read from that, so a datasheet revision updates exactly one place.

All block-local DAG node names are prefixed ``can_`` so the three-block
system DAG (CAN + MCU + power supply) doesn't collide. Hamilton wires by
parameter name and uses a flat namespace.
"""
from __future__ import annotations

from framework import Constant, Quantity
from framework.units import A, degC

from components.instances.semiconductors.tja1051t_3 import TJA1051T_3


def can_i_supply() -> Quantity:
    """Supply current per system mode, sourced from the TJA1051T/3 datasheet."""
    return Quantity(unit=A, by_mode=TJA1051T_3.supply_current_by_mode)


def can_r_theta_ja() -> Quantity:
    """Junction-to-ambient thermal resistance — datasheet."""
    assert TJA1051T_3.r_thermal_ja is not None
    return TJA1051T_3.r_thermal_ja


def can_t_j_max() -> Quantity:
    """Block-local derate: 25 C below the part's 150 C absolute max."""
    return Constant(125.0, degC)
