"""The atomic Quantity type — design doc section 6.1.

Quantity can vary along `by_scenario` (inner axis) and/or `by_mode` (outer axis).
A constant varies along neither. Arithmetic propagates both axes, enforces unit
compatibility via Pint, and produces a new immutable Quantity.

Range support: a scenario value may be a scalar (float, in `unit`) or a
2-tuple (lo, hi) — interval arithmetic is performed across ranges. Distributions
are deferred to a later phase (section 7.5, Monte Carlo opt-in).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Union

import pint

from framework.provenance import ProvenanceRef
from framework.units import registry

Scalar = float
Range = tuple[float, float]
ScalarOrRange = Union[Scalar, Range]
PintLike = Union[pint.Quantity, "Quantity"]

INVARIANT = "_"


def _as_range(v: ScalarOrRange) -> Range:
    return v if isinstance(v, tuple) else (v, v)


def _collapse(r: Range) -> ScalarOrRange:
    lo, hi = r
    return lo if lo == hi else (lo, hi)


def _coerce_to_unit(value: float | pint.Quantity, unit: pint.Unit) -> float:
    """Convert a raw number or Pint quantity into a float expressed in `unit`."""
    if isinstance(value, pint.Quantity):
        return float(value.to(unit).magnitude)
    return float(value)


def _coerce_scenario_value(
    value: ScalarOrRange | pint.Quantity | tuple[pint.Quantity, pint.Quantity],
    unit: pint.Unit,
) -> ScalarOrRange:
    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError(
                f"Range scenario value must be (lo, hi); got tuple of length {len(value)}"
            )
        lo, hi = value
        lo_f = _coerce_to_unit(lo, unit)
        hi_f = _coerce_to_unit(hi, unit)
        if lo_f > hi_f:
            raise ValueError(
                f"Range scenario lo ({lo_f}) must be <= hi ({hi_f}) in unit {unit}"
            )
        return _collapse((lo_f, hi_f))
    return _coerce_to_unit(value, unit)


@dataclass(frozen=True)
class Quantity:
    """Immutable value with mandatory unit and optional scenario/mode axes.

    Construction rules:
    - `unit` is mandatory.
    - `by_scenario` keys are scenario names; "_" denotes scenario-invariant.
    - `by_mode` values are themselves Quantities (recursive). Inner Quantities
      must share the outer's unit.
    - At least one of `by_scenario`, `by_mode`, or `nominal` must be set.

    Use the factories `Constant(value, unit)` and `RangeQuantity(lo, hi, unit)`
    for the common no-axis cases.
    """

    unit: pint.Unit
    by_scenario: dict[str, ScalarOrRange] | None = None
    by_mode: dict[str, "Quantity"] | None = None
    nominal: ScalarOrRange | None = None
    provenance: ProvenanceRef = field(default_factory=ProvenanceRef)

    def __post_init__(self) -> None:
        if not isinstance(self.unit, pint.Unit):
            raise TypeError(f"Quantity.unit must be a pint.Unit, got {type(self.unit)}")
        if self.by_scenario is None and self.by_mode is None and self.nominal is None:
            raise ValueError(
                "Quantity must specify at least one of: by_scenario, by_mode, nominal"
            )
        if self.by_scenario is not None and not self.by_scenario:
            raise ValueError("by_scenario must be non-empty if provided")
        if self.by_mode is not None:
            if not self.by_mode:
                raise ValueError("by_mode must be non-empty if provided")
            for mode_name, child in self.by_mode.items():
                if not isinstance(child, Quantity):
                    raise TypeError(
                        f"by_mode['{mode_name}'] must be a Quantity, got {type(child)}"
                    )
                if child.unit != self.unit:
                    raise ValueError(
                        f"by_mode['{mode_name}'] has unit {child.unit}, "
                        f"expected {self.unit}"
                    )
        if self.by_scenario is not None:
            coerced = {
                k: _coerce_scenario_value(v, self.unit)
                for k, v in self.by_scenario.items()
            }
            object.__setattr__(self, "by_scenario", coerced)
        if self.nominal is not None:
            object.__setattr__(
                self, "nominal", _coerce_scenario_value(self.nominal, self.unit)
            )

    def at(self, scenario: str | None = None, mode: str | None = None) -> ScalarOrRange:
        """Evaluate at a specific (scenario, mode) point.

        Returns a scalar (or range tuple) in the Quantity's `unit`. Raises
        KeyError if the axis is missing the requested key and no invariant
        fallback exists.
        """
        if self.by_mode is not None:
            if mode is None:
                raise KeyError(
                    f"This Quantity is mode-dependent (modes: {list(self.by_mode)}); "
                    "pass mode= to evaluate."
                )
            try:
                child = self.by_mode[mode]
            except KeyError as e:
                raise KeyError(
                    f"Mode '{mode}' not in {list(self.by_mode)}"
                ) from e
            return child.at(scenario=scenario)
        if self.by_scenario is not None:
            if scenario is not None and scenario in self.by_scenario:
                return self.by_scenario[scenario]
            if INVARIANT in self.by_scenario:
                return self.by_scenario[INVARIANT]
            if scenario is None:
                raise KeyError(
                    f"This Quantity is scenario-dependent (scenarios: "
                    f"{list(self.by_scenario)}); pass scenario= to evaluate."
                )
            raise KeyError(
                f"Scenario '{scenario}' not in {list(self.by_scenario)}"
            )
        assert self.nominal is not None
        return self.nominal

    def within(self, lo: pint.Quantity, hi: pint.Quantity) -> bool:
        """True iff every scenario/mode evaluation lies within [lo, hi]."""
        lo_f = _coerce_to_unit(lo, self.unit)
        hi_f = _coerce_to_unit(hi, self.unit)
        for v in self._iter_scenario_values():
            v_lo, v_hi = _as_range(v)
            if v_lo < lo_f or v_hi > hi_f:
                return False
        return True

    def _iter_scenario_values(self) -> list[ScalarOrRange]:
        if self.by_mode is not None:
            out: list[ScalarOrRange] = []
            for child in self.by_mode.values():
                out.extend(child._iter_scenario_values())
            return out
        if self.by_scenario is not None:
            return list(self.by_scenario.values())
        assert self.nominal is not None
        return [self.nominal]

    def to(self, target_unit: pint.Unit) -> "Quantity":
        """Return an equivalent Quantity expressed in `target_unit`."""
        if target_unit == self.unit:
            return self
        if not registry.Quantity(1, self.unit).check(registry.Quantity(1, target_unit).dimensionality):
            raise pint.DimensionalityError(self.unit, target_unit)
        factor = float(registry.Quantity(1, self.unit).to(target_unit).magnitude)
        return self._map_scalars(lambda x: x * factor, new_unit=target_unit)

    def _map_scalars(
        self,
        fn,
        new_unit: pint.Unit | None = None,
    ) -> "Quantity":
        u = new_unit if new_unit is not None else self.unit
        if self.by_mode is not None:
            new_modes = {
                m: child._map_scalars(fn, new_unit=new_unit)
                for m, child in self.by_mode.items()
            }
            return replace(self, by_mode=new_modes, unit=u)
        if self.by_scenario is not None:
            new_scen = {
                k: _collapse(tuple(fn(x) for x in _as_range(v)))  # type: ignore[arg-type]
                for k, v in self.by_scenario.items()
            }
            return replace(self, by_scenario=new_scen, unit=u)
        assert self.nominal is not None
        new_nom = _collapse(tuple(fn(x) for x in _as_range(self.nominal)))  # type: ignore[arg-type]
        return replace(self, nominal=new_nom, unit=u)

    def __neg__(self) -> "Quantity":
        return self._map_scalars(lambda x: -x)

    def __add__(self, other: PintLike | float | int) -> "Quantity":
        return _binop(self, other, _add_ranges, _add_units)

    def __radd__(self, other: PintLike | float | int) -> "Quantity":
        return _binop(_lift(other, self.unit), self, _add_ranges, _add_units)

    def __sub__(self, other: PintLike | float | int) -> "Quantity":
        return _binop(self, other, _sub_ranges, _add_units)

    def __rsub__(self, other: PintLike | float | int) -> "Quantity":
        return _binop(_lift(other, self.unit), self, _sub_ranges, _add_units)

    def __mul__(self, other: PintLike | float | int) -> "Quantity":
        return _binop(self, other, _mul_ranges, _mul_units)

    def __rmul__(self, other: PintLike | float | int) -> "Quantity":
        return _binop(_lift_dimensionless(other), self, _mul_ranges, _mul_units)

    def __truediv__(self, other: PintLike | float | int) -> "Quantity":
        return _binop(self, other, _div_ranges, _div_units)

    def __rtruediv__(self, other: PintLike | float | int) -> "Quantity":
        return _binop(_lift_dimensionless(other), self, _div_ranges, _div_units)

    def __pow__(self, n: int) -> "Quantity":
        if not isinstance(n, int):
            raise TypeError(
                f"Quantity exponent must be int (got {type(n).__name__}); "
                "non-integer powers would produce fractional dimensions"
            )
        new_unit_q = registry.Quantity(1.0, self.unit) ** n
        new_unit = new_unit_q.units
        scale = float(new_unit_q.magnitude)
        return self._map_scalars(_pow_range_fn(n, scale), new_unit=new_unit)


# --- arithmetic helpers ----------------------------------------------------


def _add_units(a: pint.Unit, b: pint.Unit) -> pint.Unit:
    one_a = registry.Quantity(1.0, a)
    one_b = registry.Quantity(1.0, b)
    if one_a.dimensionality != one_b.dimensionality:
        raise pint.DimensionalityError(a, b)
    return a


def _mul_units(a: pint.Unit, b: pint.Unit) -> pint.Unit:
    return (registry.Quantity(1.0, a) * registry.Quantity(1.0, b)).units


def _div_units(a: pint.Unit, b: pint.Unit) -> pint.Unit:
    return (registry.Quantity(1.0, a) / registry.Quantity(1.0, b)).units


def _convert_factor(src: pint.Unit, dst: pint.Unit) -> float:
    if src == dst:
        return 1.0
    return float(registry.Quantity(1.0, src).to(dst).magnitude)


def _add_ranges(a: ScalarOrRange, b: ScalarOrRange) -> ScalarOrRange:
    a_lo, a_hi = _as_range(a)
    b_lo, b_hi = _as_range(b)
    return _collapse((a_lo + b_lo, a_hi + b_hi))


def _sub_ranges(a: ScalarOrRange, b: ScalarOrRange) -> ScalarOrRange:
    a_lo, a_hi = _as_range(a)
    b_lo, b_hi = _as_range(b)
    return _collapse((a_lo - b_hi, a_hi - b_lo))


def _mul_ranges(a: ScalarOrRange, b: ScalarOrRange) -> ScalarOrRange:
    a_lo, a_hi = _as_range(a)
    b_lo, b_hi = _as_range(b)
    corners = (a_lo * b_lo, a_lo * b_hi, a_hi * b_lo, a_hi * b_hi)
    return _collapse((min(corners), max(corners)))


def _div_ranges(a: ScalarOrRange, b: ScalarOrRange) -> ScalarOrRange:
    b_lo, b_hi = _as_range(b)
    if b_lo <= 0.0 <= b_hi:
        raise ZeroDivisionError(
            "Quantity division by a range that includes zero is undefined"
        )
    a_lo, a_hi = _as_range(a)
    corners = (a_lo / b_lo, a_lo / b_hi, a_hi / b_lo, a_hi / b_hi)
    return _collapse((min(corners), max(corners)))


def _pow_range_fn(n: int, scale: float):
    def _fn(x: float) -> float:
        return scale * (x ** n)
    return _fn


# --- operand lifting -------------------------------------------------------


def _lift(value: PintLike | float | int, ref_unit: pint.Unit) -> "Quantity":
    if isinstance(value, Quantity):
        return value
    if isinstance(value, pint.Quantity):
        return Constant(float(value.to(ref_unit).magnitude), ref_unit)
    if isinstance(value, (int, float)):
        # Bare numbers in additive context must match the ref unit's dimensionality.
        # Treat as already-in-unit (additive only — multiplicative path uses _lift_dimensionless).
        return Constant(float(value), ref_unit)
    raise TypeError(f"Cannot lift {type(value).__name__} to Quantity")


def _lift_dimensionless(value: PintLike | float | int) -> "Quantity":
    if isinstance(value, Quantity):
        return value
    if isinstance(value, pint.Quantity):
        return Constant(float(value.magnitude), value.units)
    if isinstance(value, (int, float)):
        return Constant(float(value), registry.dimensionless)
    raise TypeError(f"Cannot lift {type(value).__name__} to Quantity")


def _binop(
    left: "Quantity",
    right_raw: PintLike | float | int,
    range_op,
    unit_op,
) -> "Quantity":
    # For multiplicative ops, dimensionless lift is the right semantics for plain
    # numbers; for additive ops, we treat plain numbers as "already in left.unit".
    # Caller passes the appropriately-lifted operand; we still accept raw to handle
    # the common Quantity-on-left case.
    right = _lift(right_raw, left.unit) if not isinstance(right_raw, Quantity) else right_raw

    # Convert right into left's unit *for additive ops* (where unit_op == _add_units).
    if unit_op is _add_units:
        if registry.Quantity(1.0, right.unit).dimensionality != registry.Quantity(1.0, left.unit).dimensionality:
            raise pint.DimensionalityError(left.unit, right.unit)
        if right.unit != left.unit:
            right = right.to(left.unit)
    out_unit = unit_op(left.unit, right.unit)

    # Combine across mode axis (outer).
    if left.by_mode is not None or right.by_mode is not None:
        return _combine_modes(left, right, range_op, unit_op, out_unit)

    # Combine across scenario axis (inner).
    return _combine_scenarios(left, right, range_op, out_unit)


def _combine_modes(left: "Quantity", right: "Quantity", range_op, unit_op, out_unit) -> "Quantity":
    left_modes = left.by_mode if left.by_mode is not None else None
    right_modes = right.by_mode if right.by_mode is not None else None
    if left_modes is not None and right_modes is not None:
        if set(left_modes) != set(right_modes):
            raise ValueError(
                f"Cannot combine Quantities with differing mode sets: "
                f"{set(left_modes)} vs {set(right_modes)}"
            )
        new_modes = {
            m: _binop(left_modes[m], right_modes[m], range_op, unit_op)
            for m in left_modes
        }
    elif left_modes is not None:
        new_modes = {m: _binop(child, right, range_op, unit_op) for m, child in left_modes.items()}
    else:
        assert right_modes is not None
        new_modes = {m: _binop(left, child, range_op, unit_op) for m, child in right_modes.items()}
    return Quantity(unit=out_unit, by_mode=new_modes)


def _combine_scenarios(left: "Quantity", right: "Quantity", range_op, out_unit) -> "Quantity":
    left_scen = left.by_scenario
    right_scen = right.by_scenario
    if left_scen is None and right_scen is None:
        assert left.nominal is not None and right.nominal is not None
        return Quantity(unit=out_unit, nominal=range_op(left.nominal, right.nominal))
    if left_scen is not None and right_scen is not None:
        keys = _aligned_scenario_keys(left_scen, right_scen)
        new_scen = {
            k: range_op(_pick(left_scen, k), _pick(right_scen, k))
            for k in keys
        }
        return Quantity(unit=out_unit, by_scenario=new_scen)
    if left_scen is not None:
        scalar_r = right.nominal if right.nominal is not None else None
        assert scalar_r is not None
        new_scen = {k: range_op(v, scalar_r) for k, v in left_scen.items()}
        return Quantity(unit=out_unit, by_scenario=new_scen)
    assert right_scen is not None
    scalar_l = left.nominal
    assert scalar_l is not None
    new_scen = {k: range_op(scalar_l, v) for k, v in right_scen.items()}
    return Quantity(unit=out_unit, by_scenario=new_scen)


def _aligned_scenario_keys(
    a: dict[str, ScalarOrRange], b: dict[str, ScalarOrRange]
) -> list[str]:
    a_keys = set(a) - {INVARIANT}
    b_keys = set(b) - {INVARIANT}
    if a_keys and b_keys and a_keys != b_keys:
        if not (a_keys <= b_keys or b_keys <= a_keys):
            raise ValueError(
                f"Cannot combine Quantities with disjoint scenario sets: "
                f"{a_keys} vs {b_keys}"
            )
    return sorted((a_keys | b_keys) or {INVARIANT})


def _pick(scen: dict[str, ScalarOrRange], key: str) -> ScalarOrRange:
    if key in scen:
        return scen[key]
    return scen[INVARIANT]


# --- factories -------------------------------------------------------------


def Constant(value: float | pint.Quantity, unit: pint.Unit | None = None) -> Quantity:
    """A scenario/mode-invariant Quantity.

    Accepts either `Constant(5.0, V)` or `Constant(5 * V)` (Pint expression).
    """
    if isinstance(value, pint.Quantity):
        if unit is None:
            unit = value.units
        return Quantity(unit=unit, nominal=float(value.to(unit).magnitude))
    if unit is None:
        raise TypeError("Constant requires a unit when value is not a pint.Quantity")
    return Quantity(unit=unit, nominal=float(value))


def RangeQuantity(
    lo: float | pint.Quantity,
    hi: float | pint.Quantity,
    unit: pint.Unit | None = None,
) -> Quantity:
    """A scenario-invariant range Quantity (worst-case min/max with no scenario detail)."""
    if isinstance(lo, pint.Quantity):
        if unit is None:
            unit = lo.units
        lo_f = float(lo.to(unit).magnitude)
    else:
        if unit is None:
            raise TypeError("RangeQuantity requires a unit when lo is not a pint.Quantity")
        lo_f = float(lo)
    if isinstance(hi, pint.Quantity):
        hi_f = float(hi.to(unit).magnitude)
    else:
        hi_f = float(hi)
    if lo_f > hi_f:
        raise ValueError(f"RangeQuantity lo ({lo_f}) must be <= hi ({hi_f}) in unit {unit}")
    return Quantity(unit=unit, nominal=(lo_f, hi_f) if lo_f != hi_f else lo_f)


__all__ = [
    "Constant",
    "INVARIANT",
    "Quantity",
    "Range",
    "RangeQuantity",
    "Scalar",
    "ScalarOrRange",
]
