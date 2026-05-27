# example_analysis — for Claude Code sessions

A reference analysis project. The user-facing side of `hw_analysis_framework`: how an engineer's actual board project consumes the framework.

**Authoritative spec:** `../hardware_analysis_framework_design.md`, especially section 6.6 (Block layout) and Appendix A (Mike/Dan Contract loop). Section map in user memory (`reference_design_doc.md`).

## What this repo is for

- Worked example of the canonical block layout (`blocks/<name>/{leaves,analysis,...}`).
- Source-of-truth for the project-level config: `project/scenarios.toml`, `project/modes.toml`, `project/requirements.py`.
- Integration test for the framework — when something breaks here, the framework's surface is wrong.

Section 17 of the design doc calls this out explicitly: *"a reference analysis project (`example_analysis`) exercising every feature, used as both documentation and integration test."*

## Layout

```
project/
  __init__.py
  scenarios.toml         # operating corners                (design doc 6.2)
  modes.toml             # system modes                     (design doc 6.3)
  requirements.py        # Jama-linked design constraints   (design doc 6.4)
blocks/
  __init__.py
  can_transceiver/       # one subpackage per block         (design doc 6.6)
    __init__.py
    leaves.py            # hand-coded leaf Quantities (datasheet values, mode-dependent currents)
    analysis.py          # derived nodes; Hamilton wires by parameter name
    contracts.py         # public Contracts (declared bounds) — design doc 6.7
    verifications.py     # @verification_test functions — design doc 6.8 / step 9a
  mcu/                   # second block — STM32G0 application MCU
    {leaves,analysis,contracts,verifications}.py
  power_supply/          # third block — NCP1117 linear regulator (publishes rail_5v)
    {leaves,analysis,contracts,verifications}.py
tests/
  conftest.py            # session-scoped project_results fixture (runs all 3 blocks)
  test_verifications.py  # parametrizes over every block's @verification_test (step 9b)
system_analysis.ipynb    # three-block end-to-end demo: load project, run DAG, render reports
```

## Kernel + venv

The notebook does **not** have its own venv. It uses the framework's:

```
../hw_analysis_framework/.venv/Scripts/python.exe
```

Point VS Code's Jupyter kernel selector at that path. The framework is editable-installed in there, so `from framework import Project` and `from blocks.can_transceiver import leaves, analysis` both resolve.

## How a new block lands

1. Create `blocks/<name>/{__init__.py, leaves.py, analysis.py}`.
2. In `leaves.py`, write functions returning leaf Quantities. Parameters can pull from project-supplied inputs (`ambient_temp`, `vbat`) or from inputs you'll pass to `project.run(...)` (e.g., a `Requirement` object).
3. In `analysis.py`, write functions whose parameter names match either other functions' names (= depends on those) or project inputs. Hamilton wires them.
4. From a notebook or script: `project.run(modules=[<name>.leaves, <name>.analysis], targets=[...], inputs={...})`.
5. Add `contracts.py` for cross-block consumption — each Contract returns its *declared* bound and points `compares_to="<actual node>"` at the local computed value. `Project.run` auto-verifies actual ⊆ declared per scenario/mode and raises `ContractViolation` on mismatch.
6. Add `verifications.py` for formal spec checks — each `@verification_test` takes a `VerificationContext`, calls `ctx.assert_quantity_below(...)` (or `_in` / `_above`), returns a `TestResult` listing the exact (scenario, mode) corners where it failed. Run with `run_verifications([verifications], results)`.
7. (Future) `report.ipynb` from the template (step 12).

## Patterns worth knowing

### Scenario-scoped requirements
For requirements that derate by environmental corner (ADC accuracy at -40 / 25 / 85 °C), declare one `Performance` per corner with `applies_to_scenario="..."`. Each gets its own Jama ID (`REQ-PERF-001a` / `-001b` / `-001c`). Matches Jama's grain. See `project/requirements.py` for the worked pattern.

### Sourcing leaf values from requirements
A block's leaf can take a project-level `Requirement` as a Hamilton input — pass the actual `SupplyEnvelope` / `TempRange` / etc. into `project.run(inputs={...})` and wire it through the parameter name. This is the pattern when a block's supply tolerance or environmental envelope should track a Jama requirement directly. In the current three-block project, the 5V rail flows from project requirement `RAIL_5V` → published as the power-supply block's `rail_5v` Contract → consumed by CAN and MCU blocks via the Contract (cycle-cut rule, design doc 6.7).

### Block-name prefixing for DAG nodes (Hamilton uses a flat namespace)
Hamilton wires DAG nodes by parameter name into a single flat namespace. When multiple blocks exist in the same project, every block-local node name must be unique across all blocks — two functions named `t_j` (one in CAN, one in MCU) would collide and Hamilton would refuse to build. Prefix every block-local node with the block name (`can_t_j`, `mcu_t_j`, `psu_t_j`) so cross-block targeting is unambiguous and the project DAG stays composable. Contracts can keep semantically meaningful names (`rail_5v`, `can_5v_draw`, `mcu_5v_draw`) since they're already block-scoped semantically.

