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

from framework import Constant, CurrentBudget, Performance, SupplyEnvelope, TempRange
from framework.units import V, degC, mA, ms, percent


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


# --- Performance targets ---------------------------------------------------
#
# ADC measurement accuracy derates with ambient temperature. Jama tracks the
# three corners as separate rows -- one Performance per scenario, each linked
# to its own REQ-PERF-001x. A single verification test iterates them.

ADC_ACCURACY_NOMINAL = Performance(
    target=0.5 * percent,
    req="REQ-PERF-001a",
    applies_to_scenario="nominal",
    description="ADC measurement accuracy at room ambient",
)
ADC_ACCURACY_HOT = Performance(
    target=1.0 * percent,
    req="REQ-PERF-001b",
    applies_to_scenario="hot_high_vin",
    description="ADC measurement accuracy at hot ambient (derated)",
)
ADC_ACCURACY_COLD = Performance(
    target=0.8 * percent,
    req="REQ-PERF-001c",
    applies_to_scenario="cold_low_vin",
    description="ADC measurement accuracy at cold ambient (derated)",
)

# A scope-independent performance target — boot time from cold start.
BOOT_TIME_MAX = Performance(
    target=200 * ms,
    req="REQ-SYS-008",
    description="MCU cold-start boot time to first CAN frame",
)
