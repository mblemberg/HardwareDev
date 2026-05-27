"""Output channels for TestResult collections (step 9c / design doc 6.8)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from framework import (
    ScenarioMode,
    Severity,
    TestResult,
    results_to_html_table,
    results_to_jama_records,
    results_to_markdown_table,
    results_to_pr_comment,
)


# Shared fixtures: a representative results dict
def _sample_results() -> dict[str, TestResult]:
    return {
        "thermal": TestResult(
            name="thermal",
            passed=False,
            severity=Severity.CRITICAL,
            failed_at=(ScenarioMode(scenario="hot_high_vin", mode="diagnostic"),),
            requirement="REQ-ENV-001",
            block="can_transceiver",
            evidence={"t_j": "<Quantity>", "t_j_max": "<Quantity>"},
        ),
        "supply": TestResult(
            name="supply",
            passed=True,
            severity=Severity.CRITICAL,
            requirement="REQ-PWR-005",
            block="can_transceiver",
        ),
        "info_only": TestResult(
            name="info_only",
            passed=False,
            severity=Severity.INFO,
            failed_at=(ScenarioMode(mode="active"),),
            block="can_transceiver",
        ),
    }


# ---------------------------------------------------------------------------
# Markdown table
# ---------------------------------------------------------------------------


class TestMarkdownTable:
    def test_empty(self) -> None:
        assert "no verification tests" in results_to_markdown_table({})

    def test_has_header_and_rows(self) -> None:
        out = results_to_markdown_table(_sample_results())
        assert "| Verdict | Severity | Test | Failed at |" in out
        assert "| ---" in out or "|---" in out
        # All three tests appear
        assert "thermal" in out
        assert "supply" in out
        assert "info_only" in out

    def test_failures_first(self) -> None:
        out = results_to_markdown_table(_sample_results())
        lines = out.splitlines()
        # First data row is the CRITICAL failure
        first_data = lines[2]
        assert "FAIL" in first_data
        assert "thermal" in first_data

    def test_passes_at_end(self) -> None:
        out = results_to_markdown_table(_sample_results())
        lines = out.splitlines()
        # Last data row is the PASS
        assert "supply" in lines[-1]
        assert "PASS" in lines[-1]


# ---------------------------------------------------------------------------
# HTML table
# ---------------------------------------------------------------------------


class TestHtmlTable:
    def test_empty(self) -> None:
        assert "no verification tests" in results_to_html_table({})

    def test_class_styling_per_row(self) -> None:
        out = results_to_html_table(_sample_results())
        assert "vt-fail" in out
        assert "vt-pass" in out
        assert "vt-info" in out

    def test_escapes_html(self) -> None:
        bad = {
            "x": TestResult(
                name="<script>alert(1)</script>",
                passed=False,
                severity=Severity.CRITICAL,
            ),
        }
        out = results_to_html_table(bad)
        assert "<script>" not in out  # raw tag must not appear
        assert "&lt;script&gt;" in out


# ---------------------------------------------------------------------------
# PR comment
# ---------------------------------------------------------------------------


class TestPrComment:
    def test_includes_counts(self) -> None:
        out = results_to_pr_comment(_sample_results())
        assert "1 pass" in out
        assert "1 fail" in out
        assert "1 info" in out

    def test_collapsibles_per_failure(self) -> None:
        out = results_to_pr_comment(_sample_results())
        # Two failures (CRITICAL + INFO), so two <details> blocks.
        assert out.count("<details>") == 2
        assert out.count("</details>") == 2

    def test_includes_failing_corners(self) -> None:
        out = results_to_pr_comment(_sample_results())
        assert "hot_high_vin" in out
        assert "diagnostic" in out

    def test_evidence_keys_listed(self) -> None:
        out = results_to_pr_comment(_sample_results())
        assert "`t_j`" in out
        assert "`t_j_max`" in out

    def test_all_pass_short_summary(self) -> None:
        only_pass = {"a": TestResult(name="a", passed=True)}
        out = results_to_pr_comment(only_pass)
        assert "All verification tests passed" in out
        assert "<details>" not in out


# ---------------------------------------------------------------------------
# Jama records
# ---------------------------------------------------------------------------


class TestJamaRecords:
    def test_round_trips_through_json(self) -> None:
        fixed = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
        records = results_to_jama_records(_sample_results(), now=fixed)
        # Must serialize cleanly.
        s = json.dumps(records)
        assert "thermal" in s

    def test_status_field_maps_severity(self) -> None:
        fixed = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
        records = results_to_jama_records(_sample_results(), now=fixed)
        by_name = {r["name"]: r for r in records}
        assert by_name["thermal"]["status"] == "fail"
        assert by_name["supply"]["status"] == "pass"
        assert by_name["info_only"]["status"] == "info"

    def test_carries_requirement_and_block(self) -> None:
        records = results_to_jama_records(_sample_results())
        by_name = {r["name"]: r for r in records}
        assert by_name["thermal"]["requirement"] == "REQ-ENV-001"
        assert by_name["thermal"]["block"] == "can_transceiver"

    def test_failed_at_serializes(self) -> None:
        records = results_to_jama_records(_sample_results())
        by_name = {r["name"]: r for r in records}
        assert by_name["thermal"]["failed_at"] == [
            {"scenario": "hot_high_vin", "mode": "diagnostic"},
        ]

    def test_evidence_keys_exposed(self) -> None:
        records = results_to_jama_records(_sample_results())
        by_name = {r["name"]: r for r in records}
        assert sorted(by_name["thermal"]["evidence_keys"]) == ["t_j", "t_j_max"]

    def test_deterministic_timestamp(self) -> None:
        fixed = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
        records = results_to_jama_records({"a": TestResult(name="a", passed=True)}, now=fixed)
        assert records[0]["executed_at"] == "2026-05-15T12:00:00+00:00"
