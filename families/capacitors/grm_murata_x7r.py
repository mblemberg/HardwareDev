"""Murata GRM series, X7R dielectric (general-purpose MLCC, AEC-Q200)."""
from __future__ import annotations

from framework.units import K, V, ppm

from components.types.capacitor import CapacitorFamily, Dielectric
from components.types.resistor import SmtSize

# Note: tempco units use ppm/K, not ppm/degC. See the ERJ3 family file for
# the offset-unit rationale.

GRM_X7R = CapacitorFamily(
    manufacturer="Murata",
    series="GRM",
    dielectric=Dielectric.X7R,
    description="X7R MLCC, AEC-Q200, general purpose decoupling and filtering",
    tolerance=0.10,                       # ±10%, dimensionless ratio
    # X7R is rated within ±15% over -55..+125 C; rough effective TC ~ 1500 ppm/K
    temp_coefficient=1500 * ppm / K,
    available_sizes=[
        SmtSize.IMP0402,
        SmtSize.IMP0603,
        SmtSize.IMP0805,
        SmtSize.IMP1206,
    ],
    voltage_rating_by_size={
        # Common ratings — actual Murata sub-series vary; these are sane defaults
        # for the populated value ranges most projects use.
        SmtSize.IMP0402: 10 * V,
        SmtSize.IMP0603: 25 * V,
        SmtSize.IMP0805: 50 * V,
        SmtSize.IMP1206: 100 * V,
    },
    psc_family_id="PSC-CAP-GRM-X7R",
)
