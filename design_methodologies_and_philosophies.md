# Design Methodologies & Philosophies

**Companion to:** `hardware_analysis_framework_design.md`
**Purpose:** This document explains *why* the framework is built the way it is. The design spec tells you *what*; this tells you *why*. Read this when you want to challenge a decision, train a new engineer, or extend the framework into new territory without breaking its principles.

---

## 1. Worst-case analysis — why corners, not combinatorial, not Monte Carlo by default

### The problem we're solving

Hardware analysis exists to answer questions like: "given component tolerances, environmental variation, and load conditions, will this rail stay within spec?" The naïve answer — pick the worst value of every parameter independently — is wrong, and dangerously so.

### Why "every parameter at its independent worst" is wrong

Take a simple example: a current through a divider where R1 and R2 are both Vishay CRCW resistors. Each has a ±1% tolerance. The current is `V / (R1 + R2)`. If you ask "what's the worst-case current?" the naïve answer is: maximize V, minimize R1 + R2 by putting both at -1%. So current goes up by ~2% above nominal.

But now consider voltage *across* R1: `V × R1 / (R1 + R2)`. The naïve worst case here puts R1 at +1% (to maximize the numerator) and R2 at -1% (to minimize the denominator).

Notice the contradiction: the first analysis says R1 is at -1%, the second says R1 is at +1%. **The same physical resistor cannot be at two values at once.** When you naïvely combine these answers downstream — say, in a power dissipation calculation that uses both current and voltage — you've assumed R1 is simultaneously short and long. The result is a worst case worse than physically possible.

This is the **correlation problem**. Parameters that share a physical source are correlated; you cannot treat them as independent without losing meaning.

### Why combinatorial enumeration doesn't fix it (and can't scale)

You might think: "Okay, just enumerate every combination of {min, nom, max} for every parameter, then throw out the contradictory ones." This addresses the correlation problem in principle but fails in practice for two reasons:

1. **It doesn't scale.** With 20 parameters that's 3.5 billion combinations. A real board has hundreds. The combinatorial explosion is infeasible long before correctness becomes the issue.
2. **It's pessimistic even when feasible.** No real device exists at the simultaneous extreme of every parameter. A board where every resistor is at +1%, every capacitor at -10%, every MOSFET at max RDS_ON, every junction at peak temperature, all at once, has effectively zero probability of being manufactured. Your "worst case" is a fiction. This is why semiconductor and tolerance engineering moved from worst-case to **RSS (root-sum-of-squares)** and Cpk-based statistical limits decades ago. Combinatorial worst-case bankrupts your design margin against a scenario that will never occur.

### The two answers that actually work

**Named corners (the default).** Define a small set of scenarios — `cold_low_vin`, `hot_high_vin`, `nominal`, `EOL_worst_thermal`, etc. — where each parameter has *one* value per scenario. Each scenario is an internally consistent worldview: R1 has one value at `hot_high_vin`, and that same value is used in *every* calculation involving R1 at that scenario. Correlation is handled by construction. The whole DAG is evaluated once per scenario.

Corners match the engineering tradition. Datasheets give you values "at 25°C, 5V supply" — that's a corner. Worst-case design intuition operates in corners. Reviewers can audit a corner and reason about it ("does this scenario represent the hot deserts of Arizona in summer with battery at 16V?"). And the math is correct, because each scenario is consistent.

The cost: you have to think about which corners matter. Picking corners is engineering judgment, not automation. The framework can suggest defaults from `OPERATING_TEMP` × `VBAT`, but the team owns the scenario set.

**Monte Carlo (opt-in for specific analyses).** Sample each parameter from a distribution *once per trial*, run the whole DAG, accumulate statistics across trials. Correlation is preserved within a trial because R1 is sampled once and used everywhere consistently. Monte Carlo gives you the *distribution* of outcomes — including the tails — at the cost of needing distribution assumptions you may not have.

Monte Carlo is the right tool for:
- Yield-sensitive trims (a 1.225V reference, ±0.5% over corners and statistical drift)
- EMI margins (statistical compliance to FCC Part 15)
- Manufacturing tolerance budgets (Cpk targets)
- Any analysis where the answer is "what fraction of devices fall outside spec"

