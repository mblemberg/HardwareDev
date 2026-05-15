"""Contracts — public commitments a block makes to other blocks (design doc 6.7).

A Contract is a Hamilton DAG node *marked* with metadata declaring it is
its block's public face. Cross-block dependencies must go through Contracts
only; a Contract may depend on inputs within its own block, on Contracts of
other blocks, and on global inputs (project requirements / scenarios /
modes / component instances), but **not** on non-Contract outputs of another
block. That rule is what makes Contracts the *cycle cut-points* of the
project's dependency graph.

Usage:

    @contract(
        description="Current drawn from 3V3 rail",
        requirement="REQ-PWR-014",
        assumed_inputs={"rail_3v3_voltage": (3.15 * units.V, 3.45 * units.V)},
    )
    def block_a_3v3_draw() -> Quantity:
        return Quantity(
            by_mode={...},
            unit=units.A,
        )

The decorator is a pure marker — it sets ``__is_contract__`` and
``__contract_meta__`` on the function and otherwise returns it unchanged,
so Hamilton sees a perfectly ordinary function-node and a separate cycle
detector (:func:`framework.detect_cycles`) inspects the markers to enforce
the cross-block rule.
"""
from __future__ import annotations

import inspect
import types
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

_T = TypeVar("_T", bound=Callable[..., Any])


@dataclass(frozen=True)
class ContractMeta:
    """Metadata attached to a function decorated with :func:`contract`."""

    description: str
    requirement: str | None = None
    assumed_inputs: dict[str, Any] = field(default_factory=dict)
    function_name: str = ""
    block: str = ""


def contract(
    *,
    description: str,
    requirement: str | None = None,
    assumed_inputs: Mapping[str, Any] | None = None,
) -> Callable[[_T], _T]:
    """Mark a function as producing a Contract (design doc 6.7).

    Args:
        description: One-line summary of what the Contract represents.
        requirement: Optional Jama requirement ID this contract binds to.
        assumed_inputs: Names → assumed values for inputs the contract's
            consumers will reference (e.g. ``{"rail_3v3_voltage":
            (3.15 * V, 3.45 * V)}``). These are *not* DAG inputs — they're
            the boundary conditions the contract's author commits to.
    """

    def decorator(fn: _T) -> _T:
        meta = ContractMeta(
            description=description,
            requirement=requirement,
            assumed_inputs=dict(assumed_inputs) if assumed_inputs else {},
            function_name=fn.__name__,
            block=block_of_function(fn),
        )
        fn.__is_contract__ = True   # type: ignore[attr-defined]
        fn.__contract_meta__ = meta  # type: ignore[attr-defined]
        return fn

    return decorator


def is_contract(fn: Any) -> bool:
    """True iff ``fn`` carries the ``@contract`` marker."""
    return bool(getattr(fn, "__is_contract__", False))


def get_contract_meta(fn: Any) -> ContractMeta | None:
    """Return the ``ContractMeta`` for ``fn``, or None if it isn't a contract."""
    return getattr(fn, "__contract_meta__", None) if is_contract(fn) else None


def block_of_function(fn: Any) -> str:
    """The block a function belongs to.

    Convention: the block name is the *last component of the module's parent
    package path*. So ``blocks.can_transceiver.contracts`` -> ``can_transceiver``,
    ``sample_block.leaves`` -> ``sample_block``, and a top-level module ``foo``
    -> ``foo``. The rule matches the design doc 6.6 block-as-subpackage layout.
    """
    mod = getattr(fn, "__module__", "")
    if not mod:
        return ""
    parts = mod.split(".")
    if len(parts) == 1:
        return parts[0]
    return parts[-2]


class CycleViolation(ValueError):
    """A Contract depends on a forbidden node (design doc 6.7, 7.4).

    Raised when:
      - a Contract's dependency reaches a non-Contract node owned by a
        different block, or
      - a Contract transitively depends on itself.
    """


