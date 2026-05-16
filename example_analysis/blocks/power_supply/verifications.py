"""Power supply block — verification tests (design doc 6.8 / step 9a).

Two checks:
1. LDO junction temperature stays below the block's derated max (125 °C).
   This is the headline thermal check — the linear-regulator dissipation
   at hot_high_vin + diagnostic mode is where the design margin gets
   tight (V_drop × I_total × R_θJA blows past the limit if any of the
   three factors are at worst case).
2. LDO output (psu_v_out_actual) stays within the published rail_5v
   envelope — a sanity check on the contract consistency for the LDO
   block itself.
"""
from __future__ import annotations

from framework import (
    Severity,
    TestResult,
    VerificationContext,
    verification_test,
)


@verification_test(
    name="PSU: LDO t_j stays below block-derated max",
    requirement="REQ-THM-011",
    severity=Severity.CRITICAL,
)
def test_psu_t_j_below_derated_max(ctx: VerificationContext) -> TestResult:
    """LDO junction temperature must not exceed 125 °C in any scenario/mode.

    Worst case for a linear regulator is hot ambient + high V_in + heavy
    load: hot_high_vin scenario (V_in=16V, ambient=85°C) and diagnostic
    mode (peak downstream draw). This verification surfaces that.
    """
    t_j = ctx.quantity("psu_t_j")
    t_j_max = ctx.quantity("psu_t_j_max")
    return ctx.assert_quantity_below(
        t_j,
        t_j_max,
        evidence={"psu_t_j": t_j, "psu_t_j_max": t_j_max},
    )


@verification_test(
    name="PSU: LDO actual output within published rail_5v envelope",
    requirement="REQ-PWR-005",
    severity=Severity.CRITICAL,
)
def test_psu_actual_within_rail_contract(ctx: VerificationContext) -> TestResult:
    """LDO's actual output envelope must lie within REQ-PWR-005's envelope.

    Mirrors the run-time consistency check (step 8); expressed as a
    verification test so it lands in the same CI / report surface as the
    rest of the block's checks. Uses the project requirement directly
    rather than walking the Contract's Quantity — same numbers, simpler
    call.
    """
    from project.requirements import RAIL_5V

    actual = ctx.quantity("psu_v_out_actual")
    declared = ctx.quantity("rail_5v")
    return ctx.assert_quantity_in(
        actual,
        RAIL_5V.min,
        RAIL_5V.max,
        evidence={"psu_v_out_actual": actual, "rail_5v": declared},
    )
