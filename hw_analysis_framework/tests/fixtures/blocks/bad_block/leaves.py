"""bad_block leaves — needed so the bad_block test can also exercise valid intra-block deps."""
from __future__ import annotations

from framework import Constant, Quantity
from framework.units import mA


def bad_internal() -> Quantity:
    return Constant(5.0, mA)
