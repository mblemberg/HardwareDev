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
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from framework.quantity import INVARIANT

if TYPE_CHECKING:
    from framework.quantity import Quantity, ScalarOrRange

_T = TypeVar("_T", bound=Callable[..., Any])


@dataclass(frozen=True)
class ContractMeta:
    """Metadata attached to a function decorated with :func:`contract`."""

    description: str
    requirement: str | None = None
    assumed_inputs: dict[str, Any] = field(default_factory=dict)
    compares_to: str | None = None
    function_name: str = ""
    block: str = ""


def contract(
    *,
    description: str,
    requirement: str | None = None,
    assumed_inputs: Mapping[str, Any] | None = None,
    compares_to: str | None = None,
) -> Callable[[_T], _T]:
    """Mark a function as producing a Contract (design doc 6.7).

    Args:
        description: One-line summary of what the Contract represents.
        requirement: Optional Jama requirement ID this contract binds to.
        assumed_inputs: Names → assumed values for inputs the contract's
            consumers will reference (e.g. ``{"rail_3v3_voltage":
            (3.15 * V, 3.45 * V)}``). These are *not* DAG inputs — they're
            the boundary conditions the contract's author commits to.
        compares_to: Name of the DAG node that computes the *actual* value of
            the same physical quantity. When set, :func:`Project.run` (or a
            manual call to :func:`check_contract_consistency`) verifies that
            the actual value lies within this Contract's declared bound for
            every scenario/mode (design doc 6.7 run-time rules).
    """

    def decorator(fn: _T) -> _T:
        meta = ContractMeta(
            description=description,
            requirement=requirement,
            assumed_inputs=dict(assumed_inputs) if assumed_inputs else {},
            compares_to=compares_to,
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


# ---------------------------------------------------------------------------
# Run-time contract consistency (design doc 6.7 run-time rules)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractMismatch:
    """One scenario/mode point where actual exceeds declared.

    Returned in lists by :func:`check_contract_consistency` (kind=``"declared"``)
    and :func:`check_contract_assumptions` (kind=``"assumed"``). ``actual``
    and ``declared`` are the raw values at that axis combination — scalars or
    ``(lo, hi)`` range tuples, in the Contract's unit.

    ``kind`` distinguishes the two flavors so callers and the formatter can
    render them differently:
    - ``"declared"``: the block's own actual exceeds the bound the block
      publishes (step 8).
    - ``"assumed"``: an upstream value the block assumes (via
      ``assumed_inputs=``) doesn't satisfy the assumed bound.
    """

    contract_name: str
    block: str
    scenario: str | None
    mode: str | None
    actual: "ScalarOrRange"
    declared: "ScalarOrRange"
    unit: str
    kind: str = "declared"


class ContractViolation(AssertionError):
    """One or more Contracts' actual values exceeded their declared bounds.

    Carries the full list of mismatches on ``.mismatches`` for programmatic
    inspection (e.g. a pytest plugin that wants to surface each one as its
    own test failure — design doc 6.7 calls for an auto-generated
    ``ContractViolation`` verification test per Contract).
    """

    def __init__(self, mismatches: list[ContractMismatch]) -> None:
        self.mismatches = mismatches
        super().__init__(format_mismatches(mismatches))


def format_mismatches(mismatches: list[ContractMismatch]) -> str:
    """Human-readable summary of contract-consistency mismatches."""
    if not mismatches:
        return "no contract mismatches"
    lines = [f"{len(mismatches)} contract mismatch(es):"]
    for m in mismatches:
        where: list[str] = []
        if m.scenario is not None and m.scenario != INVARIANT:
            where.append(f"scenario={m.scenario!r}")
        if m.mode is not None:
            where.append(f"mode={m.mode!r}")
        loc = ", ".join(where) if where else "(no axes)"
        bound_word = "assumed" if m.kind == "assumed" else "declared"
        lines.append(
            f"  - {m.contract_name!r} ({m.block}) at {loc}: "
            f"actual={m.actual} {m.unit} exceeds {bound_word}={m.declared} {m.unit}"
        )
    return "\n".join(lines)


def check_contract_consistency(
    modules: list[types.ModuleType],
    results: Mapping[str, Any],
    *,
    strict: bool = False,
) -> list[ContractMismatch]:
    """For each Contract with ``compares_to`` set, compare actual vs declared.

    Walks every ``@contract``-marked function in ``modules``. For those with a
    ``compares_to`` target, looks up that node's value in ``results``, then
    looks up the Contract's own value in ``results``, and verifies that the
    actual lies within the declared bound at every (scenario, mode) point.

    Returns a list of :class:`ContractMismatch` records — empty if all
    consistent. Use :func:`raise_on_mismatches` to convert to an exception.

    Contracts without ``compares_to`` are skipped (the Contract is a
    declaration only; no actual to compare against). Contracts whose own
    value or ``compares_to`` target is absent from ``results`` are skipped by
    default — pass ``strict=True`` to raise instead (used internally by
    :class:`Project` since it auto-adds the relevant targets).
    """
    from framework.quantity import Quantity  # local import to avoid cycle

    nodes = _collect_nodes(modules)
    mismatches: list[ContractMismatch] = []
    for name, info in nodes.items():
        if not info.is_contract:
            continue
        meta = get_contract_meta(info.fn)
        assert meta is not None
        target = meta.compares_to
        if target is None:
            continue
        if name not in results:
            if strict:
                raise ValueError(
                    f"Contract {name!r} declared compares_to={target!r}, but "
                    f"its own value is not in results."
                )
            continue
        if target not in results:
            if strict:
                raise ValueError(
                    f"Contract {name!r} declared compares_to={target!r}, but "
                    f"{target!r} is not in results."
                )
            continue
        declared = results[name]
        actual = results[target]
        if not isinstance(declared, Quantity):
            raise TypeError(
                f"Contract {name!r} returned {type(declared).__name__}, "
                f"expected framework.Quantity"
            )
        if not isinstance(actual, Quantity):
            raise TypeError(
                f"compares_to target {target!r} returned "
                f"{type(actual).__name__}, expected framework.Quantity"
            )
        mismatches.extend(
            _compare_quantities(
                contract_name=name,
                block=info.block,
                actual=actual,
                declared=declared,
            )
        )
    return mismatches


def raise_on_mismatches(mismatches: list[ContractMismatch]) -> None:
    """Raise :class:`ContractViolation` if ``mismatches`` is non-empty."""
    if mismatches:
        raise ContractViolation(mismatches)


def check_contract_assumptions(
    modules: list[types.ModuleType],
    results: Mapping[str, Any],
    *,
    strict: bool = False,
) -> list[ContractMismatch]:
    """For every Contract's ``assumed_inputs`` entry whose value is a Quantity,
    verify the actual DAG-node value (from ``results``) lies within the
    assumed bound at every (scenario, mode) point.

    This is the cross-block half of design doc §6.7 run-time rules. Where
    :func:`check_contract_consistency` verifies *a block's own* actual against
    its own declaration, this function verifies that *upstream* values a
    block assumes about (the producer's published Contract, or a project
    input) actually meet those assumptions.

    ``assumed_inputs`` entries whose values are *not* Quantities (raw tuples,
    numbers, strings — informational labels) are silently skipped. To
    participate in this check, an assumption must be expressed as a Quantity
    (typically :func:`framework.RangeQuantity`).

    The key in ``assumed_inputs`` must name a DAG node (or project input)
    present in ``results``. Missing keys are skipped lenient by default;
    pass ``strict=True`` to raise instead.
    """
    from framework.quantity import Quantity  # local: avoid cycle

    nodes = _collect_nodes(modules)
    mismatches: list[ContractMismatch] = []
    for name, info in nodes.items():
        if not info.is_contract:
            continue
        meta = get_contract_meta(info.fn)
        assert meta is not None
        for input_name, assumed_value in meta.assumed_inputs.items():
            if not isinstance(assumed_value, Quantity):
                continue  # informational only — not validatable
            if input_name not in results:
                if strict:
                    raise ValueError(
                        f"Contract {name!r} declares "
                        f"assumed_inputs[{input_name!r}], but {input_name!r} "
                        f"is not in results."
                    )
                continue
            actual = results[input_name]
            if not isinstance(actual, Quantity):
                if strict:
                    raise TypeError(
                        f"Contract {name!r} assumed_inputs[{input_name!r}]: "
                        f"actual is {type(actual).__name__}, expected Quantity."
                    )
                continue
            mismatches.extend(
                _compare_quantities(
                    contract_name=f"{name}.assumed[{input_name}]",
                    block=info.block,
                    actual=actual,
                    declared=assumed_value,
                    kind="assumed",
                )
            )
    return mismatches


def _compare_quantities(
    *,
    contract_name: str,
    block: str,
    actual: "Quantity",
    declared: "Quantity",
    kind: str = "declared",
) -> list[ContractMismatch]:
    """Per-axis comparison: every actual point must lie within declared's range."""
    from framework.quantity import Quantity, _as_range  # local import

    # Convert actual into declared's unit so comparisons are unit-correct.
    if actual.unit != declared.unit:
        actual = actual.to(declared.unit)

    mismatches: list[ContractMismatch] = []
    for scenario, mode, value in actual.iter_axes():
        try:
            d_value = _evaluate_at(declared, scenario=scenario, mode=mode)
        except KeyError as e:
            # Declared is missing this axis combination — that's an authoring
            # problem (the Contract didn't promise anything at this point).
            raise ValueError(
                f"Contract {contract_name!r}: actual carries "
                f"(scenario={scenario!r}, mode={mode!r}) but the Contract "
                f"doesn't {'assume' if kind == 'assumed' else 'declare'} a "
                f"bound there. {e}"
            ) from e
        a_lo, a_hi = _as_range(value)
        d_lo, d_hi = _as_range(d_value)
        if a_lo < d_lo or a_hi > d_hi:
            mismatches.append(
                ContractMismatch(
                    contract_name=contract_name,
                    block=block,
                    scenario=scenario,
                    mode=mode,
                    actual=value,
                    declared=d_value,
                    unit=str(declared.unit),
                    kind=kind,
                )
            )
    return mismatches


def _evaluate_at(
    q: "Quantity", *, scenario: str | None, mode: str | None
) -> "ScalarOrRange":
    """``Quantity.at`` but tolerant of missing axes on the *declared* side.

    The declared Contract may be mode-less even if the actual is mode-keyed
    (one bound covers all modes), and similarly scenario-less. This helper
    silently descends through whichever axes the declared carries.
    """
    if q.by_mode is not None:
        if mode is None:
            raise KeyError(
                f"declared Quantity is mode-keyed (modes={list(q.by_mode)}), "
                f"but actual has no mode axis"
            )
        if mode not in q.by_mode:
            raise KeyError(
                f"mode {mode!r} not in declared modes {list(q.by_mode)}"
            )
        return _evaluate_at(q.by_mode[mode], scenario=scenario, mode=None)
    if q.by_scenario is not None:
        if scenario is not None and scenario in q.by_scenario:
            return q.by_scenario[scenario]
        if INVARIANT in q.by_scenario:
            return q.by_scenario[INVARIANT]
        if scenario is None:
            # Only one entry and it isn't INVARIANT — accept it as the bound.
            if len(q.by_scenario) == 1:
                return next(iter(q.by_scenario.values()))
            raise KeyError(
                f"declared Quantity is scenario-keyed "
                f"(scenarios={list(q.by_scenario)}), but actual has no "
                f"scenario axis at this point"
            )
        raise KeyError(
            f"scenario {scenario!r} not in declared scenarios "
            f"{list(q.by_scenario)}"
        )
    assert q.value is not None
    return q.value


__all__ = [
    "ContractMeta",
    "ContractMismatch",
    "ContractViolation",
    "CycleViolation",
    "block_of_function",
    "check_contract_assumptions",
    "check_contract_consistency",
    "contract",
    "detect_cycles",
    "format_mismatches",
    "get_contract_meta",
    "is_contract",
    "raise_on_mismatches",
]
