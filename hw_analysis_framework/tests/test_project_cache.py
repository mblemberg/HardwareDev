"""Content-addressed caching tests — design doc section 8.

These tests instrument the *sample block fixture* by patching its leaf and
analysis functions in place to:
  - count how many times each function actually executes, and
  - swap function bodies at runtime to simulate code edits.

That gives a sharp signal of cache hits vs misses without touching framework
code.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterator

import pytest

import framework
from framework import Constant, Project, Quantity, RangeQuantity
from framework.cache import Cache
from framework.modes import Mode, ModeSet
from framework.scenarios import Scenario, ScenarioSet
from framework.units import A, K, V, W, degC, mA

# Pull the sample block fixtures the test_project file uses.
from sample_block import analysis, leaves


# ---------- helpers ----------


@pytest.fixture
def project(tmp_path: Path) -> Project:
    """A Project pointed at an empty fresh cache dir."""
    return Project.load(
        scenarios=ScenarioSet(scenarios=[
            Scenario(name="nominal", context={"ambient_temp": "25 degC"}),
        ]),
        modes=ModeSet(modes=[Mode(name="active")]),
        cache_dir=tmp_path / ".framework_cache",
    )


@pytest.fixture
def call_counter() -> Iterator[dict[str, int]]:
    """Wrap every function in leaves/analysis with a call counter."""
    counts: dict[str, int] = {}
    originals: dict[tuple[str, str], object] = {}

    for module in (leaves, analysis):
        for name in dir(module):
            if name.startswith("_"):
                continue
            fn = getattr(module, name)
            if not callable(fn):
                continue
            if getattr(fn, "__module__", None) != module.__name__:
                continue
            originals[(module.__name__, name)] = fn

            def make_wrapper(real_fn, key):
                def wrapped(*args, **kwargs):
                    counts[key] = counts.get(key, 0) + 1
                    return real_fn(*args, **kwargs)
                # Preserve signature + name so Hamilton sees the same DAG.
                wrapped.__name__ = real_fn.__name__
                wrapped.__module__ = real_fn.__module__
                wrapped.__qualname__ = real_fn.__qualname__
                wrapped.__signature__ = __import__("inspect").signature(real_fn)
                wrapped.__annotations__ = real_fn.__annotations__
                return wrapped

            setattr(module, name, make_wrapper(fn, name))

    yield counts

    for (mod_name, name), original in originals.items():
        module = leaves if mod_name == leaves.__name__ else analysis
        setattr(module, name, original)


# ---------- happy path: hit / miss ----------


class TestCacheHitMiss:
    def test_first_run_is_all_misses(self, project: Project, call_counter: dict[str, int]) -> None:
        project.run(modules=[leaves, analysis], targets=["t_j"])
        # Every node we touch should have executed exactly once.
        assert call_counter.get("i_supply") == 1
        assert call_counter.get("v_supply") == 1
        assert call_counter.get("r_theta") == 1
        assert call_counter.get("power") == 1
        assert call_counter.get("thermal_rise") == 1
        assert call_counter.get("t_j") == 1

    def test_second_run_is_all_hits(self, project: Project, call_counter: dict[str, int]) -> None:
        project.run(modules=[leaves, analysis], targets=["t_j"])
        call_counter.clear()
        # Second run with identical inputs / sources: nothing should execute.
        result = project.run(modules=[leaves, analysis], targets=["t_j"])
        assert call_counter == {}
        # Result still has to be correct.
        assert isinstance(result["t_j"], Quantity)

    def test_second_run_results_match_first(self, project: Project) -> None:
        first = project.run(modules=[leaves, analysis], targets=["t_j", "power"])
        second = project.run(modules=[leaves, analysis], targets=["t_j", "power"])
        assert first["power"].at() == second["power"].at()
        assert first["t_j"].at(scenario="nominal") == second["t_j"].at(scenario="nominal")

    def test_cache_files_appear_on_disk(self, project: Project) -> None:
        assert project.cache is not None
        assert len(project.cache) == 0
        project.run(modules=[leaves, analysis], targets=["t_j"])
        assert len(project.cache) > 0


# ---------- invalidation ----------


class TestInvalidation:
    def test_input_change_invalidates_downstream(
        self, project: Project, call_counter: dict[str, int]
    ) -> None:
        project.run(modules=[leaves, analysis], targets=["t_j"])
        call_counter.clear()

        # Swap ambient_temp to a fresh value -- the input hash changes, which
        # transitively invalidates t_j (the only function downstream of it).
        # power/thermal_rise don't depend on ambient_temp, so they stay cached.
        project.run(
            modules=[leaves, analysis],
            targets=["t_j"],
            inputs={"ambient_temp": Constant(323.15, K)},  # 50 degC in K
        )
        assert call_counter.get("t_j") == 1
        assert "power" not in call_counter
        assert "thermal_rise" not in call_counter

    def test_function_source_change_invalidates_self_and_descendants(
        self, project: Project, call_counter: dict[str, int]
    ) -> None:
        first = project.run(modules=[leaves, analysis], targets=["power", "t_j"])
        first_power_lo, first_power_hi = first["power"].at()
        call_counter.clear()

        # Replace i_supply with an implementation that doubles the current.
        # Its source bytes change → its hash changes → power / thermal_rise /
        # t_j (the descendants) all invalidate. r_theta and v_supply don't
        # depend on it, so they should stay cached. We verify via the result
        # values (power roughly doubles) rather than via the call counter,
        # since the freshly-defined function bypasses the conftest wrapper.
        def i_supply() -> Quantity:
            """A version returning a doubled magnitude."""
            return Constant(200.0, mA)
        i_supply.__module__ = leaves.__name__
        leaves.i_supply = i_supply

        try:
            second = project.run(modules=[leaves, analysis], targets=["power", "t_j"])
            second_power_lo, second_power_hi = second["power"].at()
            # Power should have ~doubled (current is 2x, voltage band unchanged).
            assert second_power_lo > first_power_lo * 1.5
            assert second_power_hi > first_power_hi * 1.5
            # r_theta and v_supply do not depend on i_supply — they stay cached.
            assert "r_theta" not in call_counter
            assert "v_supply" not in call_counter
        finally:
            # Restore so other tests see the original leaves.i_supply.
            from importlib import reload
            reload(leaves)

    def test_framework_version_change_invalidates_everything(
        self, project: Project, call_counter: dict[str, int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project.run(modules=[leaves, analysis], targets=["t_j"])
        call_counter.clear()

        # Bump framework version -- every function hash changes.
        monkeypatch.setattr(framework, "__version__", "9.9.9-test")
        project.run(modules=[leaves, analysis], targets=["t_j"])
        # All function nodes must have executed.
        for fn in ("i_supply", "v_supply", "r_theta", "power", "thermal_rise", "t_j"):
            assert call_counter.get(fn) == 1, f"{fn} did not re-execute on framework version bump"


# ---------- disable / passthrough ----------


class TestCacheDisabled:
    def test_disabled_cache_is_no_op(self, tmp_path: Path, call_counter: dict[str, int]) -> None:
        project = Project.load(
            scenarios=ScenarioSet(scenarios=[Scenario(name="nominal", context={"ambient_temp": "25 degC"})]),
            modes=ModeSet(modes=[Mode(name="active")]),
            cache_dir=None,
        )
        assert project.cache is None
        project.run(modules=[leaves, analysis], targets=["t_j"])
        call_counter.clear()
        project.run(modules=[leaves, analysis], targets=["t_j"])
        # Without a cache, every node should execute every time.
        for fn in ("i_supply", "v_supply", "r_theta", "power", "thermal_rise", "t_j"):
            assert call_counter.get(fn) == 1, f"{fn} did not re-execute when cache is disabled"


# ---------- robustness ----------


class TestCacheRobustness:
    def test_corrupt_cache_file_is_ignored(self, project: Project) -> None:
        # Seed the cache normally.
        project.run(modules=[leaves, analysis], targets=["t_j"])
        assert project.cache is not None
        # Corrupt one file in the cache.
        cached_files = list(project.cache.cache_dir.glob("*.pkl"))
        assert cached_files, "expected cache files to exist"
        target = cached_files[0]
        target.write_bytes(b"this is not a valid framework cache file")
        # Second run should still succeed: the corrupted entry is ignored and
        # recomputed.
        result = project.run(modules=[leaves, analysis], targets=["t_j"])
        assert isinstance(result["t_j"], Quantity)

    def test_cache_clear_forces_recompute(
        self, project: Project, call_counter: dict[str, int]
    ) -> None:
        project.run(modules=[leaves, analysis], targets=["t_j"])
        assert project.cache is not None
        project.cache.clear()
        assert len(project.cache) == 0
        call_counter.clear()
        project.run(modules=[leaves, analysis], targets=["t_j"])
        assert call_counter.get("t_j") == 1
