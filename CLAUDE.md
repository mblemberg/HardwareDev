# hw_analysis_framework — for Claude Code sessions

The framework package itself. Code for the core types (`Quantity`, `Scenario`, `Mode`, `Requirement`, `Project`) plus the Hamilton DAG runner.

**Authoritative spec:** `../hardware_analysis_framework_design.md`. Section map in user memory (`reference_design_doc.md`). Always read the relevant section before changing core abstractions.

## Mental model in one diagram

```
scenarios.toml  ─┐    Scenario(by_scenario)  ──┐
modes.toml      ─┼──▶ Mode                     │
requirements.py ─┘    Requirement              │
                                               ▼
       leaf functions in blocks/<x>/leaves.py  ─┐
       derived functions in blocks/<x>/analysis ─┤──▶ Hamilton DAG ──▶ results: dict[str, Quantity]
                                                ─┘                               │
                                                                                 ▼
                                                                       .within(lo, hi) spec checks
                                                                  (eventually: VerificationTest, step 9)
```

Every value is a `Quantity` — unit-bearing, immutable, can vary on `by_scenario` (inner axis) and/or `by_mode` (outer axis). Arithmetic propagates axes automatically; no per-corner bookkeeping.

## Things that bite (in order of how often I've hit them)

### 1. Pint offset units (degC, degF)
Three operations Pint refuses on offset units:
- `25 * degC` (`Unit.__rmul__`) → `OffsetUnitCalculusError`
- `registry.Quantity("25 degC")` (single-arg string) → same
- `registry.parse_expression("25 degC")` → same

Use one of:
- `registry.Quantity(25, "degC")` (two-arg form — what `framework._toml.parse_pint` uses internally after a regex split)
- `Constant(25, degC)` (framework factory — accepted everywhere `pint.Quantity` is)
- `"25 degC"` (string — accepted by TOML loaders and requirement validators)

### 2. Absolute-vs-delta temperature math
`Quantity(unit=degC) + Quantity(unit=K)` does **not** do what you want. Pint treats both as absolute and combines them absolutely (`25 °C + 40 K = 25 + (40 - 273.15)`). For thermal-rise math, convert ambient to K explicitly:
```python
def t_j(ambient_temp, thermal_rise):
    return (ambient_temp.to(K) + thermal_rise).to(degC)
```
See `tests/fixtures/blocks/sample_block/analysis.py` for the pattern.

### 3. Pydantic v2 validator exceptions
Validators must raise `ValueError` (not `TypeError`) for the failure to be wrapped in a `ValidationError`. `TypeError` propagates raw and bypasses the framework's error formatting. The `_coerce` helper in `requirements.py` got bitten by this and was rewritten — see the comment block there.

### 4. Hamilton wires by parameter name
`def power(v_supply: Quantity, i_supply: Quantity)` pulls the nodes named exactly `v_supply` and `i_supply`. Rename the function and every consumer's parameter name has to update too. No magic — just literal name matching.

### 5. `Project.standard_inputs()` only extracts intersection-of-keys
Scenario context keys that appear in *every* loaded scenario become auto-supplied Hamilton inputs (typically `ambient_temp`, `vbat`). Block-specific keys (only on some scenarios) don't — call `scenarios.as_quantity(key)` explicitly.

### 6. NotebookEdit vs VS Code auto-save
If a `.ipynb` is open in VS Code, VS Code will auto-save its in-memory copy and clobber NotebookEdit changes. Ask the user to close the notebook before editing.

### 7. `Project.run` runs the contract consistency check automatically
After Hamilton executes, every `@contract` with `compares_to=<actual node>` is compared against the named actual at every (scenario, mode) point — `ContractViolation` is raised on the first mismatch. The framework auto-augments the run targets so the contract and its actual both end up in `results` even when the caller only asks for one. Pass `check_contracts=False` to bypass (debugging only). For unit tests of partial results without that wiring, call `check_contract_consistency(modules, results)` directly — it skips missing targets unless you pass `strict=True`.

### 8. `@verification_test` is a marker — `run_verifications()` discovers it, NOT Hamilton
Verification-test functions take a single `ctx: VerificationContext` and return a `TestResult`. They don't participate in the DAG. Discovery is module-scan only: `run_verifications([modules...], results_from_project_run)`. Tests are keyed by their declared `name=` (not the function name), so renaming the function doesn't break dashboards. Duplicate names raise. `TestResult` carries a `__test__ = False` flag so pytest doesn't try to collect the dataclass itself as a test class.

### 9. `Quantity.iter_axes()` is the cross-axis iteration primitive
Yields `(scenario, mode, value)` for every leaf in the by_mode × by_scenario × nominal axis tree. Used by both the contract-consistency check (step 8) and verification assertion helpers (step 9a) to enumerate failing corners. Promoted from a private `_iter_axes` in `contract.py` when 9a needed it too — when you want "do something at every (scenario, mode) point this Quantity carries", use this.

## Dev workflow

```powershell
# from this directory:
poetry install -E "dev notebooks"
poetry run pytest                       # 264 tests as of step 9a
poetry run pytest --cov                 # coverage report
poetry run mypy                         # strict on src/framework
```

The venv lives at `.venv/` (Poetry `virtualenvs.in-project = true`). Point Jupyter / VS Code kernels at `.venv/Scripts/python.exe`.

`tests/conftest.py` adds `tests/fixtures/blocks/` to `sys.path` so fixture blocks import as top-level packages (mirroring how a real analysis-project's `blocks/` works).

## File layout

```
src/framework/
  __init__.py       # curated re-exports — every public symbol lives in __all__
  quantity.py       # Quantity, Constant, RangeQuantity, arithmetic
  units.py          # single shared Pint registry
  scenarios.py      # Scenario, ScenarioSet, load_scenarios
  modes.py          # Mode, ModeSet, load_modes
  requirements.py   # Requirement base + TempRange / SupplyEnvelope / CurrentBudget / Performance + registry
  project.py        # Project orchestrator + Hamilton driver
  contract.py       # @contract + ContractMeta + detect_cycles + check_contract_consistency
  component.py      # Component base + coerce_field_quantity validator
  verification.py   # @verification_test + TestResult + VerificationContext + run_verifications
  cache.py / _hashing.py  # content-addressed cache for DAG nodes
  provenance.py     # ProvenanceRef stub (full impl is step 10)
  _toml.py          # internal: Pint-string parsing with precise error locations
tests/
  fixtures/blocks/<name>/{leaves,analysis}.py
  test_*.py
```

## Don'ts

- Don't import `pint.UnitRegistry` directly anywhere. There is **one** registry, exposed as `framework.units.registry`. Mixing registries makes units silently incompatible.
- Don't use `25 * degC` syntax for offset-unit construction. See gotcha #1.
- Don't raise `TypeError` from a Pydantic validator. See gotcha #3.
- Don't pass raw `float`/`int` where a `pint.Quantity` is expected — call sites enforce explicit units. (Plain numbers are sometimes accepted in additive arithmetic on the framework `Quantity`, but only for convenience and only as same-unit-implied magnitudes.)
- Don't introduce a new requirement subclass unless two or more requirements share a non-trivial cross-field invariant. `Performance` is the escape hatch for one-off scalars.

## When changing core abstractions

1. Read the relevant design doc section first (6.1 Quantity, 6.4 Requirement, 7 DAG, etc.).
2. If the design is wrong, surface that — don't silently diverge.
3. Update tests in the same commit.
4. Coverage target: 90%+ on framework, 100% on `Quantity` arithmetic (design doc 16).
