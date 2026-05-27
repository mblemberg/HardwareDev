"""Scenarios — named environmental/operating corners (design doc 6.2).

A `Scenario` is a Pydantic-validated record with:

- ``name``      — required, unique within its set, not equal to ``INVARIANT``
                  (``"_ALL_"``, reserved as the scenario-invariant marker on Quantity).
- ``description`` — optional human-readable note.
- ``owner_block`` — None for project-global scenarios; set for block-specific
                  corners (design doc 6.2: the RF block may add
                  ``cold_carrier_drift``). The wiring that lets blocks register
                  extensions arrives with step 6 (Block).
- ``context``    — every other field on the scenario, parsed as ``pint.Quantity``
                  via :func:`framework._toml.parse_pint`. Values must be
                  Pint-format strings in TOML.

Load via :func:`load_scenarios`. A `ScenarioSet` enforces uniqueness of names
and exposes name lookup; it is the canonical way to pass scenarios around.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pint
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from framework._toml import TomlError, parse_pint, read_toml
from framework.quantity import INVARIANT

_RESERVED_TOP_LEVEL_KEYS = frozenset({"name", "description", "owner_block"})


class Scenario(BaseModel):
    """A named operating corner with a dict of unit-bearing context values."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: str = Field(..., min_length=1)
    description: str | None = None
    owner_block: str | None = None
    context: dict[str, pint.Quantity] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_not_reserved(cls, v: str) -> str:
        if v == INVARIANT:
            raise ValueError(
                f"scenario name {INVARIANT!r} is reserved as the "
                "scenario-invariant marker on Quantity.by_scenario"
            )
        return v

    @field_validator("context", mode="before")
    @classmethod
    def _parse_context(cls, v: Any) -> dict[str, pint.Quantity]:
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise TypeError(f"context must be a mapping, got {type(v).__name__}")
        out: dict[str, pint.Quantity] = {}
        for k, val in v.items():
            if not isinstance(k, str):
                raise TypeError(f"context key must be a str, got {type(k).__name__}")
            out[k] = parse_pint(val, location=f"context[{k!r}]")
        return out


class ScenarioSet(BaseModel):
    """A unique-by-name collection of `Scenario`s."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    scenarios: list[Scenario] = Field(default_factory=list)

    @model_validator(mode="after")
    def _names_unique(self) -> "ScenarioSet":
        seen: dict[str, int] = {}
        for i, s in enumerate(self.scenarios):
            if s.name in seen:
                raise ValueError(
                    f"duplicate scenario name {s.name!r} "
                    f"(at indices {seen[s.name]} and {i})"
                )
            seen[s.name] = i
        return self

    def by_name(self, name: str) -> Scenario:
        for s in self.scenarios:
            if s.name == name:
                return s
        raise KeyError(
            f"scenario {name!r} not found; available: {self.names()}"
        )

    def names(self) -> list[str]:
        return [s.name for s in self.scenarios]

    def __iter__(self) -> Iterator[Scenario]:  # type: ignore[override]
        return iter(self.scenarios)

    def __len__(self) -> int:
        return len(self.scenarios)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and any(s.name == name for s in self.scenarios)

    def as_quantity(self, key: str, *, unit: pint.Unit | None = None) -> "Quantity":
        """Build a `Quantity(by_scenario=...)` from a context key across this set.

        Only scenarios that define ``key`` are included in the result. The
        magnitude of each scenario's value is converted into ``unit`` (or, if
        not given, into the first matching scenario's unit) and stored in the
        returned Quantity's ``by_scenario`` dict.

        Raises:
            KeyError: if no scenario in this set carries ``key``.

        Example:
            >>> scenarios = load_scenarios("project/scenarios.toml")
            >>> vbat = scenarios.as_quantity("vbat")
            >>> vbat.at(scenario="cold_low_vin")
            9.0
        """
        from framework.quantity import Quantity

        carriers = [s for s in self.scenarios if key in s.context]
        if not carriers:
            raise KeyError(
                f"no scenario in this set defines {key!r}; "
                f"available context keys per scenario: "
                f"{ {s.name: sorted(s.context) for s in self.scenarios} }"
            )
        target_unit = unit if unit is not None else carriers[0].context[key].units
        by_scenario = {
            s.name: float(s.context[key].to(target_unit).magnitude) for s in carriers
        }
        return Quantity(unit=target_unit, by_scenario=by_scenario)


def load_scenarios(path: Path | str) -> ScenarioSet:
    """Load a scenarios TOML file into a `ScenarioSet`.

    Expected file shape:

    .. code-block:: toml

        [[scenario]]
        name = "nominal"
        description = "Room-temp benchmark"
        ambient_temp = "25 degC"
        vbat = "12.0 V"

        [[scenario]]
        name = "cold_low_vin"
        description = "Cold start, depleted battery"
        owner_block = "rf"          # optional; default None
        ambient_temp = "-40 degC"
        vbat = "9.0 V"

    Reserved top-level keys are ``name``, ``description``, and ``owner_block``.
    Everything else becomes a unit-bearing context value — Pint-format strings
    only (the loader rejects bare numbers).
    """
    p = Path(path)
    data = read_toml(p)
    raw_list = data.get("scenario")
    if raw_list is None:
        return ScenarioSet(scenarios=[])
    if not isinstance(raw_list, list):
        raise TomlError(
            f"{p}: top-level 'scenario' must be a TOML array of tables ([[scenario]]); "
            f"got {type(raw_list).__name__}"
        )

    scenarios: list[Scenario] = []
    for i, item in enumerate(raw_list):
        if not isinstance(item, dict):
            raise TomlError(f"{p}: scenario #{i + 1} is not a table")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise TomlError(f"{p}: scenario #{i + 1} is missing a non-empty 'name'")
        ctx_raw = {k: v for k, v in item.items() if k not in _RESERVED_TOP_LEVEL_KEYS}
        ctx_parsed: dict[str, pint.Quantity] = {}
        for k, v in ctx_raw.items():
            ctx_parsed[k] = parse_pint(
                v, location=f"{p}: scenario {name!r} field {k!r}"
            )
        try:
            scenarios.append(
                Scenario(
                    name=name,
                    description=item.get("description"),
                    owner_block=item.get("owner_block"),
                    context=ctx_parsed,
                )
            )
        except (TypeError, ValueError) as e:
            raise TomlError(f"{p}: scenario {name!r}: {e}") from e

    try:
        return ScenarioSet(scenarios=scenarios)
    except (TypeError, ValueError) as e:
        raise TomlError(f"{p}: {e}") from e


__all__ = ["Scenario", "ScenarioSet", "load_scenarios"]
