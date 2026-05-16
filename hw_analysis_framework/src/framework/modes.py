"""Modes — global system operating states (design doc 6.3).

A `Mode` is the system-wide state of the whole board at a single moment:
``off``, ``sleep``, ``active``, ``diagnostic``, ``calibration``. Per-mode leaf
values declared in each block are propagated through the DAG automatically.

`ModeSet` enforces uniqueness of names. Load via :func:`load_modes`.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from framework._toml import TomlError, read_toml
from framework.quantity import INVARIANT


class Mode(BaseModel):
    """A named system operating state."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _name_not_reserved(cls, v: str) -> str:
        if v == INVARIANT:
            raise ValueError(
                f"mode name {INVARIANT!r} is reserved as the "
                "scenario-invariant marker on Quantity.by_scenario"
            )
        return v


class ModeSet(BaseModel):
    """A unique-by-name collection of `Mode`s."""

    model_config = ConfigDict(frozen=True)

    modes: list[Mode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _names_unique(self) -> "ModeSet":
        seen: dict[str, int] = {}
        for i, m in enumerate(self.modes):
            if m.name in seen:
                raise ValueError(
                    f"duplicate mode name {m.name!r} "
                    f"(at indices {seen[m.name]} and {i})"
                )
            seen[m.name] = i
        return self

    def by_name(self, name: str) -> Mode:
        for m in self.modes:
            if m.name == name:
                return m
        raise KeyError(f"mode {name!r} not found; available: {self.names()}")

    def names(self) -> list[str]:
        return [m.name for m in self.modes]

    def __iter__(self) -> Iterator[Mode]:  # type: ignore[override]
        return iter(self.modes)

    def __len__(self) -> int:
        return len(self.modes)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and any(m.name == name for m in self.modes)


def load_modes(path: Path | str) -> ModeSet:
    """Load a modes TOML file into a `ModeSet`.

    Expected file shape:

    .. code-block:: toml

        [[mode]]
        name = "off"
        description = "Battery disconnected or master disable"

        [[mode]]
        name = "sleep"
        description = "Low-power monitoring, RTC running, MCU asleep"
    """
    p = Path(path)
    data = read_toml(p)
    raw_list = data.get("mode")
    if raw_list is None:
        return ModeSet(modes=[])
    if not isinstance(raw_list, list):
        raise TomlError(
            f"{p}: top-level 'mode' must be a TOML array of tables ([[mode]]); "
            f"got {type(raw_list).__name__}"
        )

    modes: list[Mode] = []
    for i, item in enumerate(raw_list):
        if not isinstance(item, dict):
            raise TomlError(f"{p}: mode #{i + 1} is not a table")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise TomlError(f"{p}: mode #{i + 1} is missing a non-empty 'name'")
        unknown = set(item.keys()) - {"name", "description"}
        if unknown:
            raise TomlError(
                f"{p}: mode {name!r} has unknown keys {sorted(unknown)}; "
                "Mode only accepts 'name' and 'description'"
            )
        try:
            modes.append(Mode(name=name, description=item.get("description")))
        except (TypeError, ValueError) as e:
            raise TomlError(f"{p}: mode {name!r}: {e}") from e

    try:
        return ModeSet(modes=modes)
    except (TypeError, ValueError) as e:
        raise TomlError(f"{p}: {e}") from e


__all__ = ["Mode", "ModeSet", "load_modes"]
