"""Power supply block — public Contracts (design doc 6.6 / 6.7).

The power supply publishes ``rail_5v`` — the 5 V system rail that the CAN
transceiver and MCU consume. The Contract:

- *declares* the system envelope (4.75–5.25 V) that downstream blocks
  can rely on (matches the project's REQ-PWR-005 requirement);
- *assumes* upper bounds on each downstream consumer's published draw
  (these are the Contract's ``assumed_inputs``);
- ``compares_to="psu_v_out_actual"`` ties the declared envelope to the
  LDO's actual output range for the step-8 run-time consistency check.

The assumed-inputs check (step 8b) validates that the CAN's actual
``can_5v_draw`` and the MCU's actual ``mcu_5v_draw`` stay within the
power supply's assumed bounds. If a downstream block raises its draw
beyond what the PSU planned for, the PSU's thermal model breaks and the
check fires.
"""
from __future__ import annotations

from framework import Quantity, RangeQuantity, contract
from framework.units import V, mA


@contract(
    description="System-wide 5V rail envelope (steady-state ±5%)",
    requirement="REQ-PWR-005",
    assumed_inputs={
        # Upper bounds on each downstream consumer's draw. These are the
        # numbers the PSU's thermal model assumes; if a downstream block
        # publishes a contract that exceeds these, step-8b raises.
        "can_5v_draw": RangeQuantity(0.0, 100.0, mA),
        "mcu_5v_draw": RangeQuantity(0.0, 30.0, mA),
    },
    compares_to="psu_v_out_actual",
)
def rail_5v() -> Quantity:
    """The 5V system rail this block publishes to the rest of the project.

    Returns the project-level envelope (REQ-PWR-005) — looser than the
    LDO's actual ±1% output spec, because downstream consumers should
    plan against the broader system spec, not the part's actual values
    (which let us swap to a different LDO without renegotiating with
    every consumer block).
    """
    return RangeQuantity(4.75, 5.25, V)
