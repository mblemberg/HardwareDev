"""CAN transceiver — public Contracts (design doc 6.6 / 6.7).

Anything in this file is a Contract — a commitment this block makes to other
blocks. The framework's cycle detector (design doc 7.4) enforces that
Contracts may only depend on intra-block inputs, on Contracts of other
blocks, or on global inputs (project requirements / scenarios / modes /
components). Other blocks may import names from here; they may not reach
past these into ``leaves.py`` or ``analysis.py``.

Pattern (design doc 6.7):
    - The Contract function returns the *declared* commitment (typically a
      ranged Quantity, mode-keyed) — what we promise downstream.
    - The block's analysis computes the *actual* through normal Hamilton
      nodes (in our case, ``can_i_supply`` in ``leaves.py``).
    - ``compares_to=<actual node>`` wires the two for the run-time consistency
      check (step 8). If actual ever exceeds declared in any scenario/mode,
      :class:`framework.ContractViolation` fires.
    - ``assumed_inputs`` captures the block's cross-block assumptions: the
      CAN block assumes the power supply's published ``rail_5v`` Contract
      stays in (4.75, 5.25) V. The framework's step-8b check validates that
      the upstream Contract actually satisfies the assumption at run time.
"""
from __future__ import annotations

from framework import Quantity, RangeQuantity, contract
from framework.units import V, mA


@contract(
    description="Block's draw from the 5V CAN rail",
    requirement="REQ-PWR-005",
    assumed_inputs={
        "rail_5v": RangeQuantity(4.75, 5.25, V),
    },
    compares_to="can_i_supply",
)
def can_5v_draw() -> Quantity:
    """Public-facing current draw — declared upper bounds per mode.

    These are the commitments downstream consumers (the power-supply block)
    wire into their total-load math. Values include a small margin above the
    TJA1051T/3 datasheet maxima so a part-rev or process variation that
    nudges the actual upward doesn't immediately trip CI.
    """
    return Quantity(
        unit=mA,
        by_mode={
            "off":        RangeQuantity(0.0, 0.0, mA),
            "sleep":      RangeQuantity(0.0, 0.020, mA),   # datasheet max 15 uA
            "active":     RangeQuantity(0.0, 75.0, mA),    # datasheet max 65 mA
            "diagnostic": RangeQuantity(0.0, 100.0, mA),   # datasheet max 90 mA
        },
    )
