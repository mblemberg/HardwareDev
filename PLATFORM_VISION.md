# Platform vision — next-gen hardware development platform

**Status:** north-star / aspirational. Captured from Mike's notes, 2026-05-31.

This is the larger vision the `hw_analysis_framework` is *one component of*. The
framework (worst-case analysis, Quantities, contracts, the DAG) is the Python
core; this document records the surrounding platform it's meant to grow into.
Nothing here is committed scope — it's the direction that informs design
decisions in the framework today. Where a piece already has a concrete home in
the framework spec, that's noted inline.

> Guiding claim from the notes: *"when the Python development is finished, it
> means the rest is finished as well."* The analysis framework is the hard core;
> the integrations below are the platform that wraps it.

## The conceptual core: contract vs. characterization

Two complementary models of every device:

- **The contract** — the *synthetic* analysis built from component specifications
  and datasheets. This is worst-case, corner-based, and is what the framework
  computes today. It is the promise.
- **Characterization** — how the device *really* behaves, measured across real
  samples (and across lots) in different conditions, expressed **as a
  distribution**. This is the empirical truth, and it validates (or breaks) the
  contract.

The platform's job is to hold both and reconcile them: the contract bounds the
behavior; characterization tells you where within those bounds reality actually
lands, and with what spread.

> Framework hook: design doc §6.1 already reserves a `distribution` field on
> `Quantity` (currently deferred), and §7.5 specifies opt-in Monte Carlo that
> *convolves* distributions. Characterization data is the natural producer of
> those distributions. See the design-exploration notebook
> [`quantity_as_function.ipynb`](quantity_as_function.ipynb) §6.

The platform offers a **holistic model of device operation across all operating
modes and scenarios**:

- **Modes** = *"what I'm doing"* (the device's own operating state).
- **Scenarios** = *"what my surroundings are doing"* (the environment/corner).

> Framework hook: `by_mode` / `by_scenario` axes on `Quantity` (design doc §6.2,
> §6.3) already encode this split.

## Integration surfaces (the platform around the core)

Captured roughly in the notes' order. Each is a future integration; none is built.

- **Functional-safety (FuSa) analysis** — FMEDA, FIT-rate calculation, and
  related ISO-26262-style artifacts driven off the same component + analysis
  model.
- **Git-based configuration management** — the whole design state (analyses,
  netlists, component pins, results) versioned and diffable. (The framework
  already leans on this: content-addressed caching, per-tag report snapshots.)
- **Altium integration** — schematic/PCB as a source of truth feeding the
  netlist and component data. (Design doc §10 + §14: manual netlist export in
  v1, live API sync in v2.)
- **Jama integration** — requirements + verification traceability. (Design doc
  §12.8 + §14: one-way push of test results in v1, requirements pull in v2.)
- **Characterization integration via ec-test + rack** — pull real measured
  device behavior (samples across lots, across conditions) off the lab bench
  into the platform as distributions. Pairs with the long-term lab-verification
  bridge (driving Mike's existing lab-control software from VerificationTests).
- **Silicon Expert integration** — pricing/lifecycle data, used as a **fallback**
  when internal pricing with a linked quote isn't available.
- **Dynamically-updated reports** — reports regenerate as the underlying design
  state changes. (Design doc §12 live HTML browser + design-review artifacts is
  the v1 seed of this.)
- **Interface for reconfiguring / connecting circuit blocks** — a way to wire and
  rewire the block graph (the contracts/consumers topology) interactively,
  rather than only in code.

## Open questions raised in the notes

- **Overlapping / inter-related scenarios.** How to handle scenarios that
  co-occur or interact — e.g. "hot" *and* "reverse battery" simultaneously. The
  current model names discrete corners; combinations aren't first-class.
  - Candidate direction from the notes: *maybe scenarios should never really be
    named, but instead encoded in variables* — i.e. represent the environment as
    a variable space that corners are drawn from, rather than a fixed list of
    named corners. This is a real fork in the worst-case representation; see
    [`quantity_as_function.ipynb`](quantity_as_function.ipynb) §6.4.

- **`by_mode` discipline.** From the notes: `by_mode` *"should only really be
  used to change things that can't be encoded in variables, like
  `IGNITION_VOLTAGE`."* Most variation should ride on ordinary input Quantities
  flowing through the DAG, not on hand-keyed mode dicts.

- **Derived / computed modes.** *"Blocks can maybe have their own modes that make
  sense to them, but those can be determined by inputs from other blocks or the
  project."* Today `by_mode` is a static `name → Quantity` map; selecting which
  mode a block is in *as a function of its inputs* is an unmodeled capability.
  Worked through in [`quantity_as_function.ipynb`](quantity_as_function.ipynb) §6.1.
