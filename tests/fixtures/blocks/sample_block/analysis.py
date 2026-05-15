"""Sample block derived nodes — Hamilton wires parameters by name."""
from __future__ import annotations

from framework import Quantity
from framework.units import K, degC, mW


def power(v_supply: Quantity, i_supply: Quantity) -> Quantity:
    """V * I in mW."""
    return (v_supply * i_supply).to(mW)


def thermal_rise(power: Quantity, r_theta: Quantity) -> Quantity:
    """P * R_theta in K (a temperature delta)."""
    return (power * r_theta).to(K)


def t_j(ambient_temp: Quantity, thermal_rise: Quantity) -> Quantity:
    """Junction temp = ambient + thermal rise.

    Converts ambient to K first so the additive thermal math treats the rise
    as a delta rather than an absolute K value (Pint's offset-unit semantics
    say `degC + K` adds as two absolutes, which is wrong for thermal rise).
    Returns degC for display.
    """
    return (ambient_temp.to(K) + thermal_rise).to(degC)
