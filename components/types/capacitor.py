"""Capacitor schema + family factory + dielectric enum (design doc 6.5)."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from framework import Component

from components.types._helpers import CoercedQuantity
from components.types.resistor import SmtSize, _compact_value_str


class Dielectric(str, Enum):
    """Ceramic-capacitor dielectric classes (rough thermal-stability ordering)."""

    C0G = "C0G"
    NP0 = "NP0"     # alias of C0G in some catalogs
    X5R = "X5R"
    X7R = "X7R"
    X7S = "X7S"
    X8R = "X8R"
    Y5V = "Y5V"
    Z5U = "Z5U"


class Capacitor(Component):
    """A specific surface-mount capacitor instance.

    Typically minted from a :class:`CapacitorFamily`. ``voltage_rating`` is
    the maximum allowed working voltage; derate further in your block math.
    """

    value: CoercedQuantity
    size: SmtSize
    dielectric: Dielectric
    voltage_rating: CoercedQuantity
    tolerance: CoercedQuantity
    temp_coefficient: CoercedQuantity | None = None
    manufacturer: str
    series: str


class CapacitorFamily(BaseModel):
    """Shared parameter set for a capacitor family (e.g. Murata GRM X7R)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    manufacturer: str
    series: str
    dielectric: Dielectric
    description: str | None = None
    tolerance: CoercedQuantity
    temp_coefficient: CoercedQuantity | None = None
    available_sizes: list[SmtSize]
    voltage_rating_by_size: dict[SmtSize, CoercedQuantity]
    psc_family_id: str | None = None

    @model_validator(mode="after")
    def _check_size_tables(self) -> "CapacitorFamily":
        for size in self.available_sizes:
            if size not in self.voltage_rating_by_size:
                raise ValueError(
                    f"CapacitorFamily {self.series!r}: missing voltage_rating for size {size.value!r}"
                )
        return self

    def instance(
        self,
        *,
        value: Any,
        size: SmtSize,
        part_number: str | None = None,
        psc_id: str | None = None,
    ) -> Capacitor:
        """Mint a specific :class:`Capacitor` from this family."""
        if size not in self.available_sizes:
            raise ValueError(
                f"CapacitorFamily {self.series!r}: size {size.value!r} is not in available "
                f"sizes {[s.value for s in self.available_sizes]!r}"
            )
        pn = part_number or f"{self.series}-{size.value}-{_compact_value_str(value)}"
        return Capacitor(
            part_number=pn,
            psc_id=psc_id,
            value=value,
            size=size,
            dielectric=self.dielectric,
            voltage_rating=self.voltage_rating_by_size[size],
            tolerance=self.tolerance,
            temp_coefficient=self.temp_coefficient,
            manufacturer=self.manufacturer,
            series=self.series,
        )
