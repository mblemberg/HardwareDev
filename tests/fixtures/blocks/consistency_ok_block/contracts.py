"""Declared bound — covers the actual."""
from __future__ import annotations

from framework import Quantity, RangeQuantity, contract
from framework.units import mA


@contract(description="Declared draw — matches actual_draw", compares_to="actual_draw")
def declared_ok() -> Quantity:
    return Quantity(
        unit=mA,
        by_mode={
            "sleep":  RangeQuantity(0.0, 0.020, mA),
            "active": RangeQuantity(0.0, 220.0, mA),
        },
    )
