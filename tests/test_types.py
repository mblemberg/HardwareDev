"""Smoke tests for each component-type schema — construction + validation."""
from __future__ import annotations

import math

import pydantic
import pytest

from framework import Quantity
from framework.units import A, Hz, K, Ohm, V, degC, mA, mOhm, nC, percent, ppm, uA, uF

from components.types import (
    BJT,
    BuckConverter,
    Capacitor,
    CapacitorFamily,
    Dielectric,
    Diode,
    IntegratedCircuit,
    LDO,
    MOSFET,
    Resistor,
    ResistorFamily,
    SmtSize,
)


class TestResistor:
    def test_basic(self) -> None:
        r = Resistor(
            part_number="ERJ-3-0603-10K",
            value=10_000 * Ohm,
            size=SmtSize.IMP0603,
            tolerance=0.01,
            temp_coefficient=100 * ppm / K,
            power_rating=0.1 * V * A,       # 100 mW equivalent
            max_voltage=75 * V,
            manufacturer="Panasonic",
            series="ERJ-3",
        )
        assert r.size == SmtSize.IMP0603
        assert math.isclose(r.value.to(Ohm).at(), 10_000)

    def test_size_must_be_enum(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            Resistor(
                part_number="X", value=10 * Ohm, size="not-a-size",  # type: ignore[arg-type]
                tolerance=0.01, temp_coefficient=100 * ppm / K,
                power_rating=0.1 * V * A, max_voltage=75 * V,
                manufacturer="X", series="X",
            )

    def test_bare_number_value_lifted_to_dimensionless(self) -> None:
        # Bare numbers lift to dimensionless. Surfaces as a downstream error if
        # the resistor's value is then combined with a real-unit Quantity in
        # an arithmetic op -- which is the intended catch.
        r = Resistor(
            part_number="X", value=10_000,  # type: ignore[arg-type]
            size=SmtSize.IMP0603,
            tolerance=0.01, temp_coefficient=100 * ppm / K,
            power_rating=0.1 * V * A, max_voltage=75 * V,
            manufacturer="X", series="X",
        )
        assert r.value.unit.dimensionless


class TestCapacitor:
    def test_basic(self) -> None:
        c = Capacitor(
            part_number="GRM-0603-25V-100nF",
            value=100e-9 * uF * 1000,    # 100 nF expressed in nF then via uF *1000
            size=SmtSize.IMP0603,
            dielectric=Dielectric.X7R,
            voltage_rating=25 * V,
            tolerance=0.10,
            manufacturer="Murata",
            series="GRM",
        )
        assert c.dielectric == Dielectric.X7R

    def test_optional_tempco(self) -> None:
        c = Capacitor(
            part_number="X",
            value=100 * uF / 1e6 * 1e6,
            size=SmtSize.IMP0805,
            dielectric=Dielectric.C0G,
            voltage_rating=50 * V,
            tolerance=0.01,
            manufacturer="X", series="X",
        )
        assert c.temp_coefficient is None


class TestMOSFET:
    def test_required_fields_only(self) -> None:
        m = MOSFET(
            part_number="TEST-MOSFET",
            rds_on=28 * mOhm,
            v_gs_th=1.1 * V,
            v_ds_max=30 * V,
            i_d_max=5 * A,
        )
        assert m.q_g_total is None
        assert m.r_thermal_ja is None

    def test_optional_fields(self) -> None:
        m = MOSFET(
            part_number="X",
            rds_on=28 * mOhm, v_gs_th=1.1 * V, v_ds_max=30 * V, i_d_max=5 * A,
            q_g_total=1.5 * nC,
        )
        assert m.q_g_total is not None
        assert math.isclose(m.q_g_total.to(nC).at(), 1.5)

    def test_scenario_varying_rds_on(self) -> None:
        rds = Quantity(unit=Ohm, by_scenario={"nominal": 0.028, "max_temp": 0.038})
        m = MOSFET(part_number="X", rds_on=rds,
                   v_gs_th=1.1 * V, v_ds_max=30 * V, i_d_max=5 * A)
        assert m.rds_on.at(scenario="nominal") == 0.028
        assert m.rds_on.at(scenario="max_temp") == 0.038

    def test_missing_required_raises(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            MOSFET(part_number="X", v_gs_th=1.1 * V, v_ds_max=30 * V, i_d_max=5 * A)  # type: ignore[call-arg]


class TestBJT:
    def test_basic(self) -> None:
        b = BJT(
            part_number="BC847",
            h_fe=200.0 * V / V,    # dimensionless
            v_ce_sat=0.2 * V,
            v_be_on=0.7 * V,
            v_ceo_max=45 * V,
            i_c_max=100 * mA,
        )
        assert b.f_t is None


class TestDiode:
    def test_basic(self) -> None:
        d = Diode(
            part_number="1N4148",
            v_f=0.7 * V,
            i_f_max=200 * mA,
            v_r_max=100 * V,
        )
        assert d.v_z is None


class TestLDO:
    def test_basic(self) -> None:
        l = LDO(
            part_number="MIC5219-3.3",
            v_out=3.3 * V,
            v_dropout=0.5 * V,
            i_out_max=500 * mA,
            i_q=85 * uA,
        )
        assert l.v_in_max is None


class TestBuckConverter:
    def test_basic(self) -> None:
        from framework import RangeQuantity
        b = BuckConverter(
            part_number="TPS62933",
            v_in_range=RangeQuantity(3.8, 30.0, V),
            v_out=5.0 * V,
            i_out_max=3.0 * A,
            f_sw=1.1 * 1e6 * Hz,
            efficiency_typ=0.92,
        )
        assert b.i_q is None


class TestIntegratedCircuit:
    def test_can_transceiver_shape(self) -> None:
        from framework import Constant, RangeQuantity
        from framework.units import K, W
        ic = IntegratedCircuit(
            part_number="TEST-CAN",
            supply_current_by_mode={
                "sleep":  RangeQuantity(8e-6, 15e-6, A),
                "active": RangeQuantity(45e-3, 65e-3, A),
            },
            supply_voltage_range=RangeQuantity(4.75, 5.25, V),
            r_thermal_ja=Constant(120.0, K / W),
            t_j_max=Constant(150.0, degC),
        )
        assert "sleep" in ic.supply_current_by_mode
        assert ic.r_thermal_ja is not None


class TestResistorFamily:
    def _make(self) -> ResistorFamily:
        return ResistorFamily(
            manufacturer="Panasonic",
            series="ERJ-3",
            tolerance=0.01,
            temp_coefficient=100 * ppm / K,
            available_sizes=[SmtSize.IMP0603, SmtSize.IMP0805],
            power_rating_by_size={
                SmtSize.IMP0603: 0.1 * V * A,    # 100 mW
                SmtSize.IMP0805: 0.125 * V * A,
            },
            max_voltage_by_size={
                SmtSize.IMP0603: 75 * V,
                SmtSize.IMP0805: 150 * V,
            },
        )

    def test_instance_mints_resistor(self) -> None:
        fam = self._make()
        r = fam.instance(value=10_000 * Ohm, size=SmtSize.IMP0603)
        assert isinstance(r, Resistor)
        assert math.isclose(r.value.to(Ohm).at(), 10_000)
        assert math.isclose(r.max_voltage.to(V).at(), 75.0)

    def test_unavailable_size_rejected(self) -> None:
        fam = self._make()
        with pytest.raises(ValueError, match="not in available"):
            fam.instance(value=10 * Ohm, size=SmtSize.IMP1206)

    def test_missing_size_in_table_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc:
            ResistorFamily(
                manufacturer="X", series="X",
                tolerance=0.01, temp_coefficient=100 * ppm / K,
                available_sizes=[SmtSize.IMP0603, SmtSize.IMP1206],
                power_rating_by_size={SmtSize.IMP0603: 0.1 * V * A},
                max_voltage_by_size={SmtSize.IMP0603: 75 * V, SmtSize.IMP1206: 200 * V},
            )
        assert "power_rating" in str(exc.value)

    def test_part_number_autogenerated(self) -> None:
        fam = self._make()
        r = fam.instance(value=10_000 * Ohm, size=SmtSize.IMP0603)
        assert r.part_number.startswith("ERJ-3-0603-")

    def test_explicit_part_number(self) -> None:
        fam = self._make()
        r = fam.instance(value=10_000 * Ohm, size=SmtSize.IMP0603, part_number="R_10K_0603_1PCT")
        assert r.part_number == "R_10K_0603_1PCT"


class TestCapacitorFamily:
    def _make(self) -> CapacitorFamily:
        return CapacitorFamily(
            manufacturer="Murata",
            series="GRM",
            dielectric=Dielectric.X7R,
            tolerance=0.10,
            available_sizes=[SmtSize.IMP0603, SmtSize.IMP0805],
            voltage_rating_by_size={
                SmtSize.IMP0603: 25 * V,
                SmtSize.IMP0805: 50 * V,
            },
        )

    def test_instance(self) -> None:
        fam = self._make()
        c = fam.instance(value=100e-9 * uF * 1000, size=SmtSize.IMP0603)
        assert c.dielectric == Dielectric.X7R
        assert math.isclose(c.voltage_rating.to(V).at(), 25.0)
