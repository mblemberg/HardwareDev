"""MOSFET schema (design doc 6.5 example)."""
from __future__ import annotations

from framework import Component

from components.types._helpers import CoercedQuantity


class MOSFET(Component):
    """Discrete N- or P-channel MOSFET.

    Required fields cover the parameters every analysis touches; optional
    fields are populated when known. Use ``metadata`` for catalog-specific
    extras (graph references, pinout codes, etc.).
    """

    # Required (CI rejects MOSFET instances that miss these)
    rds_on: CoercedQuantity
    v_gs_th: CoercedQuantity
    v_ds_max: CoercedQuantity
    i_d_max: CoercedQuantity

    # Standardized optional — well-known parameter names, populated when available
    q_g_total: CoercedQuantity | None = None
    r_thermal_jc: CoercedQuantity | None = None
    r_thermal_ja: CoercedQuantity | None = None
    body_diode_vf: CoercedQuantity | None = None
