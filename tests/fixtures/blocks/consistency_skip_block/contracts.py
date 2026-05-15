"""Declared bound only — no compares_to, no consistency check applies."""
from __future__ import annotations

from framework import Quantity, RangeQuantity, contract
from framework.units import mA


@contract(description="Declared, no actual configured")
def declared_no_actual() -> Quantity:
    return RangeQuantity(0.0, 100.0, mA)
