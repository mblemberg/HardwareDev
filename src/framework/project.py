"""Project — orchestrates scenarios, modes, requirements, and DAG execution.

A :class:`Project` is the runtime representation of an analysis project. It:

1. Holds loaded :class:`~framework.scenarios.ScenarioSet` and
   :class:`~framework.modes.ModeSet` (and indirectly the requirements
   registry, which is module-global).
2. Auto-derives "standard inputs" for the Hamilton DAG from the loaded
   scenarios — any context key that appears in *every* scenario becomes a
   Quantity input named after the key (e.g. ``ambient_temp``, ``vbat``).
3. Drives Hamilton against caller-supplied block modules and returns the
   requested target Quantities.

Step 4a — the DAG runner. Step 4b (content-addressed caching) bolts on top
without changing this surface.
"""
from __future__ import annotations

import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hamilton import driver

from framework.modes import ModeSet, load_modes
from framework.scenarios import ScenarioSet, load_scenarios


class Project:
    """Top-level orchestrator: scenarios + modes + Hamilton driver."""

    def __init__(self, *, scenarios: ScenarioSet, modes: ModeSet) -> None:
        self.scenarios = scenarios
        self.modes = modes

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls,
        *,
        scenarios: Path | str | ScenarioSet,
        modes: Path | str | ModeSet,
    ) -> "Project":
        """Construct a Project from TOML file paths or already-loaded sets.

        Pass either a path (``"project/scenarios.toml"``) or an already-
        constructed ``ScenarioSet`` / ``ModeSet`` (useful in tests).
        """
        ss = scenarios if isinstance(scenarios, ScenarioSet) else load_scenarios(scenarios)
        ms = modes if isinstance(modes, ModeSet) else load_modes(modes)
        return cls(scenarios=ss, modes=ms)

    # ------------------------------------------------------------------
    # DAG inputs
    # ------------------------------------------------------------------

    def standard_inputs(self) -> dict[str, Any]:
        """Auto-derive Hamilton inputs from project state.

        Includes:

        - ``scenarios`` — the loaded :class:`ScenarioSet`.
        - ``modes``     — the loaded :class:`ModeSet`.
        - one Quantity per context key that appears in **every** scenario,
          keyed by the context key name (e.g. ``ambient_temp`` becomes a
          ``Quantity(by_scenario=...)`` carrying each scenario's ambient).

        Block-specific scenario keys (those that only some scenarios carry)
        are *not* auto-extracted — call :meth:`ScenarioSet.as_quantity`
        explicitly if you need them.
        """
        out: dict[str, Any] = {
            "scenarios": self.scenarios,
            "modes": self.modes,
        }
        if not self.scenarios.scenarios:
            return out
        common_keys: set[str] = set(self.scenarios.scenarios[0].context.keys())
        for s in self.scenarios.scenarios[1:]:
            common_keys &= set(s.context.keys())
        for key in sorted(common_keys):
            out[key] = self.scenarios.as_quantity(key)
        return out

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(
        self,
        modules: list[types.ModuleType],
        targets: list[str],
        inputs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a Hamilton DAG from ``modules`` and compute ``targets``.

        ``inputs`` is layered on top of :meth:`standard_inputs` (user values
        win). Returns a dict ``{target_name: Quantity}``. Hamilton raises at
        build time if a node parameter isn't satisfied by another node, an
        input, or a default.
        """
        if not modules:
            raise ValueError("Project.run requires at least one module")
        if not targets:
            raise ValueError("Project.run requires at least one target name")
        merged: dict[str, Any] = self.standard_inputs()
        if inputs:
            merged.update(inputs)
        dr = driver.Builder().with_modules(*modules).build()
        return dr.execute(targets, inputs=merged)

    def list_nodes(self, modules: list[types.ModuleType]) -> list[str]:
        """Names of every node in the DAG built from ``modules``.

        Useful for introspection: confirm a function actually became a node,
        spot typos, surface what's available to depend on.
        """
        dr = driver.Builder().with_modules(*modules).build()
        return sorted(n.name for n in dr.list_available_variables())


__all__ = ["Project"]