It is the wrong tool for routine power-budget and rail-margin analysis, because:
- You usually don't have good distribution data (datasheets give tolerance bounds, not σ)
- Engineering teams reason about extremes ("the rail must not drop below 3.15V"), not probabilities
- Reviewers can't audit "we ran 10,000 simulations and 99.97% passed" the way they can audit a corner

### Where this leaves us

The framework treats corners as the *default* representation. Every Quantity carries `by_scenario`. Every analysis runs across all defined scenarios. Engineering reviews happen in the language of corners. Monte Carlo is available — Quantities can carry distributions, and `framework.simulate(n=10_000)` runs the DAG statistically — but it is opted into for specific analyses where the question is statistical.

We explicitly reject combinatorial enumeration. The framework will not provide it, will not encourage it, and the documentation will explain why. It is a footgun we are choosing not to build.

---

## 2. The Contract pattern — interface versus implementation, applied to hardware

### The problem: cycles between engineers' analyses

A power-supply engineer's analysis depends on what other engineers' blocks draw. But those blocks' draws may depend on the supply voltage the PSU produces, which depends on the load, which depends on the draws... Naïvely modeled, every block transitively depends on every other block and you have a dependency cycle.

You could try to solve it: a fixed-point iterative solver, like SPICE does for the operating point. Two problems:
1. You'd be reinventing SPICE poorly. If you wanted to solve coupled equations across the whole board, you'd already be using SPICE.
2. Even if you did, the cycles would obscure design intent. Engineering specs aren't iterative — they're declarative ("the rail shall stay within ±5% under loads of up to 1A").

### The hardware-engineering analog

Look at how an actual engineering team handles this without software. They use *spec sheets*. The power-supply engineer says: "I commit to 3.3V ±5% from no-load to 1A." The MCU engineer designs against that spec, not against the actual instantaneous output voltage. The two engineers don't need to iterate — they exchange declarations.

This isn't a software trick. It's how spec-driven engineering has always worked. The framework formalizes it.

### Contracts as the formalization

A **Contract** is a typed Quantity that an engineer publishes as their block's public commitment. "I draw between 80mA and 220mA from the 3.3V rail in active mode, assuming the rail stays within 3.15–3.45V." The Contract carries:
- The committed value (a Quantity with corners and modes)
- The assumed inputs (the boundary conditions under which the commitment holds)
- A Jama requirement link
- A description

Other blocks consume the Contract — never the underlying analysis. The PSU engineer sums every block's `*_draw` Contract to size the regulator. The MCU engineer designs against the assumed 3.15–3.45V range, never against the PSU's instantaneous computed output.

### Why this is more than a software pattern

The Contract is a forcing function for good engineering. It asks each block author: *What does my block promise the rest of the system?* That's the most important question they need to answer, and the framework makes it explicit and unavoidable. A block without contracts is a block that hasn't been integrated into the system's design.

The Contract is also a versioning boundary. Internal analysis math changes constantly as engineers refine their work. Contracts change less often — only when the block's external behavior changes. A diff in `contracts.py` signals "downstream impact must be considered." A diff only in `analysis.py` is locally contained. The review surface is structured by file location.

### Two phases of verification

A contract is meaningful only if it's *checked*. The framework checks it in two phases:

**Structural (graph-build time).** Before any analysis runs, the framework verifies that no Contract transitively depends on a non-Contract output of another block. This is a static graph property: walk every Contract's dependency subgraph, fail if it reaches a non-Contract owned by a different block. Errors surface at module load with a clear path: *"Contract `psu.vout_3v3` depends on `block_a.power_dissipation` (non-Contract) — express the dependency via `block_a.current_draw` (a Contract) instead."*

This phase catches design errors *before* you've spent any time running analysis. You cannot construct an analysis with cycles and then try to debug them — the framework refuses to load.