def detect_cycles(modules: list[types.ModuleType]) -> None:
    """Verify every Contract obeys the cross-block dependency rule.

    Walks the dependency graph of every Contract in ``modules``. Raises
    :class:`CycleViolation` on the first offending path, naming both the
    offending node and the chain that reaches it.

    Algorithm (design doc 7.4):
      1. Build a node table from all functions in ``modules``.
      2. For each Contract C with block B, DFS over C's transitive deps.
      3. If we visit a non-Contract node whose block != B, that's the
         cross-block violation.
      4. If we revisit C (or any ancestor), that's a self-cycle.
    """
    nodes = _collect_nodes(modules)
    for name, info in nodes.items():
        if info.is_contract:
            _walk_contract_deps(name, info.block, nodes, current=name, ancestors=[name])


@dataclass
class _NodeInfo:
    name: str
    fn: Callable[..., Any]
    deps: list[str]
    block: str
    is_contract: bool


def _collect_nodes(modules: list[types.ModuleType]) -> dict[str, _NodeInfo]:
    nodes: dict[str, _NodeInfo] = {}
    for module in modules:
        for attr in dir(module):
            if attr.startswith("_"):
                continue
            obj = getattr(module, attr, None)
            if not inspect.isfunction(obj):
                continue
            if obj.__module__ != module.__name__:
                continue  # re-export from elsewhere
            sig = inspect.signature(obj)
            deps = list(sig.parameters.keys())
            info = _NodeInfo(
                name=attr,
                fn=obj,
                deps=deps,
                block=block_of_function(obj),
                is_contract=is_contract(obj),
            )
            if attr in nodes:
                # Two modules declaring the same node name. compute_node_hashes
                # raises here too; bail with a clearer message.
                raise ValueError(
                    f"duplicate DAG node name {attr!r} (in {nodes[attr].fn.__module__!r} "
                    f"and {obj.__module__!r})"
                )
            nodes[attr] = info
    return nodes


def _walk_contract_deps(
    contract_name: str,
    contract_block: str,
    nodes: dict[str, _NodeInfo],
    current: str,
    ancestors: list[str],
) -> None:
    info = nodes.get(current)
    if info is None:
        return  # external input (project standard input, requirement, etc.)
    for dep in info.deps:
        if dep == contract_name:
            raise CycleViolation(
                f"Contract {contract_name!r} depends on itself transitively. "
                f"Path: {' -> '.join(ancestors + [dep])}"
            )
        if dep in ancestors:
            raise CycleViolation(
                f"cycle in contract subgraph reached from {contract_name!r}: "
                f"{' -> '.join(ancestors + [dep])}"
            )
        dep_info = nodes.get(dep)
        if dep_info is None:
            continue  # external input
        if dep_info.block != contract_block:
            # Crossing the block boundary. Only a Contract is allowed across.
            # Whether allowed or not, do NOT recurse: Contracts are cut-points
            # (design doc 6.7) — what the upstream block does internally is
            # validated when its own contracts are walked, not from here.
            if not dep_info.is_contract:
                raise CycleViolation(
                    f"Contract {contract_name!r} (block {contract_block!r}) depends on "
                    f"non-Contract node {dep!r} in block {dep_info.block!r}. "
                    f"Cross-block dependencies must flow through Contracts only. "
                    f"Path: {' -> '.join(ancestors + [dep])}. "
                    f"Fix: declare a Contract on {dep!r}, or read from a Contract of "
                    f"block {dep_info.block!r} instead."
                )
            continue
        # Same block: recurse so we catch indirect violations + self-cycles.
        _walk_contract_deps(
            contract_name, contract_block, nodes, current=dep, ancestors=ancestors + [dep]
        )


__all__ = [
    "ContractMeta",
    "CycleViolation",
    "block_of_function",
    "contract",
    "detect_cycles",
    "get_contract_meta",
    "is_contract",
]
