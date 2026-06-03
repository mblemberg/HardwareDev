# Quantity v2 — the distribution-over-condition-space model (design sketch)

**Status:** forward-looking / north-star. **Not** a Phase-1 change. The current
`Quantity` (design doc §6.1) stays exactly as-is until this is explicitly
scheduled. This note records the direction while it's sharp, so a future phase
can pick it up deliberately. Captured 2026-05-31.

Related: `hardware_analysis_framework_design.md` §6.1 (current Quantity), §7.5
(worst-case vs Monte Carlo), `PLATFORM_VISION.md` (the characterization-vs-contract
duality this model unifies).

---

## 1. What feels unnatural about today's Quantity

The present type represents "how a value varies" with several overlapping fields
— `value` (scalar/range), `by_scenario` (named-corner dict), `by_mode`
(named-state dict), plus a reserved-but-unbuilt `distribution`. Four symptoms
that this is the wrong cut:

1. **It stores samples of a function as if they were a lookup table.**
   `by_scenario={'cold': 9, 'hot': 16}` is a *sampled* function of temperature,
   memoized at two named points and disconnected from the variable that causes
   the variation. Author that on every leaf and a large project becomes a swamp
   of magic numbers.

2. **A lookup table has "missing keys"; a function doesn't.** The cryptic
   `KeyError: '_ALL_'` when combining `{cold}` with `{cold, hot}` (a real edge in
   the current code) is a *symptom* of the lookup-table framing, not an
   incidental bug. A value that doesn't depend on temperature should simply be
   *defined everywhere*, not "missing the hot key."

3. **It conflates two physically different kinds of variation** (see §4) into one
   `by_scenario` dict, while the kind it *doesn't* model well (intrinsic spread)
   was bolted on as an optional `distribution`.

4. **Named, enumerated axes don't compose.** `hot` and `reverse_battery` are
   points, not a space, so "hot AND reverse-battery" needs its own hand-written
   row. (This is the page-1 open question.)

## 2. The model, in one sentence

> A `Quantity` is a **function from a shared condition-space to a distribution**,
> and it is non-trivial only along the dimensions it is *programmed* to be
> sensitive to.

- **Distribution** (always present): every value carries spread. The simplest
  form is a `(min, max)` interval; richer forms add a nominal or a continuous
  shape.
- **Condition-space**: a project-global set of named **dimensions** —
  `temperature`, `mode`, `vbat`, … — analogous to today's scenario/mode axes
  promoted to first-class, composable variables.
- **Sensitivity**: how a Quantity's distribution responds to a dimension
  (`linear(100 ppm/°C)`, `gated_to_zero(mode=sleep)`, piecewise…). A Quantity
  declares sensitivity to the few dimensions it cares about and is **constant**
  along all the rest.

## 3. The distribution representation

Discrete worst-case form (the common case):

- `(min, max)` is interpreted as a **uniform distribution** over the interval.
- `nom` is an **optional named sample** — the labeled nominal/typical value
  (datasheet "typ", design center). **Invariant: `min ≤ nom ≤ max`.** It is *not*
  necessarily the mean; it's a distinguished point carried alongside.

Three tiers, one type:

| Tier | Uses | Reads |
|---|---|---|
| **Worst-case** (default) | the `(min, max)` interval — exact bounds | `min`, `max` |
| **Nominal** | the labeled `nom` sample | `nom` |
| **Monte Carlo** (opt-in, §7.5) | the distribution *shape* — uniform by default, refinable to Gaussian/etc. | full distribution |

