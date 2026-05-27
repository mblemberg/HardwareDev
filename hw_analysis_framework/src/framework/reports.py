"""Output channels for verification results and design-review reports.

Two families of renderers, sharing inline CSS and helpers:

**Verification-test formatters** (design doc 6.8 / step 9c) — one
``@verification_test`` definition, four destinations:

- :func:`results_to_markdown_table`, :func:`results_to_html_table`,
  :func:`results_to_pr_comment`, :func:`results_to_jama_records`.

**Design-review report formatters** (design doc §12 / step 12) — same
underlying data, two surfaces (raw HTML string or
``IPython.display.HTML``-wrapped notebook display):

- :func:`quantity_to_html` / :func:`quantity_to_markdown` — one
  Quantity's per-mode/scenario breakdown plus optional collapsible
  provenance chain.
- :func:`block_report_html` — one block's contracts (declared vs actual),
  verifications, key quantities, and cross-block consumers.
- :func:`project_report_html` — all blocks plus a requirement-coverage
  matrix and global verification roll-up.
- :func:`display_quantity` / :func:`display_block_report` /
  :func:`display_project_report` — thin Jupyter wrappers that call the
  HTML formatters and hand the result to ``IPython.display.HTML``.

No new dependencies — stdlib only, IPython is lazy-imported only when
the ``display_*`` helpers are called.
"""
from __future__ import annotations

import types
from collections.abc import Mapping
from datetime import datetime, timezone
from html import escape
from typing import Any

