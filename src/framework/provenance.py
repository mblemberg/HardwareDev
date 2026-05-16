"""Provenance chain traversal (design doc 9 / step 10).

Every Quantity carries a :class:`ProvenanceRef` — a pointer back to the DAG
node that produced it. Storage on the Quantity itself is O(1); the full
ancestry is reconstructed lazily by walking a per-run
:class:`ProvenanceGraph` (built by :class:`framework.Project.run` after
Hamilton executes).

API:

    q = results["t_j"]
    q.provenance                # ProvenanceRef pointing at the "t_j" node
    q.provenance.info           # ProvenanceNodeInfo (function, hash, parents)
    q.provenance.parents()      # immediate parents as a list of ProvenanceRefs
    q.provenance.chain()        # flat list of ancestors, breadth-first
    q.provenance.chain_summary()  # human-readable indented rendering

Safeguards (design doc 9):
- ``visited`` set during ``chain()`` terminates revisited branches.
- Configurable depth limit (default 100); on overshoot, ``chain()`` emits a
  warning and appends a sentinel ProvenanceRef with id "...truncated at
  depth N..." rather than silently dropping data.
- ``chain()`` results are memoized on the ProvenanceGraph for the graph's
  lifetime (which equals the lifetime of a :class:`Project.run` invocation).

Quantities created outside the DAG (literals, arithmetic results) keep a
placeholder ProvenanceRef with ``node_id="<literal>"`` — ``parents()`` on
those returns ``[]`` and ``chain()`` returns ``[self]``.
"""
from __future__ import annotations

import dataclasses
import inspect
import logging
import types
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from framework.quantity import Quantity

logger = logging.getLogger(__name__)

LITERAL_NODE_ID = "<literal>"


@dataclass(frozen=True)
class ProvenanceNodeInfo:
    """Per-node info captured at DAG-build time for a single Project.run.

    Stored on a :class:`ProvenanceGraph`. Fully immutable / hashable.
    """

    node_id: str
    function_qualname: str
    module: str
    node_hash: str
    parents: tuple[str, ...] = ()
    is_input: bool = False  # True for project-supplied inputs (no function source)


class ProvenanceGraph:
    """All node info from one ``Project.run`` invocation.

    Not a frozen dataclass — carries a memoization cache that's mutated as
    chains are walked. Logically immutable once built (nodes dict not
    mutated after construction).
    """

    __slots__ = ("nodes", "_chain_cache")

    def __init__(self, nodes: dict[str, ProvenanceNodeInfo]) -> None:
        self.nodes = nodes
        self._chain_cache: dict[tuple[str, int], list["ProvenanceRef"]] = {}

    def info(self, node_id: str) -> ProvenanceNodeInfo | None:
        return self.nodes.get(node_id)

    def __repr__(self) -> str:  # debug aid
        return f"ProvenanceGraph(nodes={len(self.nodes)})"


