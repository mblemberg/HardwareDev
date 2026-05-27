"""Truth tables for combinational logic blocks (feature request 2026-05-15).

Where the rest of the framework reasons about analog quantities under
worst-case corner math, logic blocks (gates, decoders, level-shifters,
encoders) need a different primitive: boolean inputs → boolean outputs,
enumerated exhaustively.

A :class:`TruthTable` captures one combinational logic spec as an ordered
list of named inputs, named outputs, and rows (each row is one full
input-output combination, in input-then-output order). The table is
immutable, hashable, and cache-friendly.

Two ways to build a table:
    1. :class:`TruthTable` constructor with an explicit rows list — useful
       for datasheets / hand-derived specs.
    2. :meth:`TruthTable.from_function` — enumerate every 2^n input
       combination and call a user function for each. Useful for capturing
       what a netlist *actually* implements (so it can be compared against
       the spec).

Compare two tables with :func:`compare_truth_tables` (returns a list of
:class:`TruthTableMismatch` records, one per row where actual diverges
from expected). The :class:`framework.VerificationContext` exposes a
:meth:`assert_truth_table_matches` helper that wraps this into a
:class:`framework.TestResult` for use inside ``@verification_test``.

Out of scope for v1:
- Sequential logic (latches, flip-flops, state machines). Captured as a
  follow-on; a ``StateMachine`` type with prior-state inputs and a
  reachability check is the natural extension.
- Don't-care (``X``) entries. v1 requires concrete 0/1 in every cell.
- Tri-state / high-Z outputs. v1 is two-valued boolean.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product


def _coerce_bool(v: object) -> bool:
    """Accept 0/1/True/False; reject anything else with a clear message."""
    if v is True or v == 1:
        return True
    if v is False or v == 0:
        return False
    raise TypeError(
        f"truth-table cell must be 0, 1, True, or False; got {v!r} "
        f"({type(v).__name__})"
    )


@dataclass(frozen=True)
class TruthTable:
    """An immutable combinational-logic specification.

    Fields:
        inputs:  ordered tuple of input signal names (left-to-right in rows).
        outputs: ordered tuple of output signal names (after the inputs).
        rows:    tuple of (input_values, output_values) pairs. Each
                 ``input_values`` matches ``inputs`` in order; each
                 ``output_values`` matches ``outputs`` in order. All cells
                 are ``bool``.

    Construct via :meth:`from_rows` (the natural user-facing API — accepts
    a list of flat tuples or a list of per-row dicts) or :meth:`from_function`
    (enumerates all 2^n input combinations).
    """

    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    rows: tuple[tuple[tuple[bool, ...], tuple[bool, ...]], ...] = field(default_factory=tuple)

    # ----- construction -----------------------------------------------------

    def __post_init__(self) -> None:
        if not self.inputs:
            raise ValueError("TruthTable requires at least one input")
        if not self.outputs:
            raise ValueError("TruthTable requires at least one output")
        if len(set(self.inputs)) != len(self.inputs):
            raise ValueError(f"duplicate input names in {self.inputs}")
        if len(set(self.outputs)) != len(self.outputs):
            raise ValueError(f"duplicate output names in {self.outputs}")
        overlap = set(self.inputs) & set(self.outputs)
        if overlap:
            raise ValueError(
                f"input and output names overlap: {sorted(overlap)}"
            )
        # Validate every row has the right shape and inputs are unique across rows.
        seen_inputs: set[tuple[bool, ...]] = set()
        for ins, outs in self.rows:
            if len(ins) != len(self.inputs):
                raise ValueError(
                    f"row inputs {ins!r} length != len(inputs)={len(self.inputs)}"
                )
            if len(outs) != len(self.outputs):
                raise ValueError(
                    f"row outputs {outs!r} length != len(outputs)={len(self.outputs)}"
                )
            if ins in seen_inputs:
                raise ValueError(
                    f"duplicate input combination {ins!r} in TruthTable rows"
                )
            seen_inputs.add(ins)

    @classmethod
    def from_rows(
        cls,
        *,
        inputs: Sequence[str],
        outputs: Sequence[str],
        rows: Sequence[Sequence[object] | Mapping[str, object]],
    ) -> TruthTable:
        """Build from a sequence of flat tuples or dicts.

        Flat-tuple form: each row has ``len(inputs) + len(outputs)`` cells, in
        input-then-output order.
            from_rows(inputs=["A","B"], outputs=["Y"], rows=[(0,0,0), (0,1,1), ...])

        Dict form: each row is a ``{signal_name: value}`` mapping covering
        every input and output.
            from_rows(inputs=["A","B"], outputs=["Y"], rows=[{"A":0,"B":0,"Y":0}, ...])
        """
        ins_t = tuple(inputs)
        outs_t = tuple(outputs)
        built: list[tuple[tuple[bool, ...], tuple[bool, ...]]] = []
        for row in rows:
            if isinstance(row, Mapping):
                in_vals = tuple(_coerce_bool(row[k]) for k in ins_t)
                out_vals = tuple(_coerce_bool(row[k]) for k in outs_t)
            else:
                flat = list(row)
                if len(flat) != len(ins_t) + len(outs_t):
                    raise ValueError(
                        f"row {flat!r} has {len(flat)} cells; expected "
                        f"{len(ins_t) + len(outs_t)} (inputs + outputs)"
                    )
                in_vals = tuple(_coerce_bool(v) for v in flat[: len(ins_t)])
                out_vals = tuple(_coerce_bool(v) for v in flat[len(ins_t) :])
            built.append((in_vals, out_vals))
        return cls(inputs=ins_t, outputs=outs_t, rows=tuple(built))

    @classmethod
    def from_function(
        cls,
        *,
        inputs: Sequence[str],
        outputs: Sequence[str],
        fn: Callable[..., Mapping[str, object] | object],
    ) -> TruthTable:
        """Enumerate all 2^n input combinations and call ``fn`` for each.

        ``fn`` receives input values as keyword args (one per name in ``inputs``)
        and must return either a mapping ``{output_name: bool}`` (for multi-
        output tables) or a single bool (for single-output tables).
        """
        ins_t = tuple(inputs)
        outs_t = tuple(outputs)
        built: list[tuple[tuple[bool, ...], tuple[bool, ...]]] = []
        for combo in product((False, True), repeat=len(ins_t)):
            kwargs = dict(zip(ins_t, combo, strict=False))
            result = fn(**kwargs)
            if isinstance(result, Mapping):
                out_vals = tuple(_coerce_bool(result[k]) for k in outs_t)
            else:
                if len(outs_t) != 1:
                    raise TypeError(
                        f"function returned a single value but the table has "
                        f"{len(outs_t)} outputs; return a mapping instead"
                    )
                out_vals = (_coerce_bool(result),)
            built.append((combo, out_vals))
        return cls(inputs=ins_t, outputs=outs_t, rows=tuple(built))

    # ----- access / introspection ------------------------------------------

    def evaluate(self, **input_values: object) -> dict[str, bool]:
        """Return the output values for a specific input combination.

        Raises KeyError if the combination isn't in the table.
        """
        key = tuple(_coerce_bool(input_values[name]) for name in self.inputs)
        for ins, outs in self.rows:
            if ins == key:
                return dict(zip(self.outputs, outs, strict=False))
        raise KeyError(f"input combination {dict(zip(self.inputs, key, strict=False))!r} not in table")

    def iter_rows(self) -> Iterator[tuple[dict[str, bool], dict[str, bool]]]:
        """Yield ``(inputs_dict, outputs_dict)`` for each row."""
        for ins, outs in self.rows:
            yield dict(zip(self.inputs, ins, strict=False)), dict(zip(self.outputs, outs, strict=False))

    def is_complete(self) -> bool:
        """True iff the table covers all 2**n input combinations."""
        return len(self.rows) == 2 ** len(self.inputs)

    def format(self) -> str:
        """Pretty-print as a markdown table for diagnostics / reports."""
        header = "| " + " | ".join((*self.inputs, *self.outputs)) + " |"
        sep = "|" + "|".join(["---"] * (len(self.inputs) + len(self.outputs))) + "|"
        body = []
        for ins, outs in self.rows:
            cells = [("1" if v else "0") for v in (*ins, *outs)]
            body.append("| " + " | ".join(cells) + " |")
        return "\n".join([header, sep, *body])


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TruthTableMismatch:
    """One row where actual differs from expected.

    ``inputs`` is the row's input combination (as a name→bool dict).
    ``expected`` and ``actual`` are the corresponding output dicts. If actual
    is missing the row entirely, ``actual`` is ``None``.
    """

    inputs: dict[str, bool]
    expected: dict[str, bool]
    actual: dict[str, bool] | None


def compare_truth_tables(
    actual: TruthTable,
    expected: TruthTable,
) -> list[TruthTableMismatch]:
    """Row-by-row comparison. Returns ``[]`` iff every row matches.

    Both tables must declare the same inputs (same names, same order) and the
    same outputs (same names, same order). Differing schemas raise ``ValueError``
    — that's an authoring problem, not a data-level mismatch.
    """
    if actual.inputs != expected.inputs:
        raise ValueError(
            f"input schemas differ: actual={actual.inputs} vs "
            f"expected={expected.inputs}"
        )
    if actual.outputs != expected.outputs:
        raise ValueError(
            f"output schemas differ: actual={actual.outputs} vs "
            f"expected={expected.outputs}"
        )

    expected_lookup = {ins: outs for ins, outs in expected.rows}
    actual_lookup = {ins: outs for ins, outs in actual.rows}

    mismatches: list[TruthTableMismatch] = []
    # Walk expected first so we catch rows actual is missing.
    for ins, exp_outs in expected.rows:
        inputs_dict = dict(zip(expected.inputs, ins, strict=False))
        exp_dict = dict(zip(expected.outputs, exp_outs, strict=False))
        if ins not in actual_lookup:
            mismatches.append(
                TruthTableMismatch(inputs=inputs_dict, expected=exp_dict, actual=None)
            )
            continue
        act_outs = actual_lookup[ins]
        if act_outs != exp_outs:
            act_dict = dict(zip(actual.outputs, act_outs, strict=False))
            mismatches.append(
                TruthTableMismatch(inputs=inputs_dict, expected=exp_dict, actual=act_dict)
            )
    # Also flag rows actual has but expected doesn't — table-wide surprise.
    for ins, act_outs in actual.rows:
        if ins not in expected_lookup:
            inputs_dict = dict(zip(actual.inputs, ins, strict=False))
            act_dict = dict(zip(actual.outputs, act_outs, strict=False))
            mismatches.append(
                TruthTableMismatch(inputs=inputs_dict, expected={}, actual=act_dict)
            )
    return mismatches


__all__ = [
    "TruthTable",
    "TruthTableMismatch",
    "compare_truth_tables",
]
