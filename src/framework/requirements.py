"""Requirements — external design targets (design doc 6.4).

A Requirement is a typed, Pydantic-validated record of an external constraint:
operating temperature envelope, supply voltage envelope, current budget,
performance target. Each carries a Jama requirement ID (``req``) that links
verification tests, contract assumptions, and report sections back to a
single source of truth.

Three Requirement types ship with step 3 — they cover the worked examples in
the design doc:

- :class:`TempRange`       — ambient/storage temperature envelopes
- :class:`SupplyEnvelope`  — voltage rails with operating + transient bounds
- :class:`CurrentBudget`   — max current draw, optionally scoped to a mode

Construction auto-registers the instance in the module-level registry, so
once :mod:`project.requirements` is imported anywhere in the process, every
declared Requirement is discoverable by ID via :func:`show` or :func:`list_all`.

Input flexibility for Quantity-valued fields:

>>> TempRange(min=Constant(-40.0, degC), max=Constant(85.0, degC), req="REQ-ENV-001")
>>> TempRange(min="-40 degC", max="85 degC", req="REQ-ENV-001")
>>> SupplyEnvelope(nominal=12 * V, min=9 * V, max=16 * V, req="REQ-PWR-001")

The design doc shows ``min=-40 * degC`` literally, but Pint refuses that
operation on offset units (degC, degF) — wrap with ``Constant(...)`` or use
the string form for temperature fields.
"""
from __future__ import annotations

from typing import Any

import pint
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from framework._toml import TomlError, parse_pint
from framework.quantity import Quantity as _FQ
from framework.units import registry


# ---------------------------------------------------------------------------
# Module-level registry. Populated by Requirement.__init__ on construction;
# `from project.requirements import *` is the natural population trigger.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, "Requirement"] = {}


def register(req: "Requirement") -> None:
    """Add ``req`` to the global registry.

    Idempotent for re-construction of the *same* requirement (same ``req`` ID
    and same field values — Pydantic equality). Raises ``ValueError`` if the
    ID is already taken by a Requirement with different content.
    """
    existing = _REGISTRY.get(req.req)
    if existing is not None and existing != req:
        raise ValueError(
            f"requirement id {req.req!r} is already registered with different "
            f"content; existing={existing!r}, new={req!r}"
        )
    _REGISTRY[req.req] = req


def unregister(req_id: str) -> None:
    """Remove ``req_id`` if registered. No-op if it isn't."""
    _REGISTRY.pop(req_id, None)


def clear() -> None:
    """Empty the registry. Intended for test teardown."""
    _REGISTRY.clear()


def list_all() -> list["Requirement"]:
    """All currently registered Requirements, sorted by ID."""
    return sorted(_REGISTRY.values(), key=lambda r: r.req)


def show(req_id: str) -> "Requirement":
    """Look up a Requirement by ID. Raises ``KeyError`` with a suggestion."""
    try:
        return _REGISTRY[req_id]
    except KeyError:
        prefix = req_id.split("-")[0] if "-" in req_id else req_id[:3]
        nearby = sorted(r for r in _REGISTRY if r.startswith(prefix))
        suffix = f" Available with prefix {prefix!r}: {nearby}" if nearby else (
            f" Available: {sorted(_REGISTRY)}"
        )
        raise KeyError(f"no requirement registered with id {req_id!r}.{suffix}") from None


# ---------------------------------------------------------------------------
# Coercion helper: accept pint.Quantity, framework.Quantity, or Pint string.
# ---------------------------------------------------------------------------

def _coerce(
    value: Any,
    *,
    dimensionality: pint.UnitsContainer | None = None,
    location: str = "value",
) -> pint.Quantity:
    """Convert a user-supplied Quantity into a ``pint.Quantity``.

    Accepts:
      - ``pint.Quantity`` — used directly.
      - framework ``Quantity`` — must be a scalar (no scenario/mode axes,
        no range); the nominal is unwrapped.
      - ``str`` — parsed via :func:`framework._toml.parse_pint`.

    Optionally checks dimensionality (raises if mismatched).
    """
    # All "rejection" paths raise ValueError so pydantic wraps them into a
    # proper ValidationError. TypeError would propagate raw and miss the field
    # location pydantic adds automatically.
    if isinstance(value, pint.Quantity):
        result = value
    elif isinstance(value, _FQ):
        if value.by_scenario is not None or value.by_mode is not None:
            raise ValueError(
                f"{location}: requirement field must be a scalar Quantity "
                "(no scenario or mode axes)"
            )
        nom = value.nominal
        if isinstance(nom, tuple):
            raise ValueError(f"{location}: requirement field must be a scalar (not a range)")
        assert nom is not None
        result = registry.Quantity(nom, value.unit)
    elif isinstance(value, str):
        try:
            result = parse_pint(value, location=location)
        except TomlError as e:
            raise ValueError(str(e)) from e
    else:
        raise ValueError(
            f"{location}: requirement value must be a pint.Quantity, "
            f"framework.Quantity, or Pint-format string; got {type(value).__name__}"
        )
    if dimensionality is not None and result.dimensionality != dimensionality:
        raise ValueError(
            f"{location}: dimensionality mismatch — expected {dimensionality}, "
            f"got {result.dimensionality} ({result.units})"
        )
    return result


# Pre-computed dimensionality references — cheaper and clearer than re-deriving inline.
_DIM_TEMPERATURE = registry.kelvin.dimensionality
_DIM_VOLTAGE = registry.volt.dimensionality
_DIM_CURRENT = registry.ampere.dimensionality


