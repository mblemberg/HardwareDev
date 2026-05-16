"""Actual draw value — exceeds the declared bound in 'active' mode."""
from __future__ import annotations

from framework import Quantity, RangeQuantity
from framework.units import mA


def actual_draw_over() -> Quantity:
    return Quantity(
        unit=mA,
        by_mode={
            "sleep":  RangeQuantity(0.005, 0.012, mA),
            "active": RangeQuantity(80.0, 260.0, mA),  # over the 220 mA cap
        },
    )
