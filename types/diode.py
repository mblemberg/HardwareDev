"""Diode schema (rectifier, Schottky, Zener — discriminate via metadata)."""
from __future__ import annotations

from framework import Component

from components.types._helpers import CoercedQuantity


class Diode(Component):
    """Discrete diode. Cover rectifier / Schottky / Zener via standard fields."""

    # Required
    v_f: CoercedQuantity                  # forward voltage drop at i_f_typ
    i_f_max: CoercedQuantity              # max forward current (continuous)
    v_r_max: CoercedQuantity              # max reverse voltage (V_RRM)

    # Optional
    i_r_leakage: CoercedQuantity | None = None
    v_z: CoercedQuantity | None = None    # Zener voltage (None for non-Zener)
    r_thermal_ja: CoercedQuantity | None = None
