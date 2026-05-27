# Hardware Analysis Framework — Core Design Specification

**Status:** Draft 1 (2026-05-14)
**Scope:** Core analysis model and data flow. Companion concerns (Altium live sync, Jama bidirectional sync, CI/CD details, schematic browser UI, reporting templates) are deferred to follow-on documents.
**Audience:** Engineers and AI assistants (e.g., Claude Code) implementing or extending the framework.

---

## 1. Purpose

A Python framework that lets a team of automotive electronics engineers independently develop and analyze their assigned circuit blocks while leveraging each other's results, with rigorous worst-case math, traceable provenance, and CI-enforced consistency.

## 2. Goals

1. Multiple engineers analyze their own blocks in parallel and consume each other's outputs without manual coordination.
2. Worst-case (corner-based) analysis is the default; Monte Carlo is opt-in for specific analyses.
3. Cyclic dependencies between blocks are detected at graph-build time and broken via explicit Contracts.
4. Units are enforced everywhere via Pint.
5. Every derived value is traceable to its inputs through provenance.
6. Performance scales: nothing recomputes if its inputs haven't changed.
7. The framework is intuitive in VS Code (full type hints, autocomplete, hover docs).
8. New engineers onboard quickly with cookiecutter scaffolding and a Claude Code agent assistant.

## 3. Non-Goals (v1)

- Full board-level SPICE simulation (LTSpice continues to be used for sub-analyses; not replaced).
- Custom DSLs or YAML/JSON-driven analysis definitions (Python is the substrate).
- Live Altium server API sync (manual netlist export to repo is the v1 source of truth).
- Bidirectional Jama sync (one-way push of test results is v1).
- Combinatorial enumeration of all parameter min/max combinations (statistically meaningless and combinatorially infeasible).

## 4. Stack

- **Language:** Python 3.11+
- **Packaging:** Poetry
- **DAG engine:** Hamilton (DAGWorks)
- **Typed schemas:** Pydantic v2
- **Units:** Pint (mandatory)
- **Numerics:** NumPy, SciPy
- **Plotting:** Plotly (mandatory — JSON-serializable for HTML artifacts and the future schematic browser)
- **HTML→PDF:** WeasyPrint (design-review PDF artifacts with bookmarks and internal links)
- **Notebook execution:** nbconvert (CI smoke gate and design-review generation, fresh kernel)
- **Testing:** pytest (with a custom plugin for VerificationTest)
- **Notebooks:** Jupyter
- **Source control:** GitHub Enterprise
- **Component instances:** Separately versioned `components` Python package

## 5. Repository Topology

Three repositories, versioned independently:

1. **`hw_analysis_framework`** — the framework itself (Quantity, Hamilton extensions, Contract types, VerificationTest, netlist parser, report helpers, agent definitions). Released as a versioned Python package consumed by analysis projects.
2. **`components`** — component library: Pydantic schemas for each component type, families for parametric parts (resistors, capacitors), and instances for each part number. Versioned independently. Eventually synced from the Altium PSC server (phase 2).
3. **`<product>_analysis`** — one repo per board/product. Contains the project's requirements, scenarios, modes, blocks, netlist snapshot, notebooks, and tests. Depends on the framework and component library packages.

Engineering teams primarily work in the analysis project repos. The framework and component library are maintained by smaller working groups but accept contributions via PR.

## 6. Core Abstractions

### 6.1 Quantity

The atomic data type. Every physical or derived value in the system is a `Quantity`.

```python
@dataclass(frozen=True)
class Quantity:
    by_scenario: dict[str, ScalarOrRange] | None   # values per named scenario
    by_mode:     dict[str, "Quantity"] | None      # values per operating mode
    distribution: Distribution | None              # statistical distribution (optional)
    unit:         pint.Unit                         # mandatory
    provenance:   ProvenanceRef                     # link to producing DAG node
```

**Rules:**
- Every Quantity has a unit. Arithmetic without compatible units raises at compute time.
- A Quantity can vary along `by_scenario`, `by_mode`, both, or neither. Most vary along one axis; constants vary along none.
- If both `by_scenario` and `distribution` are present, the distribution is canonical; corners are evaluation points (drawn from the distribution or specified by engineering judgment).
- Quantities are immutable. Operations return new Quantities.

**API:**
- `q.at(scenario=None, mode=None) -> Scalar` — evaluate at a specific point
- `q.at_quantile(p)` — distribution quantile (raises if no distribution)
- `q + q`, `q * q`, `q / q`, `q ** n` — arithmetic propagates axes, convolves distributions, enforces units
- `q.contains(spec)` / `q.within(lo, hi)` — predicate over all scenarios/modes
- `q.provenance.parent()` — immediate parent (O(1))
- `q.provenance.chain(max_depth=100)` — lazy traversal back to root leaves

**Sugar:**
- `Constant(value, unit)` — for mode/scenario-invariant values
- `RangeQuantity(lo, hi, unit)` — for simple min/max without scenario detail

**Construction vs arithmetic — explicit/forgiving asymmetry:**
- **Construction is explicit.** `5 * units.V` returns a raw `pint.Quantity`, NOT a framework Quantity. To construct a framework Quantity, write `Constant(5, units.V)` (or `RangeQuantity(lo, hi, unit)`, or the full `Quantity(...)` form). Auto-lifting at construction was considered (decided 2026-05-26) and rejected: it would require a `FrameworkUnit` wrapper around `pint.Unit` with `__getattr__` forwarding, divergent behavior from raw Pint, and a separate code path to maintain — for the sake of removing one `Constant(...)` call at the point of value declaration. Explicit construction won.
- **Arithmetic is forgiving.** When a framework `Quantity` is combined with a raw `pint.Quantity` in arithmetic (`Constant(5, V) + 3 * registry.volt`), the framework lifts the Pint operand into a `Constant` on the fly so the math works. The asymmetry is intentional: writing `Constant(...)` once at the point of value declaration is clarifying; writing it around every operand in every expression is just noise.

