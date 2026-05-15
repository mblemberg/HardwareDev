"""Project requirements — single source of truth for external design constraints.

All requirements in this file auto-register with ``framework.requirements`` on
import; verification tests, contracts, and report sections link back via
``req=`` IDs. Edit here when a Jama requirement changes; nothing else needs
to know.

Convention for IDs (matches Jama):
- ``REQ-ENV-*`` — environment
- ``REQ-PWR-*`` — power
- ``REQ-CAN-*`` — CAN bus (network)
- ``REQ-THM-*`` — thermal
- ``REQ-EMI-*`` — EMI / EMC
"""
from __future__ import annotations

from framework import Constant, CurrentBudget, SupplyEnvelope, TempRange
from framework.units import V, degC, mA


# --- Environmental envelopes -----------------------------------------------

OPERATING_TEMP = TempRange(
    min=Constant(-40.0, degC),
    max=Constant(85.0, degC),
    req="REQ-ENV-001",
    description="Vehicle operating ambient temperature envelope (key-on)",
)

STORAGE_TEMP = TempRange(
    min=Constant(-40.0, degC),
    max=Constant(125.0, degC),
    req="REQ-ENV-002",
    description="Vehicle storage temperature envelope (long-term, powered-down)",
)


# --- Supply envelopes ------------------------------------------------------

VBAT = SupplyEnvelope(
    nominal=12 * V,
    min=9 * V,
    max=16 * V,
    transient_min=6 * V,     # cold-crank dip
    transient_max=40 * V,    # load-dump pulse
    req="REQ-PWR-001",
    description="Vehicle 12V system with cold-crank and load-dump margins",
)

CAN_5V_RAIL = SupplyEnvelope(
    nominal=5.0 * V,
    min=4.75 * V,
    max=5.25 * V,
    req="REQ-PWR-005",
    description=(
        "5V analog/peripheral rail (steady-state +/-5%) feeding the CAN "
        "transceiver and the ADC reference"
    ),
)


# --- Current budgets -------------------------------------------------------

TOTAL_QUIESCENT_CURRENT_BUDGET = CurrentBudget(
    max=2 * mA,
    applies_to_mode="sleep",
    req="REQ-PWR-014",
    description="Vehicle key-off total quiescent current budget across all blocks",
)
