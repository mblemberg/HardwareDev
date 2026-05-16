"""Verification: actual decoder matches its spec exhaustively."""
from __future__ import annotations

from framework import TestResult, VerificationContext, verification_test


@verification_test(
    name="2-to-4 decoder truth table matches spec",
    requirement="REQ-LOGIC-001",
)
def test_decoder(ctx: VerificationContext) -> TestResult:
    return ctx.assert_truth_table_matches(
        ctx.truth_table("decoder_actual"),
        ctx.truth_table("decoder_spec"),
    )
