"""Prototype toolkit for the Quantity *v2* model — distribution-over-condition-space.

NOT framework code. The framework package still implements v1 (design doc §6.1),
and Phase-1 gating keeps it that way. This module is the shared sandbox where the
v2 distribution tier is prototyped — imported by the slide deck
(`quantity_animation.py`) and the matrix demo (`quantity_distributions_demo.py`),
and tracking the design in `quantity_v2_design.md`.

A Quantity here is a sampled distribution carrying three independent read-tiers:

    worst-case   ->  [min, max] interval bounds        (always present)
    Monte-Carlo  ->  the full sample shape             (always present)
    nominal      ->  an OPTIONAL labelled `nom` sample (may be None)

Nominal is *optional and contagiously absent*: arithmetic only yields a nominal
when BOTH operands declare one — there is no automatic midpoint fallback. If a
downstream nominal-tier analysis needs a number, the engineer opts in explicitly
with `.with_nominal(x)` (auditable, validated against min <= x <= max), rather
than the framework fabricating one. The worst-case and MC tiers never read `nom`,
so they keep working regardless.

Distribution sources:

    constant / interval / uniform / normal / bimodal    parametric
    from_samples(...)                                    empirical — smoothed
        bootstrap via a Gaussian Parzen-window (KDE). This is the
        characterization path: measured samples become a Quantity of the same
        type as a datasheet-derived one (PLATFORM_VISION.md, design doc §8 of
        quantity_v2_design.md).

Pure numpy (no scipy).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

N = 200_000
SIGMA_LIMIT = 3.0           # declared worst-case limit for unbounded (normal) forms
_rng = np.random.default_rng(20260602)


# ============================================================ distribution model
@dataclass
class Dist:
    """A sampled Quantity: MC shape + worst-case interval + optional nominal."""

    samples: np.ndarray
    lo: float
    hi: float
    nom: float | None       # None => no labelled nominal declared
    unit: str

    # nominal propagation: defined only when BOTH operands carry one. No fallback.
    def _combine(self, o, op, ivl, unit):
        nom = None if (self.nom is None or o.nom is None) else op(self.nom, o.nom)
        return Dist(op(self.samples, o.samples), ivl[0], ivl[1], nom, unit)

    def __add__(self, o):
        return self._combine(o, np.add, (self.lo + o.lo, self.hi + o.hi), self.unit)

    def __mul__(self, o):
        c = [self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi]
        return self._combine(o, np.multiply, (min(c), max(c)), f"{self.unit}·{o.unit}")

    def __truediv__(self, o):
        c = [self.lo / o.lo, self.lo / o.hi, self.hi / o.lo, self.hi / o.hi]
        return self._combine(o, np.divide, (min(c), max(c)), f"{self.unit}/{o.unit}")

    def with_nominal(self, value):
        """Explicit, auditable opt-in for a nominal. Validates min <= value <= max."""
        if not (self.lo <= value <= self.hi):
            raise ValueError(
                f"nominal {value} outside worst-case bounds [{self.lo}, {self.hi}]")
        return Dist(self.samples, self.lo, self.hi, float(value), self.unit)


# ------------------------------------------------------------ parametric sources
def constant(value, unit):
    """Degenerate distribution / point mass: min == max == nom == value."""
    return Dist(np.full(N, float(value)), value, value, value, unit)


def interval(lo, hi, unit):
    """Worst-case bounds only — uniform shape, NO declared nominal (nom is None)."""
    return Dist(_rng.uniform(lo, hi, N), lo, hi, None, unit)


def uniform(lo, hi, unit, nom="mid"):
    """Uniform over [lo, hi]; nom defaults to the midpoint (override or None)."""
    if nom == "mid":
        nom = 0.5 * (lo + hi)
    return Dist(_rng.uniform(lo, hi, N), lo, hi, nom, unit)


def normal(mean, sd, unit, nom="mean"):
    nom = mean if nom == "mean" else nom
    return Dist(_rng.normal(mean, sd, N), mean - SIGMA_LIMIT * sd,
                mean + SIGMA_LIMIT * sd, nom, unit)


def bimodal(m1, s1, w1, m2, s2, unit, nom="dominant"):
    pick = _rng.random(N) < w1
    s = np.where(pick, _rng.normal(m1, s1, N), _rng.normal(m2, s2, N))
    if nom == "dominant":
        nom = m1 if w1 >= 0.5 else m2
    return Dist(s, min(m1 - SIGMA_LIMIT * s1, m2 - SIGMA_LIMIT * s2),
                max(m1 + SIGMA_LIMIT * s1, m2 + SIGMA_LIMIT * s2), nom, unit)


# ------------------------------------------------------------ empirical source (Parzen/KDE)
def silverman_bw(raw):
    """Silverman's rule-of-thumb Gaussian KDE bandwidth (robust variant)."""
    raw = np.asarray(raw, float)
    n = raw.size
    sd = raw.std(ddof=1)
    iqr = np.subtract(*np.percentile(raw, [75, 25]))
    spread = min(sd, iqr / 1.349) if iqr > 0 else sd
    spread = spread or sd or 1.0
    return 0.9 * spread * n ** (-0.2)


