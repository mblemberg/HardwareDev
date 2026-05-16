"""Power supply block — leaf Quantities (design doc 6.6).

The NCP1117-5.0 datasheet is the source for the LDO's actual output
voltage window (±1% over the operating envelope) and its thermal
resistance. We treat the LDO's output as load-independent here — load
regulation is ~0.2% per amp, dwarfed by the ±1% line regulation already
captured. A worked example for a buck or for a more accurate load-reg
model would add a load-dependent term.
"""
from __future__ import annotations

from framework import Constant, Quantity, RangeQuantity
from framework.units import V, degC

from components.instances.regulators.ncp1117_50 import NCP1117_50


def psu_v_out_actual() -> Quantity:
    """LDO actual output voltage envelope, from the NCP1117 datasheet.

    Centered on the part's 5.0 V target with ±1% accuracy → 4.95–5.05 V.
    This is the *actual* the PSU computes; the ``rail_5v`` Contract
    declares the looser system envelope (4.75–5.25 V) that consumers can
    rely on.
    """
    return RangeQuantity(4.95, 5.05, V)


def psu_r_theta_ja() -> Quantity:
    """SOT-223 junction-to-ambient thermal resistance — datasheet.

    50 K/W is the catalogued number for the part in still air on a
    2-layer board with adequate copper pour. A real production board
    with thermal vias + a copper plane would pull this lower.
    """
    assert NCP1117_50.r_thermal_ja is not None
    return NCP1117_50.r_thermal_ja


def psu_t_j_max() -> Quantity:
    """Block-local derate: 25 °C below the part's 150 °C absolute max."""
    return Constant(125.0, degC)
