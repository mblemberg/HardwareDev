"""Contract whose assumption is violated by sagging_rail."""
from __future__ import annotations

from framework import Quantity, RangeQuantity, contract
from framework.units import V, mA


@contract(
    description="Block draws assuming the rail stays at 5 V ± 5%",
    assumed_inputs={"sagging_rail": RangeQuantity(4.75, 5.25, V)},
)
def my_draw() -> Quantity:
    return RangeQuantity(0.0, 50.0, mA)