**Why "uniform" is the right default:** worst-case math only ever touches the
bounds, so the shape is irrelevant there. The shape only matters once you sample
for yield/MC — and uniform is the honest default ("we know the band, not the
shape"), upgradeable per-leaf when characterization data justifies it.

**Closure under worst-case arithmetic.** `(min, max, nom)` is closed under the
worst-case operations:

- interval combines by interval arithmetic (`X+Y → (xmin+ymin, xmax+ymax)`;
  multiplication takes the corner envelope, as today's range math does),
- `nom` combines by ordinary nominal arithmetic (`xnom + ynom`, `xnom * ynom`).

The *true* convolved shape (sum of two uniforms is triangular, not uniform) is
deliberately **not** tracked in this form — that's the explicit worst-case/MC
tiering. If you need the real PDF, you go to the MC tier; otherwise you keep
exact bounds plus a propagated nominal, cheaply.

### 3.1 Missing nominal — explicit opt-in, never a silent fallback

`nom` is genuinely optional: some inputs have worst-case bounds but no declared
typical (a comparator offset spec'd `±5 mV max` with no `typ`; any min/max-only
datasheet limit). The three tiers are **independent reads** of one object, so a
missing `nom` only affects the tier that reads it:

- **Worst-case** and **Monte-Carlo** never touch `nom` → unaffected.
- **Nominal** arithmetic is **partial**: the result carries a `nom` *only if both
  operands declare one*. Otherwise `nom` is **contagiously absent** (`None`):

  ```
  result.nom = a.nom ∘ b.nom    if both a.nom and b.nom are present
             = None             otherwise
  ```

**No automatic midpoint fallback.** Synthesizing `(min+max)/2` would defeat the
entire reason `nom` is a separate field from the interval centre — `typ` ≠
midpoint for any asymmetric tolerance (cap −20%/+80%, LDO with skewed typ), and
fabricating one would invent data the datasheet never gave. A consumer that needs
the nominal of a `nom=None` Quantity **raises** ("no nominal declared for X")
rather than guessing.

If a downstream nominal-tier analysis genuinely needs a number, the engineer
**opts in explicitly** with `q.with_nominal(x)` — a new Quantity with `nom`
filled in, validated against `min ≤ x ≤ max`, and attributable in provenance as a
human-asserted nominal (distinct from a measured or datasheet one). Explicit,
once, where it's needed — not an invisible default everywhere.

### 3.2 Distribution sources — parametric and empirical

The same `(distribution, nom?)` shape is populated from two kinds of source:

- **Parametric** — `constant` (point mass: `min=max=nom`), `interval`
  (`min/max`, no `nom`), `uniform`, `normal`, `bimodal`, … built from spec
  numbers. This is the **contract / datasheet** side.
- **Empirical** — `from_samples(raw, …)`: an explicit set of measured values
  becomes a distribution via a **Gaussian Parzen-window (KDE)**. The KDE
  bandwidth (Silverman by default) both estimates the density *and* drives a
  **smoothed bootstrap** that lifts a handful of measurements up to the MC sample
  count; worst-case bounds default to the measured extremes; `nom` stays `None`
  unless declared (§3.1). This is the **characterization** side — and because it
  yields the *same type*, a measured part flows through arithmetic identically to
  a datasheet one. This is the concrete mechanism behind the
  characterization-vs-contract duality (§8, `PLATFORM_VISION.md`).

## 4. The correctness insight: two kinds of variation

The reason today's shape feels off is that **two physically different kinds of
variation behave differently under arithmetic**, and the current type uses one
`by_scenario` dict for the first while having no real home for the second:

| Kind | Example | Under `X + Y` |
|---|---|---|
| **Dimensional / correlated** | both scale with `temperature` | evaluate **both at the same condition-point** — perfectly correlated through the shared dimension |
| **Intrinsic / independent** | each resistor's ±1% tolerance | **convolve** — independent spreads combine statistically, not worst-case-stacked |

v2 makes both first-class. A Quantity is, in effect:

```
intrinsic_distribution  +  { dimension: sensitivity }
```

- The **intrinsic distribution** is the part that varies independently of the
  shared dimensions (manufacturing tolerance, characterization spread).
- The **sensitivities** are the correlated part — shared dimensions are
  evaluated at a common point across *all* Quantities in an expression, which is
  exactly the correlation guarantee today's `_combine_scenarios` provides by
  joining on the scenario name.

> **Open sub-question:** are two instances of the same part's intrinsic spreads
> independent (two ERJ3s on the board) or correlated (same reel/lot)? Worst-case
> stacking is always safe; statistically-correct combination needs a correlation
> declaration. Defer until MC matters.

## 5. Evaluation strategy (keeping worst-case tractable)

The hard problem with any "function over a continuous space" model is finding
the true worst case of a composed expression without falling into the
combinatorial enumeration the design explicitly rejects (§3 non-goals). The
tractable path that preserves rigor:

1. Evaluate each dimension at **declared discrete corners** (the same spirit as
   `min/nom/max`, applied to the dimensions themselves).
2. Compose only over the **dependency footprint** of an expression — the
   dimensions that actually appear in it — not the global product. A Quantity
   sensitive to one dimension is only ever evaluated along that one; the cost is
   bounded by what an expression truly depends on, and `hot ⊗ reverse_battery`
   only materializes when an expression genuinely depends on both.

**Residual risk to name out loud:** a **non-monotonic** sensitivity can hide an
interior worst case *between* declared corners. This is the one place today's
hand-curated named scenarios still earn their keep (engineering judgment about
*which* points bound the problem). Mitigations: restrict sensitivities to
monotonic forms where possible; allow extra interior corners; flag
non-monotonic compositions for MC.

## 6. This is a generalization, not a teardown

Most of the current engine maps forward — what changes is the *leaf
representation* and the *evaluation strategy*, not the arithmetic core:

| Today | v2 |
|---|---|
| `_combine_scenarios` joins on scenario **name** | joins on **condition-point** — same mechanism, generalized |
| missing scenario key → `KeyError` | insensitive dimension → **constant → automatic broadcast** (the bug is gone by construction) |
| `(min, max)` range | a degenerate distribution |
| `by_mode` (named-state dict) | just a **discrete dimension** |
| `by_scenario` (named-corner dict) | a **sampled sensitivity** to one-or-more dimensions |
| reserved `distribution` field | the **intrinsic distribution** — now central, not optional |

## 7. Illustrative type sketch (not implementation)

```python
@dataclass(frozen=True)
class Quantity:
    unit: pint.Unit
    base: Distribution                     # always present
    sensitivities: dict[str, Sensitivity]  # dimension -> response; {} == constant everywhere
    provenance: ProvenanceRef

@dataclass(frozen=True)
class Uniform(Distribution):
    min: float
    max: float
    nom: float | None = None               # OPTIONAL labeled sample; invariant: min <= nom <= max

@dataclass(frozen=True)
class Empirical(Distribution):             # the characterization source (§3.2)
    samples: np.ndarray                    # measured values
    bandwidth: float                       # Gaussian Parzen-window / KDE bandwidth
    nom: float | None = None               # stays None unless explicitly declared
    # min/max default to measured extremes; MC draws a smoothed bootstrap.

# nominal arithmetic is PARTIAL (§3.1): result.nom is present only if BOTH
# operands declare one; otherwise None. No (min+max)/2 fallback.
#   q.with_nominal(x) -> Quantity          # explicit, auditable opt-in; validates min<=x<=max

# sensitivities (vocabulary TBD):
#   Linear(per_unit, ref)           e.g. resistor tempco: +100 ppm/°C about 25 °C
#   GateToZero(dimension, value)    e.g. drops to 0 when mode == "sleep"
#   Piecewise(breakpoints)          for monotonic segmented response

# evaluation:
#   q.at(condition: dict[str, float | str]) -> Distribution
#     applies each sensitivity for dimensions present in `condition`;
#     dimensions absent from `sensitivities` leave `base` unchanged (broadcast).
```

> Prototyped (not in the framework package) in `quantity_v2_proto.py`, demonstrated
> by the slide deck (`quantity_animation.py`) and matrix demo
> (`quantity_distributions_demo.py`).

## 8. Why this is the right north star

This is the natural data model for the **characterization vision** (PLATFORM_VISION):
a *characterized* part **is** a distribution plus measured sensitivities (across
lots, across temperature). The *synthetic/datasheet* version is the **same
shape** with spec-derived `(min, nom, max)` and a datasheet tempco. So one
reconception **unifies the "characterization = distribution / synthetic spec =
contract" duality** — they stop being two systems and become one type populated
from two data sources.

## 9. Open questions before any implementation

1. **Dimension registry**: where dimensions are declared, their corner sets, and
   their types (continuous vs discrete/enumerated). Likely the successor to
   `scenarios.toml` + `modes.toml`.
2. **Sensitivity vocabulary**: the closed set of sensitivity kinds, and whether
   they must be monotonic.
3. **Non-monotonic interior worst-case** (§5) — corner policy + MC fallback.
4. **Intrinsic-spread correlation** (§4) — same-part instances independent vs
   lot-correlated.
5. **Migration**: contracts, verification, provenance, reports, and the worked
   example all consume today's `Quantity`. Sequencing a v2 without a flag-day.
6. **Distribution arithmetic at the MC tier**: convolution / sampling semantics,
   correlation preservation within a trial (§7.5 already sketches this).