@dataclass(frozen=True)
class ProvenanceRef:
    """Content-addressed pointer back to the DAG node that produced a Quantity.

    Carries a node_id (the DAG node name) and an optional reference to the
    :class:`ProvenanceGraph` of the run that produced it. Quantities outside
    the DAG (literals, arithmetic results) get ``node_id="<literal>"`` and a
    null graph — ``parents()`` returns ``[]`` and ``chain()`` returns ``[self]``.

    ``label`` is a human-readable hint, set when the framework wants to
    distinguish multiple unhooked Quantities (e.g. ``"const 25 °C"``).
    """

    node_id: str = LITERAL_NODE_ID
    label: str | None = None
    _graph: ProvenanceGraph | None = field(default=None, repr=False, compare=False)

    @property
    def info(self) -> ProvenanceNodeInfo | None:
        """Look up this ref's node info on its graph (or None if unhooked)."""
        if self._graph is None:
            return None
        return self._graph.info(self.node_id)

    @property
    def is_literal(self) -> bool:
        return self.node_id == LITERAL_NODE_ID or self._graph is None

    def parents(self) -> list["ProvenanceRef"]:
        """Immediate parent ProvenanceRefs. Empty for inputs / unhooked refs."""
        info = self.info
        if info is None or self._graph is None:
            return []
        return [
            ProvenanceRef(node_id=p, _graph=self._graph)
            for p in info.parents
        ]

    # Backwards-compat: step 1 stub exposed singular parent(). Keep the name,
    # return the first parent for callers that don't care about full ancestry.
    def parent(self) -> "ProvenanceRef | None":
        ps = self.parents()
        return ps[0] if ps else None

    def chain(self, max_depth: int = 100) -> list["ProvenanceRef"]:
        """Flat list of ancestors (breadth-first), with ``self`` first.

        Terminates revisited branches via a visited set. On overshoot of
        ``max_depth``, emits a warning and appends a sentinel ProvenanceRef
        with id ``"...truncated at depth N..."``. Results are memoized on
        the underlying graph keyed by ``(node_id, max_depth)``.
        """
        if self._graph is None:
            return [self]
        cache_key = (self.node_id, max_depth)
        cached = self._graph._chain_cache.get(cache_key)
        if cached is not None:
            return cached

        out: list[ProvenanceRef] = [self]
        visited: set[str] = {self.node_id}
        frontier: list[tuple[ProvenanceRef, int]] = [(self, 0)]
        truncated = False
        while frontier:
            ref, depth = frontier.pop(0)
            if depth >= max_depth:
                truncated = True
                break
            for p in ref.parents():
                if p.node_id in visited:
                    continue
                visited.add(p.node_id)
                out.append(p)
                frontier.append((p, depth + 1))
        if truncated:
            warnings.warn(
                f"Provenance chain truncated at depth {max_depth} "
                f"(from {self.node_id!r}). Increase max_depth= if you need "
                f"deeper introspection.",
                stacklevel=2,
            )
            out.append(
                ProvenanceRef(
                    node_id=f"...truncated at depth {max_depth}...",
                    _graph=self._graph,
                )
            )
        self._graph._chain_cache[cache_key] = out
        return out

    def chain_summary(self, max_depth: int = 100) -> str:
        """Human-readable indented rendering of the chain for diagnostics.

        Depths reflect BFS distance from ``self`` (the queried node is at
        depth 0; its immediate parents at depth 1; etc.) — independent of
        the underlying DAG's edge direction.
        """
        chain = self.chain(max_depth=max_depth)
        if len(chain) == 1 and self.is_literal:
            return f"{self.node_id}  (no DAG provenance)"

        # BFS depths from self.
        depths: dict[str, int] = {self.node_id: 0}
        queue: list[ProvenanceRef] = [self]
        while queue:
            ref = queue.pop(0)
            for p in ref.parents():
                if p.node_id not in depths:
                    depths[p.node_id] = depths[ref.node_id] + 1
                    queue.append(p)

        lines: list[str] = []
        for ref in chain:
            d = depths.get(ref.node_id, 0)
            info = ref.info
            if info is None:
                lines.append("  " * d + f"- {ref.node_id}")
                continue
            if info.is_input:
                label = "input"
            elif info.module:
                label = f"{info.module}::{info.function_qualname}"
            else:
                label = info.function_qualname
            lines.append(
                "  " * d
                + f"- {ref.node_id}  [{label}]  hash={info.node_hash[:10]}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Graph construction (called by Project.run)
# ---------------------------------------------------------------------------


def build_provenance_graph(
    modules: list[types.ModuleType],
    inputs: dict[str, Any],
    node_hashes: dict[str, str],
) -> ProvenanceGraph:
    """Build a :class:`ProvenanceGraph` for one Project.run invocation.

    Reuses the function table walk that ``_hashing.collect_module_functions``
    already does, but captures function qualnames / modules / parent-name
    lists alongside the hashes. ``node_hashes`` is the same dict produced by
    ``_hashing.compute_node_hashes``.
    """
    from framework._hashing import collect_module_functions  # local: avoid cycle

    fn_table = collect_module_functions(modules)
    nodes: dict[str, ProvenanceNodeInfo] = {}

    # Inputs first (no parents, no function).
    for name in inputs:
        nodes[name] = ProvenanceNodeInfo(
            node_id=name,
            function_qualname=f"<input:{name}>",
            module="",
            node_hash=node_hashes.get(name, ""),
            parents=(),
            is_input=True,
        )

    # Then every DAG function node.
    for name, (fn, deps, _src) in fn_table.items():
        nodes[name] = ProvenanceNodeInfo(
            node_id=name,
            function_qualname=fn.__qualname__,
            module=fn.__module__,
            node_hash=node_hashes.get(name, ""),
            parents=tuple(deps),
            is_input=False,
        )

    return ProvenanceGraph(nodes=nodes)


# ---------------------------------------------------------------------------
# Attaching provenance to result Quantities
# ---------------------------------------------------------------------------


def attach_provenance(
    quantity: "Quantity",
    *,
    node_id: str,
    graph: ProvenanceGraph,
) -> "Quantity":
    """Return a copy of ``quantity`` whose provenance points at ``node_id``.

    Recursively attaches to ``by_mode`` children too so a caller drilling
    into ``q.by_mode["active"]`` still gets a useful provenance pointer.
    Frozen-dataclass safe (uses :func:`dataclasses.replace`).
    """
    from framework.quantity import Quantity  # local: avoid cycle

    if not isinstance(quantity, Quantity):
        return quantity

    new_prov = ProvenanceRef(node_id=node_id, _graph=graph)

    if quantity.by_mode is not None:
        new_by_mode = {
            m: attach_provenance(child, node_id=node_id, graph=graph)
            for m, child in quantity.by_mode.items()
        }
        return dataclasses.replace(quantity, by_mode=new_by_mode, provenance=new_prov)
    return dataclasses.replace(quantity, provenance=new_prov)


__all__ = [
    "LITERAL_NODE_ID",
    "ProvenanceGraph",
    "ProvenanceNodeInfo",
    "ProvenanceRef",
    "attach_provenance",
    "build_provenance_graph",
]
