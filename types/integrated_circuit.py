"""IntegratedCircuit — generic IC schema (catch-all for things without a more
specific type like MOSFET / LDO / BuckConverter).

CAN transceivers, MCUs, op-amps, ADCs, etc. live here until / unless their
own typed schema earns its keep across multiple parts.
"""
from __future__ import annotations

from framework import Component, Quantity

from components.types._helpers import CoercedQuantity


class IntegratedCircuit(Component):
    """A generic IC. Captures the parameters most blocks need from any chip.

    - ``supply_current_by_mode`` — dict keyed by system-mode name, value
      is a Quantity that may itself carry a per-scenario range. This is the
      shape ``framework.Quantity(by_mode=...)`` expects, so a block leaf can
      lift it directly: ``Quantity(unit=A, by_mode=part.supply_current_by_mode)``.
    - ``supply_voltage_range`` — the tolerated rail window for the chip,
      typically a ``RangeQuantity``. Compare against the project's
      ``SupplyEnvelope`` requirement when wiring the chip into a block.
    """

    supply_current_by_mode: dict[str, CoercedQuantity]
    supply_voltage_range: CoercedQuantity

    # Standardized optional thermal fields
    r_thermal_ja: CoercedQuantity | None = None
    r_thermal_jc: CoercedQuantity | None = None
    t_j_max: CoercedQuantity | None = None

    package: str | None = None
