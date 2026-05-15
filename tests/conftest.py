"""Test-suite-wide config: make `project`, `blocks`, `components` importable.

The example_analysis repo has no Poetry venv of its own — pytest runs against
the framework's `.venv`, which has the framework editable-installed. We just
need the project's `blocks/` / `project/` / sibling `components/` on sys.path.
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
    """Run the project DAG once per pytest session; share across tests."""
    from framework import Project
    from project.requirements import CAN_5V_RAIL
    from blocks.can_transceiver import leaves, analysis, contracts

    project = Project.load(
        scenarios=ROOT / "project" / "scenarios.toml",
        modes=ROOT / "project" / "modes.toml",
        cache_dir=None,
    )
    return project.run(
        modules=[leaves, analysis, contracts],
        targets=["power", "thermal_rise", "t_j", "t_j_max", "can_5v_draw", "i_supply"],
        inputs={"can_5v_rail": CAN_5V_RAIL},
    )
