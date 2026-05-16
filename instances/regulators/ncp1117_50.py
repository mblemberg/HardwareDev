"""ON Semiconductor NCP1117ST50T3G — fixed 5.0 V LDO, 1 A continuous.

Linear (LDO) regulator. SOT-223 surface-mount. Drop-in for 12 V → 5 V rail
work where a switcher is overkill and dissipation is acceptable.

Datasheet ref: ON Semi NCP1117 product data sheet, Rev. 16 (2022). Numbers
captured here are the catalogued maxes for the -50 fixed-output variant:

- ``v_out`` 5.0 V ± 1% (4.95 – 5.05 V) for I_load between 10 mA and 800 mA.
- ``v_dropout`` 1.2 V at 1 A load (datasheet max).
- ``i_out_max`` 1 A continuous (limited by thermals on a 2-layer board).
- ``i_q`` 5 mA typical (raised slightly here to a 10 mA conservative max).
- ``v_in_max`` 20 V (absolute max on V_IN).
- ``r_thermal_ja`` 50 K/W typical for SOT-223 on 2-layer board with adequate
  copper pour (datasheet Figure 21). A real board would pull this lower with
  a copper area + thermal-via design, but 50 K/W is the conservative starting
  point for a hand-routed prototype.
- ``t_j_max`` 150 °C absolute max; the power-supply block derates 25 °C below
  this to 125 °C.
"""
from __future__ import annotations

from framework import Constant
from framework.units import A, K, V, W, degC, mA

from components.types.ldo import LDO

NCP1117_50 = LDO(
    part_number="NCP1117ST50T3G",
    psc_id="PSC-REG-NCP1117-50",
    description="ON Semi NCP1117, fixed 5.0V output, 1A linear regulator, SOT-223",
    v_out=Constant(5.0, V),
    v_dropout=Constant(1.2, V),
    i_out_max=Constant(1.0, A),
    i_q=Constant(10.0, mA),
    v_in_max=Constant(20.0, V),
    accuracy=Constant(0.01, V / V),  # +/-1% output regulation
    r_thermal_ja=Constant(50.0, K / W),
    t_j_max=Constant(150.0, degC),
)
