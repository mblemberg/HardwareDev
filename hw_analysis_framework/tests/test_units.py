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


def pytest_approx(actual: float, expected: float, tol: float = 1e-9) -> bool:
    assert abs(actual - expected) < tol, f"{actual} != {expected}"
    return True
