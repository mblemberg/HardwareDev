"""LDO regulator schema."""
from __future__ import annotations

from framework import Component

from components.types._helpers import CoercedQuantity


class LDO(Component):
    """Linear (low-dropout) regulator."""

    # Required
    v_out: CoercedQuantity                # nominal regulated output voltage
    v_dropout: CoercedQuantity            # dropout at i_out_max
    i_out_max: CoercedQuantity            # max continuous output current
    i_q: CoercedQuantity                  # quiescent current (no load)

    # Optional
    v_in_max: CoercedQuantity | None = None
    psrr: CoercedQuantity | None = None
    accuracy: CoercedQuantity | None = None   # output voltage tolerance
    r_thermal_ja: CoercedQuantity | None = None
    t_j_max: CoercedQuantity | None = None
