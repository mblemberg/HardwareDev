"""Declared bound — undercut by actual_draw_over."""
from __future__ import annotations

from framework import Quantity, RangeQuantity, contract
from framework.units import mA


@contract(description="Declared draw — under-budget vs actual_draw_over", compares_to="actual_draw_over")
def declared_violated() -> Quantity:
    return Quantity(
        unit=mA,
        by_mode={
            "sleep":  RangeQuantity(0.0, 0.020, mA),
            "active": RangeQuantity(0.0, 220.0, mA),
        },
    )
