"""Component library — typed Pydantic schemas, families, and per-part instances.

Three layers (design doc 6.5):

- :mod:`components.types`     — Pydantic schemas defining what each component
                                *is* (Resistor, Capacitor, MOSFET, LDO, ...).
- :mod:`components.families`  — shared parameter factories for parametric
                                parts (e.g. Panasonic ERJ-3 resistors).
- :mod:`components.instances` — specific part numbers as named Python objects.

Each layer is imported on demand; nothing is registered at package import time.
"""

__version__ = "0.0.1"
