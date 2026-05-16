"""bad_block — declares a contract that violates the cross-block rule.

The contract depends on ``x_internal_draw`` — a non-Contract leaf of
``block_x``. Cycle detection should reject this with a CycleViolation.
"""
from __future__ import annotations

from framework import Quantity, contract


@contract(description="Forbidden — depends on a non-Contract output of block_x")
def bad_draw(x_internal_draw: Quantity) -> Quantity:
    return x_internal_draw
