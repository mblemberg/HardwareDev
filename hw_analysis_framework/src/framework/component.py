"""Component — Pydantic base class for typed component schemas (design doc 6.5).

The `components` package builds concrete subclasses (MOSFET, Resistor, LDO,
BuckConverter, BJT, Diode, Capacitor, ...) on top of this. Each subclass adds
its typed Quantity fields — required ones, optional standardized ones, and a
free-form ``metadata`` escape hatch — and the schema is enforced at instance
construction time, so a missing required field fails CI before any analysis
runs.

Quantity-valued fields on Component subclasses accept the same input shapes
the rest of the framework does:

- ``framework.Quantity`` — used as-is (supports scenario / mode axes for
  values that legitimately vary, like ``rds_on(temperature)``).
- ``pint.Quantity`` (e.g. ``30 * V``) — lifted to a scenario-invariant
  ``Constant`` Quantity.
- Pint-format string (``"30 V"``) — parsed via the same regex-and-two-arg
  Quantity construction that ``framework._toml.parse_pint`` uses, so offset
  units (``degC``, ``degF``) work.

Use ``coerce_field_quantity`` as a ``BeforeValidator`` on every Quantity
field in subclasses to get this for free.
"""
from __future__ import annotations

from typing import Any

import pint
from pydantic import BaseModel, ConfigDict, Field

from framework._toml import TomlError, parse_pint
from framework.quantity import Constant, Quantity
from framework.units import registry


class Component(BaseModel):
    """Base for every component-type schema.

    Fields shared by every part:
      - ``part_number``: manufacturer part number, required.
      - ``psc_id``: Altium PSC catalog ID, optional (set when known).
      - ``description``: optional one-line summary.
      - ``metadata``: free-form dict — escape hatch for parameters that
        don't fit any standardized typed field on the subclass.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    part_number: str = Field(..., min_length=1, description="Manufacturer part number")
    psc_id: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def coerce_field_quantity(value: Any, *, location: str = "field") -> Quantity:
    """Pydantic ``BeforeValidator`` that lifts component-schema inputs.

    - Pass through framework ``Quantity`` instances.
    - Lift ``pint.Quantity`` to a scenario-invariant ``Constant``.
    - Parse Pint-format strings via :func:`framework._toml.parse_pint`,
      then lift the resulting pint.Quantity to a Constant.
    - Lift bare ``int`` / ``float`` to a *dimensionless* ``Constant`` — useful
      for ratios like tolerance, efficiency, or current gain. Misuse on a
      dimensioned field (e.g. ``v_ds_max=30``) silently succeeds here but
      fails loudly at the first arithmetic with a real-unit Quantity, since
      dimensionless + volts is a Pint dimensionality error.
    """
    if isinstance(value, Quantity):
        return value
    if isinstance(value, pint.Quantity):
        return Constant(value)
    if isinstance(value, bool):
        # bool is a subclass of int — reject explicitly so True/False aren't
        # silently lifted to 1.0 / 0.0 dimensionless.
        raise ValueError(
            f"{location}: bool is not a valid Quantity input"
        )
    if isinstance(value, (int, float)):
        return Constant(float(value), registry.dimensionless)
    if isinstance(value, str):
        try:
            pq = parse_pint(value, location=location)
        except TomlError as e:
            raise ValueError(str(e)) from e
        return Constant(pq)
    raise ValueError(
        f"{location}: component Quantity field must be a framework.Quantity, "
        f"pint.Quantity, Pint-format string, or a bare number (lifted to dimensionless); "
        f"got {type(value).__name__}"
    )


__all__ = ["Component", "coerce_field_quantity"]
