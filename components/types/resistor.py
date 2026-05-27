"""Resistor schema + family factory + SMT size enum (design doc 6.5)."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from framework import Component, Quantity

from components.types._helpers import CoercedQuantity


class SmtSize(str, Enum):
    """Imperial (EIA) SMT package sizes used by passives."""

    IMP0201 = "0201"
    IMP0402 = "0402"
    IMP0603 = "0603"
    IMP0805 = "0805"
    IMP1206 = "1206"
    IMP1210 = "1210"
    IMP2010 = "2010"
    IMP2512 = "2512"


class Resistor(Component):
    """A specific surface-mount resistor instance.

    Typically minted from a :class:`ResistorFamily` via ``family.instance(
    value=..., size=...)``; can also be constructed directly when a part
    doesn't fit a family (precision foil, current-sense shunt, etc.).
    """

    value: CoercedQuantity
    size: SmtSize
    tolerance: CoercedQuantity
    temp_coefficient: CoercedQuantity
    power_rating: CoercedQuantity
    max_voltage: CoercedQuantity
    manufacturer: str
    series: str


class ResistorFamily(BaseModel):
    """Shared parameter set for a family of resistors (e.g. Panasonic ERJ-3).

    Captures everything common across a series; instances are minted with
    :meth:`instance` by supplying the value and package size. Size-dependent
    ratings (power, max voltage) come from the by-size dicts.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    manufacturer: str
    series: str
    description: str | None = None
    tolerance: CoercedQuantity
    temp_coefficient: CoercedQuantity
    available_sizes: list[SmtSize]
    power_rating_by_size: dict[SmtSize, CoercedQuantity]
    max_voltage_by_size: dict[SmtSize, CoercedQuantity]
    psc_family_id: str | None = None

    @model_validator(mode="after")
    def _check_size_tables(self) -> "ResistorFamily":
        for size in self.available_sizes:
            if size not in self.power_rating_by_size:
                raise ValueError(
                    f"ResistorFamily {self.series!r}: missing power_rating for size {size.value!r}"
                )
            if size not in self.max_voltage_by_size:
                raise ValueError(
                    f"ResistorFamily {self.series!r}: missing max_voltage for size {size.value!r}"
                )
        return self

    def instance(
        self,
        *,
        value: Any,
        size: SmtSize,
        part_number: str | None = None,
        psc_id: str | None = None,
    ) -> Resistor:
        """Mint a specific :class:`Resistor` from this family."""
        if size not in self.available_sizes:
            raise ValueError(
                f"ResistorFamily {self.series!r}: size {size.value!r} is not in available "
                f"sizes {[s.value for s in self.available_sizes]!r}"
            )
        # Default part number: <series>-<size>-<value> stringified compactly.
        pn = part_number or f"{self.series}-{size.value}-{_compact_value_str(value)}"
        return Resistor(
            part_number=pn,
            psc_id=psc_id,
            value=value,
            size=size,
            tolerance=self.tolerance,
            temp_coefficient=self.temp_coefficient,
            power_rating=self.power_rating_by_size[size],
            max_voltage=self.max_voltage_by_size[size],
            manufacturer=self.manufacturer,
            series=self.series,
        )


def _compact_value_str(value: Any) -> str:
    """Best-effort short rendering of a value for auto-generated part numbers."""
    if isinstance(value, Quantity):
        nom = value.value
        if isinstance(nom, tuple):
            return f"{nom[0]}-{nom[1]}{value.unit:~P}"
        return f"{nom}{value.unit:~P}".replace(" ", "")
    return str(value).replace(" ", "")
