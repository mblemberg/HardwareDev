"""Contract whose assumption holds against upstream_rail."""
from __future__ import annotations

from framework import Quantity, RangeQuantity, contract
from framework.units import V, mA


@contract(
    description="Block draws while rail behaves",
    assumed_inputs={"upstream_rail": RangeQuantity(4.75, 5.25, V)},
)
def my_draw() -> Quantity:
    return RangeQuantity(0.0, 50.0, mA)
