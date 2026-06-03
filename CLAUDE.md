# HardwareDev workspace — for Claude Code sessions

Three sibling git repos under this directory, building a Python framework for collaborative worst-case circuit analysis (Hamilton + Pydantic + Pint + Poetry stack).

## Layout

```
HardwareDev/
  hardware_analysis_framework_design.md  # authoritative spec — read first
  design_methodologies_and_philosophies.md
  PLATFORM_VISION.md                      # north-star: the platform the framework is one piece of
  hw_analysis_framework/                  # the framework package (see its CLAUDE.md)
  components/                             # component library (see its CLAUDE.md)
  example_analysis/                       # reference analysis project (see its CLAUDE.md)
```

## Entry points

- **Implementing or changing core framework code:** `hw_analysis_framework/`. Open its `CLAUDE.md` for mental model, gotchas, and dev workflow.
- **Adding a block to the worked example, or seeing how an analysis project consumes the framework:** `example_analysis/`. Open its `CLAUDE.md`.
- **Adding a component type / family / instance:** `components/`. See its `CLAUDE.md` for the type/family/instance pattern.

## Design doc section map (`hardware_analysis_framework_design.md`)

| Section | Topic |
|---|---|
| 4 | Stack |
| 5 | Repository topology |
| 6.1 | Quantity |
| 6.2 | Scenario |
| 6.3 | Mode |
| 6.4 | Requirement |
| 6.5 | Component & component library |
| 6.6 | Block layout |
| 6.7 | Contract |
| 6.8 | VerificationTest |
| 7 | The DAG (Hamilton) |
| 8 | Caching |
| 9 | Provenance |
| 10 | Schematic binding (Altium) |
| 11 | Claude Code agent setup |
| 12 | Reporting layer |
| 13 | Layered usage (adoption path) |
| 14 | Phase boundaries (v1 / v2 / v3) |
| 15 | Suggested implementation order (15 ordered steps) |
| 16 | Open decisions before implementation |
| 17 | Quality bar |

Always check the relevant section before changing core abstractions. If the design and the code disagree, surface it — don't silently diverge.

## Current workflow: review and refinement

The framework was built in **one large unreviewed sprint** to flesh out the design space quickly. As of 2026-05-26 we are in a structured **review-and-refine** phase to convert that vibe-coded surface into code Mike fully understands and trusts.

**Operating rules during this phase:**

- Phases are gated. Don't run ahead into a later phase's surface area without explicit sign-off on the current one.
- Each phase opens a `review/phaseN` branch from `main` in the relevant repo. Reviews + fixes commit there. On sign-off, merge to `main` and tag (`v0.1-foundation` for Phase 1, etc.). `main` IS the trusted state after each merge.
- Walk through code with Mike interactively before changing anything. Surface design-vs-code drift; never silently align one to the other.
- Audit notes are throwaway; the durable record is in commits + tags + CLAUDE.md updates.
- The methodologies doc (`design_methodologies_and_philosophies.md`) is the **gate between Phase 1 and Phase 2** — Mike reads and approves it before contracts get reviewed.

**Phase 1 scope (current):** `units` → `quantity` (incl. distributions: Gaussian + Uniform) → `modes` → package surface → test-quality audit → basic components (Resistor + Capacitor + one IC instance; families deferred). Detail in `PROJECT_STATUS.md`.

**Phase ordering after 1 (sketch):** contracts → scenarios/modes/requirements → components (full library) → DAG/caching → verification/provenance/reports → standard analyses + worked example. Open to reordering as we go.

## Implementation status

Authoritative tracker: [`PROJECT_STATUS.md`](PROJECT_STATUS.md) at the workspace root — has the per-step table, test counts, commit pointers, and the "recommended next" recommendation. Cross-conversation context in user memory (`project_hardware_framework.md`).

Headline: steps 1–5, 7, 8, **9a/9b/9c**, and **10** of design doc §15 are shipped; step 6 (netlist parser) is deferred until a real netlist sample is on hand; cross-block `assumed_inputs` validation, step 11 (standard analyses library), and a couple of new feature requests (truth tables for logic blocks, Docker dev env) are the live edges. Read PROJECT_STATUS.md before starting new work — what looks "next" from a section-15 numbering view may have already been deferred for a reason captured there.

## Block ownership rule (organizational, not yet mechanically enforced)

Each schematic page has one owner; that owner's block is the **only place** Contracts are published about nets/components that primarily live on that page. This is the rule that prevents two engineers from independently publishing disagreeing analyses of the same physical rail. The framework's cycle-cut rule (design doc §6.7) constrains *consumption* — the ownership rule constrains *production*. Authoritative statement in §6.7 of the design doc; operational notes in `example_analysis/CLAUDE.md`. Mechanical enforcement lands with step 6.

## Workspace setup

- Toolchain: Python 3.12, Poetry 2.x, Git. All installed at user scope under `%LOCALAPPDATA%\Programs\Python\` and `%APPDATA%\Python\Scripts\` respectively.
- VS Code: `.vscode/settings.json` pins the test interpreter to `hw_analysis_framework/.venv/Scripts/python.exe`. If a fresh session can't find tests, see the framework CLAUDE.md "Dev workflow" section and verify the interpreter selection in VS Code (Ctrl+Shift+P → "Python: Select Interpreter").
- Each repo's `.venv/` is Poetry-managed in-project. The framework venv is the one Jupyter / VS Code should target — `example_analysis` doesn't have its own.

## When in doubt

- Read the design doc.
- Check user memory (`MEMORY.md` and linked notes) for current status and recent decisions.
- Check the relevant repo's `CLAUDE.md` for conventions and gotchas.
