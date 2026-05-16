"""Truth tables for combinational logic blocks (feature request 2026-05-15)."""
from __future__ import annotations

import pytest

from framework import (
    ScenarioMode,
    Severity,
    TestResult,
    TruthTable,
    TruthTableMismatch,
    VerificationContext,
    compare_truth_tables,
    verification_test,
)
from framework.verification import VerificationMeta


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_from_rows_flat_tuples(self) -> None:
        t = TruthTable.from_rows(
            inputs=["A", "B"], outputs=["Y"],
            rows=[(0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 1)],
        )
        assert t.inputs == ("A", "B")
        assert t.outputs == ("Y",)
        assert len(t.rows) == 4
        assert t.is_complete()

    def test_from_rows_dict_form(self) -> None:
        t = TruthTable.from_rows(
            inputs=["A", "B"], outputs=["Y"],
            rows=[
                {"A": 0, "B": 0, "Y": 0},
                {"A": 0, "B": 1, "Y": 1},
                {"A": 1, "B": 0, "Y": 1},
                {"A": 1, "B": 1, "Y": 1},
            ],
        )
        assert t.evaluate(A=True, B=False) == {"Y": True}

    def test_from_function_or_gate(self) -> None:
        t = TruthTable.from_function(
            inputs=["A", "B"], outputs=["Y"],
            fn=lambda A, B: A or B,
        )
        assert t.is_complete()
        assert t.evaluate(A=False, B=False) == {"Y": False}
        assert t.evaluate(A=True, B=False) == {"Y": True}

    def test_from_function_multi_output(self) -> None:
        # 2-input half adder: SUM = A XOR B, CARRY = A AND B
        t = TruthTable.from_function(
            inputs=["A", "B"], outputs=["S", "C"],
            fn=lambda A, B: {"S": A ^ B, "C": A and B},
        )
        assert t.evaluate(A=True, B=True) == {"S": False, "C": True}
        assert t.evaluate(A=True, B=False) == {"S": True, "C": False}

    def test_no_inputs_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one input"):
            TruthTable(inputs=(), outputs=("Y",), rows=())

    def test_duplicate_input_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate input names"):
            TruthTable(inputs=("A", "A"), outputs=("Y",), rows=())

    def test_input_output_overlap_rejected(self) -> None:
        with pytest.raises(ValueError, match="overlap"):
            TruthTable(inputs=("A",), outputs=("A",), rows=())

    def test_row_wrong_width_rejected(self) -> None:
        with pytest.raises(ValueError, match="cells"):
            TruthTable.from_rows(
                inputs=["A", "B"], outputs=["Y"],
                rows=[(0, 0)],  # missing output cell
            )

    def test_duplicate_input_combo_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate input combination"):
            TruthTable.from_rows(
                inputs=["A"], outputs=["Y"],
                rows=[(0, 0), (0, 1)],  # both A=0
            )

    def test_invalid_cell_value_rejected(self) -> None:
        with pytest.raises(TypeError, match="must be 0, 1"):
            TruthTable.from_rows(
                inputs=["A"], outputs=["Y"],
                rows=[("hi", 0)],
            )

    def test_function_single_value_with_multi_output_rejected(self) -> None:
        with pytest.raises(TypeError, match="return a mapping"):
            TruthTable.from_function(
                inputs=["A"], outputs=["X", "Y"],
                fn=lambda A: True,
            )


# ---------------------------------------------------------------------------
# Access / introspection
# ---------------------------------------------------------------------------


