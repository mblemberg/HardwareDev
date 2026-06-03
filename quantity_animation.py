"""Slide deck for the Quantity *v2* model — distribution over a condition-space.

Renders `quantity_demo.pdf`, one slide per page. Replaces the old v1 deck
(by_scenario / by_mode / _ALL_ lookup-table model); teaches the direction in
`quantity_v2_design.md` / `PLATFORM_VISION.md`.

  NORTH-STAR: the framework code today still implements v1 (design doc §6.1).
  Nothing here is shipped. The distribution toolkit lives in `quantity_v2_proto.py`
  (a prototype sandbox, not the framework package) to respect Phase-1 gating.

Conceptual slides are matplotlib diagrams; the arithmetic / temperature /
tolerance-stack / characterization / sample-KDE slides are real ~200k-sample
Monte-Carlo plots. Pure numpy + matplotlib. Run from the framework dir:

    poetry run python ../quantity_animation.py
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec

import quantity_v2_proto as q
from quantity_v2_proto import (
    GateToZero, Linear, Quadratic, bimodal, constant, from_samples, hist_fill,
    interval, kde_curve, normal, plot_dist, scaled, uniform,
)

SLIDE = (13.33, 7.5)        # 16:9
C_A, C_B, C_R = "#3b6fb0", "#c2702f", "#2e8b57"   # operand A / operand B / result
C_ACC = "#7a3b9c"
INK = "#1a1a1a"


# ============================================================ diagram helpers
def diagram_axes(fig):
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")
    return ax


def box(ax, x, y, w, h, text, fc="#eef3f9", ec="0.4", fs=11, weight="normal"):
    ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.08", fc=fc, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, weight=weight, color=INK)


def slide_title_text(ax, title, sub=None):
    ax.text(8, 8.3, title, ha="center", va="top", fontsize=20, weight="bold", color=INK)
    if sub:
        ax.text(8, 7.45, sub, ha="center", va="top", fontsize=12.5,
                style="italic", color="0.30")


# ============================================================ slides
def s_title(fig):
    ax = diagram_axes(fig)
    ax.text(8, 6.6, "Quantity  v2", ha="center", fontsize=40, weight="bold", color=INK)
    ax.text(8, 5.5, "a distribution over a condition-space", ha="center",
            fontsize=18, style="italic", color="0.30")
    box(ax, 2.2, 3.0, 11.6, 1.7,
        "A Quantity is a function from a shared condition-space to a distribution,\n"
        "non-trivial only along the dimensions it is programmed to be sensitive to.",
        fc="#f4eefa", ec=C_ACC, fs=13)
    ax.text(8, 1.4,
            "NORTH-STAR direction — the framework code today still implements v1 "
            "(the lookup-table model).",
            ha="center", fontsize=10.5, color="#a23")
    ax.text(8, 0.8, "quantity_v2_design.md  ·  PLATFORM_VISION.md",
            ha="center", fontsize=9, family="monospace", color="0.5")


def s_v1_to_v2(fig):
    ax = diagram_axes(fig)
    slide_title_text(ax, "From v1 to v2",
                     "v1 worked, but didn't fit how I actually reason about a circuit")
    box(ax, 0.7, 4.3, 6.9, 2.3,
        "v1 felt unintuitive\n\n"
        "values stored as look-up tables of named\n"
        "corners (by_scenario / by_mode), with\n"
        "spread bolted on as an optional field.\n"
        "I kept translating physics into dict keys.",
        fc="#f3f3f3", ec="0.55", fs=12)
    ax.annotate("", (8.6, 5.45), (7.75, 5.45),
                arrowprops=dict(arrowstyle="->", color=C_ACC, lw=2.4))
    box(ax, 8.7, 4.3, 6.6, 2.3,
        "v2 aims to be intuitive & useful\n\n"
        "a value is just its distribution over the\n"
        "conditions it actually responds to.\n"
        "the model matches the physics — so worst-\n"
        "case, nominal and Monte-Carlo all fall out.",
        fc="#f4eefa", ec=C_ACC, fs=12)
    ax.text(8, 3.2, "designed around worst-case circuit analysis as I do it — "
            "not a generic units library",
            ha="center", fontsize=11.5, style="italic", color="0.3")
    ax.text(8, 2.2, "the rest of this deck shows what 'intuitive' buys: honest "
            "distribution arithmetic, correlated-vs-independent variation,\n"
            "condition-space sensitivities, and one type that holds both the "
            "datasheet contract and bench characterization.",
            ha="center", fontsize=10, color="0.4")


def s_three_tiers(fig):
    d = normal(10.0, 1.2, "mA")
    gs = GridSpec(1, 5, figure=fig, wspace=0.35)
    ax = fig.add_subplot(gs[0, :3])
    hist_fill(ax, d.samples, C_A)
    ax.axvspan(d.lo, d.hi, color="0.5", alpha=0.12, lw=0)
    for b in (d.lo, d.hi):
        ax.axvline(b, color="0.30", ls="--", lw=1.3)
    ax.plot([d.nom], [0], marker="v", ms=15, color=INK, clip_on=False, zorder=5)
    ax.annotate("MC shape", (d.nom + 1.4, 0.22), fontsize=11, color=C_A, weight="bold")
    ax.annotate("worst-case  [min, max]", (d.hi, ax.get_ylim()[1] * 0.92),
                fontsize=10.5, color="0.3", ha="right")
    ax.annotate("nominal", (d.nom, 0.0), (d.nom, ax.get_ylim()[1] * 0.34),
                fontsize=10.5, ha="center", color=INK,
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.2))
    ax.set_yticks([])
    ax.tick_params(labelsize=9)
    ax.set_title("One distribution, read three ways", fontsize=13, weight="bold")

    axr = fig.add_subplot(gs[0, 3:])
    axr.axis("off")
    axr.set_title("one type, three read-tiers", fontsize=12, weight="bold", loc="left")
    tiers = [
        ("Worst-case", "the [min, max] interval — exact bounds", "min, max", C_R),
        ("Nominal", "the labelled nom sample — OPTIONAL", "nom (or None)", C_B),
        ("Monte-Carlo", "the distribution shape (opt-in)", "full shape", C_A),
    ]
    y = 0.78
    for name, use, reads, c in tiers:
        axr.add_patch(plt.matplotlib.patches.Rectangle((0.02, y - 0.02), 0.05, 0.16,
                      transform=axr.transAxes, color=c, clip_on=False))
        axr.text(0.12, y + 0.13, name, fontsize=12, weight="bold", color=INK)
        axr.text(0.12, y + 0.05, use, fontsize=9.3, color="0.3")
        axr.text(0.12, y - 0.02, f"reads:  {reads}", fontsize=9, family="monospace",
                 color=c)
        y -= 0.26
    fig.suptitle("(min, max) = uniform · nom = optional labelled sample · "
                 "invariant min ≤ nom ≤ max", fontsize=10.5, style="italic",
                 color="0.4", y=0.06)


def s_forms(fig):
    gs = GridSpec(1, 3, figure=fig, wspace=0.2)
    forms = [
        (uniform(95, 105, "Ω"), C_B, "Uniform  =  the (min, max) interval",
         "the honest default: 'we know the band, not the shape'"),
        (normal(100, 2.0, "Ω"), C_A, "Normal",
         "refine to this when characterization justifies it"),
        (bimodal(96, 0.8, 0.5, 103, 0.9, "Ω"), C_R, "Bimodal",
         "two-lot / two-population reality — structure no interval can see"),
    ]
    for i, (d, c, title, cap) in enumerate(forms):
        ax = fig.add_subplot(gs[0, i])
        hist_fill(ax, d.samples, c, rng_=(90, 110))
        ax.set_xlim(90, 110)
        ax.set_yticks([])
        ax.set_title(title, fontsize=12, weight="bold")
        ax.text(0.5, -0.13, cap, transform=ax.transAxes, ha="center", fontsize=9,
                style="italic", color="0.35")
    fig.suptitle("Distribution forms — shape only matters at the Monte-Carlo tier",
                 fontsize=14, weight="bold", y=0.97)


def s_matrix(fig):
    gs = GridSpec(3, 3, figure=fig, hspace=0.6, wspace=0.18)
    V = normal(5.00, 0.05, "V"); R = uniform(95.0, 105.0, "Ω")
    plot_dist(fig.add_subplot(gs[0, 0]), V, C_A, "Normal — supply voltage")
    plot_dist(fig.add_subplot(gs[0, 1]), R, C_B, "Uniform — resistor tol. band")
    plot_dist(fig.add_subplot(gs[0, 2]), V / R, C_R, "= V / R  →  current (A)")

    Vu = uniform(4.9, 5.1, "V"); In = normal(0.100, 0.008, "A")
    plot_dist(fig.add_subplot(gs[1, 0]), Vu, C_A, "Uniform — rail within spec")
    plot_dist(fig.add_subplot(gs[1, 1]), In, C_B, "Normal — load current")
    plot_dist(fig.add_subplot(gs[1, 2]), Vu * In, C_R, "= V × I  →  power (W)")

    Vr = bimodal(3.20, 0.025, 0.5, 3.42, 0.022, "V"); off = normal(0.020, 0.035, "V")
    plot_dist(fig.add_subplot(gs[2, 0]), Vr, C_A, "Bimodal — Vref across two lots")
    plot_dist(fig.add_subplot(gs[2, 1]), off, C_B, "Normal — aging / trim offset")
    plot_dist(fig.add_subplot(gs[2, 2]), Vr + off, C_R, "= Vref + offset  →  (V)")

    fig.suptitle("Distribution arithmetic — mixing forms under +  ×  ÷",
                 fontsize=15, weight="bold", y=0.965)
    fig.text(0.5, 0.925, "filled = MC shape   ·   dashed band = worst-case "
             "interval (interval arithmetic)   ·   ▼ = propagated nominal",
             ha="center", fontsize=9.5, style="italic", color="0.3")


def s_closure(fig):
    Vr = bimodal(3.20, 0.025, 0.5, 3.42, 0.022, "V"); off = normal(0.020, 0.035, "V")
    res = Vr + off
    ax = fig.add_subplot(111)
    hist_fill(ax, res.samples, C_R)
    ax.axvspan(res.lo, res.hi, color="0.5", alpha=0.12, lw=0)
    for b in (res.lo, res.hi):
        ax.axvline(b, color="0.30", ls="--", lw=1.4)
    ax.plot([res.nom], [0], marker="v", ms=15, color=INK, clip_on=False, zorder=5)
    ax.set_yticks([])
    ax.tick_params(labelsize=9)
    ax.set_title("Closed under worst-case arithmetic", fontsize=15, weight="bold")
    ax.text(0.02, 0.95,
            "bounds   →  interval arithmetic on the operands\n"
            "nominal  →  ordinary scalar arithmetic (if both declare one)\n"
            "shape    →  Monte-Carlo (sampled)",
            transform=ax.transAxes, fontsize=11, family="monospace", va="top",
            bbox=dict(boxstyle="round", fc="white", ec="0.6"))
    ax.text(0.5, -0.1, "the dashed worst-case band always contains the MC shape — "
            "(min, max, nom) propagates cheaply without tracking the true convolved PDF",
            transform=ax.transAxes, ha="center", fontsize=10.5, style="italic",
            color="0.3")


def s_nom_optional(fig):
    gs = GridSpec(2, 3, figure=fig, hspace=0.62, wspace=0.18)
    I = normal(0.040, 0.002, "A")
    R = interval(95.0, 105.0, "Ω")            # min/max only — NO declared nominal
    V = I * R                                  # nominal is contagiously absent

    plot_dist(fig.add_subplot(gs[0, 0]), R, C_B,
              "Resistor — interval only (min/max, no typ)")
    plot_dist(fig.add_subplot(gs[0, 1]), I, C_A, "Current — Normal (nom declared)")
    plot_dist(fig.add_subplot(gs[0, 2]), V, C_R,
              "= I × R  →  nominal tier UNDEFINED")

    R2 = R.with_nominal(100.0)                 # explicit, auditable opt-in
    V2 = I * R2
    plot_dist(fig.add_subplot(gs[1, 0]), R2, C_B,
              "R.with_nominal(100 Ω) — explicit opt-in")
    axm = fig.add_subplot(gs[1, 1]); axm.axis("off")
    axm.text(0.5, 0.5,
             "nominal propagates ONLY if\nboth operands declare one.\n\n"
             "no automatic midpoint fallback —\n"
             "(min+max)/2 ≠ typ in general.\n\n"
             "opt in explicitly, once, where a\n"
             "nominal-tier number is needed.",
             ha="center", va="center", fontsize=10.5, color=INK,
             bbox=dict(boxstyle="round", fc="#f4eefa", ec=C_ACC, lw=1.6))
    plot_dist(fig.add_subplot(gs[1, 2]), V2, C_R, "= I × R  →  nom 4.0 V")

    fig.suptitle("Optional nominal — explicit opt-in, never a silent fallback",
                 fontsize=15, weight="bold", y=0.965)


def s_two_variations(fig):
    gs = GridSpec(1, 2, figure=fig, wspace=0.25, width_ratios=[1.05, 1])
    axl = fig.add_subplot(gs[0, 0]); axl.axis("off")
    axl.set_title("Two kinds of variation", fontsize=15, weight="bold", loc="left")
    box(axl, 0.0, 0.62, 1.0, 0.28,
        "DIMENSIONAL / CORRELATED\n"
        "e.g. both scale with temperature\n"
        "→ evaluate BOTH at the same condition-point",
        fc="#eaf1f8", ec=C_A, fs=11)
    box(axl, 0.0, 0.24, 1.0, 0.28,
        "INTRINSIC / INDEPENDENT\n"
        "e.g. each resistor's ±1% tolerance\n"
        "→ CONVOLVE — independent spreads combine statistically",
        fc="#fdf0e6", ec=C_B, fs=11)
    axl.text(0.0, 0.08, "Quantity  ≈  intrinsic_distribution  +  { dimension: sensitivity }",
             fontsize=10.5, family="monospace", color=INK)

    axr = fig.add_subplot(gs[0, 1])
    indep = np.zeros(q.N)
    for _ in range(10):
        indep += q._rng.uniform(99.0, 101.0, q.N)
    hist_fill(axr, indep, C_B, rng_=(988, 1012))
    axr.axvspan(990, 1010, color="0.5", alpha=0.15, lw=0)
    for b in (990, 1010):
        axr.axvline(b, color="0.30", ls="--", lw=1.3)
    axr.set_xlim(988, 1012)
    axr.set_yticks([])
    axr.set_title("10 series resistors, each ±1%", fontsize=12.5, weight="bold")
    axr.text(0.5, 0.78, "worst-case stack:  ±1%  (dashed)", transform=axr.transAxes,
             ha="center", fontsize=10, color="0.3")
    axr.text(0.5, 0.70, "independent reality:  ≈ ±0.3%  (filled)",
             transform=axr.transAxes, ha="center", fontsize=10, color=C_B, weight="bold")
    axr.text(0.5, -0.12, "worst-case stacking independents is wildly pessimistic — "
             "v2 convolves them", transform=axr.transAxes, ha="center", fontsize=9.5,
             style="italic", color="0.35")


def s_divider(fig):
    gs = GridSpec(1, 2, figure=fig, wspace=0.24)
    Vin = 5.0   # 10k : 10k divider, Vout = Vin · R2/(R1+R2)

    # Panel A -- correlated: a shared tempco cancels in the ratio.
    axA = fig.add_subplot(gs[0, 0])
    T = np.linspace(-40, 125, 120)
    tc1, tc2 = Linear(200), Linear(50)        # +200 / +50 ppm/°C
    matched = Vin * (10e3 * tc1.at(T)) / (10e3 * tc1.at(T) + 10e3 * tc1.at(T))
    mismatch = Vin * (10e3 * tc2.at(T)) / (10e3 * tc1.at(T) + 10e3 * tc2.at(T))
    axA.plot(T, matched, color=C_R, lw=2.8, label="matched pair (correlated tempco)")
    axA.plot(T, mismatch, color=C_B, lw=2.0, ls="--",
             label="mismatched parts (independent tempco)")
    axA.set_title("Correlated — tempco cancels in a ratio", fontsize=12.5,
                  weight="bold")
    axA.set_xlabel("temperature (°C)", fontsize=9)
    axA.set_ylabel("Vout (V)", fontsize=9)
    axA.legend(fontsize=8.5, loc="center right")
    axA.text(0.5, -0.17, "matched pair drifts together → ratio invariant\n"
             "(evaluate both at one condition-point)", transform=axA.transAxes,
             ha="center", fontsize=9, style="italic", color="0.35")

    # Panel B -- independent: each ±1% tolerance convolves -> triangular shape.
    axB = fig.add_subplot(gs[0, 1])
    R1 = 10e3 * (1 + q._rng.uniform(-0.01, 0.01, q.N))
    R2 = 10e3 * (1 + q._rng.uniform(-0.01, 0.01, q.N))
    vout = Vin * R2 / (R1 + R2)
    hist_fill(axB, vout, C_B, rng_=(2.47, 2.53))
    lo, hi = Vin * 9900 / 20000, Vin * 10100 / 20000      # worst-case corners
    axB.axvspan(lo, hi, color="0.5", alpha=0.15, lw=0)
    for b in (lo, hi):
        axB.axvline(b, color="0.30", ls="--", lw=1.3)
    axB.set_xlim(2.47, 2.53)
    axB.set_yticks([])
    axB.set_title("Independent — tolerances convolve", fontsize=12.5, weight="bold")
    axB.set_xlabel("Vout (V)", fontsize=9)
    axB.text(0.5, -0.17, "independent ±1% → triangular, mass near 2.5 V\n"
             "worst-case (dashed) keeps only the corners", transform=axB.transAxes,
             ha="center", fontsize=9, style="italic", color="0.35")

    fig.suptitle("Worked example — a 10 kΩ : 10 kΩ resistor divider",
                 fontsize=15, weight="bold", y=0.99)


def s_condition_space(fig):
    gs = GridSpec(1, 2, figure=fig, wspace=0.2, width_ratios=[1, 1.05])
    axl = fig.add_subplot(gs[0, 0]); axl.set_xlim(0, 1); axl.set_ylim(0, 1)
    axl.axis("off")
    axl.set_title("Condition-space & sensitivities", fontsize=15, weight="bold",
                  loc="left")
    axl.text(0.0, 0.90, "condition-space = the named dimensions a project shares:\n"
             "{ temperature, vbat, mode, ... }, each with corner values.",
             fontsize=10.5, color=INK)
    lines = [
        ("by_mode", "→  just a discrete dimension"),
        ("by_scenario", "→  a sampled sensitivity"),
        ("insensitive dim.", "→  constant → automatic broadcast"),
        ("→ the KeyError", "is gone by construction"),
    ]
    y = 0.72
    for a, b in lines:
        axl.text(0.02, y, a, fontsize=11.5, family="monospace", weight="bold",
                 color=C_ACC)
        axl.text(0.42, y, b, fontsize=10.5, color=INK)
        y -= 0.105
    axl.text(0.0, 0.27,
             "Iload = Quantity(\n"
             "  base = normal(100, 8, 'mA'),\n"
             "  sensitivities = {\n"
             "    'mode': GateToZero(('active',)),\n"
             "    'temp': Linear(+0.5%/°C leakage),\n"
             "  })   # silent on vbat → constant there\n\n"
             "Iload.at(mode='sleep', temp=85)  →  ~0 mA",
             fontsize=9, family="monospace", va="top", color="0.15",
             bbox=dict(boxstyle="round", fc="#f4eefa", ec=C_ACC, lw=1.4))

    axr = fig.add_subplot(gs[0, 1])
    R0 = q._rng.uniform(99.0, 101.0, q.N)
    temps = [-40, 0, 25, 85, 125]
    cmap = plt.cm.coolwarm(np.linspace(0.05, 0.95, len(temps)))
    for k, T in enumerate(temps):
        drift = Linear(200).at(T)
        noise = q._rng.normal(0.0, 0.00018 * abs(T - 25), q.N)
        rT = R0 * drift * (1.0 + noise)
        hist_fill(axr, rT, cmap[k], rng_=(95.5, 105.5), bins=200, base=k * 1.0,
                  scale=0.92)
        axr.text(95.6, k * 1.0 + 0.1, f"{T:+d} °C", fontsize=9, ha="left",
                 family="monospace")
        axr.plot([100.0 * drift], [k * 1.0], marker="v", ms=8, color=INK,
                 clip_on=False, zorder=5)
    axr.set_xlim(95.5, 105.5)
    axr.set_ylim(-0.15, len(temps) * 1.0 + 0.2)
    axr.set_yticks([])
    axr.set_xlabel("resistance (Ω)", fontsize=9)
    axr.set_title("a Linear sensitivity applied to a base dist.\n"
                  "(R₀ = 100 Ω ±1%, +200 ppm/°C)", fontsize=11)


def s_sensitivities(fig):
    gs = GridSpec(1, 3, figure=fig, wspace=0.3)
    T = np.linspace(-40, 125, 200)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(T, Linear(200).at(T), color=C_A, lw=2.6)
    ax1.axhline(1.0, color="0.7", ls=":", lw=1)
    ax1.set_title("Linear", fontsize=13, weight="bold")
    ax1.set_xlabel("temperature (°C)", fontsize=9)
    ax1.set_ylabel("factor on base", fontsize=9)
    ax1.text(0.5, -0.2, "resistor tempco  +200 ppm/°C\nmonotonic — corners bound it",
             transform=ax1.transAxes, ha="center", fontsize=9, style="italic",
             color="0.35")

    ax2 = fig.add_subplot(gs[0, 1])
    modes = ["sleep", "idle", "active", "boost"]
    g = GateToZero(("active", "boost"))
    ax2.bar(modes, [g.at(m) for m in modes], color=C_B, alpha=0.8)
    ax2.set_ylim(0, 1.15)
    ax2.set_title("GateToZero", fontsize=13, weight="bold")
    ax2.set_ylabel("factor on base", fontsize=9)
    ax2.text(0.5, -0.2, "mode gating: 0 unless active\nby_mode as a discrete dimension",
             transform=ax2.transAxes, ha="center", fontsize=9, style="italic",
             color="0.35")

    ax3 = fig.add_subplot(gs[0, 2])
    f = Quadratic(-3e-6).at(T)
    ax3.plot(T, f, color=C_R, lw=2.6)
    for c in (-40, 125):
        ax3.plot([c], [Quadratic(-3e-6).at(c)], "o", color="0.3", ms=8,
                 fillstyle="none", mew=1.6)
    ax3.plot([25], [1.0], "*", color=C_ACC, ms=16)
    ax3.set_title("Quadratic  (non-monotonic)", fontsize=13, weight="bold")
    ax3.set_xlabel("temperature (°C)", fontsize=9)
    ax3.text(0.5, -0.2, "bandgap curvature: interior peak (★) hides\n"
             "between corners (○) → flag for MC (§5)", transform=ax3.transAxes,
             ha="center", fontsize=9, style="italic", color="0.35")

    fig.suptitle("A sensitivity is a function — from a condition to a factor on "
                 "the base distribution", fontsize=14.5, weight="bold", y=0.98)


def s_from_samples(fig):
    # 45 measured parts across two lots — the characterization data source.
    raw = np.concatenate([q._rng.normal(99.0, 0.45, 30),
                          q._rng.normal(101.3, 0.55, 15)])
    gs = GridSpec(1, 2, figure=fig, wspace=0.2)

    axl = fig.add_subplot(gs[0, 0])
    grid = np.linspace(97.0, 103.5, 400)
    axl.hist(raw, bins=18, range=(97, 103.5), density=True, color="0.7", alpha=0.5,
             label="measured samples")
    axl.plot(grid, kde_curve(raw, grid), color=C_ACC, lw=2.4,
             label="Parzen-window (KDE) density")
    axl.plot(raw, np.full(raw.size, -0.02), "|", color=INK, ms=12, mew=1.2,
             clip_on=False)   # rug
    axl.set_xlim(97, 103.5)
    axl.set_yticks([])
    axl.legend(fontsize=9, loc="upper right")
    axl.set_title(f"{raw.size} explicit samples → calculated density",
                  fontsize=12.5, weight="bold")
    axl.set_xlabel("resistance (Ω)", fontsize=9)

    # build a Quantity from the samples (smoothed bootstrap), then use it.
    R = from_samples(raw, "Ω")                 # nom stays None (none declared)
    I = constant(0.040, "A")
    V = I * R
    axr = fig.add_subplot(gs[0, 1])
    plot_dist(axr, V, C_R, "used in  V = I × R   (nominal undefined)")
    axr.set_xlabel("voltage (V)", fontsize=9)

    fig.suptitle("Empirical distributions — define a Quantity from measured samples",
                 fontsize=15, weight="bold", y=0.97)
    fig.text(0.5, 0.02, "a characterized part IS a distribution from data; "
             "the two-lot structure flows through arithmetic, and (no declared "
             "typ) → nominal stays undefined", ha="center", fontsize=9.5,
             style="italic", color="0.3")


def s_char_vs_contract(fig):
    ax = fig.add_subplot(111)
    contract = uniform(95, 105, "Ω")
    char = bimodal(98.5, 0.7, 0.5, 102.0, 0.8, "Ω")
    hist_fill(ax, contract.samples, "0.55", rng_=(93, 107))
    hist_fill(ax, char.samples, C_R, rng_=(93, 107))
    ax.set_xlim(93, 107)
    ax.set_yticks([])
    ax.tick_params(labelsize=9)
    ax.set_title("Characterization vs. contract — same type, two data sources",
                 fontsize=15, weight="bold")
    ax.text(0.02, 0.92, "the contract (synthetic / datasheet spec)\n"
            "uniform [95, 105] Ω — the promise", transform=ax.transAxes,
            fontsize=11, color="0.4", va="top")
    ax.text(0.98, 0.92, "characterization (measured, two lots)\n"
            "where reality actually lands", transform=ax.transAxes,
            fontsize=11, color=C_R, va="top", ha="right", weight="bold")
    ax.text(0.5, 0.55, "# same type, two constructors\n"
            "contract = uniform(95, 105, 'Ω')\n"
            "char     = from_samples(measured, 'Ω')",
            transform=ax.transAxes, ha="center", va="center", fontsize=9.5,
            family="monospace", color="0.15",
            bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.92))
    ax.text(0.5, -0.1, "a characterized part IS a distribution + measured "
            "sensitivities; the datasheet version is the same shape from a "
            "different source", transform=ax.transAxes, ha="center",
            fontsize=10.5, style="italic", color="0.3")


def s_mapping(fig):
    ax = diagram_axes(fig)
    slide_title_text(ax, "Generalization, not a teardown",
                     "the arithmetic core stays; the leaf representation generalizes")
    rows = [
        ("_combine_scenarios joins on scenario name", "joins on condition-point"),
        ("missing scenario key → KeyError", "insensitive dim → constant → broadcast"),
        ("(min, max) range", "a degenerate distribution"),
        ("by_mode (named-state dict)", "a discrete dimension"),
        ("by_scenario (named-corner dict)", "a sampled sensitivity"),
        ("reserved 'distribution' field", "the intrinsic distribution — now central"),
    ]
    ax.text(4.1, 6.55, "v1  (today)", ha="center", fontsize=12.5, weight="bold",
            color="0.4")
    ax.text(11.6, 6.55, "v2", ha="center", fontsize=12.5, weight="bold", color=C_ACC)
    y = 5.8
    for a, b in rows:
        box(ax, 0.5, y - 0.28, 7.2, 0.62, a, fc="#f2f2f2", ec="0.6", fs=10.3)
        ax.annotate("", (8.55, y + 0.03), (7.85, y + 0.03),
                    arrowprops=dict(arrowstyle="->", color=C_ACC, lw=2))
        box(ax, 8.7, y - 0.28, 6.8, 0.62, b, fc="#f4eefa", ec=C_ACC, fs=10.3)
        y -= 0.92
    ax.text(8, 0.35, "one reconception unifies the characterization = distribution / "
            "synthetic spec = contract duality", ha="center", fontsize=10.5,
            style="italic", color="0.3")


SLIDES = [s_title, s_v1_to_v2, s_three_tiers, s_forms, s_matrix, s_closure,
          s_nom_optional, s_two_variations, s_divider, s_condition_space,
          s_sensitivities, s_from_samples, s_char_vs_contract, s_mapping]


def main():
    out = "/Users/mike/code/HardwareDev/quantity_demo.pdf"
    print(f"Rendering {len(SLIDES)} slides...")
    with PdfPages(out) as pdf:
        for i, slide in enumerate(SLIDES, 1):
            fig = plt.figure(figsize=SLIDE)
            slide(fig)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            print(f"  {i:2d}/{len(SLIDES)}  {slide.__name__}")
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
