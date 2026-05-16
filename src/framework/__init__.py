"""Hardware analysis framework — public API surface.

Curated re-exports per design doc section 11 (framework.__all__).
"""

__version__ = "0.0.1"
from framework import analyses, requirements, units
from framework._toml import TomlError
from framework.component import Component, coerce_field_quantity
from framework.contract import (
    ContractMeta,
    ContractMismatch,
    ContractViolation,
    CycleViolation,
    check_contract_assumptions,
    check_contract_consistency,
    contract,
    detect_cycles,
    get_contract_meta,
    is_contract,
)
from framework.modes import Mode, ModeSet, load_modes
from framework.project import Project
from framework.provenance import (
    ProvenanceGraph,
    ProvenanceNodeInfo,
    ProvenanceRef,
)
from framework.logic import TruthTable, TruthTableMismatch, compare_truth_tables
from framework.quantity import Constant, Quantity, RangeQuantity
from framework.reports import (
    block_report_html,
    display_block_report,
    display_project_report,
    display_quantity,
    project_report_html,
    quantity_to_html,
    quantity_to_markdown,
    results_to_html_table,
    results_to_jama_records,
    results_to_markdown_table,
    results_to_pr_comment,
)
from framework.requirements import (
    CurrentBudget,
    Performance,
    Requirement,
    SupplyEnvelope,
    TempRange,
)
from framework.scenarios import Scenario, ScenarioSet, load_scenarios
from framework.verification import (
    ScenarioMode,
    Severity,
    TestResult,
    VerificationContext,
    VerificationMeta,
    collect_verification_tests,
    format_results,
    get_verification_meta,
    is_verification_test,
    run_verification_for_pytest,
    run_verifications,
    verification_test,
)

__all__ = [
    "Component",
    "Constant",
    "ContractMeta",
    "ContractMismatch",
    "ContractViolation",
    "CurrentBudget",
    "CycleViolation",
    "Mode",
    "ModeSet",
    "Performance",
    "Project",
    "ProvenanceGraph",
    "ProvenanceNodeInfo",
    "ProvenanceRef",
    "Quantity",
    "RangeQuantity",
    "Requirement",
    "Scenario",
    "ScenarioMode",
    "ScenarioSet",
    "Severity",
    "SupplyEnvelope",
    "TempRange",
    "TestResult",
    "TomlError",
    "TruthTable",
    "TruthTableMismatch",
    "VerificationContext",
    "VerificationMeta",
    "analyses",
    "block_report_html",
    "check_contract_assumptions",
    "check_contract_consistency",
    "coerce_field_quantity",
    "collect_verification_tests",
    "compare_truth_tables",
    "contract",
    "detect_cycles",
    "display_block_report",
    "display_project_report",
    "display_quantity",
    "format_results",
    "get_contract_meta",
    "get_verification_meta",
    "is_contract",
    "is_verification_test",
    "load_modes",
    "load_scenarios",
    "project_report_html",
    "quantity_to_html",
    "quantity_to_markdown",
    "requirements",
    "results_to_html_table",
    "results_to_jama_records",
    "results_to_markdown_table",
    "results_to_pr_comment",
    "run_verification_for_pytest",
    "run_verifications",
    "units",
    "verification_test",
]
