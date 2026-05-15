"""Provenance stub.

Full implementation lands in step 10 of the design doc's implementation order.
Step 1 only needs the type as a placeholder field on Quantity so signatures
and equality semantics are stable before the DAG-aware version arrives.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProvenanceRef:
    """Content-addressed pointer to a producing DAG node.

    Step 1 placeholder: holds a node id and an optional human label.
    Step 10 will add lazy chain traversal against the cached DAG.
    """

    node_id: str = "<literal>"
    label: str | None = None

    def parent(self) -> "ProvenanceRef | None":
        return None

    def chain(self, max_depth: int = 100) -> list["ProvenanceRef"]:
        return [self]
