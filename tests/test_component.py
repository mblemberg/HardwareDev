"""Component base class + Quantity-field coercion helper."""
from __future__ import annotations

import math
from typing import Annotated

import pint
import pydantic
import pytest
from pydantic import BeforeValidator, Field

from framework import Component, Constant, Quantity, coerce_field_quantity
from framework.units import A, V, mA, mOhm


# A toy subclass standing in for the real schemas (MOSFET / Resistor / ...)
# the `components` package will define on top of Component.
_CoercedQ = Annotated[Quantity, BeforeValidator(coerce_field_quantity)]


class _ToyMOSFET(Component):
    rds_on: _CoercedQ
    v_ds_max: _CoercedQ
    i_d_max: _CoercedQ
    q_g_total: _CoercedQ | None = None


class TestComponentBase:
    def test_required_fields(self) -> None:
        m = _ToyMOSFET(
            part_number="TEST-MOSFET-1",
            rds_on=28 * mOhm,
            v_ds_max=30 * V,
            i_d_max=5 * A,
        )
        assert m.part_number == "TEST-MOSFET-1"
        assert m.psc_id is None
        assert m.metadata == {}

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError) as exc_info:
            _ToyMOSFET(part_number="X", rds_on=28 * mOhm, v_ds_max=30 * V)
        assert "i_d_max" in str(exc_info.value)

    def test_missing_part_number_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            _ToyMOSFET(rds_on=28 * mOhm, v_ds_max=30 * V, i_d_max=5 * A)  # type: ignore[call-arg]

    def test_psc_id_optional(self) -> None:
        m = _ToyMOSFET(
            part_number="X", psc_id="PSC-X-001",
            rds_on=28 * mOhm, v_ds_max=30 * V, i_d_max=5 * A,
        )
        assert m.psc_id == "PSC-X-001"

    def test_metadata_free_form(self) -> None:
        m = _ToyMOSFET(
            part_number="X",
            rds_on=28 * mOhm, v_ds_max=30 * V, i_d_max=5 * A,
            metadata={"datasheet_rev": "B", "rohs": True},
        )
        assert m.metadata["datasheet_rev"] == "B"
        assert m.metadata["rohs"] is True

    def test_frozen(self) -> None:
        m = _ToyMOSFET(part_number="X", rds_on=28 * mOhm, v_ds_max=30 * V, i_d_max=5 * A)
        with pytest.raises(pydantic.ValidationError):
            m.part_number = "Y"  # type: ignore[misc]


class TestCoerceFieldQuantity:
    def test_framework_quantity_passes_through(self) -> None:
        q = Constant(28.0, mOhm)
        m = _ToyMOSFET(part_number="X", rds_on=q, v_ds_max=30 * V, i_d_max=5 * A)
        assert m.rds_on is q

    def test_pint_quantity_lifted_to_constant(self) -> None:
        m = _ToyMOSFET(part_number="X", rds_on=28 * mOhm, v_ds_max=30 * V, i_d_max=5 * A)
        assert isinstance(m.rds_on, Quantity)
        assert math.isclose(m.rds_on.to(mOhm).at(), 28.0)

    def test_string_lifted_to_constant(self) -> None:
        # In strings, use the spelled-out Pint form for prefixed units like
        # milliohm -- Pint can't alias prefixed forms (see framework/units.py).
        # In code, keep the capitalized engineering form (mOhm symbol).
        m = _ToyMOSFET(
            part_number="X",
            rds_on="28 milliohm", v_ds_max="30 V", i_d_max="5 A",
        )
        assert math.isclose(m.rds_on.to(mOhm).at(), 28.0)
        assert math.isclose(m.v_ds_max.to(V).at(), 30.0)
        assert math.isclose(m.i_d_max.to(A).at(), 5.0)

    def test_bare_number_lifted_to_dimensionless(self) -> None:
        # Bare numbers are accepted as dimensionless -- useful for ratios.
        # Misuse on a dimensioned field surfaces later as a dimensionality
        # error during arithmetic, not at construction.
        m = _ToyMOSFET(part_number="X", rds_on=28, v_ds_max=30 * V, i_d_max=5 * A)
        assert m.rds_on.unit.dimensionless
        # Combining dimensionless with a real unit fails loudly later.
        with pytest.raises(pint.DimensionalityError):
            _ = m.rds_on + Constant(1.0, mA)

    def test_bool_rejected(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            _ToyMOSFET(part_number="X", rds_on=True, v_ds_max=30 * V, i_d_max=5 * A)  # type: ignore[arg-type]

    def test_optional_field_accepts_none(self) -> None:
        m = _ToyMOSFET(part_number="X", rds_on=28 * mOhm, v_ds_max=30 * V, i_d_max=5 * A)
        assert m.q_g_total is None

    def test_optional_field_accepts_value(self) -> None:
        from framework.units import nC
        m = _ToyMOSFET(
            part_number="X",
            rds_on=28 * mOhm, v_ds_max=30 * V, i_d_max=5 * A,
            q_g_total=1.5 * nC,
        )
        assert m.q_g_total is not None
        assert math.isclose(m.q_g_total.to(nC).at(), 1.5)

    def test_scenario_varying_quantity_accepted(self) -> None:
        # The whole point of using framework.Quantity (vs pint.Quantity) in
        # component schemas: parameters that legitimately vary with operating
        # condition. MOSFET rds_on increases with junction temperature.
        rds = Quantity(unit=mOhm, by_scenario={"nominal": 28.0, "max_temp": 38.0})
        m = _ToyMOSFET(part_number="X", rds_on=rds, v_ds_max=30 * V, i_d_max=5 * A)
        assert m.rds_on.at(scenario="nominal") == 28.0
        assert m.rds_on.at(scenario="max_temp") == 38.0
