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
4. Content-addresses every DAG node and reuses cached results when the
   function source + inputs + framework version all match (design doc 8).
"""
from __future__ import annotations

import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hamilton import driver
from hamilton.lifecycle import NodeExecutionHook

import framework
from framework._hashing import compute_node_hashes
from framework.cache import Cache
from framework.contract import detect_cycles
from framework.modes import ModeSet, load_modes
from framework.scenarios import ScenarioSet, load_scenarios


class _CacheWriteHook(NodeExecutionHook):
    """Post-execution hook: write each computed node's result into the cache."""

    def __init__(self, cache: Cache, node_hashes: dict[str, str]) -> None:
        self._cache = cache
        self._node_hashes = node_hashes

    def run_before_node_execution(self, **_kwargs: Any) -> None:
        pass

    def run_after_node_execution(
        self,
        *,
        node_name: str,
        result: Any,
        success: bool,
        error: Exception | None,
        **_kwargs: Any,
    ) -> None:
        if not success or error is not None:
            return
        h = self._node_hashes.get(node_name)
        if h is not None:
            self._cache.put(h, result)


class Project:
    """Top-level orchestrator: scenarios + modes + Hamilton driver + cache.

    Caching: by default the project enables a content-addressed disk cache at
    ``./.framework_cache``. Pass ``cache_dir=None`` to disable, or a custom
    ``Path`` to relocate. The cache key for every DAG node folds together the
    framework version, the function source bytes, and the (transitive) hashes
    of every ancestor input — so any change in any leaf, any function, or any
    framework bump triggers exactly the recompute it ought to.
    """

    DEFAULT_CACHE_DIR_NAME = ".framework_cache"

    def __init__(
        self,
        *,
        scenarios: ScenarioSet,
        modes: ModeSet,
        cache_dir: Path | str | None = "default",
    ) -> None:
        self.scenarios = scenarios
        self.modes = modes
        if cache_dir == "default":
            cache_dir = Path.cwd() / self.DEFAULT_CACHE_DIR_NAME
        self._cache: Cache | None = Cache(cache_dir) if cache_dir is not None else None

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls,
        *,
        scenarios: Path | str | ScenarioSet,
        modes: Path | str | ModeSet,
        cache_dir: Path | str | None = "default",
    ) -> "Project":
        """Construct a Project from TOML file paths or already-loaded sets.

        Pass either a path (``"project/scenarios.toml"``) or an already-
        constructed ``ScenarioSet`` / ``ModeSet`` (useful in tests).
        ``cache_dir`` defaults to ``./.framework_cache`` — pass ``None`` to
        disable caching, or a custom path to relocate.
        """
        ss = scenarios if isinstance(scenarios, ScenarioSet) else load_scenarios(scenarios)
        ms = modes if isinstance(modes, ModeSet) else load_modes(modes)
        return cls(scenarios=ss, modes=ms, cache_dir=cache_dir)

    # ------------------------------------------------------------------
    # Cache access
    # ------------------------------------------------------------------

    @property
    def cache(self) -> Cache | None:
        """The project's disk cache, or ``None`` if caching is disabled."""
        return self._cache

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
        validate_contracts: bool = True,
    ) -> dict[str, Any]:
        """Build a Hamilton DAG from ``modules`` and compute ``targets``.

        ``inputs`` is layered on top of :meth:`standard_inputs` (user values
        win). Returns a dict ``{target_name: Quantity}``. Hamilton raises at
        build time if a node parameter isn't satisfied by another node, an
        input, or a default.

        Caching: when this project has a cache (the default), every node in
        the DAG gets a content-addressed hash and the cache is consulted for
        each. Hits are supplied to Hamilton via ``overrides=`` so the function
        body never runs; misses are computed normally and written back to the
        cache via a post-execute hook.

        Contract cycle detection (design doc 7.4): before Hamilton runs, every
        ``@contract``-marked function's dependency subgraph is walked and the
        cross-block rule is enforced (a Contract may not depend on non-Contract
        outputs of other blocks). Pass ``validate_contracts=False`` to skip;
        useful for debugging.
        """
        if not modules:
            raise ValueError("Project.run requires at least one module")
        if not targets:
            raise ValueError("Project.run requires at least one target name")

        if validate_contracts:
            detect_cycles(modules)

        merged: dict[str, Any] = self.standard_inputs()
        if inputs:
            merged.update(inputs)

        if self._cache is None:
            dr = driver.Builder().with_modules(*modules).build()
            return dr.execute(targets, inputs=merged)

        # Content-address every node, then split into "served from cache"
        # (overrides) vs "compute and write back" (lifecycle hook).
        node_hashes = compute_node_hashes(
            modules, dict(merged), framework_version=framework.__version__
        )
        overrides: dict[str, Any] = {}
        misses: dict[str, str] = {}
        # Don't override input names — Hamilton accepts those via inputs=.
        input_names = set(merged.keys())
        for name, h in node_hashes.items():
            if name in input_names:
                continue
            cached = self._cache.get(h)
            if cached is not None:
                overrides[name] = cached
            else:
                misses[name] = h

        hook = _CacheWriteHook(self._cache, misses)
        dr = (
            driver.Builder()
            .with_modules(*modules)
            .with_adapters(hook)
            .build()
        )
        return dr.execute(targets, inputs=merged, overrides=overrides)

    def list_nodes(self, modules: list[types.ModuleType]) -> list[str]:
        """Names of every node in the DAG built from ``modules``.

        Useful for introspection: confirm a function actually became a node,
        spot typos, surface what's available to depend on.
        """
        dr = driver.Builder().with_modules(*modules).build()
        return sorted(n.name for n in dr.list_available_variables())


__all__ = ["Project"]
