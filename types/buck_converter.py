"""Buck (step-down) DC-DC converter schema."""
from __future__ import annotations

from framework import Component

from components.types._helpers import CoercedQuantity


class BuckConverter(Component):
    """Switching buck regulator (internal-FET integrated or external)."""

    # Required
    v_in_range: CoercedQuantity           # supported input range
    v_out: CoercedQuantity                # nominal output voltage
    i_out_max: CoercedQuantity            # max continuous output current
    f_sw: CoercedQuantity                 # switching frequency (typ)
    efficiency_typ: CoercedQuantity       # typical efficiency at moderate load

    # Optional
    v_out_ripple: CoercedQuantity | None = None
    i_q: CoercedQuantity | None = None
    r_thermal_ja: CoercedQuantity | None = None
    t_j_max: CoercedQuantity | None = None
