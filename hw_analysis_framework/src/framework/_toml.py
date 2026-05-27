"""TOML loading helpers — Pint-string parsing with precise error locations.

The framework's TOML files (scenarios, modes, requirements, project config)
all require unit-bearing numeric values to be written as Pint expression
strings: ``"25 degC"``, ``"9.0 V"``, ``"100 ppm / degC"``. Bare numbers are
rejected at load time so a missing unit never propagates into compute.

Raised errors carry a ``location`` string identifying the file path, the
table, and the field, so editor errors are actionable.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pint

from framework.units import registry


class TomlError(ValueError):
    """A TOML file failed to parse or validate against framework conventions."""


# Splits a Pint-format string into (magnitude, unit). The unit part may be
# empty (dimensionless input like "0.01"). Constructed via two-arg
# registry.Quantity(magnitude, unit_str) so offset units (degC, degF) work —
# `parse_expression("25 degC")` and `Quantity("25 degC")` both raise
# OffsetUnitCalculusError, but `Quantity(25, "degC")` does not.
_NUMERIC = re.compile(
    r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*?)\s*$"
)


def read_toml(path: Path | str) -> dict[str, Any]:
    """Read a TOML file from disk. Raises TomlError with the path on failure."""
    p = Path(path)
    if not p.is_file():
        raise TomlError(f"TOML file not found: {p}")
    try:
        return tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise TomlError(f"{p}: {e}") from e


def parse_pint(value: Any, *, location: str) -> pint.Quantity:
    """Parse a value as a Pint quantity. Strict: only strings accepted.

    ``location`` is folded into the error message — pass something like
    ``"scenarios.toml: scenario 'cold_low_vin' field 'vbat'"``.

    Bare numbers (int, float) are *rejected* on purpose: the framework's
    contract is that every value in TOML carries explicit units.
    """
    if isinstance(value, pint.Quantity):
        return value
    if not isinstance(value, str):
        raise TomlError(
            f"{location}: expected a Pint-format string (e.g. '25 degC'); "
            f"got {type(value).__name__} {value!r}. "
            "All unit-bearing values must include their unit explicitly."
        )
    m = _NUMERIC.match(value)
    if m is None:
        raise TomlError(
            f"{location}: cannot parse {value!r} — expected '<number> <unit>' "
            "(e.g. '25 degC', '9.0 V', '20 ppm')"
        )
    mag_str, unit_str = m.group(1), m.group(2)
    try:
        magnitude: float | int = (
            float(mag_str) if ("." in mag_str or "e" in mag_str.lower()) else int(mag_str)
        )
    except ValueError as e:
        raise TomlError(f"{location}: bad magnitude {mag_str!r} in {value!r} — {e}") from e
    try:
        if unit_str:
            return registry.Quantity(magnitude, unit_str)
        return registry.Quantity(magnitude)
    except (pint.UndefinedUnitError, pint.PintError, ValueError, AttributeError) as e:
        raise TomlError(
            f"{location}: cannot interpret unit {unit_str!r} in {value!r} — {e}"
        ) from e


__all__ = ["TomlError", "parse_pint", "read_toml"]
