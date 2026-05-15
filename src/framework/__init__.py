"""Hardware analysis framework — public API surface.

Curated re-exports per design doc section 11 (framework.__all__).
"""

__version__ = "0.0.1"
from framework import requirements, units
from framework._toml import TomlError
from framework.component import Component, coerce_field_quantity
from framework.contract import (
    ContractMeta,
    CycleViolation,
    contract,
    detect_cycles,
    get_contract_meta,
    is_contract,
)
from framework.modes import Mode, ModeSet, load_modes
from framework.project import Project
from framework.provenance import ProvenanceRef
from framework.quantity import Constant, Quantity, RangeQuantity
from framework.requirements import (
    CurrentBudget,
    Performance,
    Requirement,
    SupplyEnvelope,
    TempRange,
)
from framework.scenarios import Scenario, ScenarioSet, load_scenarios

__all__ = [
    "Component",
    "Constant",
    "ContractMeta",
    "CurrentBudget",
    "CycleViolation",
    "Mode",
    "ModeSet",
    "Performance",
    "Project",
    "ProvenanceRef",
    "Quantity",
    "RangeQuantity",
    "Requirement",
    "Scenario",
    "ScenarioSet",
    "SupplyEnvelope",
    "TempRange",
    "TomlError",
    "coerce_field_quantity",
    "contract",
    "detect_cycles",
    "get_contract_meta",
    "is_contract",
    "load_modes",
    "load_scenarios",
    "requirements",
    "units",
]
