"""Infineon IRLML6344 — N-channel logic-level MOSFET (SOT-23).

Often used as a low-side switch on 5 V or 12 V loads from a 3.3 V GPIO.
R_DS(on) varies meaningfully with junction temperature; captured as a
by_scenario Quantity so block analysis can pick the right corner.

Datasheet ref: Infineon IRLML6344, Rev. 1.6 (2017).
"""
from __future__ import annotations

from framework import Constant, Quantity
from framework.units import A, K, Ohm, V, W, degC, nC

from components.types.mosfet import MOSFET

IRLML6344 = MOSFET(
    part_number="IRLML6344TRPBF",
    psc_id="PSC-MOSFET-IRLML6344",
    description="N-channel MOSFET, 30V, 5A, V_GS_th < 1.5V (logic-level)",
    rds_on=Quantity(unit=Ohm, by_scenario={
        "nominal":  0.028,    # 28 mOhm at 25 C
        "max_temp": 0.038,    # 38 mOhm at 125 C
    }),
    v_gs_th=Quantity(unit=V, by_scenario={
        "min": 0.6,
        "typ": 1.1,
        "max": 1.5,
    }),
    v_ds_max=30 * V,
    i_d_max=5 * A,
    q_g_total=Constant(1.5, nC),
    r_thermal_ja=Constant(250.0, K / W),    # SOT-23 in still air
    body_diode_vf=Constant(0.8, V),
)
