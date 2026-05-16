"""block_y — public contracts. Depends on block_x's contract (allowed)."""
from __future__ import annotations

from framework import Quantity, contract


@contract(description="Total downstream draw — composed from block_x")
def y_total_draw(x_3v3_draw: Quantity) -> Quantity:
    """Cross-block dep via a Contract — allowed by design doc 6.7."""
    return x_3v3_draw
