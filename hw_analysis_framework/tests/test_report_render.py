"""Design-review report renderers (design doc §12 / step 12)."""
from __future__ import annotations

import pytest

from framework import (
    Constant,
    Project,
    Quantity,
    RangeQuantity,
    Severity,
    TestResult,
    block_report_html,
    project_report_html,
    quantity_to_html,
    quantity_to_markdown,
)
from framework.modes import ModeSet
from framework.scenarios import ScenarioSet
from framework.units import degC, mA


def _empty_project() -> Project:
    return Project(
        scenarios=ScenarioSet(scenarios=[]),
        modes=ModeSet(modes=[]),
        cache_dir=None,
    )


# ---------------------------------------------------------------------------
# Quantity formatters (12a)
# ---------------------------------------------------------------------------


class TestQuantityToMarkdown:
    def test_constant(self) -> None:
        q = Constant(5.0, mA)
        out = quantity_to_markdown(q, name="i_q")
        assert "**i_q**" in out
        assert "(unit: mA)" in out
        assert "| value |" in out
        # Single nominal row.
        assert "5 mA" in out

    def test_range(self) -> None:
        q = RangeQuantity(1.0, 2.0, mA)
        out = quantity_to_markdown(q, name="r")
        assert "1 – 2 mA" in out

    def test_by_mode(self) -> None:
        q = Quantity(unit=mA, by_mode={
            "sleep":  Constant(0.01, mA),
            "active": RangeQuantity(80.0, 220.0, mA),
        })
        out = quantity_to_markdown(q, name="i_supply")
        assert "| mode |" in out
        assert "| value |" in out
        assert "sleep" in out
        assert "active" in out
        assert "80 – 220 mA" in out

    def test_literal_skips_provenance(self) -> None:
        # Literal Quantity has no chain — section should be omitted.
        q = Constant(5.0, mA)
        out = quantity_to_markdown(q, name="x")
        assert "Provenance:" not in out

    def test_rejects_non_quantity(self) -> None:
        with pytest.raises(TypeError):
            quantity_to_markdown("not a quantity")  # type: ignore[arg-type]


class TestQuantityToHtml:
    def test_constant_table_shape(self) -> None:
        q = Constant(5.0, mA)
        out = quantity_to_html(q, name="i_q")
        assert "<table" in out
        assert "5 mA" in out
        # No provenance block for literal Quantities.
        assert "Provenance chain" not in out

    def test_html_escapes_label(self) -> None:
        q = Constant(5.0, mA)
        out = quantity_to_html(q, name="<script>")
        # Tag form should be escaped — never appear as a literal element.
        assert "<script>" not in out
        assert "&lt;script&gt;" in out

    def test_by_mode_renders_each_mode(self) -> None:
        q = Quantity(unit=mA, by_mode={
            "sleep":  Constant(0.01, mA),
            "active": Constant(220.0, mA),
        })
        out = quantity_to_html(q, name="i_supply")
        assert "sleep" in out
        assert "active" in out
        assert "<th>Mode</th>" in out
        assert "<th>Scenario</th>" not in out  # no scenario axis

    def test_show_provenance_false_skips_block(self) -> None:
        # Hook a Quantity to a real graph by running it through Project.run.
        from sample_block import analysis, leaves

        out = _empty_project().run(
            modules=[leaves, analysis],
            targets=["t_j"],
            inputs={"ambient_temp": Constant(25, degC)},
        )
        t_j = out["t_j"]
        with_prov = quantity_to_html(t_j, show_provenance=True)
        without_prov = quantity_to_html(t_j, show_provenance=False)
        assert "Provenance chain" in with_prov
        assert "Provenance chain" not in without_prov


# ---------------------------------------------------------------------------
# Per-block report (12b)
# ---------------------------------------------------------------------------


