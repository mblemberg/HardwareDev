"""Distribution-arithmetic matrix for the Quantity *v2* model.

Companion to `quantity_v2_design.md`. Renders one figure
(`quantity_distributions_demo.png`): a matrix of Monte-Carlo plots showing
normal / uniform / bimodal mixing under arithmetic, plus a temperature-driven
transform. Every result panel overlays the v2 three read-tiers:

    filled histogram = full MC shape
    dashed band      = worst-case [min, max] (interval arithmetic on operands)
    ▼                = propagated nominal

The distribution model lives in `quantity_v2_proto.py` (the shared prototype
sandbox — NOT the framework package; Phase-1 gating keeps the framework on v1).

    poetry run python ../quantity_distributions_demo.py     # from framework dir
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

import quantity_v2_proto as q
from quantity_v2_proto import bimodal, hist_fill, normal, plot_dist, uniform

C_A, C_B, C_R = "#3b6fb0", "#c2702f", "#2e8b57"   # operand A / operand B / result

fig = plt.figure(figsize=(15, 14))
gs = GridSpec(4, 3, figure=fig, hspace=0.55, wspace=0.18,
              height_ratios=[1, 1, 1, 1.25])

# Row 1 -- Ohm's law: Normal voltage ÷ Uniform resistance -> current
V = normal(5.00, 0.05, "V"); R = uniform(95.0, 105.0, "Ω")
plot_dist(fig.add_subplot(gs[0, 0]), V, C_A, "Normal — supply voltage")
plot_dist(fig.add_subplot(gs[0, 1]), R, C_B, "Uniform — resistor tolerance band")
plot_dist(fig.add_subplot(gs[0, 2]), V / R, C_R, "= V / R   →   current (A)")

# Row 2 -- Power: Uniform voltage × Normal current -> power
Vu = uniform(4.9, 5.1, "V"); In = normal(0.100, 0.008, "A")
plot_dist(fig.add_subplot(gs[1, 0]), Vu, C_A, "Uniform — rail within spec")
plot_dist(fig.add_subplot(gs[1, 1]), In, C_B, "Normal — load current")
plot_dist(fig.add_subplot(gs[1, 2]), Vu * In, C_R, "= V × I   →   power (W)")

# Row 3 -- Bimodal (two-lot Vref) + Normal aging/trim offset
Vref = bimodal(3.20, 0.025, 0.5, 3.42, 0.022, "V")
off = normal(0.020, 0.035, "V")
plot_dist(fig.add_subplot(gs[2, 0]), Vref, C_A, "Bimodal — Vref across two lots")
plot_dist(fig.add_subplot(gs[2, 1]), off, C_B, "Normal — aging / trim offset")
plot_dist(fig.add_subplot(gs[2, 2]), Vref + off, C_R, "= Vref + offset   →   (V)")

# Row 4 -- temperature transform (ridgeline): a sensitivity along `temperature`.
axT = fig.add_subplot(gs[3, :])
R0_tol = q._rng.uniform(99.0, 101.0, q.N)
alpha = 200e-6
temps = [-40, 0, 25, 85, 125]
cmap = plt.cm.coolwarm(np.linspace(0.05, 0.95, len(temps)))
for k, T in enumerate(temps):
    drift = 1.0 + alpha * (T - 25)
    char_noise = q._rng.normal(0.0, 0.00018 * abs(T - 25), q.N)
    rT = R0_tol * drift * (1.0 + char_noise)
    hist_fill(axT, rT, cmap[k], rng_=(95.5, 105.5), bins=200, base=k * 1.0, scale=0.92)
    axT.text(95.6, k * 1.0 + 0.1, f"{T:+d} °C", fontsize=9, ha="left",
             family="monospace")
    axT.plot([100.0 * drift], [k * 1.0], marker="v", ms=8, color="black",
             clip_on=False, zorder=5)
axT.set_title("Temperature transform — a sensitivity applied to one base "
              "distribution (R₀ = 100 Ω ±1%, +200 ppm/°C)\n"
              "the band drifts with ambient temperature and widens off the "
              "25 °C reference; ▼ marks the propagated nominal",
              fontsize=10.5, pad=8)
axT.set_xlabel("resistance (Ω)", fontsize=9)
axT.set_yticks([])
axT.set_xlim(95.5, 105.5)
axT.set_ylim(-0.15, len(temps) * 1.0 + 0.2)
axT.tick_params(labelsize=8)

fig.suptitle("Quantity v2 — distribution arithmetic  ·  one type, three read-tiers",
             fontsize=16, weight="bold", y=0.975)
fig.text(0.5, 0.945,
         "filled = full Monte-Carlo shape   ·   dashed band = worst-case "
         "[min, max] (interval arithmetic)   ·   ▼ = nominal sample   "
         "—   note the interval always contains the MC shape, and the gap "
         "between the bimodal humps is invisible to the interval/nominal tiers",
         fontsize=9.5, ha="center", style="italic", color="0.25")

out = "/Users/mike/code/HardwareDev/quantity_distributions_demo.png"
fig.savefig(out, dpi=130, bbox_inches="tight")
print(f"saved {out}")
plt.close(fig)
