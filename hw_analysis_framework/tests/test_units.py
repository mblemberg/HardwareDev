"""Smoke tests for the shared Pint registry."""
from __future__ import annotations

import pint

from framework import units
from framework.units import A, V, kOhm, mA, registry, uA


def test_registry_is_singleton_shared_across_symbols() -> None:
    assert V._REGISTRY is registry
    assert mA._REGISTRY is registry
    assert kOhm._REGISTRY is registry


def test_voltage_current_resistance_compose() -> None:
    v = 3.3 * V
    i = 2 * mA
    r = (v / i).to(kOhm)
    assert pytest_approx(r.magnitude, 1.65)


def test_si_prefix_conversion() -> None:
    assert pytest_approx((1 * A).to(mA).magnitude, 1000.0)
    assert pytest_approx((1500 * uA).to(mA).magnitude, 1.5)


def test_unit_arithmetic_is_dimensional() -> None:
    p = (5 * V) * (10 * mA)
    assert pytest_approx(p.to(units.mW).magnitude, 50.0)


def test_incompatible_units_raise() -> None:
    import pytest
    with pytest.raises(pint.DimensionalityError):
        (1 * V) + (1 * A)


def test_length_units_are_length_dimensional() -> None:
    from framework.units import cm, inch, m, mm, nm, um
    for u in (m, mm, um, nm, cm, inch):
        assert (1 * u).dimensionality == (1 * m).dimensionality


def test_mil_override_is_ee_sense() -> None:
    # Pint's default mil is a dimensionless 1/1000 ratio; we redefine it
    # to mean 1/1000 inch. 1 mil = 25.4 µm; 1000 mil = 1 inch.
    from framework.units import inch, mil
    assert (1 * mil).dimensionality == (1 * inch).dimensionality
    assert pytest_approx((1 * mil).to("micrometer").magnitude, 25.4, tol=1e-9)
    assert pytest_approx((1000 * mil).to(inch).magnitude, 1.0, tol=1e-9)


def test_mil_override_visible_to_string_parser() -> None:
    # The cache-clear in _redefine_unit is what makes this work — Pint
    # otherwise keeps the pre-override dimensionality cached.
    q = registry.parse_expression("5 mil")
    assert pytest_approx(q.to("micrometer").magnitude, 127.0, tol=1e-9)


def pytest_approx(actual: float, expected: float, tol: float = 1e-9) -> bool:
    assert abs(actual - expected) < tol, f"{actual} != {expected}"
    return True
