"""Single shared Pint registry — `framework.units`.

Per design doc section 16 item 2 (Open Decisions): a single shared registry
exposed as `framework.units`; consumers must not instantiate their own
UnitRegistry. The ruff lint rule on `pint.UnitRegistry` enforces this
mechanically (configured in `pyproject.toml`).

Importing from `framework.units` directly:

    from framework.units import V, A, mA, uA, Ohm, kOhm, mOhm, W, degC, F, uF, nF, pF

All of the bound symbols are `pint.Unit` instances (`5 * V` produces a
`pint.Quantity`). `framework.quantity` lifts `pint.Quantity` operands to
the framework's `Quantity` type when used in arithmetic.
"""

from __future__ import annotations

import pint

# the singleton unit registry.  linter forbids creation of alternates.
registry = pint.UnitRegistry()  # noqa: TID251

# use the pint formatting mini language
registry.formatter.default_format = "~P"

# instruct pint to use this registry to decode units
pint.set_application_registry(registry)

# pint uses lower case o for Ohm, so we fix that here with an alias in the registry
registry.define("@alias ohm = Ohm")

# Voltage
V = registry.volt
mV = registry.millivolt
uV = registry.microvolt
kV = registry.kilovolt

# Current
A = registry.ampere
mA = registry.milliampere
uA = registry.microampere
nA = registry.nanoampere

# Resistance
Ohm = registry.ohm
mOhm = registry.milliohm
kOhm = registry.kiloohm
MOhm = registry.megaohm
GOhm = registry.gigaohm

# Power
W = registry.watt
mW = registry.milliwatt
uW = registry.microwatt
kW = registry.kilowatt

# Capacitance
F = registry.farad
mF = registry.millifarad
uF = registry.microfarad
nF = registry.nanofarad
pF = registry.picofarad

# Inductance
H = registry.henry
mH = registry.millihenry
uH = registry.microhenry
nH = registry.nanohenry

# Frequency
Hz = registry.hertz
kHz = registry.kilohertz
MHz = registry.megahertz
GHz = registry.gigahertz

# Charge
C = registry.coulomb
nC = registry.nanocoulomb
pC = registry.picocoulomb

# Temperature (Kelvin-based scale used for deltas; degC for absolute)
K = registry.kelvin
degC = registry.degC
degF = registry.degF

# Length
# `mil` gotcha: Pint's default `mil` is a dimensionless 1/1000 ratio, NOT
# 1/1000 inch. For the EE sense (PCB trace widths etc.), use `thou` — Pint's
# name for 1/1000 inch = 25.4 µm. Overriding Pint's `mil` is possible but
# requires touching internals (see git history); deferred until a real need
# motivates it.
m = registry.meter
cm = registry.centimeter
mm = registry.millimeter
um = registry.micrometer
nm = registry.nanometer
km = registry.kilometer
inch = registry.inch
thou = registry.thou

# Time
s = registry.second
ms = registry.millisecond
us = registry.microsecond
ns = registry.nanosecond
ps = registry.picosecond
minute = registry.minute  # NOT `min` -- would shadow the Python built-in
hour = registry.hour

# Dimensionless ratios
ppm = registry.ppm
percent = registry.percent

__all__ = [
    "A",
    "C",
    "F",
    "GHz",
    "GOhm",
    "H",
    "Hz",
    "K",
    "MHz",
    "MOhm",
    "Ohm",
    "V",
    "W",
    "cm",
    "degC",
    "degF",
    "hour",
    "inch",
    "kHz",
    "km",
    "kOhm",
    "kV",
    "kW",
    "m",
    "mA",
    "mF",
    "mH",
    "mOhm",
    "mV",
    "mW",
    "minute",
    "mm",
    "ms",
    "nA",
    "nC",
    "nF",
    "nH",
    "nm",
    "ns",
    "pC",
    "pF",
    "percent",
    "ppm",
    "ps",
    "registry",
    "s",
    "thou",
    "uA",
    "uF",
    "uH",
    "uV",
    "uW",
    "um",
    "us",
]