# ---------------------------------------------------------------------------
# Base + specific Requirement types
# ---------------------------------------------------------------------------

class Requirement(BaseModel):
    """Base class — every Requirement carries a Jama ID and optional description.

    Subclasses add typed Quantity fields. Construction auto-registers the
    instance via :func:`register`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    req: str = Field(..., min_length=1, description="Jama requirement ID, e.g. 'REQ-PWR-001'")
    description: str | None = None

    def model_post_init(self, _ctx: Any) -> None:
        register(self)


def _temp_to_K(q: pint.Quantity) -> float:
    return float(q.to(registry.kelvin).magnitude)


class TempRange(Requirement):
    """An inclusive temperature range — e.g. ``OPERATING_TEMP`` or ``STORAGE_TEMP``."""

    min: pint.Quantity
    max: pint.Quantity

    @field_validator("min", mode="before")
    @classmethod
    def _coerce_min(cls, v: Any) -> pint.Quantity:
        return _coerce(v, dimensionality=_DIM_TEMPERATURE, location="TempRange.min")

    @field_validator("max", mode="before")
    @classmethod
    def _coerce_max(cls, v: Any) -> pint.Quantity:
        return _coerce(v, dimensionality=_DIM_TEMPERATURE, location="TempRange.max")

    @model_validator(mode="after")
    def _min_le_max(self) -> "TempRange":
        if _temp_to_K(self.min) > _temp_to_K(self.max):
            raise ValueError(
                f"TempRange {self.req}: min ({self.min}) > max ({self.max})"
            )
        return self


class SupplyEnvelope(Requirement):
    """A voltage rail's operating envelope, with optional transient bounds.

    Steady-state: ``min <= nominal <= max``.
    Transient (e.g. cold-crank, load-dump): ``transient_min <= min``
    and ``transient_max >= max`` when both are provided.
    """

    nominal: pint.Quantity
    min: pint.Quantity
    max: pint.Quantity
    transient_min: pint.Quantity | None = None
    transient_max: pint.Quantity | None = None

    @field_validator("nominal", mode="before")
    @classmethod
    def _coerce_nominal(cls, v: Any) -> pint.Quantity:
        return _coerce(v, dimensionality=_DIM_VOLTAGE, location="SupplyEnvelope.nominal")

    @field_validator("min", mode="before")
    @classmethod
    def _coerce_min(cls, v: Any) -> pint.Quantity:
        return _coerce(v, dimensionality=_DIM_VOLTAGE, location="SupplyEnvelope.min")

    @field_validator("max", mode="before")
    @classmethod
    def _coerce_max(cls, v: Any) -> pint.Quantity:
        return _coerce(v, dimensionality=_DIM_VOLTAGE, location="SupplyEnvelope.max")

    @field_validator("transient_min", mode="before")
    @classmethod
    def _coerce_tmin(cls, v: Any) -> pint.Quantity | None:
        if v is None:
            return None
        return _coerce(v, dimensionality=_DIM_VOLTAGE, location="SupplyEnvelope.transient_min")

    @field_validator("transient_max", mode="before")
    @classmethod
    def _coerce_tmax(cls, v: Any) -> pint.Quantity | None:
        if v is None:
            return None
        return _coerce(v, dimensionality=_DIM_VOLTAGE, location="SupplyEnvelope.transient_max")

    @model_validator(mode="after")
    def _check_envelope(self) -> "SupplyEnvelope":
        # Compare in volts to avoid surprises with mV / V mixing.
        V = registry.volt
        mn = float(self.min.to(V).magnitude)
        mx = float(self.max.to(V).magnitude)
        nom = float(self.nominal.to(V).magnitude)
        if not (mn <= nom <= mx):
            raise ValueError(
                f"SupplyEnvelope {self.req}: require min ({self.min}) <= "
                f"nominal ({self.nominal}) <= max ({self.max})"
            )
        if self.transient_min is not None:
            tmn = float(self.transient_min.to(V).magnitude)
            if tmn > mn:
                raise ValueError(
                    f"SupplyEnvelope {self.req}: transient_min ({self.transient_min}) "
                    f"must be <= min ({self.min}) — transients should expand the envelope"
                )
        if self.transient_max is not None:
            tmx = float(self.transient_max.to(V).magnitude)
            if tmx < mx:
                raise ValueError(
                    f"SupplyEnvelope {self.req}: transient_max ({self.transient_max}) "
                    f"must be >= max ({self.max}) — transients should expand the envelope"
                )
        return self


class CurrentBudget(Requirement):
    """Maximum allowed current draw, optionally scoped to a mode.

    ``applies_to_mode`` ties the budget to a specific system mode (typically
    ``"sleep"`` for quiescent-current limits). If ``None``, the budget applies
    in every mode.
    """

    max: pint.Quantity
    applies_to_mode: str | None = None

    @field_validator("max", mode="before")
    @classmethod
    def _coerce_max(cls, v: Any) -> pint.Quantity:
        return _coerce(v, dimensionality=_DIM_CURRENT, location="CurrentBudget.max")

    @model_validator(mode="after")
    def _max_positive(self) -> "CurrentBudget":
        if float(self.max.to(registry.ampere).magnitude) <= 0:
            raise ValueError(
                f"CurrentBudget {self.req}: max ({self.max}) must be > 0"
            )
        return self


__all__ = [
    "CurrentBudget",
    "Requirement",
    "SupplyEnvelope",
    "TempRange",
    "clear",
    "list_all",
    "register",
    "show",
    "unregister",
]
