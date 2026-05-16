"""VerificationTest — first-class registered test (design doc 6.8 / step 9a).

A ``@verification_test`` is a function the engineer writes once and the
framework dispatches to multiple destinations (pytest in CI, Jama push,
notebook tables, PR-comment summary). This module ships the *foundation*
of step 9 — the decorator, the result type, the helper context, and a
runner — but not yet the pytest plugin or the output channels (those land
as step 9b / 9c).

Usage:

    from framework import verification_test, Severity, Constant
    from framework.units import degC

    @verification_test(
        name="CAN block thermal margin",
        requirement="REQ-ENV-001",
        severity=Severity.CRITICAL,
    )
    def test_t_j_margin(ctx):
        t_j = ctx.quantity("t_j")
        return ctx.assert_quantity_below(
            t_j, Constant(125, degC), name="t_j vs 125 °C limit"
        )

Then::

    from framework import run_verifications
    results = project.run(...)
    test_results = run_verifications([verifications], results)
    for name, r in test_results.items():
        print(name, "OK" if r.passed else f"FAIL at {r.failed_at}")

The decorator is a pure marker (like ``@contract`` — Hamilton never sees
these functions, only the runner does). ``VerificationContext`` is the
minimal surface the test function uses: ``ctx.quantity(name)`` fetches a
result by DAG node name, ``ctx.assert_quantity_in / below / above`` runs
the comparison and returns a :class:`TestResult` carrying the failing
corners.
"""
from __future__ import annotations

import enum
import types
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from framework.quantity import Quantity, _as_range, _coerce_to_unit

if TYPE_CHECKING:
    import pint

    from framework.logic import TruthTable

_T = TypeVar("_T", bound=Callable[..., "TestResult"])


# ---------------------------------------------------------------------------
# Severity / ScenarioMode / TestResult
# ---------------------------------------------------------------------------


class Severity(enum.Enum):
    """How loud a verification failure should be.

    ``CRITICAL`` fails the CI run (pytest exit non-zero); ``WARNING`` is
    reported but doesn't fail; ``INFO`` is purely informational. The runner
    in 9a captures severity on the result; the pytest plugin in 9b applies
    these semantics.
    """

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ScenarioMode:
    """One (scenario, mode) point in the cross-product axis space."""

    scenario: str | None = None
    mode: str | None = None

    def __str__(self) -> str:
        parts: list[str] = []
        if self.scenario is not None and self.scenario != "_":
            parts.append(f"scenario={self.scenario!r}")
        if self.mode is not None:
            parts.append(f"mode={self.mode!r}")
        return ", ".join(parts) if parts else "(no axes)"


