"""Hardware analysis framework — public API surface.

Curated re-exports per design doc section 11 (framework.__all__).
"""
from framework import requirements, units
from framework._toml import TomlError
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
    "Constant",
    "CurrentBudget",
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
    "load_modes",
    "load_scenarios",
    "requirements",
    "units",
]
