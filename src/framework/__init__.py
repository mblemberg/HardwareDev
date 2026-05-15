"""Hardware analysis framework — public API surface.

Curated re-exports per design doc section 11 (framework.__all__).
"""
from framework import units
from framework._toml import TomlError
from framework.modes import Mode, ModeSet, load_modes
from framework.provenance import ProvenanceRef
from framework.quantity import Constant, Quantity, RangeQuantity
from framework.scenarios import Scenario, ScenarioSet, load_scenarios

__all__ = [
    "Constant",
    "Mode",
    "ModeSet",
    "ProvenanceRef",
    "Quantity",
    "RangeQuantity",
    "Scenario",
    "ScenarioSet",
    "TomlError",
    "load_modes",
    "load_scenarios",
    "units",
]
