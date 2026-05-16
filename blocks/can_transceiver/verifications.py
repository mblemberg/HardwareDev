"""CAN transceiver — verification tests (design doc 6.8 / step 9a).

Each ``@verification_test`` is the formal expression of a requirement check.
The framework's runner (:func:`framework.run_verifications`) discovers them
by module scan and dispatches results to the relevant output channel.

All node references are block-prefixed (``can_t_j``, ``can_i_supply``) to
match the renamed CAN-block surface in the three-block system DAG.
"""
from __future__ import annotations

from framework import (
    Quantity,
    ScenarioMode,
    Severity,
    TestResult,
    VerificationContext,
    verification_test,
)


@verification_test(
    name="CAN: t_j stays below block-derated max",
    requirement="REQ-ENV-001",
    severity=Severity.CRITICAL,
)
def test_can_t_j_below_derated_max(ctx: VerificationContext) -> TestResult:
    """Junction temperature must not exceed 125 °C in any scenario/mode.

    The block derates 25 °C below the TJA1051T/3 datasheet absolute max
    of 150 °C — see :func:`blocks.can_transceiver.leaves.can_t_j_max`.
    """
    t_j = ctx.quantity("can_t_j")
    t_j_max = ctx.quantity("can_t_j_max")
    return ctx.assert_quantity_below(
        t_j,
        t_j_max,
        evidence={"can_t_j": t_j, "can_t_j_max": t_j_max},
    )


@verification_test(
    name="CAN: i_supply stays within published can_5v_draw contract",
    requirement="REQ-PWR-005",
    severity=Severity.CRITICAL,
)
def test_can_i_supply_within_contract(ctx: VerificationContext) -> TestResult:
    """Block's actual draw must lie within its declared per-mode bounds.

    Mirrors step-8's run-time consistency check, but expressed as a
    proper verification test so it lands in the same CI / report surface
    as the rest of the block's checks.
    """
    i_supply = ctx.quantity("can_i_supply")
    declared = ctx.quantity("can_5v_draw")
    # The declared bound is mode-keyed; iterate over the actual's axes and
    # compare against the matching declared mode.
    from framework.contract import _evaluate_at
    from framework.quantity import _as_range
    failed = []
    for scenario, mode, value in i_supply.iter_axes():
        d_value = _evaluate_at(declared, scenario=scenario, mode=mode)
        a_lo, a_hi = _as_range(value)
        d_lo, d_hi = _as_range(d_value)
        if a_lo < d_lo or a_hi > d_hi:
            failed.append(ScenarioMode(scenario=scenario, mode=mode))
    return TestResult(
        name="CAN: i_supply stays within published can_5v_draw contract",
        passed=not failed,
        severity=Severity.CRITICAL,
        failed_at=tuple(failed),
        evidence={"can_i_supply": i_supply, "can_5v_draw": declared},
    )
