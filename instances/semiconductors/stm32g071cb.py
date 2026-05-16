"""STMicroelectronics STM32G071CB — Cortex-M0+ MCU, 64 MHz, 128 KB flash, LQFP-48.

General-purpose 32-bit MCU. The example_analysis project's MCU block uses
this part as its main controller; it drives the CAN transceiver via TXD/RXD
plus a few peripherals. Supply is the 5 V rail produced by the power-supply
block, fed through the chip's internal 1.8 V LDO to the core.

Datasheet ref: ST RM0444 / DS12767. Numbers captured here are the
catalogued worst-case values relevant to a worst-case current and thermal
analysis:

- Supply current bounds are conservative envelopes covering the chip's own
  spread plus a generous allowance for peripheral activity. The active-mode
  number assumes core at 48 MHz, ADC + USART + TIM peripherals active,
  CAN ISR firing at moderate bus load. Diagnostic mode adds the on-board
  comparator + debug peripherals + worst-case CAN bus loading.
- ``r_thermal_ja`` 60 K/W typical for LQFP-48 on 4-layer board (datasheet
  Table 100). The MCU block uses this number directly.
- ``t_j_max`` 105 °C industrial-grade absolute max. The MCU block derates
  to 90 °C for the thermal verification.
"""
from __future__ import annotations

from framework import Constant, RangeQuantity
from framework.units import A, K, V, W, degC

from components.types.integrated_circuit import IntegratedCircuit

STM32G071CB = IntegratedCircuit(
    part_number="STM32G071CB",
    psc_id="PSC-MCU-STM32G071CB",
    description="ST Cortex-M0+, 64MHz, 128KB flash, LQFP-48, 5V-tolerant via internal LDO",
    package="LQFP-48",
    supply_current_by_mode={
        "off":        Constant(0.0, A),
        "sleep":      RangeQuantity(0.5e-6, 5e-6, A),     # standby + RTC
        "active":     RangeQuantity(5e-3, 15e-3, A),      # core@48MHz + peripherals
        "diagnostic": RangeQuantity(12e-3, 25e-3, A),     # peak diagnostic load
    },
    supply_voltage_range=RangeQuantity(4.5, 5.5, V),
    r_thermal_ja=Constant(60.0, K / W),
    t_j_max=Constant(105.0, degC),
)