class TestBlockReportHtml:
    def test_renders_contracts_section(self) -> None:
        from consistency_ok_block import contracts, leaves

        proj = _empty_project()
        # return_all_computed=True pulls in the contract's compares_to target
        # automatically so the report can render the status column without
        # the caller having to enumerate every actual.
        results = proj.run(
            modules=[contracts, leaves],
            targets=["declared_ok"],
            return_all_computed=True,
        )
        html = block_report_html(
            proj,
            modules=[contracts, leaves],
            results=results,
            block="consistency_ok_block",
        )
        assert "Contracts" in html
        assert "declared_ok" in html
        # Status badges should appear on the per-mode rows.
        assert ">OK<" in html

    def test_filters_to_named_block(self) -> None:
        from consistency_ok_block import contracts, leaves

        proj = _empty_project()
        results = proj.run(
            modules=[contracts, leaves],
            targets=["declared_ok"],
        )
        html = block_report_html(
            proj,
            modules=[contracts, leaves],
            results=results,
            block="some_other_block",
        )
        # Contracts list is empty for an unrelated block.
        assert "No contracts declared in this block" in html

    def test_renders_verifications_subsection_when_supplied(self) -> None:
        from consistency_ok_block import contracts, leaves

        proj = _empty_project()
        results = proj.run(
            modules=[contracts, leaves],
            targets=["declared_ok"],
        )
        test_results = {
            "supply": TestResult(
                name="supply check",
                passed=True,
                severity=Severity.CRITICAL,
                requirement="REQ-PWR-005",
                block="consistency_ok_block",
            ),
            "foreign": TestResult(
                name="other-block test",
                passed=True,
                severity=Severity.CRITICAL,
                block="some_other_block",
            ),
        }
        html = block_report_html(
            proj,
            modules=[contracts, leaves],
            results=results,
            block="consistency_ok_block",
            test_results=test_results,
        )
        assert "supply check" in html
        # Other-block test is filtered out.
        assert "other-block test" not in html

    def test_renders_key_quantities(self) -> None:
        from consistency_ok_block import contracts, leaves

        proj = _empty_project()
        results = proj.run(
            modules=[contracts, leaves],
            targets=["declared_ok", "actual_draw"],
        )
        html = block_report_html(
            proj,
            modules=[contracts, leaves],
            results=results,
            block="consistency_ok_block",
        )
        assert "Key quantities" in html
        # actual_draw is the non-contract block-owned Quantity.
        assert "actual_draw" in html


# ---------------------------------------------------------------------------
# Project-wide report (12c)
# ---------------------------------------------------------------------------


class TestProjectReportHtml:
    def test_includes_counts(self) -> None:
        from consistency_ok_block import contracts, leaves

        proj = _empty_project()
        results = proj.run(
            modules=[contracts, leaves],
            targets=["declared_ok"],
        )
        html = project_report_html(
            proj,
            modules=[contracts, leaves],
            results=results,
        )
        assert "Project design review" in html
        assert "blocks" in html
        assert "contracts" in html

    def test_requirement_coverage_matrix(self) -> None:
        from consistency_ok_block import contracts, leaves

        proj = _empty_project()
        results = proj.run(
            modules=[contracts, leaves],
            targets=["declared_ok"],
        )
        test_results = {
            "supply": TestResult(
                name="supply check",
                passed=True,
                severity=Severity.CRITICAL,
                requirement="REQ-PWR-014",
                block="consistency_ok_block",
            ),
        }
        html = project_report_html(
            proj,
            modules=[contracts, leaves],
            results=results,
            test_results=test_results,
        )
        assert "Requirement coverage" in html
        assert "REQ-PWR-014" in html
        # The test verdict chip should appear.
        assert "supply check" in html

    def test_no_requirements_message(self) -> None:
        # An empty module list yields an empty report — should not crash.
        proj = _empty_project()
        html = project_report_html(
            proj,
            modules=[],
            results={},
        )
        assert "No requirement IDs referenced" in html


# ---------------------------------------------------------------------------
# Notebook display helpers (lazy IPython import)
# ---------------------------------------------------------------------------


class TestDisplayHelpers:
    def test_display_quantity_calls_ipython(self, monkeypatch) -> None:
        # We don't actually need IPython at the venv — patch the lazy import.
        called: dict[str, object] = {}

        class _FakeHTML:
            def __init__(self, html: str) -> None:
                called["html"] = html

        def _fake_display(obj):
            called["displayed"] = obj

        import sys
        import types as _types
        fake_mod = _types.ModuleType("IPython.display")
        fake_mod.HTML = _FakeHTML
        fake_mod.display = _fake_display
        monkeypatch.setitem(sys.modules, "IPython", _types.ModuleType("IPython"))
        monkeypatch.setitem(sys.modules, "IPython.display", fake_mod)

        from framework import display_quantity
        display_quantity(Constant(3.0, mA), name="x")
        assert "html" in called
        assert "3 mA" in called["html"]  # type: ignore[operator]
