"""Smoke tests for shipped instances + families."""
from __future__ import annotations

import math

from framework.units import A, V, W, K, Ohm, degC, mA, percent, uA

from components.families.capacitors.grm_murata_x7r import GRM_X7R
from components.families.resistors.erj3_panasonic import ERJ3
from components.instances.mosfets.irlml6344 import IRLML6344
from components.instances.semiconductors.tja1051t_3 import TJA1051T_3
from components.types import Resistor, Capacitor, MOSFET, SmtSize, Dielectric


class TestERJ3Family:
    def test_mints_a_10k_resistor(self) -> None:
        r = ERJ3.instance(value=10_000 * Ohm, size=SmtSize.IMP0603)
        assert isinstance(r, Resistor)
        assert math.isclose(r.value.to(Ohm).at(), 10_000)
        assert math.isclose(r.power_rating.to(W).at(), 0.1)
        assert r.manufacturer == "Panasonic"

    def test_size_outside_available_rejected(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            ERJ3.instance(value=10 * Ohm, size=SmtSize.IMP2010)


class TestGRMX7RFamily:
    def test_mints_a_capacitor(self) -> None:
        from framework.units import uF
        # 100 nF in the 0603 form factor at 25 V working
        c = GRM_X7R.instance(value=0.1 * uF, size=SmtSize.IMP0603)
        assert isinstance(c, Capacitor)
        assert c.dielectric == Dielectric.X7R
        assert math.isclose(c.voltage_rating.to(V).at(), 25.0)


class TestTJA1051T3:
    def test_supply_current_modes_present(self) -> None:
        assert set(TJA1051T_3.supply_current_by_mode) == {"off", "sleep", "active", "diagnostic"}

    def test_supply_current_active_range(self) -> None:
        active = TJA1051T_3.supply_current_by_mode["active"]
        lo, hi = active.at()
        assert math.isclose(lo, 45e-3)
        assert math.isclose(hi, 65e-3)

    def test_supply_voltage_range(self) -> None:
        lo, hi = TJA1051T_3.supply_voltage_range.at()
        assert math.isclose(lo, 4.75)
        assert math.isclose(hi, 5.25)

    def test_thermal_parameters(self) -> None:
        assert TJA1051T_3.r_thermal_ja is not None
        assert math.isclose(TJA1051T_3.r_thermal_ja.to(K / W).at(), 120.0)
        assert TJA1051T_3.t_j_max is not None
        assert math.isclose(TJA1051T_3.t_j_max.to(degC).at(), 150.0)


class TestIRLML6344:
    def test_rds_on_scenarios(self) -> None:
        # Datasheet shows rds_on increasing with temperature: 28 mOhm @ 25 C, 38 mOhm @ 125 C.
        rds = IRLML6344.rds_on
        assert math.isclose(rds.at(scenario="nominal"), 0.028)
        assert math.isclose(rds.at(scenario="max_temp"), 0.038)

    def test_v_gs_th_min_typ_max(self) -> None:
        vth = IRLML6344.v_gs_th
        assert math.isclose(vth.at(scenario="min"), 0.6)
        assert math.isclose(vth.at(scenario="typ"), 1.1)
        assert math.isclose(vth.at(scenario="max"), 1.5)

    def test_ratings(self) -> None:
        assert math.isclose(IRLML6344.v_ds_max.to(V).at(), 30.0)
        assert math.isclose(IRLML6344.i_d_max.to(A).at(), 5.0)
