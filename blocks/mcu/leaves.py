"""MCU block — leaf Quantities (design doc 6.6).

The STM32G071CB datasheet is the source of mode-dependent supply current
and thermal-resistance numbers; this block reads them off the component
instance so a part-rev update lands in exactly one place.

The MCU's main job in this system is running the CAN protocol stack and
talking to the CAN transceiver via TXD/RXD; from a power-analysis
perspective it's another load on the 5V rail produced by the power-supply
block.
"""
from __future__ import annotations

from framework import Constant, Quantity
from framework.units import A, degC

from components.instances.semiconductors.stm32g071cb import STM32G071CB


def mcu_i_supply() -> Quantity:
    """MCU supply current per system mode, sourced from the STM32G071 datasheet."""
    return Quantity(unit=A, by_mode=STM32G071CB.supply_current_by_mode)


def mcu_r_theta_ja() -> Quantity:
    """Junction-to-ambient thermal resistance — datasheet for LQFP-48."""
    assert STM32G071CB.r_thermal_ja is not None
    return STM32G071CB.r_thermal_ja


def mcu_t_j_max() -> Quantity:
    """Block-local derate: 15 °C below the part's 105 °C industrial absolute max.

    More aggressive derate than the CAN block because the MCU is on a
    dense PCB area with hot neighbors (the LDO and the CAN transceiver).
    """
    return Constant(90.0, degC)
