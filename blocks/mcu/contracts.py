"""MCU block — public Contracts (design doc 6.6 / 6.7).

The MCU publishes ``mcu_5v_draw`` — its committed upper bound on the 5V
rail. The power-supply block consumes this for its total-load math; the
framework's run-time consistency check (step 8) verifies the block's
actual ``mcu_i_supply`` never exceeds this bound.

The contract also declares its cross-block assumption that the published
``rail_5v`` (from the power-supply block) stays in (4.75, 5.25) V. The
step-8b assumed-inputs check validates the upstream Contract satisfies
this at run time.
"""
from __future__ import annotations

from framework import Quantity, RangeQuantity, contract
from framework.units import V, mA


@contract(
    description="MCU draw from the 5V system rail",
    requirement="REQ-PWR-007",
    assumed_inputs={
        "rail_5v": RangeQuantity(4.75, 5.25, V),
    },
    compares_to="mcu_i_supply",
)
def mcu_5v_draw() -> Quantity:
    """Public-facing current draw — declared upper bounds per mode.

    Bounds include small headroom above the STM32G071 datasheet maxes so
    a firmware revision that adds peripheral activity doesn't immediately
    trip CI. The power-supply block uses these bounds for its total-load
    math and validates the assumption at run time via step-8b.
    """
    return Quantity(
        unit=mA,
        by_mode={
            "off":        RangeQuantity(0.0, 0.0, mA),
            "sleep":      RangeQuantity(0.0, 0.010, mA),    # datasheet max 5 uA + margin
            "active":     RangeQuantity(0.0, 20.0, mA),     # datasheet max 15 mA + margin
            "diagnostic": RangeQuantity(0.0, 30.0, mA),     # datasheet max 25 mA + margin
        },
    )
