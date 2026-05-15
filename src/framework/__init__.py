"""Hardware analysis framework — public API surface.

Curated re-exports per design doc section 11 (framework.__all__).
"""
from framework import units
from framework.provenance import ProvenanceRef
from framework.quantity import Constant, Quantity, RangeQuantity

__all__ = [
    "Constant",
    "ProvenanceRef",
    "Quantity",
    "RangeQuantity",
    "units",
]
