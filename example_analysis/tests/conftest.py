"""Test-suite-wide config: make `project`, `blocks`, `components` importable.

The example_analysis repo has no Poetry venv of its own — pytest runs against
the framework's `.venv`, which has the framework editable-installed. We just
need the project's `blocks/` / `project/` / sibling `components/` on sys.path.

The ``project_results`` fixture runs the full three-block DAG once per
pytest session and shares the result dict across every verification test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Project root is this file's grandparent (tests/ -> example_analysis/).
ROOT = Path(__file__).resolve().parent.parent
COMPONENTS_PARENT = ROOT.parent  # so `components` package resolves

for p in (ROOT, COMPONENTS_PARENT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


@pytest.fixture(scope="session")
def project_results():
    """Run the project DAG once per pytest session; share across tests.

    Loads all three blocks (CAN transceiver, MCU, power supply) so the
    cross-block Contract dependencies (CAN + MCU consume rail_5v from
    the PSU; PSU sums the published can_5v_draw and mcu_5v_draw bounds)
    resolve correctly.

    ``return_all_computed=True`` returns the full DAG output rather than
    filtering to user-requested targets — the design-review report
    renderers and verification tests both need access to Contracts and
    their compares_to actuals.
    """
    from framework import Project
    from blocks.can_transceiver import (
        leaves as can_leaves,
        analysis as can_analysis,
        contracts as can_contracts,
    )
    from blocks.mcu import (
        leaves as mcu_leaves,
        analysis as mcu_analysis,
        contracts as mcu_contracts,
    )
    from blocks.power_supply import (
        leaves as psu_leaves,
        analysis as psu_analysis,
        contracts as psu_contracts,
    )

    project = Project.load(
        scenarios=ROOT / "project" / "scenarios.toml",
        modes=ROOT / "project" / "modes.toml",
        cache_dir=None,
    )
    return project.run(
        modules=[
            can_leaves, can_analysis, can_contracts,
            mcu_leaves, mcu_analysis, mcu_contracts,
            psu_leaves, psu_analysis, psu_contracts,
        ],
        targets=[
            # Per-block headline values
            "can_t_j", "can_t_j_max", "can_power", "can_5v_draw", "can_i_supply",
            "mcu_t_j", "mcu_t_j_max", "mcu_power", "mcu_5v_draw", "mcu_i_supply",
            "psu_t_j", "psu_t_j_max", "psu_power_dissipation", "rail_5v",
            "psu_v_out_actual", "psu_total_5v_load",
        ],
        return_all_computed=True,
    )
