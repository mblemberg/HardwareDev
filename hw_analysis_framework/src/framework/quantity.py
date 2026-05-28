"""The atomic Quantity type — design doc section 6.1.

Quantity can vary along `by_scenario` (inner axis) and/or `by_mode` (outer axis).
A constant varies along neither. Arithmetic propagates both axes, enforces unit
compatibility via Pint, and produces a new immutable Quantity.

Range support: a scenario value may be a scalar (float, in `unit`) or a
2-tuple (min, max) — interval arithmetic is performed across ranges. Distributions
are deferred to a later phase (section 7.5, Monte Carlo opt-in).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from typing import Union

import pint

from framework.provenance import ProvenanceRef
from framework.units import registry

Scalar = float
Range = tuple[float, float]
ScalarOrRange = Union[Scalar, Range]
PintLike = Union[pint.Quantity, "Quantity"]

INVARIANT = "_ALL_"  # indicates that this value is the same across all scenarios


def _as_range(v: ScalarOrRange) -> Range:
    return v if isinstance(v, tuple) else (v, v)


def _collapse(r: Range) -> ScalarOrRange:
    """Canonicalize a range: a zero-width interval is stored as a scalar.

    This is the framework's canonical-form contract — a value with no spread
    (``RangeQuantity(5, 5)``, or any interval that pinches to a point during
    arithmetic, e.g. ``x - x``) is held as a plain scalar, not ``(v, v)``.
    Scalars and ``(v, v)`` tuples are behaviorally identical downstream because
    every consumer re-expands via ``_as_range``; collapsing keeps zero-width
    tuples from propagating indefinitely.
    """
    min, max = r  # noqa: A001
    return min if min == max else (min, max)


def _magnitude_in(value: float | pint.Quantity | Quantity, unit: pint.Unit) -> float:
    """The bare magnitude that ``value`` has when expressed in ``unit``.

    Accepts a raw number, a Pint quantity, or a scalar framework Quantity, and
    returns just the number (the unit is tracked once on the owning Quantity, not
    repeated per value). Scalar framework Quantities are unwrapped offset-aware;
    axed or range Quantities raise — spec bounds must be single points.
    """
    if isinstance(value, pint.Quantity):
        return float(value.to(unit).magnitude)
    if isinstance(value, Quantity):
        if value.by_scenario is not None or value.by_mode is not None:
            raise TypeError(
                "spec bound must be a scalar Quantity, not one carrying "
                "scenario or mode axes"
            )
        nom = value.value
        if isinstance(nom, tuple):
            raise TypeError("spec bound must be a scalar, not a range")
        assert nom is not None
        return float(registry.Quantity(nom, value.unit).to(unit).magnitude)
    return float(value)


def _coerce_scenario_value(
    value: ScalarOrRange | pint.Quantity | tuple[pint.Quantity, pint.Quantity],
    unit: pint.Unit,
) -> ScalarOrRange:
    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError(
                f"Range scenario value must be (min, max); got tuple of length {len(value)}"
            )
        min, max = value  # noqa: A001
        min_f = _magnitude_in(min, unit)
        max_f = _magnitude_in(max, unit)
        if min_f > max_f:
            raise ValueError(
                f"Range scenario min ({min_f}) must be <= max ({max_f}) in unit {unit}"
            )
        return _collapse((min_f, max_f))
    return _magnitude_in(value, unit)


@dataclass(frozen=True)
class Quantity:
    """Immutable value with mandatory unit and optional scenario/mode axes.

    Construction rules:
    - `unit` is mandatory.
    - `by_scenario` keys are scenario names; ``INVARIANT`` (``"_ALL_"``) denotes scenario-invariant.
    - `by_mode` values are themselves Quantities (recursive). Inner Quantities
      must share the outer's unit.
    - At least one of `by_scenario`, `by_mode`, or `value` must be set.

    Use the factories `Constant(value, unit)` and `RangeQuantity(min, max, unit)`
    for the common no-axis cases.
    """

    unit: pint.Unit
    by_scenario: dict[str, ScalarOrRange] | None = None
    by_mode: dict[str, Quantity] | None = None
    value: ScalarOrRange | None = None
    provenance: ProvenanceRef = field(default_factory=ProvenanceRef)

    def __post_init__(self) -> None:
        if not isinstance(self.unit, pint.Unit):
            raise TypeError(f"Quantity.unit must be a pint.Unit, got {type(self.unit)}")
        set_fields = [
            n for n in ("by_scenario", "by_mode", "value")
            if getattr(self, n) is not None
        ]
        if not set_fields:
            raise ValueError(
                "Quantity must specify at least one of: by_scenario, by_mode, value"
            )
        if len(set_fields) > 1:
            raise ValueError(
                f"Quantity carries more than one of by_scenario/by_mode/value "
                f"({set_fields}); the axes nest — put scenario variation *inside* "
                f"each by_mode child, not alongside it"
            )
        if self.by_scenario is not None and not self.by_scenario:
            raise ValueError("by_scenario must be non-empty if provided")
        if self.by_mode is not None:
            if not self.by_mode:
                raise ValueError("by_mode must be non-empty if provided")
            # Collect each mode-child's non-invariant scenario keys; they must
            # agree across modes. A child that is scenario-invariant (no
            # by_scenario, or only INVARIANT) opts out — that's the legitimate
            # "active varies by scenario, sleep is flat" case. Disagreement
            # among the non-invariant children signals a construction bug.
            scenario_key_sets: list[tuple[str, frozenset[str]]] = []
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
                if child.by_scenario is not None:
                    keys = frozenset(child.by_scenario) - {INVARIANT}
                    if keys:
                        scenario_key_sets.append((mode_name, keys))
            if scenario_key_sets:
                ref_mode, ref_keys = scenario_key_sets[0]
                for mode_name, keys in scenario_key_sets[1:]:
                    if keys != ref_keys:
                        raise ValueError(
                            f"by_mode children disagree on scenario keys: mode "
                            f"'{ref_mode}' has {set(ref_keys)} but mode "
                            f"'{mode_name}' has {set(keys)}; non-invariant scenario "
                            f"keys must match across modes (use INVARIANT for "
                            f"scenario-invariant modes)"
                        )
        if self.by_scenario is not None:
            coerced = {
                k: _coerce_scenario_value(v, self.unit)
                for k, v in self.by_scenario.items()
            }
            object.__setattr__(self, "by_scenario", coerced)
        if self.value is not None:
            object.__setattr__(
                self, "value", _coerce_scenario_value(self.value, self.unit)
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
                raise KeyError(f"Mode '{mode}' not in {list(self.by_mode)}") from e
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
            raise KeyError(f"Scenario '{scenario}' not in {list(self.by_scenario)}")
        assert self.value is not None
        return self.value

    def within(
        self,
        min: pint.Quantity | Quantity | float,  # noqa: A002
        max: pint.Quantity | Quantity | float,  # noqa: A002
    ) -> bool:
        """True iff every scenario/mode evaluation lies within [min, max].

        ``min`` and ``max`` may be:

        - ``pint.Quantity`` (e.g. ``3.3 * units.V``) — convenient for non-offset units;
        - framework ``Quantity`` (e.g. ``Constant(125, units.degC)``) — works for
          offset units like degC/degF where ``125 * degC`` raises in Pint;
        - plain numbers — assumed to be in ``self.unit``.
        """
        min_f = _magnitude_in(min, self.unit)
        max_f = _magnitude_in(max, self.unit)
        for v in self._iter_scenario_values():
            v_min, v_max = _as_range(v)
            if v_min < min_f or v_max > max_f:
                return False
        return True

    def iter_axes(
        self,
    ) -> Iterator[tuple[str | None, str | None, ScalarOrRange]]:
        """Yield ``(scenario, mode, value)`` for every axis combination.

        Scenario and mode are ``None`` when the Quantity doesn't carry that
        axis at the leaf being visited. ``value`` is a scalar or ``(min, max)``
        range tuple in ``self.unit``. Used by run-time contract consistency
        (design doc 6.7) and verification-test result enumeration (6.8) to
        report the exact corner(s) where a check failed.
        """
        if self.by_mode is not None:
            for mode, child in self.by_mode.items():
                for s, _ignored, v in child.iter_axes():
                    yield (s, mode, v)
            return
        if self.by_scenario is not None:
            for s, v in self.by_scenario.items():
                yield (s, None, v)
            return
        assert self.value is not None
        yield (None, None, self.value)

    def _iter_scenario_values(self) -> list[ScalarOrRange]:
        if self.by_mode is not None:
            out: list[ScalarOrRange] = []
            for child in self.by_mode.values():
                out.extend(child._iter_scenario_values())
            return out
        if self.by_scenario is not None:
            return list(self.by_scenario.values())
        assert self.value is not None
        return [self.value]

    def to(self, target_unit: pint.Unit) -> Quantity:
        """Return an equivalent Quantity expressed in `target_unit`.

        Per-magnitude conversion through Pint, so offset units (degC, degF)
        convert correctly: 358.15 K → 85.0 °C, not 358.15 × (-272.15).
        Note that adding a K-unit Quantity to a degC-unit Quantity uses
        offset-aware conversion on the operand, which is *not* what you want
        for temperature deltas — do thermal math in K and convert to °C
        only for display.
        """
        if target_unit == self.unit:
            return self
        src_dim = registry.Quantity(1.0, self.unit).dimensionality
        dst_dim = registry.Quantity(1.0, target_unit).dimensionality
        if src_dim != dst_dim:
            raise pint.DimensionalityError(self.unit, target_unit)
        src = self.unit
        dst = target_unit

        def _convert(x: float) -> float:
            return float(registry.Quantity(x, src).to(dst).magnitude)

        return self._map_scalars(_convert, new_unit=target_unit)

    def _map_scalars(
        self,
        fn,
        new_unit: pint.Unit | None = None,
    ) -> Quantity:
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
        assert self.value is not None
        new_nom = _collapse(tuple(fn(x) for x in _as_range(self.value)))  # type: ignore[arg-type]
        return replace(self, value=new_nom, unit=u)

    def __neg__(self) -> Quantity:
        return self._map_scalars(lambda x: -x)

    def __add__(self, other: PintLike | float | int) -> Quantity:
        return _binop(self, other, _add_ranges, _add_units)

    def __radd__(self, other: PintLike | float | int) -> Quantity:
        return _binop(_lift(other, self.unit), self, _add_ranges, _add_units)

    def __sub__(self, other: PintLike | float | int) -> Quantity:
        return _binop(self, other, _sub_ranges, _add_units)

    def __rsub__(self, other: PintLike | float | int) -> Quantity:
        return _binop(_lift(other, self.unit), self, _sub_ranges, _add_units)

    def __mul__(self, other: PintLike | float | int) -> Quantity:
        return _binop(self, other, _mul_ranges, _mul_units)

    def __rmul__(self, other: PintLike | float | int) -> Quantity:
        return _binop(_lift_dimensionless(other), self, _mul_ranges, _mul_units)

    def __truediv__(self, other: PintLike | float | int) -> Quantity:
        return _binop(self, other, _div_ranges, _div_units)

    def __rtruediv__(self, other: PintLike | float | int) -> Quantity:
        return _binop(_lift_dimensionless(other), self, _div_ranges, _div_units)

    def __pow__(self, n: int) -> Quantity:
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
    a_min, a_max = _as_range(a)
    b_min, b_max = _as_range(b)
    return _collapse((a_min + b_min, a_max + b_max))


def _sub_ranges(a: ScalarOrRange, b: ScalarOrRange) -> ScalarOrRange:
    a_min, a_max = _as_range(a)
    b_min, b_max = _as_range(b)
    return _collapse((a_min - b_max, a_max - b_min))


def _mul_ranges(a: ScalarOrRange, b: ScalarOrRange) -> ScalarOrRange:
    a_min, a_max = _as_range(a)
    b_min, b_max = _as_range(b)
    corners = (a_min * b_min, a_min * b_max, a_max * b_min, a_max * b_max)
    return _collapse((min(corners), max(corners)))


def _div_ranges(a: ScalarOrRange, b: ScalarOrRange) -> ScalarOrRange:
    b_min, b_max = _as_range(b)
    if b_min <= 0.0 <= b_max:
        raise ZeroDivisionError(
            "Quantity division by a range that includes zero is undefined"
        )
    a_min, a_max = _as_range(a)
    corners = (a_min / b_min, a_min / b_max, a_max / b_min, a_max / b_max)
    return _collapse((min(corners), max(corners)))


def _pow_range_fn(n: int, scale: float):
    def _fn(x: float) -> float:
        return scale * (x**n)

    return _fn


# --- operand lifting -------------------------------------------------------


def _lift(value: PintLike | float | int, ref_unit: pint.Unit) -> Quantity:
    if isinstance(value, Quantity):
        return value
    if isinstance(value, pint.Quantity):
        return Constant(float(value.to(ref_unit).magnitude), ref_unit)
    if isinstance(value, (int, float)):
        # Bare numbers in additive context must match the ref unit's dimensionality.
        # Treat as already-in-unit (additive only — multiplicative path uses _lift_dimensionless).
        return Constant(float(value), ref_unit)
    raise TypeError(f"Cannot lift {type(value).__name__} to Quantity")


def _lift_dimensionless(value: PintLike | float | int) -> Quantity:
    if isinstance(value, Quantity):
        return value
    if isinstance(value, pint.Quantity):
        return Constant(float(value.magnitude), value.units)
    if isinstance(value, (int, float)):
        return Constant(float(value), registry.dimensionless)
    raise TypeError(f"Cannot lift {type(value).__name__} to Quantity")


def _binop(
    left: Quantity,
    right_raw: PintLike | float | int,
    range_op,
    unit_op,
) -> Quantity:
    # Bare-number lifting depends on the operation:
    #   - Additive (+/-): treat the number as already-in-left's-unit. ``Q(5 V) + 1``
    #     means 6 V, not 5 V + 1 of any other unit.
    #   - Multiplicative (*, /): treat the number as dimensionless. ``Q(5 V) * 2``
    #     means 10 V, not 10 V². Latent bug found 2026-05-16: __mul__ / __truediv__
    #     used to hit the additive branch via _lift(value, left.unit), which
    #     squared the unit (10 V * 1.0 → 10 V²). All multiplicative bare-number
    #     ops now go through _lift_dimensionless.
    if isinstance(right_raw, Quantity):
        right = right_raw
    elif unit_op is _add_units:
        right = _lift(right_raw, left.unit)
    else:
        right = _lift_dimensionless(right_raw)

    # Convert right into left's unit *for additive ops* (where unit_op == _add_units).
    if unit_op is _add_units:
        if (
            registry.Quantity(1.0, right.unit).dimensionality
            != registry.Quantity(1.0, left.unit).dimensionality
        ):
            raise pint.DimensionalityError(left.unit, right.unit)
        if right.unit != left.unit:
            right = right.to(left.unit)
    out_unit = unit_op(left.unit, right.unit)

    # Combine across mode axis (outer).
    if left.by_mode is not None or right.by_mode is not None:
        return _combine_modes(left, right, range_op, unit_op, out_unit)

    # Combine across scenario axis (inner).
    return _combine_scenarios(left, right, range_op, out_unit)


def _combine_modes(
    left: Quantity, right: Quantity, range_op, unit_op, out_unit
) -> Quantity:
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
        new_modes = {
            m: _binop(child, right, range_op, unit_op)
            for m, child in left_modes.items()
        }
    else:
        assert right_modes is not None
        new_modes = {
            m: _binop(left, child, range_op, unit_op)
            for m, child in right_modes.items()
        }
    return Quantity(unit=out_unit, by_mode=new_modes)


def _combine_scenarios(left: Quantity, right: Quantity, range_op, out_unit) -> Quantity:
    left_scen = left.by_scenario
    right_scen = right.by_scenario
    if left_scen is None and right_scen is None:
        assert left.value is not None and right.value is not None
        return Quantity(unit=out_unit, value=range_op(left.value, right.value))
    if left_scen is not None and right_scen is not None:
        keys = _aligned_scenario_keys(left_scen, right_scen)
        new_scen = {
            k: range_op(_pick(left_scen, k), _pick(right_scen, k)) for k in keys
        }
        return Quantity(unit=out_unit, by_scenario=new_scen)
    if left_scen is not None:
        scalar_r = right.value if right.value is not None else None
        assert scalar_r is not None
        new_scen = {k: range_op(v, scalar_r) for k, v in left_scen.items()}
        return Quantity(unit=out_unit, by_scenario=new_scen)
    assert right_scen is not None
    scalar_l = left.value
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
        return Quantity(unit=unit, value=float(value.to(unit).magnitude))
    if unit is None:
        raise TypeError("Constant requires a unit when value is not a pint.Quantity")
    return Quantity(unit=unit, value=float(value))


def RangeQuantity(
    min: float | pint.Quantity,  # noqa: A002
    max: float | pint.Quantity,  # noqa: A002
    unit: pint.Unit | None = None,
) -> Quantity:
    """A scenario-invariant range Quantity (worst-case min/max with no scenario detail)."""
    if isinstance(min, pint.Quantity):
        if unit is None:
            unit = min.units
        min_f = float(min.to(unit).magnitude)
    else:
        if unit is None:
            raise TypeError(
                "RangeQuantity requires a unit when min is not a pint.Quantity"
            )
        min_f = float(min)
    if isinstance(max, pint.Quantity):
        max_f = float(max.to(unit).magnitude)
    else:
        max_f = float(max)
    if min_f > max_f:
        raise ValueError(
            f"RangeQuantity min ({min_f}) must be <= max ({max_f}) in unit {unit}"
        )
    return Quantity(unit=unit, value=(min_f, max_f) if min_f != max_f else min_f)


__all__ = [
    "Constant",
    "INVARIANT",
    "Quantity",
    "Range",
    "RangeQuantity",
    "Scalar",
    "ScalarOrRange",
]