def kde_curve(raw, grid, bw=None):
    """Parzen-window (Gaussian-kernel) density estimate of `raw` on `grid`."""
    raw = np.asarray(raw, float)
    h = bw or silverman_bw(raw)
    u = (grid[:, None] - raw[None, :]) / h
    return (np.exp(-0.5 * u * u) / np.sqrt(2 * np.pi)).mean(axis=1) / h


def from_samples(raw, unit, nom=None, bounds=None, bw=None):
    """Empirical Quantity from explicit samples via a smoothed bootstrap.

    The Parzen/KDE bandwidth `bw` (Silverman by default) both smooths the
    density and drives the smoothed bootstrap that lifts a handful of measured
    points up to N MC samples. `nom` stays None unless the caller declares one
    (the explicit-opt-in rule); `bounds` defaults to the measured extremes.
    """
    raw = np.asarray(raw, float)
    h = bw or silverman_bw(raw)
    idx = _rng.integers(0, raw.size, N)
    samples = raw[idx] + _rng.normal(0.0, h, N)
    lo, hi = bounds if bounds is not None else (float(raw.min()), float(raw.max()))
    return Dist(samples, lo, hi, nom, unit)


# ============================================================ sensitivities (minimal)
# A sensitivity is a FUNCTION from a condition value to a dimensionless factor
# applied to the base distribution. Vocabulary mirrors quantity_v2_design.md §7
# ("TBD" there); these minimal forms back the deck's worked examples.
@dataclass(frozen=True)
class Linear:
    """Constant slope, e.g. a resistor tempco: +200 ppm/°C about 25 °C."""

    ppm_per_unit: float
    ref: float = 25.0

    def at(self, x):
        return 1.0 + self.ppm_per_unit * 1e-6 * (x - self.ref)


@dataclass(frozen=True)
class GateToZero:
    """1.0 in the listed (active) states, 0.0 everywhere else — e.g. mode gating."""

    active: tuple

    def at(self, state):
        return 1.0 if state in self.active else 0.0


@dataclass(frozen=True)
class Quadratic:
    """Curvature, e.g. a bandgap's parabolic tempco — NON-monotonic (see §5)."""

    per_unit2: float
    ref: float = 25.0

    def at(self, x):
        return 1.0 + self.per_unit2 * (x - self.ref) ** 2


def scaled(d, factor, unit=None):
    """Apply a dimensionless sensitivity factor to a base distribution."""
    nom = None if d.nom is None else d.nom * factor
    return Dist(d.samples * factor, d.lo * factor, d.hi * factor, nom, unit or d.unit)


# ============================================================ plot primitives
def hist_fill(ax, samples, color, rng_=None, bins=140, base=0.0, scale=None):
    counts, edges = np.histogram(samples, bins=bins, range=rng_, density=True)
    centres = 0.5 * (edges[:-1] + edges[1:])
    h = counts if scale is None else counts / counts.max() * scale
    ax.fill_between(centres, base, base + h, step="mid", color=color, alpha=0.45, lw=0)
    ax.plot(centres, base + h, color=color, lw=1.2, drawstyle="steps-mid")
    return centres, h


def plot_dist(ax, d, color, title, tiers=True, ink="#1a1a1a"):
    hist_fill(ax, d.samples, color)
    if tiers:
        ax.axvspan(d.lo, d.hi, color="0.5", alpha=0.10, lw=0)
        for b in (d.lo, d.hi):
            ax.axvline(b, color="0.30", ls="--", lw=1.1)
        if d.nom is not None:
            ax.plot([d.nom], [0], marker="v", ms=11, color=ink, clip_on=False, zorder=5)
    ax.set_title(title, fontsize=11, pad=5)
    ax.set_yticks([])
    ax.tick_params(labelsize=8)
    nom_txt = "—  (no nominal)" if d.nom is None else f"{d.nom:.3g}"
    ax.text(0.97, 0.93, f"[{d.lo:.3g}, {d.hi:.3g}] {d.unit}\nnom {nom_txt}",
            transform=ax.transAxes, fontsize=8, ha="right", va="top",
            family="monospace",
            bbox=dict(boxstyle="round", fc="white", ec="0.7", alpha=0.85))


def seed(value):
    """Reset the module RNG (kept simple for reproducible decks)."""
    global _rng
    _rng = np.random.default_rng(value)
