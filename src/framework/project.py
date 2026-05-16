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
from framework.contract import (
    check_contract_assumptions,
    check_contract_consistency,
    detect_cycles,
    raise_on_mismatches,
)
from framework.provenance import attach_provenance, build_provenance_graph
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
        check_contracts: bool = True,
        attach_provenance_to_results: bool = True,
        return_all_computed: bool = False,
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

        Contract consistency (design doc 6.7 run-time rules): after Hamilton
        executes, every Contract with ``compares_to=<node>`` set is compared
        against that node's actual computed value at every scenario/mode point.
        If any actual exceeds its declared bound, raises :class:`ContractViolation`
        carrying the full mismatch list. To run this check the relevant
        Contract node and its ``compares_to`` target must both be reachable —
        the framework adds them to the DAG execution set automatically. Pass
        ``check_contracts=False`` to skip.

        Return shape: by default the return dict is filtered down to the
        caller's ``targets`` (auto-augmented Contract / ``compares_to`` /
        ``assumed_inputs`` nodes are an implementation detail). Pass
        ``return_all_computed=True`` to receive everything Hamilton computed
        for this run — useful for the design-review renderers
        (:func:`framework.block_report_html` / :func:`framework.project_report_html`),
        which need the full declared+actual+assumed surface to render the
        contracts table.
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

        # Augment targets with every Contract + its compares_to actual so the
        # consistency check has values to compare. Hamilton will pull through
        # the rest of the DAG to satisfy them.
        run_targets = list(targets)
        if check_contracts:
            extra = self._contract_check_targets(modules, set(targets), set(merged))
            for name in extra:
                if name not in run_targets:
                    run_targets.append(name)

        # Node hashes are needed for the cache layer when one exists and
        # always for provenance (when enabled).
        node_hashes: dict[str, str] = {}
        if self._cache is not None or attach_provenance_to_results:
            node_hashes = compute_node_hashes(
                modules, dict(merged), framework_version=framework.__version__
            )

        if self._cache is None:
            dr = driver.Builder().with_modules(*modules).build()
            results = dr.execute(run_targets, inputs=merged)
        else:
            # Split into "served from cache" (overrides) vs "compute and write
            # back" (lifecycle hook).
            overrides: dict[str, Any] = {}
            misses: dict[str, str] = {}
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
            results = dr.execute(run_targets, inputs=merged, overrides=overrides)

        # Attach provenance: every Quantity returned gets a ProvenanceRef
        # pointing at its DAG node, with a shared per-run ProvenanceGraph so
        # callers can walk q.provenance.chain() to see the full ancestry.
        if attach_provenance_to_results:
            graph = build_provenance_graph(modules, dict(merged), node_hashes)
            from framework.quantity import Quantity  # local: avoid cycle
            results = {
                name: (
                    attach_provenance(val, node_id=name, graph=graph)
                    if isinstance(val, Quantity) else val
                )
                for name, val in results.items()
            }

        if check_contracts:
            mismatches = check_contract_consistency(modules, results, strict=True)
            # check_contract_assumptions is run lenient: assumed_inputs may
            # reference nodes the consumer doesn't pull through this run, and
            # informational (non-Quantity) entries are silently skipped.
            mismatches.extend(check_contract_assumptions(modules, results))
            raise_on_mismatches(mismatches)

        if return_all_computed:
            return dict(results)
        # Return only what the caller asked for (auto-added contract targets
        # were an implementation detail).
        return {k: results[k] for k in targets if k in results} if targets else results

    @staticmethod
    def _contract_check_targets(
        modules: list[types.ModuleType],
        existing_targets: set[str],
        input_names: set[str],
    ) -> list[str]:
        """Names of contract + compares_to + Quantity-valued assumed_inputs
        nodes to add to the run targets. Ensures the consistency check has
        the contract's own value AND its compares_to target, and the
        assumptions check has every Quantity-valued assumed_inputs key."""
        from framework.contract import get_contract_meta, is_contract
        from framework.quantity import Quantity

        extra: list[str] = []
        def _maybe_add(name: str) -> None:
            if name in input_names or name in existing_targets or name in extra:
                return
            extra.append(name)

        for module in modules:
            for attr in dir(module):
                if attr.startswith("_"):
                    continue
                obj = getattr(module, attr, None)
                if obj is None or not is_contract(obj):
                    continue
                if getattr(obj, "__module__", None) != module.__name__:
                    continue
                meta = get_contract_meta(obj)
                if meta is None:
                    continue
                # Consistency check (step 8): contract + compares_to.
                if meta.compares_to is not None:
                    _maybe_add(attr)
                    _maybe_add(meta.compares_to)
                # Assumptions check (cross-block): contract + each Quantity-
                # valued assumed_inputs key.
                if meta.assumed_inputs:
                    has_quantity_assumption = any(
                        isinstance(v, Quantity) for v in meta.assumed_inputs.values()
                    )
                    if has_quantity_assumption:
                        _maybe_add(attr)
                        for key, value in meta.assumed_inputs.items():
                            if isinstance(value, Quantity):
                                _maybe_add(key)
        return extra

    def list_nodes(self, modules: list[types.ModuleType]) -> list[str]:
        """Names of every node in the DAG built from ``modules``.

        Useful for introspection: confirm a function actually became a node,
        spot typos, surface what's available to depend on.
        """
        dr = driver.Builder().with_modules(*modules).build()
        return sorted(n.name for n in dr.list_available_variables())


__all__ = ["Project"]