@dataclass(frozen=True)
class TestResult:
    """Outcome of one ``@verification_test`` (design doc 6.8).

    ``failed_at`` lists every (scenario, mode) corner the test failed.
    ``evidence`` is whatever the test author wants to surface to the
    Jama push / notebook table — typically a few Quantities that drove
    the conclusion. ``margin`` is the distance to the nearest spec edge
    (positive on pass, negative on fail) for the dominant corner; the
    runner doesn't compute it for you in 9a (helpers do when they can).
    """

    __test__ = False  # don't let pytest mistake this dataclass for a test class

    name: str
    passed: bool
    severity: Severity = Severity.CRITICAL
    failed_at: tuple[ScenarioMode, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
    margin: Quantity | None = None
    report_markdown: str = ""
    requirement: str | None = None
    block: str = ""

    def summary(self) -> str:
        """One-line summary for table rendering."""
        if self.passed:
            return f"PASS  [{self.severity.value}]  {self.name}"
        corners = "; ".join(str(c) for c in self.failed_at) or "(unspecified)"
        return f"FAIL  [{self.severity.value}]  {self.name} — at {corners}"


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationMeta:
    """Metadata captured by ``@verification_test``."""

    name: str
    requirement: str | None = None
    block: str = ""
    severity: Severity = Severity.CRITICAL
    modes: tuple[str, ...] = ()
    scenarios: tuple[str, ...] = ()
    function_name: str = ""


def verification_test(
    *,
    name: str,
    requirement: str | None = None,
    block: str | None = None,
    severity: Severity = Severity.CRITICAL,
    modes: tuple[str, ...] | list[str] = (),
    scenarios: tuple[str, ...] | list[str] = (),
) -> Callable[[_T], _T]:
    """Mark a function as a verification test (design doc 6.8).

    Args:
        name: Human-readable test name (used in reports and pytest discovery).
        requirement: Jama requirement ID this test binds to (optional).
        block: Owning block. Defaults to ``framework.contract.block_of_function``
            (the function's parent package name).
        severity: ``CRITICAL`` (default), ``WARNING``, or ``INFO``.
        modes: Restrict the test to these system modes (informational in 9a;
            the test author is responsible for honoring it).
        scenarios: Restrict to these scenarios (same caveat).
    """
    from framework.contract import block_of_function  # local: avoid cycle

    def decorator(fn: _T) -> _T:
        meta = VerificationMeta(
            name=name,
            requirement=requirement,
            block=block if block is not None else block_of_function(fn),
            severity=severity,
            modes=tuple(modes),
            scenarios=tuple(scenarios),
            function_name=fn.__name__,
        )
        fn.__is_verification_test__ = True   # type: ignore[attr-defined]
        fn.__verification_meta__ = meta      # type: ignore[attr-defined]
        return fn

    return decorator


def is_verification_test(fn: Any) -> bool:
    """True iff ``fn`` carries the ``@verification_test`` marker."""
    return bool(getattr(fn, "__is_verification_test__", False))


def get_verification_meta(fn: Any) -> VerificationMeta | None:
    """Return the ``VerificationMeta`` for ``fn``, or None if it isn't a test."""
    if not is_verification_test(fn):
        return None
    return getattr(fn, "__verification_meta__", None)


# ---------------------------------------------------------------------------
# VerificationContext — the ``ctx`` argument
# ---------------------------------------------------------------------------


class VerificationContext:
    """Runtime context handed to a ``@verification_test`` function.

    Holds the project run's results (mapping DAG node name to Quantity) and
    exposes the assertion helpers that produce :class:`TestResult` records.
    """

    def __init__(
        self,
        results: Mapping[str, Any],
        *,
        meta: VerificationMeta | None = None,
    ) -> None:
        self._results = results
        self._meta = meta

    @property
    def meta(self) -> VerificationMeta | None:
        return self._meta

    def quantity(self, node_name: str) -> Quantity:
        """Look up a Quantity result by DAG node name."""
        if node_name not in self._results:
            raise KeyError(
                f"Verification context has no result named {node_name!r}. "
                f"Available: {sorted(self._results)}"
            )
        v = self._results[node_name]
        if not isinstance(v, Quantity):
            raise TypeError(
                f"Result {node_name!r} is {type(v).__name__}, expected Quantity"
            )
        return v

    def truth_table(self, node_name: str) -> "TruthTable":
        """Look up a TruthTable result by DAG node name."""
        from framework.logic import TruthTable  # local: avoid cycle

        if node_name not in self._results:
            raise KeyError(
                f"Verification context has no result named {node_name!r}. "
                f"Available: {sorted(self._results)}"
            )
        v = self._results[node_name]
        if not isinstance(v, TruthTable):
            raise TypeError(
                f"Result {node_name!r} is {type(v).__name__}, expected TruthTable"
            )
        return v

    # ----- assertion helpers ---------------------------------------------

    def assert_quantity_in(
        self,
        q: Quantity,
        lo: "pint.Quantity | Quantity | float",
        hi: "pint.Quantity | Quantity | float",
        *,
        name: str | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> TestResult:
        """Check that every corner of ``q`` lies within ``[lo, hi]``."""
        lo_f = _coerce_to_unit(lo, q.unit)
        hi_f = _coerce_to_unit(hi, q.unit)
        failed: list[ScenarioMode] = []
        for scenario, mode, value in q.iter_axes():
            v_lo, v_hi = _as_range(value)
            if v_lo < lo_f or v_hi > hi_f:
                failed.append(ScenarioMode(scenario=scenario, mode=mode))
        return self._make_result(
            name=name,
            passed=not failed,
            failed_at=tuple(failed),
            evidence=dict(evidence) if evidence else {},
        )

    def assert_quantity_below(
        self,
        q: Quantity,
        upper: "pint.Quantity | Quantity | float",
        *,
        name: str | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> TestResult:
        """Check that every corner of ``q`` is ``<= upper``."""
        u = _coerce_to_unit(upper, q.unit)
        failed: list[ScenarioMode] = []
        for scenario, mode, value in q.iter_axes():
            _, v_hi = _as_range(value)
            if v_hi > u:
                failed.append(ScenarioMode(scenario=scenario, mode=mode))
        return self._make_result(
            name=name,
            passed=not failed,
            failed_at=tuple(failed),
            evidence=dict(evidence) if evidence else {},
        )

    def assert_quantity_above(
        self,
        q: Quantity,
        lower: "pint.Quantity | Quantity | float",
        *,
        name: str | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> TestResult:
        """Check that every corner of ``q`` is ``>= lower``."""
        lo = _coerce_to_unit(lower, q.unit)
        failed: list[ScenarioMode] = []
        for scenario, mode, value in q.iter_axes():
            v_lo, _ = _as_range(value)
            if v_lo < lo:
                failed.append(ScenarioMode(scenario=scenario, mode=mode))
        return self._make_result(
            name=name,
            passed=not failed,
            failed_at=tuple(failed),
            evidence=dict(evidence) if evidence else {},
        )

    def assert_truth_table_matches(
        self,
        actual: "TruthTable",
        expected: "TruthTable",
        *,
        name: str | None = None,
        evidence: Mapping[str, Any] | None = None,
    ) -> TestResult:
        """Check that ``actual`` matches ``expected`` row-for-row.

        Each row where they differ contributes one entry to ``TestResult.failed_at``
        — the row is encoded as a ``ScenarioMode(scenario=str(inputs_dict), mode=None)``
        so the existing per-test formatters (`format_results`, the HTML / PR-comment
        tables) can render it without special-casing logic tests. Logic blocks
        aren't axis-keyed in the analog sense, so ``scenario`` is just a label
        identifying the offending input combination.
        """
        from framework.logic import compare_truth_tables  # local: avoid cycle

        mismatches = compare_truth_tables(actual, expected)
        failed: list[ScenarioMode] = []
        for m in mismatches:
            # Render inputs as a stable, sorted, compact label so the
            # rendered tables stay readable.
            label = ",".join(f"{k}={int(v)}" for k, v in sorted(m.inputs.items()))
            failed.append(ScenarioMode(scenario=label, mode=None))
        ev = dict(evidence) if evidence else {}
        ev.setdefault("actual_table", actual)
        ev.setdefault("expected_table", expected)
        return self._make_result(
            name=name,
            passed=not failed,
            failed_at=tuple(failed),
            evidence=ev,
        )

    # ----- helpers --------------------------------------------------------

    def _make_result(
        self,
        *,
        name: str | None,
        passed: bool,
        failed_at: tuple[ScenarioMode, ...],
        evidence: dict[str, Any],
    ) -> TestResult:
        if name is None:
            name = self._meta.name if self._meta else "unnamed"
        if self._meta is not None:
            severity = self._meta.severity
            requirement = self._meta.requirement
            block = self._meta.block
        else:
            severity = Severity.CRITICAL
            requirement = None
            block = ""
        return TestResult(
            name=name,
            passed=passed,
            severity=severity,
            failed_at=failed_at,
            evidence=evidence,
            requirement=requirement,
            block=block,
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_verifications(
    modules: list[types.ModuleType],
    results: Mapping[str, Any],
) -> dict[str, TestResult]:
    """Discover and run every ``@verification_test`` in ``modules``.

    Each function is invoked with a freshly-built ``VerificationContext``
    bound to ``results``. The returned dict is keyed by the test's
    declared ``name`` (so renaming a function doesn't break dashboards).
    Duplicate names raise ``ValueError``.

    9a runs every test serially; severity / modes / scenarios on
    :class:`VerificationMeta` are captured into the result but don't yet
    filter execution. The pytest plugin (step 9b) will respect them.
    """
    out: dict[str, TestResult] = {}
    for module in modules:
        for attr in dir(module):
            if attr.startswith("_"):
                continue
            obj = getattr(module, attr, None)
            if not is_verification_test(obj):
                continue
            if getattr(obj, "__module__", None) != module.__name__:
                continue
            meta = get_verification_meta(obj)
            assert meta is not None
            if meta.name in out:
                raise ValueError(
                    f"Duplicate verification-test name {meta.name!r} "
                    f"(in {obj.__module__!r})"
                )
            ctx = VerificationContext(results, meta=meta)
            result = obj(ctx)
            if not isinstance(result, TestResult):
                raise TypeError(
                    f"Verification test {meta.function_name!r} returned "
                    f"{type(result).__name__}, expected framework.TestResult"
                )
            out[meta.name] = result
    return out


def format_results(results: Mapping[str, TestResult]) -> str:
    """One-line-per-test markdown summary, sorted FAIL first."""
    if not results:
        return "(no verification tests run)"
    rows = sorted(results.values(), key=lambda r: (r.passed, r.name))
    return "\n".join(r.summary() for r in rows)


# ---------------------------------------------------------------------------
# pytest integration (step 9b)
# ---------------------------------------------------------------------------


def collect_verification_tests(modules: list[types.ModuleType]) -> list[Callable[..., TestResult]]:
    """Discover every ``@verification_test`` function in ``modules``.

    Returns them in (block, name) order for stable pytest test-IDs across
    runs. Use with ``pytest.mark.parametrize`` to expand them into one
    pytest item per test::

        TESTS = collect_verification_tests([blocks.can_transceiver.verifications])

        @pytest.mark.parametrize(
            "test_fn", TESTS,
            ids=lambda f: f.__verification_meta__.name,
        )
        def test_verification(test_fn, verification_results):
            run_verification_for_pytest(test_fn, verification_results)
    """
    tests: list[tuple[str, str, Callable[..., TestResult]]] = []
    for module in modules:
        for attr in dir(module):
            if attr.startswith("_"):
                continue
            obj = getattr(module, attr, None)
            if not is_verification_test(obj):
                continue
            if getattr(obj, "__module__", None) != module.__name__:
                continue
            meta = get_verification_meta(obj)
            assert meta is not None
            tests.append((meta.block, meta.name, obj))
    tests.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in tests]


def run_verification_for_pytest(
    test_fn: Callable[..., TestResult],
    results: Mapping[str, Any],
) -> TestResult:
    """Run one ``@verification_test`` and map failure to pytest's verdict.

    Severity ``CRITICAL`` → ``pytest.fail`` (hard fail, CI breaks).
    Severity ``WARNING``  → ``pytest.xfail`` (expected failure, CI green).
    Severity ``INFO``     → ``pytest.skip`` (informational, CI green).
    Passes return the ``TestResult`` for inspection.

    pytest is an optional import — only required if you actually call this.
    """
    if not is_verification_test(test_fn):
        raise TypeError(
            f"{test_fn!r} is not a @verification_test (missing marker)."
        )
    meta = get_verification_meta(test_fn)
    assert meta is not None
    ctx = VerificationContext(results, meta=meta)
    result = test_fn(ctx)
    if not isinstance(result, TestResult):
        raise TypeError(
            f"Verification test {meta.function_name!r} returned "
            f"{type(result).__name__}, expected framework.TestResult"
        )
    if result.passed:
        return result

    corners = "; ".join(str(c) for c in result.failed_at) or "(unspecified)"
    msg = f"{result.name} failed at: {corners}"
    if meta.requirement:
        msg = f"[{meta.requirement}] {msg}"

    import pytest  # imported here so 'pytest' is optional for non-test users
    if result.severity is Severity.INFO:
        pytest.skip(msg)
    elif result.severity is Severity.WARNING:
        pytest.xfail(msg)
    else:
        pytest.fail(msg, pytrace=False)
    return result  # unreachable; satisfies the type checker


__all__ = [
    "ScenarioMode",
    "Severity",
    "TestResult",
    "VerificationContext",
    "VerificationMeta",
    "collect_verification_tests",
    "format_results",
    "get_verification_meta",
    "is_verification_test",
    "run_verification_for_pytest",
    "run_verifications",
    "verification_test",
]
