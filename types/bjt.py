"""BJT schema."""
from __future__ import annotations

from framework import Component

from components.types._helpers import CoercedQuantity


class BJT(Component):
    """Bipolar junction transistor (NPN or PNP)."""

    # Required
    h_fe: CoercedQuantity                 # current gain (dimensionless)
    v_ce_sat: CoercedQuantity             # collector-emitter saturation voltage
    v_be_on: CoercedQuantity              # base-emitter turn-on voltage
    v_ceo_max: CoercedQuantity            # collector-emitter breakdown
    i_c_max: CoercedQuantity              # max continuous collector current

    # Optional
    f_t: CoercedQuantity | None = None    # transition frequency
    r_thermal_ja: CoercedQuantity | None = None
