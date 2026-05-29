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
    from framework.units import cm, inch, m, mm, nm, thou, um
    for u in (m, mm, um, nm, cm, inch, thou):
        assert (1 * u).dimensionality == (1 * m).dimensionality


def test_thou_is_the_ee_mil() -> None:
    # 1 thou = 1/1000 inch = 25.4 µm. Pint's default `mil` is a dimensionless
    # 1/1000 ratio (not the EE sense), so `thou` is the right symbol until we
    # commit to overriding Pint's `mil`. See units.py.
    from framework.units import inch, thou
    assert pytest_approx((1 * thou).to("micrometer").magnitude, 25.4, tol=1e-9)
    assert pytest_approx((1000 * thou).to(inch).magnitude, 1.0, tol=1e-9)


def pytest_approx(actual: float, expected: float, tol: float = 1e-9) -> bool:
    assert abs(actual - expected) < tol, f"{actual} != {expected}"
    return True
