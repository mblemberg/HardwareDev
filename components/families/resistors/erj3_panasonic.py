"""Panasonic ERJ-3 thick-film chip resistor family (AEC-Q200, general purpose)."""
from __future__ import annotations

from framework.units import K, V, W, ppm

from components.types.resistor import ResistorFamily, SmtSize

# Note: tempco units use ppm/K, not ppm/degC. Pint refuses division by an
# offset unit (it's ambiguous between absolute and delta semantics), and a
# temperature *coefficient* is unambiguously per-delta-kelvin anyway.

ERJ3 = ResistorFamily(
    manufacturer="Panasonic",
    series="ERJ-3",
    description="Thick-film chip resistors, general purpose, AEC-Q200",
    tolerance=0.01,                       # ±1%, dimensionless ratio
    temp_coefficient=100 * ppm / K,
    available_sizes=[
        SmtSize.IMP0603,
        SmtSize.IMP0805,
        SmtSize.IMP1206,
    ],
    power_rating_by_size={
        SmtSize.IMP0603: 0.1 * W,
        SmtSize.IMP0805: 0.125 * W,
        SmtSize.IMP1206: 0.25 * W,
    },
    max_voltage_by_size={
        SmtSize.IMP0603: 75 * V,
        SmtSize.IMP0805: 150 * V,
        SmtSize.IMP1206: 200 * V,
    },
    psc_family_id="PSC-RES-ERJ3",
)
