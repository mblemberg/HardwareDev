"""block_x — leaf inputs (internal to the block)."""
from __future__ import annotations

from framework import Constant, Quantity
from framework.units import mA


def x_internal_draw() -> Quantity:
    """An internal leaf — NOT a contract. Other blocks must not depend on this."""
    return Constant(20.0, mA)
