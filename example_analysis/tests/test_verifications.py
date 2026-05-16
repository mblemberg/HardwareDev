"""pytest-driven verification tests (design doc 6.8 / step 9b).

Each ``@verification_test`` in a block's ``verifications.py`` becomes its own
parametrized pytest item here, so CI fails per-test (precise diagnostics)
rather than per-suite. ``run_verification_for_pytest`` maps test severity:
``CRITICAL`` → ``pytest.fail``; ``WARNING`` → ``pytest.xfail``; ``INFO`` →
``pytest.skip``.

The ``project_results`` fixture (in ``conftest.py``) builds and runs the
project DAG once per session and shares the result dict across every
verification test below.
"""
from __future__ import annotations

import pytest

from framework import collect_verification_tests, run_verification_for_pytest


def _all_block_verifications():
    """Every @verification_test in every block's verifications.py.

    Extend this when you add a new block — see CLAUDE.md "How a new block lands".
    """
    from blocks.can_transceiver import verifications as can_transceiver_v
    from blocks.mcu import verifications as mcu_v
    from blocks.power_supply import verifications as psu_v

    return collect_verification_tests([can_transceiver_v, mcu_v, psu_v])


VERIFICATION_TESTS = _all_block_verifications()


@pytest.mark.parametrize(
    "test_fn",
    VERIFICATION_TESTS,
    ids=[t.__verification_meta__.name for t in VERIFICATION_TESTS],  # type: ignore[attr-defined]
)
def test_verification(test_fn, project_results):
    run_verification_for_pytest(test_fn, project_results)
