"""Provenance chain traversal (design doc 9 / step 10)."""
from __future__ import annotations

import types
import warnings

import pytest

from framework import (
    Constant,
    Project,
    ProvenanceGraph,
    ProvenanceNodeInfo,
    ProvenanceRef,
    Quantity,
)
from framework.modes import ModeSet
from framework.provenance import attach_provenance, build_provenance_graph
from framework.scenarios import ScenarioSet
from framework.units import K, V, degC, mA, mW


# ---------------------------------------------------------------------------
# Literal refs (no graph)
# ---------------------------------------------------------------------------


class TestLiteralRef:
    def test_default_is_literal(self) -> None:
        ref = ProvenanceRef()
        assert ref.is_literal
        assert ref.parents() == []
        assert ref.chain() == [ref]

    def test_chain_summary_for_literal(self) -> None:
        ref = ProvenanceRef()
        s = ref.chain_summary()
        assert "no DAG provenance" in s

    def test_quantity_default_provenance_is_literal(self) -> None:
        q = Constant(5.0, mA)
        assert q.provenance.is_literal


# ---------------------------------------------------------------------------
# build_provenance_graph
# ---------------------------------------------------------------------------


def _mk_mod(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__name__ = name
    return mod


class TestBuildGraph:
    def test_inputs_become_nodes(self) -> None:
        graph = build_provenance_graph([], {"ambient_temp": Constant(25, degC)}, {"ambient_temp": "h1"})
        info = graph.info("ambient_temp")
        assert info is not None
        assert info.is_input
        assert info.parents == ()
        assert info.node_hash == "h1"

    def test_function_nodes_capture_qualname_module_parents(self) -> None:
        mod = _mk_mod("pmod")

        def leaf() -> Quantity:
            return Constant(1.0, mA)

        def derived(leaf: Quantity, ambient_temp: Quantity) -> Quantity:
            return leaf

        leaf.__module__ = "pmod"
        derived.__module__ = "pmod"
        mod.leaf = leaf
        mod.derived = derived

        graph = build_provenance_graph(
            [mod],
            {"ambient_temp": Constant(25, degC)},
            {"leaf": "hL", "derived": "hD", "ambient_temp": "hA"},
        )
        leaf_info = graph.info("leaf")
        derived_info = graph.info("derived")
        assert leaf_info is not None and derived_info is not None
        assert leaf_info.parents == ()
        assert leaf_info.is_input is False
        assert set(derived_info.parents) == {"leaf", "ambient_temp"}
        assert derived_info.module == "pmod"
        assert derived_info.function_qualname == "TestBuildGraph.test_function_nodes_capture_qualname_module_parents.<locals>.derived"


# ---------------------------------------------------------------------------
# ProvenanceRef walks (parents, chain, summary)
# ---------------------------------------------------------------------------


def _two_level_graph() -> ProvenanceGraph:
    """leaf <- mid <- top"""
    nodes = {
        "leaf": ProvenanceNodeInfo("leaf", "leaf_fn", "m", "h_leaf"),
        "mid":  ProvenanceNodeInfo("mid",  "mid_fn",  "m", "h_mid",  parents=("leaf",)),
        "top":  ProvenanceNodeInfo("top",  "top_fn",  "m", "h_top",  parents=("mid",)),
    }
    return ProvenanceGraph(nodes)


def _diamond_graph() -> ProvenanceGraph:
    """leaf <- a, leaf <- b, top depends on (a, b)"""
    nodes = {
        "leaf": ProvenanceNodeInfo("leaf", "leaf_fn", "m", "h_leaf"),
        "a":    ProvenanceNodeInfo("a", "a_fn", "m", "h_a", parents=("leaf",)),
        "b":    ProvenanceNodeInfo("b", "b_fn", "m", "h_b", parents=("leaf",)),
        "top":  ProvenanceNodeInfo("top", "top_fn", "m", "h_top", parents=("a", "b")),
    }
    return ProvenanceGraph(nodes)


class TestWalks:
    def test_parents_returns_immediate_parents(self) -> None:
        g = _two_level_graph()
        top_ref = ProvenanceRef(node_id="top", _graph=g)
        ps = top_ref.parents()
        assert [p.node_id for p in ps] == ["mid"]

    def test_chain_walks_to_leaf(self) -> None:
        g = _two_level_graph()
        top_ref = ProvenanceRef(node_id="top", _graph=g)
        chain = top_ref.chain()
        assert [r.node_id for r in chain] == ["top", "mid", "leaf"]

    def test_chain_dedupes_diamond_visits(self) -> None:
        g = _diamond_graph()
        top_ref = ProvenanceRef(node_id="top", _graph=g)
        chain = top_ref.chain()
        ids = [r.node_id for r in chain]
        assert ids[0] == "top"
        assert set(ids) == {"top", "a", "b", "leaf"}
        # 'leaf' appears exactly once even though both a and b point to it
        assert ids.count("leaf") == 1

    def test_chain_depth_limit_truncates(self) -> None:
        # Build a chain of 10 nodes: n0 <- n1 <- ... <- n9
        nodes: dict[str, ProvenanceNodeInfo] = {}
        for i in range(10):
            parents = (f"n{i - 1}",) if i > 0 else ()
            nodes[f"n{i}"] = ProvenanceNodeInfo(
                f"n{i}", f"fn{i}", "m", f"h{i}", parents=parents
            )
        g = ProvenanceGraph(nodes)
        ref = ProvenanceRef(node_id="n9", _graph=g)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            chain = ref.chain(max_depth=3)
        assert any("truncated at depth 3" in str(w.message) for w in captured)
        assert chain[-1].node_id.startswith("...truncated")

    def test_chain_summary_indents_with_depth(self) -> None:
        g = _two_level_graph()
        top_ref = ProvenanceRef(node_id="top", _graph=g)
        summary = top_ref.chain_summary()
        lines = summary.splitlines()
        assert lines[0].startswith("- top")
        # mid is at depth 1 (2 spaces indent)
        assert lines[1].startswith("  - mid")
        # leaf is at depth 2 (4 spaces indent)
        assert lines[2].startswith("    - leaf")

    def test_chain_memoized(self) -> None:
        g = _two_level_graph()
        ref = ProvenanceRef(node_id="top", _graph=g)
        chain1 = ref.chain()
        chain2 = ref.chain()
        # Same object — memoized.
        assert chain1 is chain2

    def test_parent_singular_back_compat(self) -> None:
        g = _two_level_graph()
        top_ref = ProvenanceRef(node_id="top", _graph=g)
        p = top_ref.parent()
        assert p is not None
        assert p.node_id == "mid"

    def test_parent_returns_none_for_leaf(self) -> None:
        g = _two_level_graph()
        ref = ProvenanceRef(node_id="leaf", _graph=g)
        assert ref.parent() is None


# ---------------------------------------------------------------------------
# attach_provenance
# ---------------------------------------------------------------------------


class TestAttachProvenance:
    def test_attaches_top_level(self) -> None:
        g = _two_level_graph()
        q = Constant(5.0, mA)
        out = attach_provenance(q, node_id="top", graph=g)
        assert out.provenance.node_id == "top"
        assert out.provenance._graph is g

    def test_recurses_into_by_mode_children(self) -> None:
        g = _two_level_graph()
        q = Quantity(unit=mA, by_mode={
            "a": Constant(1.0, mA),
            "b": Constant(2.0, mA),
        })
        out = attach_provenance(q, node_id="top", graph=g)
        assert out.provenance.node_id == "top"
        for child in out.by_mode.values():
            assert child.provenance.node_id == "top"

    def test_passthrough_non_quantity(self) -> None:
        # Non-Quantity values should be returned unchanged (Project.run
        # may have results dicts with input objects mixed in).
        sentinel = object()
        assert attach_provenance(sentinel, node_id="x", graph=_two_level_graph()) is sentinel  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# End-to-end: Project.run attaches provenance
# ---------------------------------------------------------------------------


def _empty_project() -> Project:
    return Project(
        scenarios=ScenarioSet(scenarios=[]),
        modes=ModeSet(modes=[]),
        cache_dir=None,
    )


class TestProjectRunIntegration:
    """End-to-end via the sample_block fixture (real module, Hamilton-compatible)."""

    def test_result_quantities_carry_provenance(self) -> None:
        from sample_block import analysis, leaves

        out = _empty_project().run(
            modules=[leaves, analysis],
            targets=["t_j"],
            inputs={"ambient_temp": Constant(25, degC)},
        )
        ref = out["t_j"].provenance
        assert ref.node_id == "t_j"
        ids = {r.node_id for r in ref.chain()}
        # Full lineage: t_j depends on ambient_temp + thermal_rise →
        # power + r_theta → v_supply + i_supply.
        assert {"t_j", "thermal_rise", "power", "r_theta", "i_supply",
                "v_supply", "ambient_temp"} <= ids

    def test_inputs_appear_in_chain_as_is_input(self) -> None:
        from sample_block import analysis, leaves

        out = _empty_project().run(
            modules=[leaves, analysis],
            targets=["t_j"],
            inputs={"ambient_temp": Constant(25, degC)},
        )
        chain = out["t_j"].provenance.chain()
        amb_ref = next(r for r in chain if r.node_id == "ambient_temp")
        assert amb_ref.info is not None
        assert amb_ref.info.is_input is True

    def test_function_node_carries_qualname(self) -> None:
        from sample_block import analysis, leaves

        out = _empty_project().run(
            modules=[leaves, analysis],
            targets=["t_j"],
            inputs={"ambient_temp": Constant(25, degC)},
        )
        chain = out["t_j"].provenance.chain()
        t_j_ref = next(r for r in chain if r.node_id == "t_j")
        assert t_j_ref.info is not None
        assert "t_j" in t_j_ref.info.function_qualname
        assert "sample_block" in t_j_ref.info.module

    def test_provenance_disabled_with_flag(self) -> None:
        from sample_block import analysis, leaves

        out = _empty_project().run(
            modules=[leaves, analysis],
            targets=["t_j"],
            inputs={"ambient_temp": Constant(25, degC)},
            attach_provenance_to_results=False,
        )
        assert out["t_j"].provenance.is_literal

    def test_chain_summary_renders(self) -> None:
        from sample_block import analysis, leaves

        out = _empty_project().run(
            modules=[leaves, analysis],
            targets=["t_j"],
            inputs={"ambient_temp": Constant(25, degC)},
        )
        s = out["t_j"].provenance.chain_summary()
        # Top node + first parent both rendered.
        assert "- t_j" in s
        assert "thermal_rise" in s
        # Function qualname referenced for at least one node.
        assert "sample_block" in s
