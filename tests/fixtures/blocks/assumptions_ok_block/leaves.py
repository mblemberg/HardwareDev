"""Upstream value the block makes an assumption about (within bound)."""
from __future__ import annotations

from framework import Quantity, RangeQuantity
from framework.units import V


def upstream_rail() -> Quantity:
    return RangeQuantity(4.85, 5.15, V)  # within (4.75, 5.25)
