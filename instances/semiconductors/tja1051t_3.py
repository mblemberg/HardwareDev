"""NXP TJA1051T/3 — high-speed CAN transceiver with 3.3 V interface.

Supply: 5 V on V_CC, separate 3.3 V on V_IO for the host-side digital
interface. Mode-dependent supply current spans ~10 μA in standby to ~75 mA
under heavy bus loading. Datasheet absolute max T_J = 150 °C; this project
derates at the block layer.

Datasheet ref: NXP TJA1051T/3 product data sheet, Rev. 7 (2020).
"""
from __future__ import annotations

from framework import Constant, Quantity, RangeQuantity
from framework.units import A, K, V, W, degC

from components.types.integrated_circuit import IntegratedCircuit

TJA1051T_3 = IntegratedCircuit(
    part_number="TJA1051T/3",
    psc_id="PSC-CAN-TJA1051T3",
    description="NXP high-speed CAN transceiver, 5V supply with 3.3V I/O level",
    package="SO-8",
    # Supply current keyed by the project's system modes. Each mode's value is
    # a RangeQuantity covering datasheet min/max where applicable.
    supply_current_by_mode={
        "off":        Constant(0.0, A),
        "sleep":      RangeQuantity(8e-6,  15e-6, A),    # standby mode I_CC
        "active":     RangeQuantity(45e-3, 65e-3, A),    # normal operation, dominant + recessive avg
        "diagnostic": RangeQuantity(70e-3, 90e-3, A),    # bus-loaded worst case
    },
    supply_voltage_range=RangeQuantity(4.75, 5.25, V),
    r_thermal_ja=Constant(120.0, K / W),                  # SO-8 in still air
    t_j_max=Constant(150.0, degC),                         # datasheet absolute max
)
