"""MCU block — derived analyses (design doc 6.6).

Hamilton wires by parameter name. ``mcu_power(rail_5v, mcu_i_supply)``
pulls the PSU's published ``rail_5v`` Contract and this block's own
``mcu_i_supply`` leaf. The cross-block dependency on PSU's Contract is
allowed by the cycle-cut rule (design doc 6.7); the CAN block does the
same thing.
"""
from __future__ import annotations

from framework import Quantity
from framework.units import K, degC, mW


def mcu_power(rail_5v: Quantity, mcu_i_supply: Quantity) -> Quantity:
    """MCU supply power dissipation (V * I), in mW."""
    return (rail_5v * mcu_i_supply).to(mW)


def mcu_thermal_rise(mcu_power: Quantity, mcu_r_theta_ja: Quantity) -> Quantity:
    """Junction-to-ambient thermal rise (P * R_theta), in K."""
    return (mcu_power * mcu_r_theta_ja).to(K)


def mcu_t_j(ambient_temp: Quantity, mcu_thermal_rise: Quantity) -> Quantity:
    """Junction temperature.

    Ambient (degC) → K first so the thermal rise is added as a delta;
    convert back to degC for display. See framework gotcha #2.
    """
    return (ambient_temp.to(K) + mcu_thermal_rise).to(degC)
