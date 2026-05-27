"""Sample block leaves — fixed inputs the engineer hand-codes."""
from __future__ import annotations

from framework import Constant, Quantity, RangeQuantity
from framework.units import K, V, W, mA


def i_supply() -> Quantity:
    """Mode-independent supply current for the simplest test case."""
    return Constant(100.0, mA)


def v_supply() -> Quantity:
    """5 V rail tolerance window."""
    return RangeQuantity(4.75, 5.25, V)


def r_theta() -> Quantity:
    """Junction-to-ambient thermal resistance."""
    return Constant(80.0, K / W)
