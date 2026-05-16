"""Contract decorator + cycle detection (design doc 6.7, 7.4)."""
from __future__ import annotations

import types

import pytest

from framework import (
    Constant,
    CycleViolation,
    Quantity,
    contract,
    detect_cycles,
    get_contract_meta,
    is_contract,
)
from framework.contract import block_of_function
from framework.units import V, mA


# ---------------------------------------------------------------------------
# Decorator + metadata
# ---------------------------------------------------------------------------


class TestDecorator:
    def test_marks_function(self) -> None:
        @contract(description="x")
        def fn() -> Quantity:
            return Constant(1.0, mA)
        assert is_contract(fn) is True

    def test_un_decorated_function_is_not_a_contract(self) -> None:
        def fn() -> Quantity:
            return Constant(1.0, mA)
        assert is_contract(fn) is False
        assert get_contract_meta(fn) is None

    def test_metadata_captured(self) -> None:
        @contract(
            description="Current drawn from 3V3 rail",
            requirement="REQ-PWR-014",
            assumed_inputs={"rail_3v3_voltage": (3.15, 3.45)},
        )
        def fn() -> Quantity:
            return Constant(1.0, mA)
        meta = get_contract_meta(fn)
        assert meta is not None
        assert meta.description == "Current drawn from 3V3 rail"
        assert meta.requirement == "REQ-PWR-014"
        assert meta.assumed_inputs == {"rail_3v3_voltage": (3.15, 3.45)}
        assert meta.function_name == "fn"

    def test_function_remains_callable(self) -> None:
        @contract(description="x")
        def fn() -> Quantity:
            return Constant(42.0, mA)
        out = fn()
        assert isinstance(out, Quantity)
        assert out.at() == 42.0


# ---------------------------------------------------------------------------
# Block-of-function rule
# ---------------------------------------------------------------------------


class TestBlockOf:
    def test_two_component_module(self) -> None:
        def fn() -> None: ...
        fn.__module__ = "sample_block.leaves"
        assert block_of_function(fn) == "sample_block"

    def test_three_component_module(self) -> None:
        def fn() -> None: ...
        fn.__module__ = "blocks.can_transceiver.analysis"
        assert block_of_function(fn) == "can_transceiver"

    def test_single_module_falls_back(self) -> None:
        def fn() -> None: ...
        fn.__module__ = "standalone"
        assert block_of_function(fn) == "standalone"

    def test_missing_module(self) -> None:
        def fn() -> None: ...
        fn.__module__ = ""
        assert block_of_function(fn) == ""


# ---------------------------------------------------------------------------
# Cycle detection (design doc 7.4)
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_valid_intra_block_passes(self) -> None:
        # block_x: contract depends only on its own block's leaf — fine.
        from block_x import contracts as x_contracts, leaves as x_leaves
        detect_cycles([x_leaves, x_contracts])

    def test_valid_cross_block_via_contract_passes(self) -> None:
        # block_y's contract depends on block_x's contract — allowed.
        from block_x import contracts as x_contracts, leaves as x_leaves
        from block_y import contracts as y_contracts
        detect_cycles([x_leaves, x_contracts, y_contracts])

    def test_cross_block_non_contract_dep_rejected(self) -> None:
        # bad_block.bad_draw depends on x_internal_draw — a non-Contract from another block.
        from block_x import leaves as x_leaves
        from bad_block import contracts as bad_contracts
        with pytest.raises(CycleViolation) as exc_info:
            detect_cycles([x_leaves, bad_contracts])
        msg = str(exc_info.value)
        assert "bad_draw" in msg
        assert "x_internal_draw" in msg
        assert "block_x" in msg
        # The hint about how to fix is part of the contract.
        assert "Contract" in msg

    def test_no_contracts_means_no_validation(self) -> None:
        # The sample_block fixture has no contracts; detection is a no-op.
        from sample_block import analysis, leaves
        detect_cycles([leaves, analysis])

    def test_self_cycle_is_an_error(self) -> None:
        # Synthesize a module with a self-referential contract via types.ModuleType.
        mod = types.ModuleType("synthetic_block.contracts")
        mod.__name__ = "synthetic_block.contracts"

        @contract(description="self-referential")
        def loop(loop: Quantity) -> Quantity:   # type: ignore[no-redef]
            return loop
        loop.__module__ = "synthetic_block.contracts"
        mod.loop = loop
        with pytest.raises(CycleViolation, match="itself"):
            detect_cycles([mod])

    def test_duplicate_node_name_across_modules_rejected(self) -> None:
        # Two modules both export `dup`. _collect_nodes refuses.
        mod_a = types.ModuleType("block_alpha.x")
        mod_a.__name__ = "block_alpha.x"
        mod_b = types.ModuleType("block_alpha.y")
        mod_b.__name__ = "block_alpha.y"

        def dup() -> Quantity:
            return Constant(1.0, mA)
        dup.__module__ = "block_alpha.x"
        mod_a.dup = dup

        def dup2() -> Quantity:
            return Constant(2.0, mA)
        dup2.__name__ = "dup"
        dup2.__module__ = "block_alpha.y"
        mod_b.dup = dup2
        with pytest.raises(ValueError, match="duplicate DAG node name"):
            detect_cycles([mod_a, mod_b])