### 6.2 Scenario

A named environmental/operating corner. Project-global.

```toml
# project/scenarios.toml
[[scenario]]
name = "nominal"
ambient_temp = 25
vbat = 12.0

[[scenario]]
name = "cold_low_vin"
ambient_temp = -40
vbat = 9.0
description = "Cold start, depleted battery"

[[scenario]]
name = "hot_high_vin"
ambient_temp = 85
vbat = 16.0
description = "Hot ambient, alternator load"
```

Blocks may extend the global scenario set with block-specific corners (e.g., the RF block adds `cold_carrier_drift`). Block-specific scenarios are explicitly opt-in; the framework knows which blocks defined them and consumers must either map them to a global scenario or ignore them.

Default scenarios are auto-generated from `project/requirements.py` (operating temp range × supply envelope) and can be edited.

### 6.3 Mode

A global system operating state. The whole board is in one mode at one moment.

```toml
# project/modes.toml
[[mode]]
name = "off"
description = "Battery disconnected or master disable"

[[mode]]
name = "sleep"
description = "Low-power monitoring, RTC running, MCU asleep"

[[mode]]
name = "active"
description = "Normal operation, all peripherals available"

[[mode]]
name = "diagnostic"
description = "Manufacturing test mode, all rails enabled"

[[mode]]
name = "calibration"
description = "Reference calibration, specific subcircuits active"
```

Each engineer's block declares its **mode-dependent leaf values** (current draws, peripheral states, clock frequencies). Downstream analysis math is written **once**, mode-agnostic, and the framework propagates each mode through the DAG automatically. Engineers do not write per-mode duplicate functions.

### 6.4 Requirement (Design Target)

External design constraints — operating envelope, supply specs, performance targets, regulatory limits. Single source of truth, instantly discoverable.

```python
# project/requirements.py
from framework.units import V, A, mA, uA, degC
from framework.requirements import (
    TempRange, SupplyEnvelope, CurrentBudget, Performance
)

OPERATING_TEMP = TempRange(
    min=-40 * degC, max=85 * degC,
    req="REQ-ENV-001",
    description="Vehicle operating envelope",
)

STORAGE_TEMP = TempRange(
    min=-40 * degC, max=125 * degC,
    req="REQ-ENV-002",
)

VBAT = SupplyEnvelope(
    nominal=12 * V, min=9 * V, max=16 * V,
    transient_min=6 * V, transient_max=40 * V,
    req="REQ-PWR-001",
    description="Vehicle 12V system with cold-crank and load-dump margins",
)

TOTAL_QUIESCENT_CURRENT_BUDGET = CurrentBudget(
    max=2 * mA,
    applies_to_mode="sleep",
    req="REQ-PWR-014",
)
```

**Rules:**
- All project-level requirements live in `project/requirements.py`. Discoverable in one place.
- Each carries a `req=` Jama ID. Verification tests link tests → requirements via this field.
- Requirements feed scenario and mode defaults (the framework can auto-suggest scenarios from `OPERATING_TEMP` × `VBAT`).
- Importable as Python symbols anywhere: `from project.requirements import VBAT`.
- The framework exposes `framework.requirements.list()` and `framework.requirements.show("REQ-PWR-001")`.
- The Claude Code agent provides `/show-requirements` and `/find-requirement <topic>`.

### 6.5 Component & Component Library

The `components` package has three layers:

