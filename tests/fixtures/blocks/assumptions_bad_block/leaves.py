"""Upstream value that drifts outside the assumed bound."""
from __future__ import annotations

from framework import Quantity, RangeQuantity
from framework.units import V


def sagging_rail() -> Quantity:
    return RangeQuantity(4.40, 5.10, V)  # 4.40 V is below the assumed (4.75, 5.25)