**Behavioral (run-time).** After the DAG executes, the framework compares every Contract's declared value against the block's actual computed value of the same quantity. If Mike committed to drawing at most 220mA active but his analysis (now using Dan's real PSU output) shows 235mA in `hot_high_vin`, an auto-generated `ContractViolation` test fails with the precise scenario, mode, declared bound, actual value, and gap. The engineer doesn't write this assertion — the framework generates it for every Contract.

The combination means: contracts are *valid* (cycle-free, well-formed) at graph-build time and *honest* (declared matches reality) at run-time. Both phases are automatic.

### What this rules out and what it costs

It rules out fixed-point iterative solvers across blocks. If you have a feedback loop whose small-signal behavior genuinely requires iteration, you model it inside one block using a real tool (LTSpice via subprocess), not across the Hamilton DAG. The Contract pattern is for steady-state, decoupled-block design — which is the overwhelming majority of board-level analysis.

It costs you the discipline of declaring contracts. Engineers must think about their block's public commitment. We consider this a feature.

---

## 3. Everything is a Quantity (and a Quantity is more than a float)

### Why raw floats are forbidden

The naïve way to represent values is as Python floats. A current is `0.085`, a voltage is `3.3`, a resistance is `10000`. This is wrong in three independent ways:

1. **No units.** Is `0.085` amps or milliamps? Is `10000` ohms or millivolts? Python doesn't know, and neither will the next engineer reading the code. The Mars Climate Orbiter crashed in 1999 because two teams used different units in their interface. Hardware engineering has the same failure mode, and we choose not to invite it.
2. **No worst-case context.** A float is one number. Worst-case design needs ranges or distributions. A current is rarely "85mA" — it's "between 80mA and 220mA in active mode, between 5µA and 12µA in sleep mode." A float can't express that, so engineers reach for tuples or dicts, and conventions diverge across the team.
3. **No provenance.** A float carries no record of where it came from. If a design review asks "why is this number 235mA?" the engineer has to manually trace through code. With provenance attached, the framework can answer.

### What a Quantity is

A Quantity is a typed container carrying:
- The value (per-scenario, per-mode, or distribution)
- The unit (Pint, mandatory)
- The provenance (a content-addressed pointer to its source DAG node)

Arithmetic on Quantities propagates all three. `q1 + q2` produces a new Quantity whose values are computed scenario-wise, whose unit is verified compatible, whose provenance points to the combining operation. You can never accidentally add amps to volts; the framework catches it.

### Why Pint specifically

Pint is the standard Python units library: battle-tested, NumPy-compatible, with a unit registry rich enough for engineering. It catches dimensional errors at compute time with clear messages ("Cannot convert from 'ampere' to 'volt'"). It supports the engineering prefixes you actually use (µ, m, k, M). It survives serialization through JSON and Excel exports. Mandating Pint costs nothing once engineers internalize the discipline; not mandating it costs the team unit-confusion bugs forever.

We use a single shared Pint registry exposed as `framework.units`. Importing `from pint import UnitRegistry` directly produces a lint warning. This is intentional: a single registry means quantities are interoperable across every block, every analysis, every test. Multiple registries silently fail to convert.

### Why provenance matters

Provenance is the answer to "explain this number." In design review, the most valuable question a reviewer can ask is: "where did this come from?" With provenance, the framework can produce a traversal back to root inputs: this current came from `block_a.current_draw` × `psu.vout_3v3`; `vout_3v3` came from `vin - ldo_dropout`; `vin` came from `VBAT.nominal`; and so on. The reviewer can challenge any step.

Provenance is also the basis for cache invalidation, because content-addressed caching needs to know "what produced this value." It's not an add-on feature — it's woven into the framework's foundation.

We store provenance as a Merkle-DAG reference: each Quantity points to its source DAG node by hash. Walking the chain is on-demand. Storage is O(1) per Quantity, traversal is O(depth) when requested, and cycles cannot occur because graph-build-time cycle detection has already eliminated them.

---

## 4. Python, not a DSL

### The temptation

When a team has engineers at varying Python skill levels, it's tempting to build a higher-level interface: YAML configs, a JSON-driven analysis language, a GUI form-filler. The pitch is always: "make it accessible to non-coders."

### Why it fails

Every team that builds a DSL for technical analysis hits the same wall. Users want to do something the DSL doesn't support. The team adds an escape hatch. Then another. Then a way to call Python from the DSL. Eighteen months in, the DSL has reinvented Python — poorly — and the maintenance burden of the parallel toolchain has crushed the productivity gain. Worse, the documentation, examples, and Stack Overflow questions are all in Python; the DSL is on its own.

### The principle

Python *is* the interface. The framework's API is the interface. Type hints, autocomplete, hover docs, the debugger, pytest, the entire ecosystem — engineers get the lot for free.

The path for engineers who aren't yet comfortable with Python:
1. **Open a pre-built notebook.** It Just Runs.
2. **Tweak inputs in the top cell.** Substitute a part number; restrict to a mode subset. Still no real coding.
3. **Call a standard analysis function.** `voltage_divider(top=R5, bottom=R6, vin=VBAT)`. One line of Python.
4. **Write a custom Hamilton node.** A function with type hints. Five to ten lines.
5. **Publish a Contract.** Mark a function `@contract(...)`. The block becomes a citizen of the system.

Nobody is locked out. The substrate is consistent. The team trains people on basic Python as a baseline skill — a reasonable expectation for engineers in 2026 — and the framework's API is shaped so the on-ramp is shallow. We provide rich examples, a CLAUDE.md that the agent uses to help, and a `/new-block` workflow that scaffolds a working block. By the time an engineer needs to write a Hamilton node, they've already been editing notebook cells for weeks.

### What this gives up

The framework gives up the appearance of accessibility to people who refuse to learn any Python at all. We accept that. The alternative — a DSL parallel toolchain — costs more than it saves over a five-year horizon. Better to invest the same effort in training, examples, and AI-assisted scaffolding.

---

## 5. The DAG model and Hamilton

### Why a DAG at all

A board-level analysis is a graph of dependencies. The 3V3 rail droop depends on the load, which depends on every block's draw, which depends on each block's components and modes. Representing this as a DAG isn't a choice; it's just the shape of the problem. The question is whether we build the graph by hand (e.g., a class hierarchy with explicit `parent`/`children` references) or let the framework derive it.

### Why function signatures

Hamilton derives the DAG from function signatures: each function is a node; parameter names match the output names of other nodes. `def vout_3v3(vin, total_load, ldo_dropout)` automatically wires to whichever functions produce `vin`, `total_load`, `ldo_dropout`. This has three benefits:

1. **The graph is obvious from the code.** No separate wiring file, no `pipeline.add_node()` boilerplate. The function *is* the node, the parameter *is* the edge. New engineers reading the code see the graph.
2. **Refactor is free.** Rename a function, all consumers track the new name (with IDE help). Add a parameter, the DAG picks it up. No wiring to maintain.
3. **Testability is free.** Each Hamilton node is a pure function. Test it like any other function: pass in inputs, assert on outputs.

### Why Hamilton specifically

Hamilton (from DAGWorks, formerly Stitch Fix) has solved the hard parts: function-signature parsing, parameterization across an axis, content-addressed caching, visualization, parallel execution. It is battle-tested at scale in ML pipelines, which have the identical structural problem. Building our own DAG framework would burn six months and we'd end up with something less capable.

Hamilton is also extensible. The Contract type, the scenario × mode parameterization, the content-addressed cache key, the introspection API for the Claude Code agent — all of these are framework-specific extensions on top of Hamilton's primitives. We get the foundations for free and customize the layer above.

The cost is the dependency on a third-party library. We pin a minor version, contribute upstream when we hit edges, and accept that this is a better trade than rolling our own.

### Why content-addressed caching is more than a speed trick

Content-addressed caching hashes each node's inputs (function source bytes + input values + framework version + component library version) and keys outputs by the hash. Identical inputs produce identical hashes, and cached outputs are returned without recomputing.

The obvious benefit is speed: a PR that touches one block doesn't re-run the entire board's analysis. The less-obvious benefits are correctness and reproducibility:

- **Correctness.** "Did I change anything that affects this result?" becomes decidable. If the hash matches, nothing changed. This eliminates the class of bugs where an engineer thinks they're seeing a stale result.
- **Reproducibility.** A given commit produces deterministic hashes, which produce deterministic results. A failing CI run today reproduces tomorrow. Hardware engineering at this depth has historically been ad-hoc and irreproducible; content-addressed caching gives us auditable design history.
- **CI scaling.** Phase 2's S3-backed remote cache lets every PR start from the latest main's cache. A PR that touches one analysis re-executes O(touched nodes), not O(whole board).

### Why cycle detection at graph-build time

The framework refuses to construct a DAG containing a cycle. This catches design errors at module load — *before* any analysis runs. Compare to the alternative: discover the cycle at run-time, when a stack overflows or a fixed-point fails to converge after an hour. Graph-build detection is fast, deterministic, and produces clear error messages naming the offending path and suggesting the fix.

This is why Contracts are mandatory cut-points. A graph where any function can cross a block boundary is too permissive — cycles sneak in through transitive chains and detection becomes tedious. A graph where only Contracts cross boundaries has a single rule: "no Contract transitively depends on a non-Contract owned by another block." The rule is simple, the check is fast, the error messages are clear.

---

## 6. Discoverability is a first principle

### Why this matters more than people think

In a six-person team, the cost of an engineer not finding a requirement, a scenario, or a component instance is small individually but compounds across the team and the years. The same questions get re-asked. The same mistakes get re-made. Tribal knowledge accumulates as a tax on every new hire.

Discoverability is the antidote. Every artifact has a *single, obvious place* it lives:

- **Project requirements** live in `project/requirements.py`. One file, importable from anywhere, type-hinted, hover-doc'd in VS Code. Every requirement carries a Jama ID. The framework offers `framework.requirements.list()` and `framework.requirements.show("REQ-PWR-001")`. The Claude Code agent offers `/show-requirements` and `/find-requirement <topic>`.
- **Scenarios** live in `project/scenarios.toml`.
- **Modes** live in `project/modes.toml`.
- **Components** live in the `components` package, organized by type, family, and instance. The agent offers `/find-component <part-number-or-description>`.
- **A block's public surface** is exactly `blocks/<block>/contracts.py`. Anything else is private.
- **Tests** live next to the analysis they test (block-scoped) or in `project/verifications/` (system-scoped).

### The principle

If an engineer has to ask another engineer where something lives, that's a discoverability failure and the framework or its documentation should be fixed. New engineers find their answers by reading code (made readable by conventions), using autocomplete (made informative by type hints), or asking the Claude Code agent (which is briefed by `CLAUDE.md` on every convention).

This is why naming conventions are enforced by lint. It's why one-file conventions are absolute. It's why introspection APIs (`framework.describe()`) return everything in JSON form. The framework is designed to be *navigable* — by humans and by AI agents.

---

## 7. Testing philosophy — VerificationTest as a richer abstraction

### Why pytest alone isn't enough

pytest is great for unit testing. The framework uses pytest as the execution engine. But pytest's `assert` model collapses a test result to a boolean — and we need more.

A verification test in hardware analysis answers a design-review question: "does the rail meet spec across all corners and modes?" The reviewer wants to know:
- Did it pass?
- If it failed, in which scenario and mode?
- What were the actual values?
- What's the margin to the spec edge?
- Which Quantity provenance chain produced the result?
- Which Jama requirement does this satisfy?

A boolean throws all of that away.

### The class-based abstraction

`VerificationTest` is a first-class class that carries metadata (name, requirement ID, severity, applicable modes) and produces a rich `TestResult` (pass/fail, failed scenario-mode pairs, evidence, margin, markdown summary, provenance). One definition feeds four output channels:

- **pytest** — for CI and local test runs
- **Jama push** — structured test-run records linked to requirement IDs
- **Notebook reports** — rendered as tables with pass/fail/margin columns
- **PR comment bot** — concise summary on every pull request

The engineer writes the test once. The framework dispatches the result to the right place in the right format.

### Why tests live in two places

Block-scoped tests live next to the analysis they test. The block author owns them; a change to the analysis can update the tests in the same PR; the diff stays local.

Project-scoped tests live in `project/verifications/`. These are cross-block integration tests, system-level requirements, contract-consistency checks. They're owned by the integration role — a senior engineer or a dedicated reviewer — and are the system's truth set.

Both locations are run by CI on every PR. The two-location pattern is not about which tests are "more important" — they're both critical — but about ownership and locality.

---

## 8. Block ownership — Conway's Law in your favor

Conway's Law: organizations design systems that mirror their communication structure. The team's organizational structure (one engineer per circuit block) is going to determine the framework's structure whether we plan for it or not. So we plan for it.

A block is a Python subpackage. One engineer owns it. Their contracts are the team's contract with that engineer. PR review for that block goes to that engineer. CI ownership for that block's tests goes to that engineer.

This is good. It means:
- Code ownership matches engineering ownership.
- Reviews are fast (one expert per block).
- Refactoring is local (you change your block; contracts insulate consumers).
- Onboarding is bounded (a new engineer learns one block first).
- Performance reviews can reference specific blocks.

It also means the framework cannot rescue you from organizational pathology. If the team is unclear about who owns what, the blocks will mirror that confusion. Ownership clarity is a prerequisite, not an output, of the framework.

---

## 9. The Claude Code agent as a first-class team member

### Not bolted on — designed in

The Claude Code agent is treated as a first-class team member from day one. Not as a feature added after launch. The framework is designed *to be navigable by an agent*:

- Type hints on every public function.
- Comprehensive docstrings (Google style).
- Consistent error messages with `Did you mean ...?` suggestions.
- Introspection API (`framework.describe()`) that returns the DAG, scenarios, modes, components, contracts, and tests in JSON form.
- A curated `framework.__all__`.
- A `.claude/` directory checked into every repo with `CLAUDE.md`, custom subagents, and slash commands.

These same disciplines pay off for human readers. Good docstrings help humans. Clear error messages help humans. The Claude Code agent and a new engineer are reading the same artifacts — the framework just makes both first-class audiences.

### The agents

**`analysis-helper`** — for block authoring and debugging. Scaffolds new blocks (`/new-block <name>`), explains scenario coverage gaps (`/audit-coverage`), traces failures (`/explain-failure <test_name>`), walks the provenance chain of a Quantity (`/explain-quantity <name>`).

**`design-reviewer`** — for PR review. Walks changed analyses, identifies affected verification tests, summarizes worst-case margins, flags missing scenarios or untested modes, posts the summary as a PR comment.

**`migration-helper`** (v2) — reads legacy Mathcad sheets and Excel analyses, walks the engineer through each formula proposing Python equivalents, emits a draft block subpackage.

### Why this matters for adoption

The biggest barrier to adopting a Python-based analysis framework with engineers at varying Python skill levels is the on-ramp. The agent shrinks the on-ramp. A new engineer pulls the repo, opens Claude Code, asks "I need to add analysis for the CAN transceiver block — current draws per mode, dissipation, junction temp," and gets a working skeleton. They iterate on it. They learn by reading what the agent produced and by asking follow-up questions.

The agent doesn't replace engineering judgment. It accelerates it.

---

## 10. ASPICE 4.0 alignment

ASPICE (Automotive SPICE) is a process assessment model widely used in automotive electronics development. It defines maturity levels around requirements management, design, verification, traceability, and configuration management. The framework aligns with several ASPICE 4.0 principles natively, without being designed around them:

- **Traceability (SWE.1, SWE.6).** Every Quantity carries provenance back to root inputs. Every VerificationTest links to a Jama requirement ID. Every Contract carries a requirement ID. The chain from requirement → contract → analysis → test result → Jama test run is automatic.
- **Bidirectional requirements traceability.** Tests reference requirements by ID; requirements (in `project/requirements.py`) carry their Jama ID. The framework can produce a coverage matrix on demand.
- **Configuration management (SUP.8).** Everything is in GitHub Enterprise. Component library is versioned independently. Analysis projects pin component library versions. Reproducibility is enforced by content-addressed caching.
- **Verification (SWE.4, SWE.6).** VerificationTests are first-class artifacts with rich evidence. Test results are auditable; provenance chains are preservable.
- **Design (SWE.2, SWE.3).** Contracts make block-level interfaces explicit and reviewable. The block-as-subpackage structure mirrors the engineering ownership structure.

What the framework does *not* automate is the process side of ASPICE — formal reviews, role separation, training records, defect tracking. Those are organizational, not technological. But by making the technical artifacts rigorous, the framework removes friction from process compliance, which is usually where ASPICE adoption stalls.

---

## 11. Independent re-derivation as cross-check — when external constraints force a second representation

External constraints sometimes require an analysis to exist in two tools at once. The most common case in automotive electronics is a contractual deliverable that mandates Mathcad worksheets even though the team's working environment is Python. The instinctive response is to build a translator — auto-generate the Mathcad from the Python — and treat the second representation as a derived artifact.

This is the wrong instinct. A translator faithfully reproduces conceptual errors. If the Python analysis silently uses the wrong thermal resistance or the wrong duty cycle, the auto-generated Mathcad uses the same wrong values, and a reviewer reading the Mathcad has no independent basis to catch it. The two artifacts agree, but they agree because they're literally the same calculation written twice. That isn't verification; it's review theater.

The correct response is to **treat the second representation as an independent re-derivation** done by a different engineer, working from the same authoritative inputs (requirements, component parameters, operating conditions, contract values) but deriving the math afresh. Two engineers, two tools, two derivations. If the numbers agree, that is real evidence that both are correct. If they disagree, the discrepancy points cleanly at the math rather than at typos in the inputs — because the inputs are mechanically shared from a single source of truth.

This pattern has names in adjacent fields: dissimilar redundancy in avionics, the four-eyes principle in finance, differential testing in software. All of them rest on the same observation: two independent paths to the same answer is stronger evidence of correctness than one path with a checker.

### How the framework supports it

For the Mathcad case specifically, the framework emits **inputs-only worksheets** (see design spec §12.9): every requirement, component value, contract value, and operating condition declared as a named Mathcad variable with units and provenance comments, but with the derivation region intentionally left empty. The verification engineer fills it in. The framework provides the inputs and the expected results; the human provides the math.

### The principle generalizes

Any time external constraints force a second representation — a customer-specific spreadsheet template, a legacy LTSpice deck, a regulatory-mandated calculation form — the framework should emit inputs and let a human re-derive, not auto-translate. Translation collapses two artifacts into one with extra steps. Re-derivation buys real verification at modest cost.

The same logic argues *against* generating "fully worked" Mathcad files for review purposes even when no contractual deliverable forces the issue. If a reviewer wants to cross-check an analysis, the cheapest way to make their review meaningful is to hand them the inputs and let them derive — not to hand them the same calculation in two visual styles.

### The discipline that makes it work

Re-derivation is only verification if the verifying engineer does not consult the original analysis. The moment they read the Python source, talk through the algorithm with the author, or copy the structure from a previous Mathcad sheet, the two derivations become correlated and the cross-check degrades. This is organizational, not technological — it belongs in the team's review process documentation, not the framework. The framework's job is to make the discipline cheap to follow (inputs are auto-supplied; provenance is auto-attached) and the discipline's job is to keep the cross-check honest.

### What this turns the obligation into

A contractual Mathcad requirement read naively is overhead — a second deliverable to maintain in a worse tool. Read this way, it becomes a structured, externally-enforced verification step. The contract pays for the second pair of eyes. The framework hands those eyes a worksheet pre-populated with everything except the math. The deliverable is satisfied; the analysis is more verified; nobody had to translate any Python.

---

## 12. Summary — the principles in one place

When in doubt about a design decision, apply these principles:

1. **Worst-case is corners by default; Monte Carlo is opt-in; combinatorial is forbidden.**
2. **Contracts are the only thing crossing block boundaries.** Cycles are caught at graph-build time. Consistency is checked at run-time.
3. **Everything is a Quantity.** Floats are forbidden. Units are mandatory. Provenance is universal.
4. **Python is the substrate.** No DSL. Layered usage so nobody is locked out.
5. **Hamilton is the DAG engine.** Function signatures define the graph.
6. **Content-addressed caching is foundational.** Reproducibility and CI scaling, not just speed.
7. **Discoverability is a first principle.** One obvious place for everything. Conventions enforced by lint.
8. **Tests carry rich evidence.** One definition, four output channels.
9. **Blocks are subpackages owned by one engineer.** Conway's Law in your favor.
10. **The Claude Code agent is first-class.** The framework is designed for human + agent navigation.
11. **Independent re-derivation is verification, not translation.** When external constraints force a second representation of an analysis (Mathcad worksheets, legacy templates, customer-specific forms), emit only the inputs and let a different engineer re-derive the math. Two independent paths to the same answer is real verification; auto-translating Python into another tool is review theater.

When extending the framework, ask: does this extension preserve these principles, or does it require breaking them? If it requires breaking them, document the reasoning explicitly. If it preserves them, ship it.
