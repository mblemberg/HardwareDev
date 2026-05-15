"""CAN transceiver — public Contracts (design doc 6.6 / 6.7).

Anything in this file is a Contract — a commitment this block makes to other
blocks. The framework's cycle detector (design doc 7.4) enforces that
Contracts may only depend on intra-block inputs, on Contracts of other
blocks, or on global inputs (project requirements / scenarios / modes /
components). Other blocks may import names from here; they may not reach
past these into ``leaves.py`` or ``analysis.py``.
"""
from __future__ import annotations

from framework import Quantity, contract


@contract(
    description="Block's draw from the 5V CAN rail",
    requirement="REQ-PWR-005",
    assumed_inputs={
        # The block assumes the rail stays within this window. The power-supply
        # block must guarantee it (validated by step 8's run-time consistency
        # check, once that lands).
        "can_5v_rail_window_V": (4.75, 5.25),
    },
)
def can_5v_draw(i_supply: Quantity) -> Quantity:
    """Public-facing current draw, mode-keyed.

    Surfaces the same ``i_supply`` Quantity the local analysis uses, but
    exposed as a Contract so downstream consumers (the power supply block)
    can wire it into their total-load math without reaching into our
    internals.
    """
    return i_supply