### Separating DAG modules from verification modules
`project.run(modules=...)` should receive only `{leaves, analysis, contracts}` — passing `verifications` modules in causes Hamilton to see `@verification_test` functions as DAG nodes (they take a `ctx` arg, which leaks as an extra input node). `run_verifications(modules, results)` should receive the `verifications` modules; the notebook and conftest pattern is to keep two lists (`DAG_MODULES` / `VERIFICATION_MODULES`) and pass each to the appropriate call. The report renderers (`block_report_html`, `project_report_html`) take the DAG modules — they walk for `@contract`-marked functions only.

### Thermal math: ambient to K first
`(ambient_temp.to(K) + thermal_rise).to(degC)` — see `blocks/can_transceiver/analysis.py::t_j`. Adding `degC + K` directly does the wrong thing because Pint treats both as absolutes. (See the framework's CLAUDE.md, gotcha #2.)

### Declared-vs-actual pattern in Contracts
A `@contract` function returns the *declared* commitment (typically a mode-keyed range with headroom above the datasheet maxes). The matching `compares_to="<actual node>"` names the local DAG node that computes the *actual* — usually a leaf or an `analysis.py` function. `Project.run` runs the consistency check automatically after Hamilton execute and raises `ContractViolation` on the first mismatch. See `blocks/can_transceiver/contracts.py::can_5v_draw` for the worked pattern.

### `@verification_test` is the formal version of a manual `.within(...)` check
Where `Quantity.within(lo, hi)` returns just `True`/`False`, a `@verification_test` carries a name, Jama requirement ID, severity, and returns a `TestResult` listing the exact failing corners. The runner is `run_verifications([verifications], results)`. The same definition feeds:
- pytest (step 9b): `tests/test_verifications.py` parametrizes over `collect_verification_tests([...])`; each test gets its own pytest item with severity-aware verdicts (`pytest.fail` / `xfail` / `skip`).
- output channels (step 9c): `results_to_html_table` / `results_to_markdown_table` / `results_to_pr_comment` / `results_to_jama_records`.

Notebook section 6 demonstrates the HTML table + PR-comment render. The thermal verification is *designed to fail* (it surfaces the T_J overshoot at `hot_high_vin / {active, diagnostic}` — the worked example's headline failure) — `pytest tests/` will exit non-zero until the design is derated, which is the correct CI signal.

### Adding a new block's verifications
1. Write `blocks/<name>/verifications.py` with `@verification_test` functions.
2. Add an import to `tests/test_verifications.py::_all_block_verifications` so the parametrize sees it. (Manual for now — auto-discovery is a small follow-on if multiple blocks land.)

### Block ownership: one engineer per page, one publisher per physical thing
Each schematic page has one owner. That owner's block is the **only place** Contracts get published about nets and components that primarily live on that page. If you want to declare `vout_3v3` and the buck regulator sits on someone else's page, the contract belongs in *their* block — talk to them, don't fork the analysis. Multi-page nets (a bus crossing pages) require a human pick on which block owns the contract.

This is what prevents two engineers from independently publishing disagreeing analyses of the same physical rail. The framework's cycle-cut rule constrains *consumption* (you can't reach past another block's contract); the ownership rule constrains *production* (you can't publish contracts about another block's physical things). Until step 6 (netlist parser) lands and ownership becomes mechanically enforceable via refdes-to-block mapping, this is a code-review concern.

When in doubt about a multi-page net, pick the page where the net is most *defined* (the page that creates it / sets its voltage), not the pages it merely passes through.

## Don'ts

- Don't define `__init__.py` content beyond re-exports. Per design doc 6.6, `blocks/<name>/__init__.py` re-exports public Contracts and **nothing else**. Internals stay private.
- Don't import another block's non-Contract symbols. The cycle detector refuses imports of non-Contract names across blocks (build-time, before `project.run`).
- Don't publish Contracts about another block's nets or components — see the ownership rule above. Talk to the owner instead.
- Don't hand-edit the cached state in `.framework_cache/` — it's content-addressed; the framework owns it.

## Verifying changes locally

```powershell
# from this directory:
../hw_analysis_framework/.venv/Scripts/python.exe -m jupyter nbconvert `
    --to notebook --execute system_analysis.ipynb `
    --output system_analysis.ipynb
```

The notebook executes end-to-end and bakes outputs back in. If it fails, the framework probably has a real bug — example_analysis exists to surface those. Designed-to-fail thermal verifications (CAN + MCU + PSU at `hot_high_vin`) are expected; an `nbconvert` exit code of 0 plus three FAIL rows in the verification table is the correct steady state.
