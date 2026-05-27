# Project status

**Date:** 2026-05-26

> ⚠️ **Trust state:** the implementation table below reflects what's been *built*, not what's been *reviewed*. As of 2026-05-26 the framework is in a structured **review-and-refine phase** — a single large vibe-coded build sprint produced everything shipped to date, and we're now going back layer by layer to verify each piece against the design doc, tighten correctness, and earn explicit sign-off. Trusted state advances by merging `review/phaseN` branches into `main` and tagging (`v0.1-foundation` for Phase 1, etc.). Until tagged, code on `main` is "shipped but unverified." See workspace `CLAUDE.md` for the workflow and the active Phase 1 step list.

Hardware analysis framework. Three sibling repos under this workspace. Authoritative spec: [`hardware_analysis_framework_design.md`](hardware_analysis_framework_design.md).

> Worked example expanded to three blocks (`power_supply` + `mcu` + `can_transceiver`) — see [`example_analysis/system_analysis.ipynb`](example_analysis/system_analysis.ipynb).

## Section 15 implementation progress

| # | Step | Status | Notes |
|---|------|--------|-------|
| 1 | Quantity + Pint + arithmetic | ✅ shipped | Step-1 follow-ups outstanding: 100% coverage on arithmetic (currently 93%); Pint-expression auto-lift sugar deferred (needs custom unit shim). |
| 2 | Scenario + Mode + TOML loaders | ✅ shipped | |
| 3 | Requirements registry + typed types | ✅ shipped | `TempRange`, `SupplyEnvelope`, `CurrentBudget`, `Performance` + uniform `applies_to_mode` / `applies_to_scenario` scoping on the base. |
| 4a | Hamilton DAG integration + `Project` runner | ✅ shipped | `Project.load` + `run(modules, targets, inputs)` + `list_nodes`. Standard inputs auto-derived from scenario context intersection. |
| 4b | Content-addressed caching | ✅ shipped | Hash = sha256(framework version + function source + sorted ancestor hashes). Hits supplied via Hamilton `overrides=`, misses written back via `NodeExecutionHook`. Local pickle storage; pint `set_application_registry` so unpickled units stay attached to our singleton. |
| 5 | Component library | ✅ shipped | `framework.Component` base + `coerce_field_quantity` validator; concrete types (`Resistor`, `Capacitor`, `MOSFET`, `BJT`, `Diode`, `LDO`, `BuckConverter`, `IntegratedCircuit`) + enums (`SmtSize`, `Dielectric`); two parametric families (`ERJ3`, `GRM_X7R`); two real instances (`TJA1051T_3`, `IRLML6344`). Example refactored to source from `TJA1051T_3`. |
| 6 | Netlist parser (Protel ASCII) + block ownership | ⏳ pending | |
| 7 | Contract type + graph-build cycle detection | ✅ shipped | `@contract` decorator + `ContractMeta` + `detect_cycles(modules)` + `CycleViolation`. Block detection from `__module__`. Contracts are cut-points: cross-block deps via a Contract stop the walk. Auto-called by `Project.run`. |
| 8 | Run-time contract consistency checker | ✅ shipped | `compares_to=<actual node>` parameter on `@contract` + `ContractViolation` + `check_contract_consistency()` + `ContractMismatch`. Auto-runs in `Project.run` after Hamilton execute; raises on mismatch with per-mode/scenario diffs. Pass `check_contracts=False` to skip. |
| 8b | Cross-block assumed-input validation | ✅ shipped | `check_contract_assumptions()` validates Quantity-valued `assumed_inputs` entries against their named DAG node's actual at every (scenario, mode). `ContractMismatch.kind` distinguishes `"declared"` (step 8) from `"assumed"` (this). Project.run auto-augments targets so the assumed key gets computed even when nothing downstream needs it. Informational (non-Quantity) entries skipped silently. |
| 9a | VerificationTest foundation: decorator + TestResult + runner | ✅ shipped | `@verification_test` + `Severity` + `ScenarioMode` + `TestResult` + `VerificationContext` (with `quantity()` / `assert_quantity_in/below/above`) + `run_verifications(modules, results)` + `format_results()`. Pure marker (Hamilton doesn't see them); discovered by module scan; results keyed by declared `name`. |
| 9b | pytest helpers | ✅ shipped | `collect_verification_tests(modules)` + `run_verification_for_pytest(test_fn, results)`. User writes a ~15-line `tests/test_verifications.py` that parametrizes over the collection; pytest fails per-test. Severity → `pytest.fail` (CRITICAL) / `xfail` (WARNING) / `skip` (INFO). |
| 9c | Output channels | ✅ shipped | `results_to_markdown_table` (CI step summaries / READMEs) + `results_to_html_table` (notebook display, with row coloring) + `results_to_pr_comment` (GitHub markdown with `<details>` collapsibles) + `results_to_jama_records` (list of plain dicts ready for JSON / Jama push). `TestResult` carries `requirement` and `block` so Jama records are self-contained. |
| 10 | Provenance chain traversal | ✅ shipped | `ProvenanceGraph` + `ProvenanceNodeInfo` + extended `ProvenanceRef.parents()` / `chain(max_depth=100)` / `chain_summary()`. `Project.run` builds the graph per invocation and attaches refs to every result Quantity (recursive through `by_mode` children). Walks are memoized on the graph. BFS-ordered chain with cycle-set safeguard + depth-limit warning + truncation sentinel. Pass `attach_provenance_to_results=False` to skip the attach. |
| 11 | Standard analyses library | 🟡 partial | v1 ships `voltage_divider` (scalar or parallel-list inputs), `rc_filter_cutoff` (R and C accept lists → paralleled), `mosfet_thermal_rise` (conduction losses with optional duty cycle), `parallel_resistance` / `series_resistance` / `parallel_capacitance` / `series_capacitance` helpers — all unit- and axis-propagating. `worst_case_droop`, `current_limit_check`, generic `power_dissipation` / `thermal_rise` deferred. Latent `_binop` bug fixed alongside v1: `Q * float` was squaring the unit (lifted to left.unit instead of dimensionless) — found via the MOSFET formula. |
| 12 | Notebook templates + report rendering | 🟡 partial | v1 ships `quantity_to_html` / `quantity_to_markdown` (per-Quantity table + collapsible provenance chain), `block_report_html` (contracts table with declared-vs-actual status, verifications filtered to block, key quantities, cross-block consumers via forward walk of `ProvenanceGraph`), `project_report_html` (header counts, global verification roll-up, per-block subsections, requirement-coverage matrix). All renderers return self-contained HTML strings sharing one `_HTML_CSS` block; `display_quantity` / `display_block_report` / `display_project_report` are thin `IPython.display.HTML` wrappers (lazy import — no notebook dep at the framework venv level). `Project.run` grew `return_all_computed=False` — set True for the design-review renderers so contracts + `compares_to` + Quantity-valued `assumed_inputs` are visible in `results` (default keeps the existing filtered-to-user-targets contract). `can_transceiver_report_template.ipynb` rewritten from forward-looking spec into a runnable copy-paste template. PDF rendering (WeasyPrint) deferred to 12d — design doc §12 calls for it, but browser print-to-PDF on the executed HTML covers v1. |
| 13 | Cookiecutter scaffolding | ⏳ pending | |
| 14 | `.claude/` agents + slash commands | 🟡 partial | CLAUDE.md files written for both repos + workspace root. Agents and slash commands not yet scaffolded. |
| 15 | CI pipeline | ⏳ pending | Local `pytest` + `mypy` configured; no remote CI yet. |
| FR1 | Truth tables for logic blocks | ✅ shipped | `framework.logic.TruthTable` (frozen, hashable; `from_rows` accepts flat tuples or per-row dicts; `from_function` enumerates all 2^n inputs) + `TruthTableMismatch` + `compare_truth_tables(actual, expected)`. `VerificationContext.assert_truth_table_matches` and `.truth_table(name)` integrate with the existing `@verification_test` surface — each failing input combination becomes one `ScenarioMode` in `TestResult.failed_at` so the existing HTML/PR-comment formatters render it without special-casing. Worked example: `logic_block` fixture (2-to-4 decoder spec + actual + verification). Sequential logic / latches / don't-cares deferred. |

## Tests

**431 passing**, no skips. Split: 401 in `hw_analysis_framework`, 30 in `components`. (Example_analysis has 2 pytest items as of step 9b: 1 pass + 1 designed-to-fail thermal verification.)

Per-module coverage from last full run:

| Module | Cover |
|---|---|
| `framework.__init__` | 100% |
| `framework.units` | 100% |
| `framework.modes` | 96% |
| `framework.scenarios` | 92% |
| `framework.requirements` | 98% |
| `framework.quantity` | 93% |
| `framework.cache` | (new — included in 207) |
| `framework._hashing` | (new — included in 207) |
| `framework.project` | (new — included in 207) |
| `framework.component` | (new — included in 207) |
| `framework._toml` | 87% |
| `framework.provenance` | 80% (stub) |

## Repos

| Repo | Commits | Tip |
|---|---|---|
| `hw_analysis_framework` | 22 | `ebc3918` — Step 12 v1: notebook templates + design-review report rendering |
| `components` | 3 | `cbd8388` — Adds NCP1117_50 LDO + STM32G071CB MCU instances |
| `example_analysis` | 17 | `c98536c` — Three-block expansion: power_supply + mcu + can_transceiver |

## Worked example

End-to-end **three-block** analysis at [`example_analysis/system_analysis.ipynb`](example_analysis/system_analysis.ipynb). Blocks:

| Block | Role | Part | Headline output |
|---|---|---|---|
| `power_supply` | 12V → 5V linear LDO | NCP1117ST50T3G (SOT-223) | publishes `rail_5v` Contract; consumes `can_5v_draw` + `mcu_5v_draw` |
| `mcu` | Application processor + CAN protocol stack | STM32G071CB (LQFP-48) | publishes `mcu_5v_draw`; consumes `rail_5v` |
| `can_transceiver` | High-speed CAN PHY | NXP TJA1051T/3 (SO-8) | publishes `can_5v_draw`; consumes `rail_5v` |

Cross-block wiring exercises the cycle-cut rule (design doc 6.7): the PSU's `rail_5v` Contract has `assumed_inputs={can_5v_draw, mcu_5v_draw}` capturing the load envelope; the CAN and MCU blocks have `assumed_inputs={rail_5v}` capturing their supply envelope. The framework's step-8 + step-8b checks validate all four assumptions on every run.

**Six verification tests** in steady state:
- 3 **PASS** (each block's actual current draw within its published Contract).
- 3 **FAIL** at `hot_high_vin` (designed-to-fail thermal margins: CAN active+diagnostic, MCU diagnostic, PSU active+diagnostic). All three are surfaced by the same renderer surface as a CI deliverable — exactly the design issues a worst-case analysis is supposed to expose.

12 requirements registered (3 Performance ADC-accuracy reqs scoped by scenario, 1 boot-time Performance, 2 TempRange, 1 SupplyEnvelope for the 5V rail, 1 CurrentBudget for total quiescent, 1 CurrentBudget for MCU active-mode, 2 Performance for MCU + PSU T_J derates).

Two new component instances live alongside the existing parts:
- [`components/instances/regulators/ncp1117_50.py`](components/instances/regulators/ncp1117_50.py) — NCP1117-5.0 LDO.
- [`components/instances/semiconductors/stm32g071cb.py`](components/instances/semiconductors/stm32g071cb.py) — STM32G0 MCU (uses the generic `IntegratedCircuit` type).

## Outstanding follow-ups

- Close `quantity.py` from 93% → 100% per design doc §17 (step 1 quality bar).
- Pint auto-lift sugar from design doc §6.1 (`5 * units.V` → Constant Quantity) — needs a custom unit shim, deferred.
- Caching limitation: source-byte hashing assumes pure functions. Block analyses that read module-level globals instead of taking DAG inputs will see stale cached results. Documented in framework CLAUDE.md.
- Component library version not yet folded into the cache hash. Will land with step 5 once `components` has a stable surface.
- **Mathcad inputs-only worksheet emitter** (design spec §12.9, methodologies §11). Generates `.mcdx` per (analysis × scenario) containing requirements, component parameters, operating conditions, contract inputs, expected results, and an empty derivation region for independent re-derivation by a second engineer. Scheduled for v2 (see §14 Phase Boundaries); pull forward into v1 if a contractual Mathcad deliverable surfaces. Implementation choice (raw .mcdx XML emission vs. COM automation via `pywin32`) deferred until a project requires it.

## Tooling state

- `.vscode/settings.json` pins framework `.venv` as test interpreter; `python.testing.cwd` points at the framework dir.
- `.claude/settings.json` allowlist trims 22 noisy read-only PowerShell patterns out of the prompt loop (Push-Location, git status / log / diff, poetry run pytest, Get-ChildItem, Test-Path, etc.).
- `CLAUDE.md` files at workspace root + each repo capture mental model, dev workflow, and the running list of Pint gotchas (offset units, application registry, ohm-prefix alias quirks).
- User memory at `~/.claude/projects/.../memory/` tracks status, decisions, and gotchas across sessions.

## Recommended next

With steps 1–5, 7, 8, 9a/b/c, **10**, **11 (v1.1)**, and **12 (v1)** shipped, the framework covers everything in the design doc §15 critical path that doesn't depend on external artifacts (netlist, Altium, Jama-side schema). Remaining active edges:

**Step 11 follow-ons** — `worst_case_droop`, `current_limit_check`, generic `power_dissipation` / `thermal_rise`. Add on demand.

**Step 12 follow-ons** — `12d` (PDF rendering via WeasyPrint) deferred; browser print-to-PDF on the executed HTML covers v1. Auto-discovery of "every block" (currently `_all_blocks` walks supplied modules — fine for now, but a `Project.discover_blocks()` method that scans `blocks/` would tighten the UX once multiple blocks ship).

**Step 6 (netlist parser)** — deferred until a real Protel ASCII netlist sample is on hand. Mechanical block-ownership enforcement also lands here.

## Pending feature requests (captured for design before code)

- **Sequential logic (latches, flip-flops, state machines)** — extension of FR1. v1 truth tables cover combinational logic only; sequential logic needs a `StateMachine` type with prior-state inputs and a reachability check. Pairs with the existing `@verification_test` surface like truth tables do.
- **Don't-care (X) / tri-state cells in truth tables** — v1 requires concrete 0/1. Small extension once a real datasheet needs it.
- **Docker dev environment** — onboarding helper that ships a stable Python + Poetry + framework stack so a new engineer is one `docker compose up` away from a working analysis project. Pairs naturally with step 13 (cookiecutter) — the cookiecutter could emit a `Dockerfile` / `compose.yml` alongside the project skeleton.
- **Net / component-tied Quantities** — declare that a Quantity represents a specific net or component param so redundant / conflicting analyses on the same physical thing are detectable. Mostly subsumed by the block-ownership rule (Contracts are the production-side namespace) but a small Contract extension (`binds_to_net=`, `binds_to_component_param=`) would close the residual gap once a netlist namespace exists.