from framework.contract import (
    ContractMeta,
    get_contract_meta,
    is_contract,
)
from framework.quantity import INVARIANT, Quantity, _as_range
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
  .vt-table { border-collapse: collapse; font-family: sans-serif; font-size: 0.9em; margin: 4px 0 8px 0; }
  .vt-table th, .vt-table td { padding: 4px 10px; border: 1px solid #ccc; text-align: left; }
  .vt-table th { background: #f4f4f4; font-weight: 600; }
  .vt-pass { background: #e6f6e6; }
  .vt-fail { background: #fbe6e6; }
  .vt-warn { background: #fff5d6; }
  .vt-info { background: #e6f0fb; }
  .vt-chip { font-family: monospace; font-weight: 600; }
  .vt-report { font-family: sans-serif; color: #222; }
  .vt-report h2 { border-bottom: 2px solid #444; padding-bottom: 4px; margin-top: 24px; }
  .vt-report h3 { border-bottom: 1px solid #888; padding-bottom: 2px; margin-top: 18px; }
  .vt-report h4 { margin-top: 14px; margin-bottom: 4px; }
  .vt-report details { margin: 4px 0 8px 0; }
  .vt-report summary { cursor: pointer; color: #444; }
  .vt-counts { font-size: 0.95em; margin: 4px 0 12px 0; }
  .vt-counts span { display: inline-block; margin-right: 12px; }
  .vt-chain { font-family: monospace; font-size: 0.85em; white-space: pre; background: #fafafa;
              border: 1px solid #ddd; padding: 6px 10px; }
  .vt-muted { color: #888; }
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


# ---------------------------------------------------------------------------
# Design-review report renderers (design doc §12 / step 12)
# ---------------------------------------------------------------------------
#
# These share the same _HTML_CSS so the verification-test tables and the
# block / project reports compose visually when embedded in the same
# notebook. All HTML-returning functions are pure (no Jupyter dependency);
# the ``display_*`` helpers wrap them with IPython.display.HTML for
# notebook surfaces.


def _format_scalar(v: float, unit: Any) -> str:
    """Tight scalar formatting: 4 significant digits + Pint short unit symbol."""
    return f"{v:.4g} {unit:~}"


def _format_value(v: Any, unit: Any) -> str:
    """Format a scalar or ``(lo, hi)`` range tuple in ``unit``."""
    if isinstance(v, tuple):
        lo, hi = v
        if lo == hi:
            return _format_scalar(lo, unit)
        return f"{lo:.4g} – {hi:.4g} {unit:~}"
    return _format_scalar(v, unit)


def _block_of_module_path(module: str) -> str:
    """Mirror ``contract.block_of_function`` but starting from a module string.

    ``blocks.can_transceiver.contracts`` -> ``can_transceiver``;
    ``foo`` -> ``foo``.
    """
    if not module:
        return ""
    parts = module.split(".")
    if len(parts) == 1:
        return parts[0]
    return parts[-2]


def _iter_contracts(
    modules: list[types.ModuleType],
) -> list[tuple[str, ContractMeta, str]]:
    """Yield ``(node_name, meta, owning_block)`` for every Contract in ``modules``.

    Same module-scan rule as the cycle detector / consistency checker.
    """
    out: list[tuple[str, ContractMeta, str]] = []
    for module in modules:
        for attr in dir(module):
            if attr.startswith("_"):
                continue
            obj = getattr(module, attr, None)
            if obj is None or not is_contract(obj):
                continue
            if getattr(obj, "__module__", None) != module.__name__:
                continue
            meta = get_contract_meta(obj)
            assert meta is not None
            out.append((attr, meta, meta.block))
    return out


def _extract_provenance_graph(results: Mapping[str, Any]) -> Any:
    """Pull the per-run ProvenanceGraph off the first result Quantity that has one."""
    for v in results.values():
        if isinstance(v, Quantity):
            graph = getattr(v.provenance, "_graph", None)
            if graph is not None:
                return graph
    return None


def _reverse_adjacency(graph: Any) -> dict[str, list[str]]:
    """Build ``{node_id: [direct_children]}`` from a ProvenanceGraph."""
    rev: dict[str, list[str]] = {}
    if graph is None:
        return rev
    for node_id, info in graph.nodes.items():
        for parent in info.parents:
            rev.setdefault(parent, []).append(node_id)
    return rev


# ---------- Quantity formatters (12a) --------------------------------------


def quantity_to_markdown(
    q: Quantity,
    *,
    name: str | None = None,
    show_provenance: bool = True,
) -> str:
    """Render one Quantity as a GitHub-flavored markdown block.

    Produces a header (``**name** (unit)``), a table whose columns adapt to
    which axes the Quantity carries, and — when ``show_provenance`` is true
    and the Quantity is hooked to a :class:`ProvenanceGraph` —
    a fenced block with ``q.provenance.chain_summary()``.

    Args:
        q: the Quantity to render.
        name: header label. Defaults to the Quantity's provenance node id
            (or "Quantity" for unhooked values).
        show_provenance: include the chain summary block (default true).
    """
    if not isinstance(q, Quantity):
        raise TypeError(f"quantity_to_markdown expected Quantity, got {type(q).__name__}")
    label = name if name is not None else _default_quantity_label(q)
    lines: list[str] = [f"**{label}**  _(unit: {q.unit:~})_", ""]
    rows = list(q.iter_axes())
    has_scenario = any(s is not None for s, _, _ in rows)
    has_mode = any(m is not None for _, m, _ in rows)
    headers: list[str] = []
    if has_scenario:
        headers.append("scenario")
    if has_mode:
        headers.append("mode")
    headers.append("value")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for scenario, mode, value in rows:
        cells: list[str] = []
        if has_scenario:
            cells.append("—" if scenario is None else scenario)
        if has_mode:
            cells.append("—" if mode is None else mode)
        cells.append(_format_value(value, q.unit))
        lines.append("| " + " | ".join(cells) + " |")
    if show_provenance and not q.provenance.is_literal:
        lines.append("")
        lines.append("Provenance:")
        lines.append("")
        lines.append("```")
        lines.append(q.provenance.chain_summary())
        lines.append("```")
    return "\n".join(lines)


def quantity_to_html(
    q: Quantity,
    *,
    name: str | None = None,
    show_provenance: bool = True,
) -> str:
    """Render one Quantity as an HTML fragment (table + optional collapsible chain).

    Same data as :func:`quantity_to_markdown`; the provenance chain is
    wrapped in a ``<details>`` element so it's collapsed by default.
    """
    if not isinstance(q, Quantity):
        raise TypeError(f"quantity_to_html expected Quantity, got {type(q).__name__}")
    label = name if name is not None else _default_quantity_label(q)
    rows = list(q.iter_axes())
    has_scenario = any(s is not None for s, _, _ in rows)
    has_mode = any(m is not None for _, m, _ in rows)
    headers: list[str] = []
    if has_scenario:
        headers.append("Scenario")
    if has_mode:
        headers.append("Mode")
    headers.append("Value")

    parts: list[str] = [_HTML_CSS]
    parts.append('<div class="vt-report">')
    parts.append(
        f"<h4>{escape(label)} "
        f'<span class="vt-muted">(unit: {escape(f"{q.unit:~}")})</span></h4>'
    )
    parts.append('<table class="vt-table">')
    parts.append(
        "<thead><tr>"
        + "".join(f"<th>{escape(h)}</th>" for h in headers)
        + "</tr></thead>"
    )
    parts.append("<tbody>")
    for scenario, mode, value in rows:
        cells: list[str] = []
        if has_scenario:
            cells.append(escape("—" if scenario is None else scenario))
        if has_mode:
            cells.append(escape("—" if mode is None else mode))
        cells.append(escape(_format_value(value, q.unit)))
        parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    parts.append("</tbody></table>")
    if show_provenance and not q.provenance.is_literal:
        chain_text = q.provenance.chain_summary()
        parts.append(
            "<details><summary>Provenance chain</summary>"
            f'<div class="vt-chain">{escape(chain_text)}</div>'
            "</details>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def _default_quantity_label(q: Quantity) -> str:
    if q.provenance.is_literal:
        return "Quantity"
    return q.provenance.node_id


# ---------- Per-block report (12b) -----------------------------------------


def _contract_status_for_mode(
    declared: Any, actual: Any
) -> tuple[str, str]:
    """Return ``(status, css_class)`` for a (declared, actual) pair at one mode.

    Both inputs are scalar-or-range values in the same unit. Status is
    ``"OK"`` when actual ⊆ declared, ``"MISMATCH"`` otherwise.
    """
    a_lo, a_hi = _as_range(actual)
    d_lo, d_hi = _as_range(declared)
    if a_lo < d_lo or a_hi > d_hi:
        return "MISMATCH", "vt-fail"
    return "OK", "vt-pass"


def _render_contract_block(
    node_name: str,
    meta: ContractMeta,
    results: Mapping[str, Any],
    rev_adj: dict[str, list[str]],
    graph: Any,
) -> str:
    """One Contract's section: header + declared-vs-actual table + assumed inputs + consumers."""
    parts: list[str] = []
    parts.append(f"<h4>Contract: <code>{escape(node_name)}</code></h4>")
    desc_bits: list[str] = []
    if meta.description:
        desc_bits.append(escape(meta.description))
    if meta.requirement:
        desc_bits.append(f"<strong>Requirement:</strong> <code>{escape(meta.requirement)}</code>")
    if desc_bits:
        parts.append("<p>" + " &middot; ".join(desc_bits) + "</p>")

    declared = results.get(node_name)
    actual = results.get(meta.compares_to) if meta.compares_to else None

    if not isinstance(declared, Quantity):
        parts.append('<p class="vt-muted">Declared value not in results.</p>')
    else:
        # Per-mode/scenario comparison table.
        parts.append('<table class="vt-table">')
        cols = ["Scenario", "Mode", "Declared"]
        if isinstance(actual, Quantity):
            cols.extend(["Actual", "Status"])
        parts.append(
            "<thead><tr>"
            + "".join(f"<th>{escape(c)}</th>" for c in cols)
            + "</tr></thead><tbody>"
        )
        declared_axes = list(declared.iter_axes())
        # If declared is mode-only and actual carries scenarios too, drive
        # the iteration from actual (covers more corners). Otherwise drive
        # from declared.
        if isinstance(actual, Quantity):
            actual_axes = list(actual.iter_axes())
            driving = actual_axes if len(actual_axes) >= len(declared_axes) else declared_axes
        else:
            driving = declared_axes
        for scenario, mode, _v in driving:
            # Look up declared & actual at this corner.
            try:
                d_val = _evaluate_safely(declared, scenario=scenario, mode=mode)
            except Exception:
                d_val = None
            if isinstance(actual, Quantity):
                try:
                    a_val = _evaluate_safely(actual.to(declared.unit), scenario=scenario, mode=mode)
                except Exception:
                    a_val = None
            else:
                a_val = None
            row_cells: list[str] = []
            row_cells.append(escape("—" if scenario in (None, INVARIANT) else scenario))
            row_cells.append(escape("—" if mode is None else mode))
            row_cells.append(escape(_format_value(d_val, declared.unit)) if d_val is not None else '<span class="vt-muted">—</span>')
            if isinstance(actual, Quantity):
                if a_val is None or d_val is None:
                    row_cells.append('<span class="vt-muted">—</span>')
                    row_cells.append('<span class="vt-muted">N/A</span>')
                    row_class = ""
                else:
                    row_cells.append(escape(_format_value(a_val, declared.unit)))
                    status, row_class = _contract_status_for_mode(d_val, a_val)
                    row_cells.append(f'<span class="vt-chip">{status}</span>')
                parts.append(
                    f'<tr class="{row_class}">'
                    + "".join(f"<td>{c}</td>" for c in row_cells)
                    + "</tr>"
                )
            else:
                parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in row_cells) + "</tr>")
        parts.append("</tbody></table>")
        if not isinstance(actual, Quantity) and meta.compares_to:
            parts.append(
                f'<p class="vt-muted">Actual node <code>{escape(meta.compares_to)}</code> '
                "not in results — declared bound shown without comparison.</p>"
            )
        elif meta.compares_to is None:
            parts.append('<p class="vt-muted">No <code>compares_to</code> set — declaration only.</p>')

    # Assumed inputs (Quantity-valued entries get a comparison row each).
    if meta.assumed_inputs:
        parts.append("<details><summary>Assumed inputs</summary>")
        parts.append('<table class="vt-table">')
        parts.append(
            "<thead><tr><th>Input</th><th>Assumed</th><th>Actual</th><th>Status</th></tr></thead><tbody>"
        )
        for key, assumed in meta.assumed_inputs.items():
            actual_val = results.get(key)
            row_cells: list[str] = [f"<code>{escape(key)}</code>"]
            if isinstance(assumed, Quantity):
                # Render the assumption compactly: nominal range or first axis.
                axes = list(assumed.iter_axes())
                if len(axes) == 1:
                    _, _, v = axes[0]
                    row_cells.append(escape(_format_value(v, assumed.unit)))
                else:
                    row_cells.append(escape(f"{len(axes)} corners"))
                if isinstance(actual_val, Quantity):
                    # Compare ranges across the union of axes (degraded but useful).
                    try:
                        actual_u = actual_val.to(assumed.unit)
                    except Exception:
                        actual_u = actual_val
                    a_axes = list(actual_u.iter_axes())
                    if len(a_axes) == 1:
                        _, _, av = a_axes[0]
                        row_cells.append(escape(_format_value(av, assumed.unit)))
                    else:
                        row_cells.append(escape(f"{len(a_axes)} corners"))
                    # Approximate status — full check is in
                    # check_contract_assumptions; here we only flag obviously
                    # bad single-corner cases.
                    if len(axes) == 1 and len(a_axes) == 1:
                        status, css = _contract_status_for_mode(axes[0][2], a_axes[0][2])
                        row_cells.append(f'<span class="vt-chip">{status}</span>')
                    else:
                        row_cells.append('<span class="vt-muted">see contract check</span>')
                else:
                    row_cells.append('<span class="vt-muted">not in results</span>')
                    row_cells.append('<span class="vt-muted">—</span>')
            else:
                row_cells.append(escape(str(assumed)))
                row_cells.append('<span class="vt-muted">(informational)</span>')
                row_cells.append('<span class="vt-muted">—</span>')
            parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in row_cells) + "</tr>")
        parts.append("</tbody></table></details>")

    # Cross-block consumers from the ProvenanceGraph (when available).
    if graph is not None and node_name in rev_adj:
        consumers = rev_adj[node_name]
        cross_block: list[tuple[str, str]] = []  # (consumer_node, consumer_block)
        for c in consumers:
            info = graph.info(c)
            if info is None:
                continue
            c_block = _block_of_module_path(info.module)
            if c_block != meta.block:
                cross_block.append((c, c_block))
        if cross_block:
            parts.append("<details><summary>Consumed by</summary>")
            parts.append('<table class="vt-table">')
            parts.append("<thead><tr><th>Consumer node</th><th>Block</th></tr></thead><tbody>")
            for c, c_block in cross_block:
                parts.append(
                    f"<tr><td><code>{escape(c)}</code></td>"
                    f"<td>{escape(c_block) if c_block else '<span class=\"vt-muted\">—</span>'}</td></tr>"
                )
            parts.append("</tbody></table></details>")
    return "\n".join(parts)


def _evaluate_safely(q: Quantity, *, scenario: str | None, mode: str | None) -> Any:
    """Best-effort evaluate ``q`` at (scenario, mode); descend missing axes silently."""
    if q.by_mode is not None:
        if mode is None or mode not in q.by_mode:
            # Try the first mode as a fallback (caller treats as None).
            return None
        return _evaluate_safely(q.by_mode[mode], scenario=scenario, mode=None)
    if q.by_scenario is not None:
        if scenario is not None and scenario in q.by_scenario:
            return q.by_scenario[scenario]
        if INVARIANT in q.by_scenario:
            return q.by_scenario[INVARIANT]
        if scenario is None and len(q.by_scenario) == 1:
            return next(iter(q.by_scenario.values()))
        return None
    return q.value


def _block_test_results(
    test_results: Mapping[str, TestResult] | None,
    block: str,
) -> dict[str, TestResult]:
    if not test_results:
        return {}
    return {k: r for k, r in test_results.items() if r.block == block}


def _block_key_quantities(
    results: Mapping[str, Any],
    graph: Any,
    block: str,
) -> list[tuple[str, Quantity]]:
    """Result Quantities whose producing node lives in ``block``, sorted by name.

    Excludes Contract nodes (they're rendered in their own section). Inputs
    are excluded too — they're not block-internal.
    """
    if graph is None:
        return []
    out: list[tuple[str, Quantity]] = []
    for name, val in results.items():
        if not isinstance(val, Quantity):
            continue
        info = graph.info(name)
        if info is None or info.is_input:
            continue
        if _block_of_module_path(info.module) != block:
            continue
        out.append((name, val))
    out.sort(key=lambda kv: kv[0])
    return out


def block_report_html(
    project: Any,
    modules: list[types.ModuleType],
    results: Mapping[str, Any],
    *,
    block: str,
    test_results: Mapping[str, TestResult] | None = None,
    title: str | None = None,
    include_key_quantities: bool = True,
) -> str:
    """Render a per-block design-review report as a self-contained HTML fragment.

    Sections:

    1. **Contracts** — for every ``@contract`` whose owning block matches
       ``block``: declared vs actual per (scenario, mode) corner, with a
       status badge per row. Assumed-inputs and cross-block consumers are
       rendered as collapsible ``<details>`` blocks.
    2. **Verifications** — :func:`results_to_html_table` filtered to tests
       whose ``TestResult.block`` matches ``block``.
    3. **Key quantities** — every result Quantity whose producing DAG node
       lives in ``block``, each via :func:`quantity_to_html` with the
       provenance chain collapsed.

    ``project`` is currently informational only (its scenarios / modes are
    consulted indirectly via the results' axis space) and accepted for
    forward-compat with project-wide aggregations.
    """
    parts: list[str] = [_HTML_CSS, '<div class="vt-report">']
    parts.append(f"<h2>{escape(title or f'Block report — {block}')}</h2>")

    # 1. Contracts
    parts.append("<h3>Contracts</h3>")
    contracts = [
        (name, meta) for (name, meta, owning) in _iter_contracts(modules)
        if owning == block
    ]
    if not contracts:
        parts.append('<p class="vt-muted">No contracts declared in this block.</p>')
    else:
        graph = _extract_provenance_graph(results)
        rev_adj = _reverse_adjacency(graph)
        for name, meta in contracts:
            parts.append(_render_contract_block(name, meta, results, rev_adj, graph))

    # 2. Verifications
    parts.append("<h3>Verifications</h3>")
    block_tests = _block_test_results(test_results, block)
    if not block_tests and test_results is not None:
        parts.append('<p class="vt-muted">No verification tests declared in this block.</p>')
    elif test_results is None:
        parts.append(
            '<p class="vt-muted">Verification results not supplied — '
            "pass <code>test_results=</code> to render them.</p>"
        )
    else:
        # _sorted_results / results_to_html_table both include CSS; strip
        # the redundant <style> block on the inner call to avoid duplication.
        inner = results_to_html_table(block_tests)
        parts.append(_strip_inline_css(inner))

    # 3. Key quantities
    if include_key_quantities:
        parts.append("<h3>Key quantities</h3>")
        graph = _extract_provenance_graph(results)
        keys = _block_key_quantities(results, graph, block)
        if not keys:
            parts.append('<p class="vt-muted">No block-owned Quantities in results.</p>')
        else:
            for name, q in keys:
                parts.append(_strip_inline_css(quantity_to_html(q, name=name)))

    parts.append("</div>")
    return "\n".join(parts)


def _strip_inline_css(html: str) -> str:
    """Drop a leading ``<style>...</style>`` block.

    All renderers prepend ``_HTML_CSS`` so they're self-contained. When
    composing them inside ``block_report_html`` / ``project_report_html``
    we only want the CSS once; this helper trims it from sub-renderers.
    """
    if "<style>" in html and "</style>" in html:
        start = html.index("<style>")
        end = html.index("</style>") + len("</style>")
        return html[:start] + html[end:].lstrip()
    return html


# ---------- Project-wide report (12c) --------------------------------------


def _all_blocks(modules: list[types.ModuleType]) -> list[str]:
    """All distinct block names contributing functions to the DAG, sorted."""
    blocks: set[str] = set()
    for module in modules:
        b = _block_of_module_path(module.__name__)
        if b:
            blocks.add(b)
    return sorted(blocks)


def _requirement_coverage(
    modules: list[types.ModuleType],
    test_results: Mapping[str, TestResult] | None,
) -> dict[str, dict[str, list[str]]]:
    """Build ``{requirement_id: {"contracts": [...], "tests": [(name, status), ...]}}``.

    Status is one of ``"pass"``, ``"fail"``, ``"warn"``, ``"info"`` — matched
    to the verification-test verdict semantics used elsewhere.
    """
    out: dict[str, dict[str, Any]] = {}
    for node_name, meta, _block in _iter_contracts(modules):
        if not meta.requirement:
            continue
        slot = out.setdefault(meta.requirement, {"contracts": [], "tests": []})
        slot["contracts"].append(node_name)
    if test_results:
        for r in test_results.values():
            if not r.requirement:
                continue
            slot = out.setdefault(r.requirement, {"contracts": [], "tests": []})
            if r.passed:
                status = "pass"
            elif r.severity is Severity.INFO:
                status = "info"
            elif r.severity is Severity.WARNING:
                status = "warn"
            else:
                status = "fail"
            slot["tests"].append((r.name, status))
    return out


def project_report_html(
    project: Any,
    modules: list[types.ModuleType],
    results: Mapping[str, Any],
    *,
    test_results: Mapping[str, TestResult] | None = None,
    title: str = "Project design review",
    include_key_quantities: bool = True,
) -> str:
    """Render a project-wide design-review report as a self-contained HTML fragment.

    Aggregates:

    1. **Header counts** — number of blocks, contracts, and verification
       tests (with pass/fail/warn/info breakdown).
    2. **One subsection per block**, embedding :func:`block_report_html`
       output (with the redundant ``<style>`` stripped).
    3. **Requirement coverage matrix** — for every Jama ``requirement`` id
       referenced by a Contract or a verification test, the contracts
       declaring against it and the tests verifying it (with their
       verdicts).

    ``include_key_quantities`` propagates to each block subsection — flip
    it off to keep the project report focused on contracts + verifications.
    """
    blocks = _all_blocks(modules)
    contracts = _iter_contracts(modules)
    n_tests = len(test_results) if test_results else 0
    n_pass = sum(1 for r in (test_results or {}).values() if r.passed)
    n_fail = sum(
        1 for r in (test_results or {}).values()
        if not r.passed and r.severity is Severity.CRITICAL
    )
    n_warn = sum(
        1 for r in (test_results or {}).values()
        if not r.passed and r.severity is Severity.WARNING
    )
    n_info = sum(
        1 for r in (test_results or {}).values()
        if not r.passed and r.severity is Severity.INFO
    )

    parts: list[str] = [_HTML_CSS, '<div class="vt-report">']
    parts.append(f"<h2>{escape(title)}</h2>")
    parts.append('<div class="vt-counts">')
    parts.append(f"<span><strong>{len(blocks)}</strong> blocks</span>")
    parts.append(f"<span><strong>{len(contracts)}</strong> contracts</span>")
    parts.append(f"<span><strong>{n_tests}</strong> verification tests</span>")
    if n_tests:
        parts.append(
            "<span>"
            f"<strong>{n_pass}</strong> pass · "
            f"<strong>{n_fail}</strong> fail · "
            f"<strong>{n_warn}</strong> warn · "
            f"<strong>{n_info}</strong> info</span>"
        )
    parts.append("</div>")

    # Verification roll-up across all blocks.
    if test_results:
        parts.append("<h3>All verifications</h3>")
        parts.append(_strip_inline_css(results_to_html_table(test_results)))

    # Per-block subsections.
    for block in blocks:
        inner = block_report_html(
            project,
            modules,
            results,
            block=block,
            test_results=test_results,
            title=f"Block — {block}",
            include_key_quantities=include_key_quantities,
        )
        parts.append(_strip_inline_css(inner))

    # Requirement coverage matrix.
    coverage = _requirement_coverage(modules, test_results)
    parts.append("<h3>Requirement coverage</h3>")
    if not coverage:
        parts.append('<p class="vt-muted">No requirement IDs referenced.</p>')
    else:
        parts.append('<table class="vt-table">')
        parts.append(
            "<thead><tr><th>Requirement</th><th>Contracts</th>"
            "<th>Verification tests</th></tr></thead><tbody>"
        )
        for req in sorted(coverage):
            slot = coverage[req]
            contracts_cell = (
                ", ".join(f"<code>{escape(c)}</code>" for c in slot["contracts"])
                if slot["contracts"]
                else '<span class="vt-muted">—</span>'
            )
            if slot["tests"]:
                test_bits = []
                for name, status in slot["tests"]:
                    cls = {"pass": "vt-pass", "fail": "vt-fail",
                           "warn": "vt-warn", "info": "vt-info"}.get(status, "")
                    test_bits.append(
                        f'<span class="vt-chip {cls}" style="padding:1px 6px;">'
                        f"{escape(name)} ({status})</span>"
                    )
                tests_cell = " ".join(test_bits)
            else:
                tests_cell = '<span class="vt-muted">—</span>'
            parts.append(
                f"<tr><td><code>{escape(req)}</code></td>"
                f"<td>{contracts_cell}</td>"
                f"<td>{tests_cell}</td></tr>"
            )
        parts.append("</tbody></table>")

    parts.append("</div>")
    return "\n".join(parts)


# ---------- Notebook helpers (thin IPython.display wrappers) ---------------


def display_quantity(q: Quantity, **kwargs: Any) -> None:
    """Jupyter helper — render :func:`quantity_to_html` and display it inline."""
    from IPython.display import HTML, display  # lazy: optional dep
    display(HTML(quantity_to_html(q, **kwargs)))


def display_block_report(*args: Any, **kwargs: Any) -> None:
    """Jupyter helper — render :func:`block_report_html` and display it inline."""
    from IPython.display import HTML, display  # lazy: optional dep
    display(HTML(block_report_html(*args, **kwargs)))


def display_project_report(*args: Any, **kwargs: Any) -> None:
    """Jupyter helper — render :func:`project_report_html` and display it inline."""
    from IPython.display import HTML, display  # lazy: optional dep
    display(HTML(project_report_html(*args, **kwargs)))


__all__ = [
    "block_report_html",
    "display_block_report",
    "display_project_report",
    "display_quantity",
    "project_report_html",
    "quantity_to_html",
    "quantity_to_markdown",
    "results_to_html_table",
    "results_to_jama_records",
    "results_to_markdown_table",
    "results_to_pr_comment",
]
