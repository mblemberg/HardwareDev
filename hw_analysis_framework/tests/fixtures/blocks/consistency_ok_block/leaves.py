"""Actual draw value — within the declared bound."""
from __future__ import annotations

from framework import Quantity, RangeQuantity
from framework.units import mA


def actual_draw() -> Quantity:
    return Quantity(
        unit=mA,
        by_mode={
            "sleep":  RangeQuantity(0.005, 0.012, mA),
            "active": RangeQuantity(80.0, 220.0, mA),
        },
    )
