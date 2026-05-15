"""Output channels for ``TestResult`` collections (design doc 6.8 / step 9c).

One ``@verification_test`` definition, four destinations:

- :func:`results_to_markdown_table` — GitHub-flavored markdown table for
  block / project README rendering and CI step summaries.
- :func:`results_to_html_table` — HTML table for notebook display via
  ``IPython.display.HTML`` (no Plotly dep; just inline CSS).
- :func:`results_to_pr_comment` — markdown summary suitable for a GitHub
  PR comment, with collapsible ``<details>`` blocks for failing-corner
  detail and evidence so the comment stays short by default.
- :func:`results_to_jama_records` — list of plain ``dict`` records ready
  for JSON export and Jama push.

All four operate on the same ``Mapping[str, TestResult]`` returned by
:func:`framework.run_verifications`. No new dependencies — stdlib only,
so the framework stays light for users who never need report rendering.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from html import escape
from typing import Any

from framework.verification import ScenarioMode, Severity, TestResult


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------


def _verdict_chip(passed: bool, severity: Severity) -> str:
    """Short label for the verdict column."""
    if passed:
        return "PASS"
    if severity is Severity.INFO:
        return "INFO"
    if severity is Severity.WARNING:
        return "WARN"
    return "FAIL"


def _format_corners(corners: tuple[ScenarioMode, ...]) -> str:
    if not corners:
        return ""
    return "; ".join(str(c) for c in corners)


def _sorted_results(results: Mapping[str, TestResult]) -> list[TestResult]:
    """Stable order: fails first by severity, then alphabetical by name."""
    severity_rank = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    return sorted(
        results.values(),
        key=lambda r: (r.passed, severity_rank[r.severity], r.name),
    )


# ---------------------------------------------------------------------------
# Markdown table
# ---------------------------------------------------------------------------


def results_to_markdown_table(results: Mapping[str, TestResult]) -> str:
    """GitHub-flavored markdown table — one row per test."""
    if not results:
        return "_(no verification tests run)_"
    rows = ["| Verdict | Severity | Test | Failed at |",
            "|---|---|---|---|"]
    for r in _sorted_results(results):
        verdict = _verdict_chip(r.passed, r.severity)
        corners = _format_corners(r.failed_at) or "—"
        rows.append(
            f"| {verdict} | {r.severity.value} | {r.name} | {corners} |"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# HTML table (notebook)
# ---------------------------------------------------------------------------


_HTML_CSS = """
<style>
  .vt-table { border-collapse: collapse; font-family: sans-serif; font-size: 0.9em; }
  .vt-table th, .vt-table td { padding: 4px 10px; border: 1px solid #ccc; text-align: left; }
  .vt-table th { background: #f4f4f4; font-weight: 600; }
  .vt-pass { background: #e6f6e6; }
  .vt-fail { background: #fbe6e6; }
  .vt-warn { background: #fff5d6; }
  .vt-info { background: #e6f0fb; }
  .vt-chip { font-family: monospace; font-weight: 600; }
</style>
"""


def results_to_html_table(results: Mapping[str, TestResult]) -> str:
    """HTML table for Jupyter — pair with ``IPython.display.HTML``.

    Rows are colored by verdict (pass/fail/warning/info) and the verdict
    column is shown as a monospace chip for at-a-glance scanning.
    """
    if not results:
        return _HTML_CSS + "<p><em>(no verification tests run)</em></p>"
    rows: list[str] = [
        _HTML_CSS,
        '<table class="vt-table">',
        "<thead><tr><th>Verdict</th><th>Severity</th><th>Test</th>"
        "<th>Failed at</th></tr></thead>",
        "<tbody>",
    ]
    for r in _sorted_results(results):
        if r.passed:
            cls = "vt-pass"
        elif r.severity is Severity.INFO:
            cls = "vt-info"
        elif r.severity is Severity.WARNING:
            cls = "vt-warn"
        else:
            cls = "vt-fail"
        verdict = _verdict_chip(r.passed, r.severity)
        corners = _format_corners(r.failed_at) or "—"
        rows.append(
            f'<tr class="{cls}">'
            f'<td><span class="vt-chip">{verdict}</span></td>'
            f"<td>{escape(r.severity.value)}</td>"
            f"<td>{escape(r.name)}</td>"
            f"<td>{escape(corners)}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# PR comment (markdown summary)
# ---------------------------------------------------------------------------


def results_to_pr_comment(
    results: Mapping[str, TestResult],
    *,
    title: str = "Verification results",
) -> str:
    """GitHub-flavored markdown summary for posting as a PR comment.

    Header gives pass / fail / warning / info counts. Each failure gets a
    collapsible ``<details>`` block listing the failing corners so the
    comment doesn't dominate the PR view by default.
    """
    if not results:
        return f"## {title}\n\n_(no verification tests run)_"
    pass_count = sum(1 for r in results.values() if r.passed)
    fail_count = sum(
        1 for r in results.values()
        if not r.passed and r.severity is Severity.CRITICAL
    )
    warn_count = sum(
        1 for r in results.values()
        if not r.passed and r.severity is Severity.WARNING
    )
    info_count = sum(
        1 for r in results.values()
        if not r.passed and r.severity is Severity.INFO
    )
    parts: list[str] = [f"## {title}"]
    parts.append(
        f"**{pass_count} pass**, **{fail_count} fail**, "
        f"**{warn_count} warn**, **{info_count} info**"
    )
    for r in _sorted_results(results):
        if r.passed:
            continue
        verdict = _verdict_chip(r.passed, r.severity)
        corners = _format_corners(r.failed_at) or "_(no axes)_"
        parts.append("")
        parts.append(f"<details><summary>{verdict} — {r.name}</summary>")
        parts.append("")
        parts.append(f"- Severity: `{r.severity.value}`")
        parts.append(f"- Failed at: {corners}")
        if r.evidence:
            parts.append("- Evidence:")
            for key in sorted(r.evidence):
                parts.append(f"  - `{key}`")
        parts.append("")
        parts.append("</details>")
    # Single PASS-only summary line if no failures
    if pass_count == len(results):
        parts.append("")
        parts.append("All verification tests passed.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Jama-shape records (JSON-ready)
# ---------------------------------------------------------------------------


def results_to_jama_records(
    results: Mapping[str, TestResult],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """List of plain dicts ready for ``json.dumps`` and Jama push.

    Each record:
        - ``name``: test name (matches ``TestResult.name``)
        - ``requirement``: Jama requirement ID, or null
        - ``status``: ``"pass"`` / ``"fail"`` / ``"warning"`` / ``"info"``
        - ``severity``: same string as ``Severity.value``
        - ``failed_at``: list of ``{"scenario": ..., "mode": ...}`` records
        - ``evidence_keys``: list of evidence keys (Quantities themselves
          are not serialized in 9c; that's a follow-up that needs a
          JSON-shaped Quantity encoder)
        - ``executed_at``: ISO-8601 UTC timestamp

    ``now`` is a hook for deterministic testing.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    ts = now.isoformat()
    out: list[dict[str, Any]] = []
    for r in _sorted_results(results):
        if r.passed:
            status = "pass"
        elif r.severity is Severity.INFO:
            status = "info"
        elif r.severity is Severity.WARNING:
            status = "warning"
        else:
            status = "fail"
        out.append({
            "name": r.name,
            "block": r.block,
            "requirement": r.requirement,
            "status": status,
            "severity": r.severity.value,
            "failed_at": [
                {"scenario": c.scenario, "mode": c.mode} for c in r.failed_at
            ],
            "evidence_keys": sorted(r.evidence.keys()),
            "executed_at": ts,
        })
    return out


__all__ = [
    "results_to_html_table",
    "results_to_jama_records",
    "results_to_markdown_table",
    "results_to_pr_comment",
]
