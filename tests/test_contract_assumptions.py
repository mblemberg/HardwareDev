"""Cross-block assumed-input validation (design doc 6.7 / second half)."""
from __future__ import annotations

import pytest

from framework import (
    Constant,
    ContractMismatch,
    ContractViolation,
    Project,
    Quantity,
    RangeQuantity,
    check_contract_assumptions,
    contract,
)
from framework.modes import ModeSet
from framework.scenarios import ScenarioSet
from framework.units import V, mA


def _empty_project() -> Project:
    return Project(
        scenarios=ScenarioSet(scenarios=[]),
        modes=ModeSet(modes=[]),
        cache_dir=None,
    )


# ---------------------------------------------------------------------------
# Direct calls with hand-built results
# ---------------------------------------------------------------------------


class TestDirectCheck:
    def test_assumption_holds_no_mismatch(self) -> None:
        from assumptions_ok_block import contracts, leaves
        results = {
            "my_draw":       contracts.my_draw(),
            "upstream_rail": leaves.upstream_rail(),
        }
        assert check_contract_assumptions([leaves, contracts], results) == []

    def test_assumption_violated_returns_mismatch(self) -> None:
        from assumptions_bad_block import contracts, leaves
        results = {
            "my_draw":      contracts.my_draw(),
            "sagging_rail": leaves.sagging_rail(),
        }
        mismatches = check_contract_assumptions([leaves, contracts], results)
        assert len(mismatches) == 1
        m = mismatches[0]
        assert m.kind == "assumed"
        assert "sagging_rail" in m.contract_name
        # actual lo (4.40) is below assumed lo (4.75)
        assert m.actual == (4.40, 5.10)
        assert m.declared == (4.75, 5.25)

    def test_non_quantity_entry_skipped(self) -> None:
        """Informational `assumed_inputs` (raw tuples, strings) are skipped."""
        import types
        mod = types.ModuleType("info_only.contracts")

        @contract(
            description="x",
            assumed_inputs={"foo": (4.75, 5.25)},  # raw tuple, not a Quantity
        )
        def c() -> Quantity:
            return RangeQuantity(0.0, 1.0, mA)

        c.__module__ = "info_only.contracts"
        mod.c = c
        results = {"c": c(), "foo": Constant(10.0, V)}  # would violate if checked
        assert check_contract_assumptions([mod], results) == []

    def test_missing_key_lenient_default(self) -> None:
        from assumptions_ok_block import contracts, leaves
        # Drop the assumed-input key from results.
        results = {"my_draw": contracts.my_draw()}
        assert check_contract_assumptions([leaves, contracts], results) == []

    def test_missing_key_strict_raises(self) -> None:
        from assumptions_ok_block import contracts, leaves
        results = {"my_draw": contracts.my_draw()}
        with pytest.raises(ValueError, match="upstream_rail"):
            check_contract_assumptions([leaves, contracts], results, strict=True)

    def test_wrong_type_strict_raises(self) -> None:
        from assumptions_ok_block import contracts, leaves
        # upstream_rail key present but not a Quantity.
        results = {"my_draw": contracts.my_draw(), "upstream_rail": "not a quantity"}
        with pytest.raises(TypeError, match="expected Quantity"):
            check_contract_assumptions([leaves, contracts], results, strict=True)


# ---------------------------------------------------------------------------
# ContractMismatch.kind round-trip + format_mismatches
# ---------------------------------------------------------------------------


class TestMismatchKind:
    def test_default_kind_is_declared(self) -> None:
        m = ContractMismatch(
            contract_name="c", block="b", scenario=None, mode=None,
            actual=1.0, declared=0.5, unit="mA",
        )
        assert m.kind == "declared"

    def test_format_uses_assumed_word(self) -> None:
        from framework.contract import format_mismatches
        m = ContractMismatch(
            contract_name="c.assumed[rail]", block="b", scenario=None, mode=None,
            actual=(4.40, 5.10), declared=(4.75, 5.25), unit="V",
            kind="assumed",
        )
        out = format_mismatches([m])
        assert "assumed=" in out
        assert "declared=" not in out  # only the assumed flavor in this output


# ---------------------------------------------------------------------------
# End-to-end via Project.run
# ---------------------------------------------------------------------------


class TestProjectRunIntegration:
    def test_passing_assumption_runs_clean(self) -> None:
        from assumptions_ok_block import contracts, leaves
        out = _empty_project().run(
            modules=[leaves, contracts], targets=["my_draw"],
        )
        assert "my_draw" in out

    def test_violated_assumption_raises_contract_violation(self) -> None:
        from assumptions_bad_block import contracts, leaves
        with pytest.raises(ContractViolation) as exc_info:
            _empty_project().run(modules=[leaves, contracts], targets=["my_draw"])
        # The violation message identifies the assumption flavor and the
        # offending bound.
        v = exc_info.value
        assert any(m.kind == "assumed" for m in v.mismatches)
        assert "sagging_rail" in str(v)

    def test_check_off_skips(self) -> None:
        from assumptions_bad_block import contracts, leaves
        out = _empty_project().run(
            modules=[leaves, contracts],
            targets=["my_draw"],
            check_contracts=False,
        )
        assert "my_draw" in out
