"""Shared validator alias used by every component type schema."""
from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator

from framework import Quantity, coerce_field_quantity

# Use this on every Quantity-typed field in a Component subclass. It lifts
# pint.Quantity / Pint-format strings into framework.Quantity at construction
# time and rejects bare numbers (every field must carry its unit explicitly).
CoercedQuantity = Annotated[Quantity, BeforeValidator(coerce_field_quantity)]
