"""block_x — public contracts."""
from __future__ import annotations

from framework import Quantity, contract


@contract(description="Block X's 3V3 current draw")
def x_3v3_draw(x_internal_draw: Quantity) -> Quantity:
    """Depends only on a same-block leaf — fine."""
    return x_internal_draw
