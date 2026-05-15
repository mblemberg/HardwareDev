# example_analysis — for Claude Code sessions

A reference analysis project. The user-facing side of `hw_analysis_framework`: how an engineer's actual board project consumes the framework.

**Authoritative spec:** `../hardware_analysis_framework_design.md`, especially section 6.6 (Block layout) and Appendix A (Mike/Dan Contract loop). Section map in user memory (`reference_design_doc.md`).

## What this repo is for

- Worked example of the canonical block layout (`blocks/<name>/{leaves,analysis,...}`).
- Source-of-truth for the project-level config: `project/scenarios.toml`, `project/modes.toml`, `project/requirements.py`.
- Integration test for the framework — when something breaks here, the framework's surface is wrong.

Section 16 of the design doc calls this out explicitly: *"a reference analysis project (`example_analysis`) exercising every feature, used as both documentation and integration test."*

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
    # future: verifications.py (step 9), report.ipynb (step 12)
can_transceiver_analysis.ipynb   # end-to-end demo: load project, run DAG, render results
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
6. (Future) `verifications.py` for spec checks (step 9), `report.ipynb` from the template (step 12).

## Patterns worth knowing

### Scenario-scoped requirements
For requirements that derate by environmental corner (ADC accuracy at -40 / 25 / 85 °C), declare one `Performance` per corner with `applies_to_scenario="..."`. Each gets its own Jama ID (`REQ-PERF-001a` / `-001b` / `-001c`). Matches Jama's grain. See `project/requirements.py` for the worked pattern.

### Sourcing leaf values from requirements
`leaves.v_supply(can_5v_rail) -> Quantity` takes `can_5v_rail` as a Hamilton input, then `project.run(inputs={"can_5v_rail": CAN_5V_RAIL})` passes the actual `SupplyEnvelope`. This wires REQ-PWR-005 directly into the block's supply tolerance without hard-coding numbers.

### Thermal math: ambient to K first
`(ambient_temp.to(K) + thermal_rise).to(degC)` — see `blocks/can_transceiver/analysis.py::t_j`. Adding `degC + K` directly does the wrong thing because Pint treats both as absolutes. (See the framework's CLAUDE.md, gotcha #2.)

### Declared-vs-actual pattern in Contracts
A `@contract` function returns the *declared* commitment (typically a mode-keyed range with headroom above the datasheet maxes). The matching `compares_to="<actual node>"` names the local DAG node that computes the *actual* — usually a leaf or an `analysis.py` function. `Project.run` runs the consistency check automatically after Hamilton execute and raises `ContractViolation` on the first mismatch. See `blocks/can_transceiver/contracts.py::can_5v_draw` for the worked pattern.

## Don'ts

- Don't define `__init__.py` content beyond re-exports. Per design doc 6.6, `blocks/<name>/__init__.py` will re-export public Contracts (step 7) and **nothing else**. Internals stay private.
- Don't import another block's non-Contract symbols. The future cycle detector (step 7) will refuse imports of non-Contract names across blocks.
- Don't hand-edit the cached state in `.framework_cache/` once step 4b lands — it's content-addressed; the framework owns it.

## Verifying changes locally

```powershell
# from this directory:
../hw_analysis_framework/.venv/Scripts/python.exe -m jupyter nbconvert `
    --to notebook --execute can_transceiver_analysis.ipynb `
    --output can_transceiver_analysis.ipynb
```

The notebook executes end-to-end and bakes outputs back in. If it fails, the framework probably has a real bug — example_analysis exists to surface those.
