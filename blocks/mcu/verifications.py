"""MCU block — verification tests (design doc 6.8 / step 9a).

Two checks:
1. Junction temperature stays below the block's derated max (90 °C).
2. Block's actual current draw stays within the published mcu_5v_draw
   contract bounds (mirrors step 8 but as a first-class verification test).
"""
from __future__ import annotations

from framework import (
    ScenarioMode,
    Severity,
    TestResult,
    VerificationContext,
    verification_test,
)


@verification_test(
    name="MCU: t_j stays below block-derated max",
    requirement="REQ-THM-010",
    severity=Severity.CRITICAL,
)
def test_mcu_t_j_below_derated_max(ctx: VerificationContext) -> TestResult:
    """Junction temperature must not exceed the MCU block's derated max.

    The block derates to 90 °C from the STM32G071 industrial absolute max
    of 105 °C — see :func:`blocks.mcu.leaves.mcu_t_j_max`.
    """
    t_j = ctx.quantity("mcu_t_j")
    t_j_max = ctx.quantity("mcu_t_j_max")
    return ctx.assert_quantity_below(
        t_j,
        t_j_max,
        evidence={"mcu_t_j": t_j, "mcu_t_j_max": t_j_max},
    )


@verification_test(
    name="MCU: i_supply stays within published mcu_5v_draw contract",
    requirement="REQ-PWR-007",
    severity=Severity.CRITICAL,
)
def test_mcu_i_supply_within_contract(ctx: VerificationContext) -> TestResult:
    """Block's actual draw must lie within its declared per-mode bounds."""
    i_supply = ctx.quantity("mcu_i_supply")
    declared = ctx.quantity("mcu_5v_draw")
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
        name="MCU: i_supply stays within published mcu_5v_draw contract",
        passed=not failed,
        severity=Severity.CRITICAL,
        failed_at=tuple(failed),
        evidence={"mcu_i_supply": i_supply, "mcu_5v_draw": declared},
    )