class TestAccess:
    def test_evaluate_missing_combo_raises(self) -> None:
        t = TruthTable.from_rows(
            inputs=["A"], outputs=["Y"], rows=[(0, 0)],  # only A=0 row
        )
        with pytest.raises(KeyError, match="not in table"):
            t.evaluate(A=True)

    def test_iter_rows(self) -> None:
        t = TruthTable.from_rows(
            inputs=["A"], outputs=["Y"], rows=[(0, 0), (1, 1)],
        )
        rows = list(t.iter_rows())
        assert rows == [
            ({"A": False}, {"Y": False}),
            ({"A": True},  {"Y": True}),
        ]

    def test_format_renders_markdown(self) -> None:
        t = TruthTable.from_rows(
            inputs=["A"], outputs=["Y"], rows=[(0, 0), (1, 1)],
        )
        out = t.format()
        assert "| A | Y |" in out
        assert "| 0 | 0 |" in out
        assert "| 1 | 1 |" in out

    def test_immutability_via_frozen_dataclass(self) -> None:
        t = TruthTable.from_rows(
            inputs=["A"], outputs=["Y"], rows=[(0, 0)],
        )
        with pytest.raises((AttributeError, TypeError)):
            t.inputs = ("B",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


class TestComparison:
    def _or_spec(self) -> TruthTable:
        return TruthTable.from_function(
            inputs=["A", "B"], outputs=["Y"],
            fn=lambda A, B: A or B,
        )

    def test_identical_no_mismatch(self) -> None:
        a = self._or_spec()
        b = self._or_spec()
        assert compare_truth_tables(a, b) == []

    def test_one_row_diverges(self) -> None:
        spec = self._or_spec()
        # Buggy implementation: A=1, B=0 returns 0 instead of 1
        buggy = TruthTable.from_rows(
            inputs=["A", "B"], outputs=["Y"],
            rows=[(0, 0, 0), (0, 1, 1), (1, 0, 0), (1, 1, 1)],
        )
        mismatches = compare_truth_tables(buggy, spec)
        assert len(mismatches) == 1
        m = mismatches[0]
        assert m.inputs == {"A": True, "B": False}
        assert m.expected == {"Y": True}
        assert m.actual == {"Y": False}

    def test_missing_row_in_actual(self) -> None:
        spec = self._or_spec()
        partial = TruthTable.from_rows(
            inputs=["A", "B"], outputs=["Y"],
            rows=[(0, 0, 0), (0, 1, 1), (1, 0, 1)],  # missing (1, 1)
        )
        mismatches = compare_truth_tables(partial, spec)
        assert len(mismatches) == 1
        assert mismatches[0].inputs == {"A": True, "B": True}
        assert mismatches[0].actual is None

    def test_extra_row_in_actual_flagged(self) -> None:
        spec = TruthTable.from_rows(
            inputs=["A"], outputs=["Y"], rows=[(0, 0)],  # only A=0
        )
        extra = TruthTable.from_rows(
            inputs=["A"], outputs=["Y"], rows=[(0, 0), (1, 1)],
        )
        mismatches = compare_truth_tables(extra, spec)
        # The extra (A=1) row triggers a mismatch with expected={}
        extras = [m for m in mismatches if m.expected == {}]
        assert len(extras) == 1
        assert extras[0].inputs == {"A": True}

    def test_different_input_schema_raises(self) -> None:
        a = TruthTable.from_rows(inputs=["A"], outputs=["Y"], rows=[(0, 0), (1, 1)])
        b = TruthTable.from_rows(inputs=["X"], outputs=["Y"], rows=[(0, 0), (1, 1)])
        with pytest.raises(ValueError, match="input schemas"):
            compare_truth_tables(a, b)

    def test_different_output_schema_raises(self) -> None:
        a = TruthTable.from_rows(inputs=["A"], outputs=["Y"], rows=[(0, 0), (1, 1)])
        b = TruthTable.from_rows(inputs=["A"], outputs=["Z"], rows=[(0, 0), (1, 1)])
        with pytest.raises(ValueError, match="output schemas"):
            compare_truth_tables(a, b)


# ---------------------------------------------------------------------------
# VerificationContext.assert_truth_table_matches
# ---------------------------------------------------------------------------


class TestVerificationContext:
    def _ctx(self) -> VerificationContext:
        meta = VerificationMeta(name="logic test", severity=Severity.CRITICAL, block="logic_block")
        return VerificationContext({}, meta=meta)

    def _or_spec(self) -> TruthTable:
        return TruthTable.from_function(
            inputs=["A", "B"], outputs=["Y"], fn=lambda A, B: A or B,
        )

    def test_matching_tables_pass(self) -> None:
        actual = self._or_spec()
        expected = self._or_spec()
        r = self._ctx().assert_truth_table_matches(actual, expected)
        assert r.passed
        assert r.failed_at == ()

    def test_mismatch_records_failed_combos(self) -> None:
        actual = TruthTable.from_rows(
            inputs=["A", "B"], outputs=["Y"],
            rows=[(0, 0, 0), (0, 1, 1), (1, 0, 0), (1, 1, 1)],
        )
        expected = self._or_spec()
        r = self._ctx().assert_truth_table_matches(actual, expected)
        assert not r.passed
        assert len(r.failed_at) == 1
        # The label encodes the offending input combo
        assert "A=1" in r.failed_at[0].scenario
        assert "B=0" in r.failed_at[0].scenario

    def test_evidence_carries_both_tables(self) -> None:
        a = self._or_spec()
        e = self._or_spec()
        r = self._ctx().assert_truth_table_matches(a, e)
        assert r.evidence["actual_table"] is a
        assert r.evidence["expected_table"] is e

    def test_ctx_truth_table_fetch(self) -> None:
        t = self._or_spec()
        ctx = VerificationContext({"my_table": t})
        assert ctx.truth_table("my_table") is t

    def test_ctx_truth_table_wrong_type(self) -> None:
        ctx = VerificationContext({"x": "not a table"})
        with pytest.raises(TypeError, match="expected TruthTable"):
            ctx.truth_table("x")


# ---------------------------------------------------------------------------
# End-to-end through Project.run + run_verifications
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """The logic_block fixture wires a decoder spec + actual + verification."""

    def _project(self):
        from framework import Project
        from framework.modes import ModeSet
        from framework.scenarios import ScenarioSet
        return Project(scenarios=ScenarioSet(scenarios=[]), modes=ModeSet(modes=[]), cache_dir=None)

    def test_decoder_verification_passes(self) -> None:
        from framework import run_verifications
        from logic_block import leaves, verifications

        results = self._project().run(
            modules=[leaves],
            targets=["decoder_spec", "decoder_actual"],
        )
        test_results = run_verifications([verifications], results)
        assert "2-to-4 decoder truth table matches spec" in test_results
        assert test_results["2-to-4 decoder truth table matches spec"].passed