- **Types** — Pydantic schemas defining what a MOSFET / capacitor / LDO / etc. *is* (the team's component vocabulary).
- **Families** — Shared parameter sets for parametric parts. A family captures everything that's shared across many specific values: manufacturer, series, tolerance, temp coefficient, dielectric (for caps), available SMT sizes, and size-dependent ratings. Specific instances are minted from a family by supplying a value and size. Primarily used for resistors and capacitors; rarely needed for other types.
- **Instances** — Specific part numbers as concrete, named Python objects. ASICs, MCUs, MOSFETs, LDOs, buck regulators all live here as one-offs. Resistor and capacitor instances are typically generated from families.

**Repo layout:**

```
components/
  types/                       # Pydantic schemas — what a component IS
    resistor.py
    capacitor.py
    mosfet.py
    bjt.py
    ldo.py
    buck_converter.py
    diode.py
    ...
  families/                    # Shared parameter sets for parametric parts
    resistors/
      erj3_panasonic.py
      crcw_vishay.py
    capacitors/
      grm_murata_x7r.py
      gcm_murata_aec_q200.py
      ...
  instances/                   # Specific parts
    mosfets/
      irlml6344.py
    semiconductors/
      tja1051t_3.py
    regulators/
      tps62933.py
    ...
  CONTRIBUTING.md              # naming conventions, how to add types/families/instances
```

**Component types — Pydantic schemas with required / optional-standardized / free-form fields:**

```python
# components/types/mosfet.py
class MOSFET(Component):
    # Required — schema validation fails CI if missing
    rds_on:    Quantity
    v_gs_th:   Quantity
    v_ds_max:  Quantity
    i_d_max:   Quantity

    # Standardized optional — well-known parameter names, populated when available
    q_g_total:     Quantity | None = None
    r_thermal_jc:  Quantity | None = None
    r_thermal_ja:  Quantity | None = None
    body_diode_vf: Quantity | None = None

    # Free-form escape hatch
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Families — shared parameter factory for parametric parts:**

```python
# components/families/resistors/erj3_panasonic.py
from components.types import Resistor, ResistorFamily, SmtSize
from framework.units import Ohm, W, V, ppm, degC

ERJ3 = ResistorFamily(
    manufacturer="Panasonic",
    series="ERJ-3",
    description="Thick-film chip resistors, general purpose, AEC-Q200",
    tolerance=Quantity(by_scenario={"_": 0.01}),               # ±1%
    temp_coefficient=Quantity(by_scenario={"_": 100 * ppm / degC}),
    available_sizes=[SmtSize.IMP0603, SmtSize.IMP0805, SmtSize.IMP1206],
    power_rating_by_size={
        SmtSize.IMP0603: 0.1   * W,
        SmtSize.IMP0805: 0.125 * W,
        SmtSize.IMP1206: 0.25  * W,
    },
    max_voltage_by_size={
        SmtSize.IMP0603: 75  * V,
        SmtSize.IMP0805: 150 * V,
        SmtSize.IMP1206: 200 * V,
    },
    psc_family_id="PSC-RES-ERJ3",   # links to Altium PSC family entry
)

# Specific instances minted from the family
R_10K_0603_1PCT = ERJ3.instance(value=10 * kOhm, size=SmtSize.IMP0603)
R_4K7_0603_1PCT = ERJ3.instance(value=4.7 * kOhm, size=SmtSize.IMP0603)
```

`ERJ3.instance(value, size)` returns a `Resistor` instance with all family parameters propagated, the chosen value, and size-dependent ratings filled in.

**Component instances — one-offs:**

```python
# components/instances/mosfets/irlml6344.py
from components.types import MOSFET
from framework.units import V, A, mOhm, nC

IRLML6344 = MOSFET(
    part_number="IRLML6344TRPBF",
    psc_id="PSC-MOSFET-00123",          # link to Altium PSC catalog
    rds_on=Quantity(by_scenario={
        "nominal":   28 * mOhm,
        "max_temp":  38 * mOhm,
    }),
    v_gs_th=Quantity(by_scenario={
        "min": 0.6 * V, "typ": 1.1 * V, "max": 1.5 * V,
    }),
    v_ds_max=Quantity(by_scenario={"_": 30 * V}),
    i_d_max=Quantity(by_scenario={"_":  5 * A}),
    q_g_total=Quantity(by_scenario={"typ": 1.5 * nC}),
)
```

**Rules:**
- Each component type schema is reviewed before being added (defines the team's vocabulary).
- New families are reviewed similarly — they encode design conventions and material choices.
- New instances added by PR; required fields validated by CI.
- Optional standardized fields use consistent names across all instances (no `Q_g` vs `qg` vs `gate_charge`).
- `metadata` is reserved for parameters that don't fit any standardized field.
- The library is independently versioned; analysis projects pin a version.

**Naming conventions (enforced by lint / CI):**
- Type files: `snake_case.py` matching the class name (`mosfet.py` defines `MOSFET`).
- Family files: `<series>_<manufacturer>.py` lowercased (`erj3_panasonic.py`, `grm_murata_x7r.py`).
- Family Python identifiers: UPPER_SNAKE matching the series (`ERJ3`, `GRM_X7R`).
- Instance Python identifiers (one-off parts): UPPER_SNAKE_CASE matching the part number, with hyphens/slashes replaced by underscores (`IRLML6344`, `TJA1051T_3`).
- Family-minted resistor / capacitor identifiers: `R_<value>_<size>_<tol>` and `C_<value>_<size>_<voltage>` (`R_10K_0603_1PCT`, `C_100N_0603_25V`). Values use engineering prefixes (10K not 10000, 100N not 0.0000001, 4N7 not 4.7N).
- Units in identifiers: capitalized correctly (V, A, mA, uF, nF, mOhm).
- All Quantity fields populated with Pint units, never raw floats.

**Contributing guide (`components/CONTRIBUTING.md`) covers:**
- How to add a new component type (Pydantic schema, required vs optional fields, naming).
- How to define a new family (factory method shape, size-dependent ratings).
- How to add a new instance (one-off vs family-minted).
- Unit hygiene rules (mandatory Pint, correct capitalization).
- Required fields per existing type.
- How to link to Altium PSC.
- PR review checklist.
- The Claude Code agent provides `/new-component <type>` to scaffold a new instance and `/new-family <type>` for a new family.

### 6.6 Block

A Python subpackage owned by one engineer.

```
blocks/
  power_supply/
    __init__.py          # re-exports only public Contracts
    components.py        # refdes ownership + per-instance overrides
    leaves.py            # mode-dependent leaf Quantities
    analysis.py          # Hamilton DAG nodes (derivations)
    contracts.py         # public Contract-typed Quantities
    verifications.py     # block-scoped VerificationTests
    report.ipynb         # block-level notebook report
    README.md            # description, owner, gotchas
```

**Rules:**
- `__init__.py` does `from .contracts import *` and nothing else. Internals stay private.
- `components.py` declares `OWNED = ["U101", "C101", ...]` — list of refdes this block owns. The framework validates every netlist refdes is owned by exactly one block.
- Hamilton auto-discovers nodes from `analysis.py`, `leaves.py`, `contracts.py`.
- A block may have subpackages, but typically won't.

A cookiecutter template scaffolds new blocks (`/new-block <name>` via the Claude Code agent).

### 6.7 Contract

A `Contract` is a specially-typed Quantity representing a block's public commitment to other blocks. **Contracts are the cycle cut-points** of the dependency graph.

```python
# blocks/block_a/contracts.py
from framework import contract, Quantity, units

@contract(
    description="Current drawn from 3V3 rail",
    requirement="REQ-PWR-014",
    assumed_inputs={"rail_3v3_voltage": (3.15 * units.V, 3.45 * units.V)},
)
def block_a_3v3_draw() -> Quantity:
    return Quantity(
        by_mode={
            "sleep":      Quantity(by_scenario={"_": (5 * uA,   12 * uA)}),
            "active":     Quantity(by_scenario={"_": (80 * mA, 220 * mA)}),
            "diagnostic": Quantity(by_scenario={"_": (100 * mA, 260 * mA)}),
        },
        unit=units.A,
    )
```

**Graph-build-time rules (enforced before any analysis runs):**
- A Contract may depend on inputs *within its own block*, on Contracts of *other blocks*, and on *global* inputs (requirements, scenarios, modes, component library).
- A Contract **may not** depend on a non-Contract output of another block. Violation raises `CycleViolation` at module-load with the offending dependency path.

**Ownership rule (organizational, not currently mechanically enforced):**
- Each schematic page has exactly one owner. That owner's block is the **only place** Contracts may be published about nets and component parameters that primarily live on that page. If you want to publish a Contract about `NET_3V3` and `NET_3V3`'s power source is on someone else's page, the contract belongs in *their* block, not yours.
- Multi-page nets (a bus that crosses functional boundaries) require a human decision on which block owns the contract — pick the page where the net is most defined / least incidental.
- This rule is what guarantees no two Contracts describe the same physical thing. Without it, two engineers could independently publish disagreeing analyses of the same rail with no framework-level detection (Python-name uniqueness ≠ physical-thing uniqueness). The cycle-cut rule above doesn't catch this — it constrains *consumption*, not *production*.
- Mechanical enforcement is deferred: once §10 schematic binding lands and a netlist is available, `block.owner` + refdes-to-block mapping will let the framework refuse contracts that violate this rule. Until then, treat it as a CLAUDE.md / code-review concern.

**Run-time rules (enforced after the DAG executes):**
- For every Contract, the framework compares the declared value against the block's actual computed value of the same Quantity.
- If actual exceeds declared in any scenario/mode, an auto-generated `ContractViolation` verification test fails: *"Contract `block_a_3v3_draw` declares max 220 mA active; actual is 235 mA in `hot_high_vin`/`active`."*

The engineer does not have to write the consistency assertion — it is generated for every Contract automatically.

### 6.8 VerificationTest

A first-class registered test, supporting pytest, Jama sync, notebook reports, and PR comments through one definition.

```python
# blocks/power_supply/verifications.py
from framework import verification_test, Severity, Range, units

@verification_test(
    name="3V3 rail margin under worst-case droop",
    requirement="REQ-PWR-0142",
    block="power_supply",
    severity=Severity.CRITICAL,
    modes=["active", "diagnostic"],
)
def test_3v3_margin(ctx) -> "TestResult":
    rail = ctx.quantity("power_supply.vout_3v3")
    spec = Range(3.15 * units.V, 3.45 * units.V)
    return ctx.assert_quantity_in(rail, spec)
```

**`TestResult` carries:**
- `passed: bool`
- `failed_at: list[ScenarioMode]` — failing corner/mode pairs
- `evidence: dict[str, Quantity]` — values that drove the conclusion
- `margin: Quantity | None` — distance to the nearest spec edge
- `report_markdown: str` — human-readable summary (rendered for Jama and PR comments)
- `provenance: list[ProvenanceRef]` — links to source DAG nodes for traceability

**Output channels (one definition, four destinations):**
- pytest plugin discovers and runs all `@verification_test`s in CI
- `framework.run_verifications()` produces structured output for Jama push
- Notebook helpers render results as tables / pass-fail summaries
- A PR comment bot posts a summary of pass/fail/margin

**Locations:**
- `blocks/<block>/verifications.py` — block-scoped tests, owned by the block author
- `project/verifications/` — cross-block / system-level tests, owned by the integration role

## 7. The DAG (Hamilton)

### 7.1 Construction

Hamilton parses Python function signatures into a directed acyclic graph. Parameter names are wired to other node outputs of matching name.

```python
# blocks/power_supply/analysis.py
def vout_3v3(
    vin: Quantity,
    load_3v3_total: Quantity,    # cross-block: aggregated from Contracts
    ldo_dropout: Quantity,        # internal: derived from components
) -> Quantity:
    """3V3 rail output accounting for LDO dropout and load."""
    return vin - ldo_dropout      # placeholder; real formula richer
```

### 7.2 Cross-Block Wiring

Cross-block references flow **only through Contracts**. A function in one block may import from another block only if it imports a Contract. The framework's import validator enforces this.

### 7.3 Execution Model

The DAG is executed across the cross-product of (scenarios × modes). Content-addressed caching ensures nodes that don't vary along a given axis execute once and the result is reused across all axis values. Typical board with 6 scenarios × 5 modes runs in ~2-4× the time of a single (scenario, mode) execution, not 30×.

### 7.4 Cycle Detection (Graph-Build Time)

Performed once at framework initialization:
1. Build the full DAG by parsing all blocks.
2. For each Contract C, walk C's dependency subgraph.
3. If the subgraph reaches a non-Contract node owned by a different block, raise `CycleViolation` with the offending path.
4. If the subgraph reaches C itself transitively, raise `CycleViolation`.

Error messages name the path and suggest the fix: *"Break this cycle by introducing a Contract on `block_a.power_dissipation` or by reading from `block_a.current_draw` (a Contract) instead."*

### 7.5 Worst-Case Math

- **Corners (default):** Quantities carry `by_scenario`. Arithmetic propagates scenario-wise. Each scenario is a self-consistent worldview — correlation handled by construction. The same physical R701 has one value per scenario, used everywhere in that scenario's evaluation.
- **Monte Carlo (opt-in per analysis):** Quantities carry a `distribution`. `framework.simulate(n=10_000)` runs the DAG N times, sampling each leaf distribution once per trial (preserving correlation within a trial), and accumulates statistics. Used for yield-sensitive trims, reference voltages, EMI margins.
- **Combinatorial enumeration is explicitly not supported** — pessimistic, statistically meaningless at high N, and combinatorially infeasible.

## 8. Caching

Content-addressed. Each DAG node has a hash computed from:
- Function source bytes
- The hashes of all input values
- Framework version
- Component library version

Outputs are stored in a local `.framework_cache/` directory (gitignored). A remote shared cache (e.g., S3-backed) for CI is phase 2. On re-execution, if the input hash matches a cached entry, the cached output is returned.

CI implication: a PR re-runs only nodes whose hashes changed (transitively).

## 9. Provenance

Every Quantity carries a `ProvenanceRef` — a content-addressed pointer to its source DAG node. Storage is O(1) per Quantity (just the hash).

The full provenance **chain** is reconstructed on demand by walking the cached DAG. Storage stays flat; reconstruction is lazy.

**Safeguards (defensive — cycles already prevented at graph-build time):**
- `visited` set during traversal terminates revisited branches
- Configurable depth limit (default 100). Exceeded: emit warning, truncate with `...truncated at depth N...` marker.
- Lazy expansion: `q.provenance.parent()` returns immediate parent (O(1)); `q.provenance.chain()` walks (O(depth)).
- Memoization: repeated chain queries for the same Quantity are cached for the object's lifetime.

## 10. Schematic Binding (Altium → Python)

### 10.1 Source of Truth

The Altium-exported netlist in **Protel ASCII format**, committed to the repo at `project/netlist/<board>.NET`. Versioned with the analysis code. Regenerated by the schematic engineer after Altium changes.

(Format choice: Protel ASCII is cleaner than IPC-356 and well-supported by Altium's export. Revisit if the team's projects use features Protel doesn't capture.)

### 10.2 Parsing

```python
from framework.netlist import load_netlist

board = load_netlist("project/netlist/main.NET")

Q701 = board.refdes("Q701")           # → MOSFET instance with refdes context
rail = board.net("3V3")               # → Net
rail.components                       # → list[ComponentInstance]
Q701.nets                             # → dict[pin, Net]
```

The netlist's part number for each refdes is looked up in `components`. Unknown part numbers fail parsing with a clear error and a `/add-component` hint.

### 10.3 Block Ownership Validation

Every refdes in the netlist must be owned by exactly one block. Framework enforces at startup; missing or duplicate ownership fails CI.

## 11. The Claude Code Agent

Checked-in agent configuration that gives every engineer an in-IDE assistant trained on the framework.

```
.claude/
  CLAUDE.md                          # project conventions, mental model
  agents/
    analysis-helper.md               # block authoring, debugging
    design-reviewer.md               # PR review assistance
  commands/
    new-block.md                     # /new-block <name>
    show-requirements.md             # lists all project requirements
    find-requirement.md              # /find-requirement <topic>
    explain-failure.md               # diagnoses verification test failures
    audit-coverage.md                # reports scenario/mode coverage gaps
    explain-quantity.md              # walks the provenance chain
```

**`CLAUDE.md` includes:**
- Mental model: Quantity, Contract, Block, VerificationTest
- Layered usage path: notebook → standard analyses → custom Hamilton nodes → publish Contracts
- File structure and naming conventions
- "Don'ts": pass raw floats, use combinatorial enumeration, depend on non-Contract values across blocks, skip units
- Where to find requirements, scenarios, modes
- Example block walkthrough

**Framework design choices that make the agent effective:**
- Comprehensive docstrings (Google style) on all public APIs
- Type hints on every function parameter and return
- Introspection API: `framework.describe()` returns the full DAG, scenarios, modes, components, contracts, and tests in JSON form
- Error messages with `Did you mean ...?` suggestions and links to docs
- Curated `framework.__all__`

A second agent — **design-reviewer** — assists during PR review: walks changed analyses, identifies affected verification tests, summarizes worst-case margins, flags missing scenarios or untested modes.

## 12. Reporting Layer

The framework produces reports for three audiences, each with a different artifact. All three share the same rendering primitives (VerificationTest results, Quantity rendering, Plotly plots).

### 12.1 Three audiences, three artifacts

1. **Engineers working day-to-day** — `report.ipynb` in each block, plus a project-level integration notebook. Live, regenerable, the daily driver.
2. **PR reviewers** — automated GitHub Action posts a summary comment on every pull request.
3. **Formal design reviewers** — frozen HTML + PDF generated on every git tag. PDF and HTML uploaded to team SharePoint; `reviews/INDEX.md` in the analysis project repo links to each release's artifacts.

### 12.2 Block-level notebook anatomy

Every block's `report.ipynb` follows a standardized structure. A worked example for a CAN transceiver block lives at `examples/can_transceiver_report_template.ipynb`. Cells:

1. **Cell 1 — Compute.** A single cell calls `project.run(block="<name>")`, executing the full DAG with caching. Every subsequent cell only *renders* from the resulting `results` object — no further computation. This sidesteps the notebook-stateful-re-run problem entirely.
2. **Header** (auto, `render.header`) — block name, owner, generated timestamp, framework version, component library version, netlist hash, git commit hash.
3. **Status banner** (auto, `render.status_banner`) — green / yellow / red.
4. **Contracts table** (auto, `render.contracts_table`) — every Contract published, declared vs actual per mode, gap, status.
5. **Verification test results** (auto, `render.verification_results`) — each `@verification_test`'s pass/fail, evidence, margin, Jama link.
6. **Key analyses** — engineer-curated plots and tables. The only section the block owner edits.
7. **Requirement coverage** (auto, `render.requirement_coverage`) — which Jama requirements this block tests, with explicit gap callouts.
8. **Cross-block consumers** (auto, `render.cross_block_consumers`) — generated by walking the DAG forward from each Contract. Shows which blocks consume this block's outputs.
9. **Provenance drill-down** (auto, `render.provenance_explorer`) — interactive Plotly tree for any Quantity in `results`, traversable to root inputs.

The cookiecutter block template ships with this structure prefilled. Engineers customize Section 6 only.

### 12.3 Project-level integration report

`project/report.ipynb` mirrors the block report at system level: aggregate power-budget table (per mode), system-wide contract-consistency report, requirement coverage matrix, cross-block integration tests, links to each block report.

### 12.4 PR comment bot

Implemented as a GitHub Action posting under `github-actions[bot]`. On every PR:
- Identify changed blocks
- Run analysis and verification tests
- Diff results against the base branch
- Post a concise summary comment

Sample comment:

```
🔌 Hardware Analysis — PR #142

Changed blocks: power_supply, block_a
Tests:    142 passed, 2 failed (1 new failure), 0 new
Contracts: 1 modified (block_a.3v3_draw: max 220 mA → 245 mA active)
Margins:   ↓ 70 mV  power_supply.test_3v3_margin (now 80 mV, was 150 mV)
           ↑ 15 µA  block_a.test_sleep_quiescent (now 60 µA budget)

⚠️ block_a's increased active draw narrows 3V3 rail margin under hot_high_vin.
    Reviewer attention recommended.

Full report: <link>
```

The bot is informational, not autonomous. Test failures block merges through normal pytest CI; the bot's job is to surface the change clearly to reviewers.

### 12.5 Live HTML browser and design-review artifacts

The HTML browser is the team's daily-driver canonical view of the analysis. The PDF is the formal archival record. Both are produced from a single rendering pipeline (nbconvert with a fresh kernel for reproducibility, WeasyPrint for HTML→PDF), but the cadence differs.

**HTML browser — generated on every push to main, hosted persistently:**

- Stable URL: `https://hwanalysis.internal/<product>/main/` (host configured per project in `project/config.toml`).
- Regenerated on every push to main. Snapshots of each commit are archived at `main/<short-sha>/` for traceability.
- Tagged versions live at `https://hwanalysis.internal/<product>/<tag>/`.
- The team bookmarks the `main/` URL as the canonical "current state" view.

**Browser features:**

- **Hamilton DAG visualization** embedded — click a node to see its function source, inputs, outputs, and downstream consumers. Same DAG visualization Hamilton already ships, themed and integrated with the framework's metadata.
- **Searchable contracts and tests** — type a refdes, a net name, a block, or a requirement ID; jump to anything that references it.
- **Drill-through provenance** — every Quantity in a report is clickable; the chain expands to root leaf values and component-library entries.
- **Filterable verifications** — show only failing tests, only CRITICAL severity, only tests touching a given requirement, only tests in a given block.
- **Block index** — at-a-glance status per block, with links to each block's report.
- **Tag picker** — switch between `main` and any tagged version without leaving the page; useful for comparing current vs. last design-review state.
- **Diff view** between any two revisions — surfaces contract changes, test result deltas, margin shifts.

**PDF — generated on git tags only:**

- Same nbconvert + WeasyPrint pipeline as the HTML, flattened to a print layout.
- Full PDF outline (bookmarks from heading hierarchy), internal hyperlinks (test name → detail section), external links (Jama requirement IDs).
- Uploaded to the team SharePoint location configured in `project/config.toml`.
- The analysis project repo holds `reviews/INDEX.md`, a chronological index linking each tag to its SharePoint URL plus a brief description. This keeps the repo lightweight (no binary PDFs in git) while preserving discoverability.

Example `reviews/INDEX.md`:

```markdown
# Design Review Artifacts

| Tag         | Date       | Description                                | Artifact |
|---|---|---|---|
| DR2_2026Q4  | 2026-11-15 | Q4 design review, EVT-1 build              | [SharePoint](https://…) |
| DR1_2026Q3  | 2026-08-22 | Initial design review                      | [SharePoint](https://…) |
```

**Architectural note:** the HTML browser is the substrate on which the v3 schematic browser eventually lands. The infrastructure (persistent hosting fed by CI, interactive front-end, integrated with the framework's introspection API) exists from v1. The v3 addition is a netlist-driven view layered on top — click a net, see voltage range, current, all verifications referencing it.

### 12.6 CI gates for reports

On every PR, every block's `report.ipynb` is executed end-to-end with a fresh kernel as a smoke test. Catches notebooks that have drifted out of sync with the framework or with their block. Content-addressed caching makes this fast — only changed nodes recompute. The execution gate is a separate CI job from verification tests so failures are distinguishable in PR status checks.

If a notebook fails to execute, the PR is blocked. The error names the failing cell, includes the exception, and surfaces the block owner from `blocks/<block>/README.md`.

### 12.7 Plotting

Plotly is the mandatory plot library. Reasons: JSON-serializable (survives the HTML artifact pipeline natively and the future schematic browser), interactive by default in HTML, static SVG fallback works in PDF (via WeasyPrint), mature ecosystem.

The framework's `framework.plotting` module exposes helpers for standard chart types — `bar_by_mode`, `bar_by_scenario`, `heatmap`, `tree`, `sankey`, `box_by_part`, `quantity_to_plot`. Engineers drop to raw Plotly for custom plots in their Key Analyses section.

### 12.8 Jama push payload

At the end of each CI run, all `VerificationTest` results push to Jama as Test Runs. Bulk API call. Idempotent by `(commit_hash, test_name)` — re-pushing the same results is a no-op.

Per-result fields:
- `test_name: str`
- `requirement_id: str` — Jama requirement reference
- `result: Passed | Failed | Blocked`
- `executed_by: "framework@<commit_hash>"`
- `executed_at: ISO 8601 timestamp`
- `severity: CRITICAL | WARNING | INFO`
- `evidence: str` — markdown summary of failed scenarios/modes, actual values, margin
- `artifact_url: str` — link to the block report at this commit

If Jama is unreachable, results queue locally and re-push on the next successful CI run.

### 12.9 Mathcad worksheet export (inputs-only, for independent re-derivation)

Some customers and internal processes require analysis deliverables in Mathcad (.mcdx). Auto-translating arbitrary Python analyses into Mathcad is impractical: the framework's `Quantity` semantics, scenario × mode product, Pydantic component models, and Hamilton DAG have no Mathcad equivalents. Any translator that pretended otherwise would either restrict the analysis subset so severely as to defeat the framework, or produce Mathcad files containing opaque "could not translate" comments where the interesting math lived. Worse, an auto-translation is review theater (see methodologies doc §11): if the Python analysis silently contains a conceptual error, the auto-generated Mathcad contains the same conceptual error, and the second artifact provides no independent evidence of correctness.

Rather than translate, the framework emits **inputs-only Mathcad worksheets** that a second engineer re-derives the analysis in by hand. The resulting cross-check is stronger than any translator could produce: two engineers, two tools, two independent derivations from a common set of authoritative inputs.

**What the framework emits.** One `.mcdx` per (analysis × scenario), each containing:

1. **Header section** — analysis name, project tag, framework version, component library version, git commit hash, generated timestamp, scenario identifier.
2. **Requirements block** — every requirement the analysis references, as named Mathcad variables with units, with comments carrying the Jama ID.
3. **Component parameters block** — every component-derived Quantity used (R_DS(on), V_BE, θ_JA, etc.), as named variables with units, scenario-resolved to the worksheet's scenario, with comments carrying the part number and `components/` path.
4. **Operating conditions block** — leaf Quantities the engineer declared as analysis inputs (drain currents, duty cycles, ambient temperatures, etc.), with provenance comments.
5. **Contract inputs block** — any cross-block Contract values consumed by the analysis, with comments naming the source block and contract.
6. **Expected results block** — the Python analysis's computed result values, listed but not derived, so the Mathcad engineer can confirm convergence after their derivation lands.
7. **Empty derivation region** — a clearly labeled section where the Mathcad engineer adds the math by hand.

**What the framework does *not* emit.** Any of the math. The point is that the Mathcad engineer derives independently from the requirements and operating conditions, not from the Python author's algorithm. Auto-supplying the derivation would defeat the cross-check.

**Scoping.** One worksheet per (analysis × scenario). Mathcad does not handle scenario products natively; emitting a worksheet per corner keeps each one a clean, self-contained derivation. Most contractual deliverables only require the worst-case corner; the framework defaults to emitting only the tightest/failing corner with a note pointing at the Python report for the rest.

**Process discipline (out of scope for the framework, in scope for team rollout).** The Mathcad engineer must not consult the Python author or read the Python analysis when deriving. If they do, the dissimilar-redundancy property collapses and the cross-check becomes review theater. Worth codifying in the team's PR review checklist for analyses with Mathcad deliverables.

**Implementation.** `.mcdx` is a zipped XML package; the emitter generates it from a template worksheet (one-time reverse-engineering effort against a hand-built sample). On Windows hosts with Mathcad Prime installed, the alternative is COM automation via `pywin32` — Mathcad renders its own math, the framework just feeds it inputs. COM is cleaner and more forward-compatible; XML emission is portable. The framework can support either; the choice can be deferred until a project actually requires the export.

**Relation to §12.4–12.5.** Mathcad export is a separate output channel from the HTML browser and PDF design-review artifacts. It does not replace them. Engineers' daily driver remains the notebook + HTML browser; Mathcad worksheets are produced on demand for specific contractual deliverables, not on every commit.

---

## 13. Layered Usage (Adoption Path)

Three layers, traversed by every engineer as they grow:

1. **Pre-built notebook.** Opens a templated `report.ipynb`, runs all cells, sees the block's report.
2. **Parameterize the notebook.** Edits inputs in the top cell — what scenarios to include, what part number to substitute, what mode subset.
3. **Write a new analysis function.** Adds a Hamilton node in `analysis.py` that performs a calculation specific to their block, possibly calling standard library analyses (`voltage_divider`, `rc_filter_cutoff`, `worst_case_droop`).
4. **Publish a Contract.** Declares a public commitment in `contracts.py` so downstream blocks can consume.
5. **Cross-block consumption.** Imports another block's Contract and integrates it into their own analysis.

No DSL, no YAML-driven analysis language. Python is the substrate. Training people on basic Python is part of the rollout.

## 14. Phase Boundaries

**v1 (initial release):**
- All of the above core abstractions
- Manual Altium netlist export → repo
- LTSpice integration via subprocess (engineer invokes from their analysis when needed)
- One-way Jama push (test runs)
- Local cache only
- **Live HTML browser** at `<product>/main/` regenerated on every push to main, plus per-tag snapshots. Hamilton DAG visualization, searchable contracts/tests, drill-through provenance, filterable verifications, tag picker, diff view between revisions.
- PDF design-review artifact on tags only, uploaded to SharePoint, indexed via `reviews/INDEX.md`.

**v2:**
- Altium live API sync for netlist + PSC component pulls
- Jama requirements pull (read-only)
- S3-backed remote cache for CI
- Cookiecutter template repo split out from the framework
- **Mathcad / Excel migration assistant** — a Claude Code subagent that reads legacy Mathcad sheets (.mcdx) and Excel analyses (.xlsx), walks the engineer through each formula, proposes Python framework equivalents, and emits a draft block subpackage. Parses Excel via openpyxl; Mathcad Prime via its XML archive format.
- **Mathcad inputs-only worksheet emitter** — generates a `.mcdx` per (analysis × scenario) containing requirements, component parameters, operating conditions, contract inputs, expected results, and an empty derivation region for independent re-derivation by a second engineer. See §12.9 for the channel and methodologies doc §11 for the rationale. Schedule-driven: pulled forward into v1 if any v1 project has a contractual Mathcad deliverable; otherwise lands in v2.

**v3:**
- Schematic-aware view layered onto the existing HTML browser: click a net, see voltage range, current, all verifications referencing it (the browser substrate already exists from v1; v3 adds the netlist-driven panel)
- PCB layout integration: trace parasitics, thermal coupling
- Statistical yield analysis as a first-class report

## 15. Suggested Implementation Order

1. `Quantity` type with Pint integration and arithmetic (with scenario propagation)
2. Scenario + Mode + project config loading (TOML)
3. `project/requirements.py` module and framework registry
4. Hamilton integration: DAG builder, execution across (scenarios × modes), content-addressed caching
5. Component library: Pydantic `Component` base class, MOSFET / resistor / capacitor / LDO / buck-converter / BJT initial types
6. Netlist parser (Protel ASCII), `Board` model, block ownership validation
7. `Contract` type, graph-build-time cycle detection
8. Run-time contract consistency checker
9. `VerificationTest` class, pytest plugin, output channels (Jama stub, PR comment, notebook table)
10. Provenance traversal + chain rendering helpers
11. Standard analyses library (voltage_divider, rc_filter_cutoff, worst_case_droop, current_limit_check, power_dissipation, thermal_rise)
12. Reporting layer: notebook templates with auto-rendered sections (header, status, contracts, verifications, coverage, consumers, provenance), `framework.plotting` helpers, PR comment bot (GitHub Action), live HTML browser hosted at stable URL with Hamilton DAG viz + search + drill-through provenance + diff view (regenerated on every push to main), PDF design-review artifact generator (WeasyPrint) on tags with SharePoint upload + `reviews/INDEX.md`, CI notebook execution gate
13. Cookiecutter for new analysis project + new block
14. `.claude/` setup, first agents, slash commands
15. CI pipeline: lint, mypy, pytest unit tests, verification tests, framework self-tests, contract consistency

## 16. Open Decisions Before Implementation

1. **Hamilton version pin and roll-our-own escape hatch.** Hamilton committed; pin minor version. If a critical feature is missing, are we comfortable contributing upstream rather than forking?
2. **Pint version and registry.** Pint 0.24+ recommended. Single shared registry exposed as `framework.units`; importing `from pint import UnitRegistry` directly should produce a lint warning to keep all units interoperable.
3. **`Contract` implementation: runtime type vs. decorator marker.** Recommend runtime type (instance check) so graph-build-time cycle detection is unambiguous.
4. **Netlist format.** Protel ASCII chosen. Confirm Altium reliably exports it for all current projects, including hierarchical schematics.
5. **Cookiecutter template repo or in-tree template?** Recommend separate repo so it can evolve independently and version against framework releases.
6. **Caching key includes component library version.** Means a component library bump invalidates the entire cache. Acceptable for correctness; revisit if CI cache hit rates suffer.

## 17. Quality Bar

- Coverage: 90%+ on framework code; 100% on `Quantity` arithmetic.
- Type checking: mypy strict on the framework; permissive (`--ignore-missing-imports`) on user-block code.
- Documentation: every public API has a docstring with at least one example.
- Examples: a reference analysis project (`example_analysis`) exercising every feature, used as both documentation and integration test.
- Self-tests: framework CI runs a synthetic project that exercises Contract cycles, mode propagation, scenario extension, provenance traversal, cache invalidation.

---

## Appendix A — Worked Example: The Mike/Dan Contract Loop

**Setup.** Mike owns `blocks/block_a` (a sensor MCU subsystem on the 3V3 rail). Dan owns `blocks/power_supply` (the buck regulator generating 3V3).

**Mike's contract** declares what he draws:

```python
# blocks/block_a/contracts.py
@contract(
    description="3V3 rail current draw",
    requirement="REQ-PWR-014",
    assumed_inputs={"rail_3v3_voltage": (3.15 * V, 3.45 * V)},
)
def block_a_3v3_draw() -> Quantity:
    return Quantity(by_mode={
        "sleep":  Quantity(by_scenario={"_": (5*uA, 12*uA)}),
        "active": Quantity(by_scenario={"_": (80*mA, 220*mA)}),
    }, unit=A)
```

**Dan's analysis** consumes the aggregated load and computes the actual rail voltage:

```python
# blocks/power_supply/analysis.py
from blocks.block_a import block_a_3v3_draw
from blocks.block_b import block_b_3v3_draw
from blocks.block_c import block_c_3v3_draw

def total_3v3_load() -> Quantity:
    return block_a_3v3_draw() + block_b_3v3_draw() + block_c_3v3_draw()

def vout_3v3(vin: Quantity, total_3v3_load: Quantity, ldo_dropout: Quantity) -> Quantity:
    # ... compute actual rail voltage accounting for droop
    return ...
```

**Mike's analysis** uses his Contract's assumed `rail_3v3_voltage` (NOT Dan's computed `vout_3v3`):

```python
# blocks/block_a/analysis.py
def block_a_actual_draw(rail_3v3_voltage_assumed: Quantity, ...) -> Quantity:
    # uses the Contract's assumed rail voltage range, not Dan's runtime computation
    ...
```

**Cycle prevention.** If Mike tried to import `from blocks.power_supply import vout_3v3`, the import validator refuses — Mike may only import Contracts from other blocks.

**Run-time consistency check.** After the DAG executes:
- Framework compares `block_a.actual_draw` against `block_a_3v3_draw()` (the Contract).
- Framework compares Dan's computed `vout_3v3` against the assumed range in Mike's Contract.
- Any violation fails CI with a precise location: scenario, mode, declared value, actual value, gap.

The result is that the system is always self-consistent or CI fails. No circular import, no fixed-point solver, no Mike-waits-for-Dan coordination overhead.

## Appendix B — Glossary

- **Block** — A Python subpackage owned by one engineer, corresponding to a circuit block / schematic page.
- **Component** — A Pydantic-typed object representing a physical part (part_number + parameters).
- **Contract** — A specially-typed Quantity that is a block's public commitment. Cycle cut-point in the dependency graph.
- **Hamilton** — Python DAG framework (DAGWorks). Used as the execution engine.
- **Mode** — A global system operating state (sleep, active, diagnostic, etc.). The whole board is in one mode at one time.
- **Pint** — Python units library. Mandatory throughout the framework.
- **Provenance** — Traceability metadata on every Quantity linking it back to its inputs.
- **Quantity** — The atomic data type representing any physical or derived value.
- **Requirement** — An external design target (operating temp range, supply spec, etc.), defined in `project/requirements.py`, linked to Jama.
- **Scenario** — A named environmental/operating corner (cold_low_vin, hot_high_vin, etc.). Project-global.
- **VerificationTest** — A first-class test type integrating pytest, Jama, and report generation.
