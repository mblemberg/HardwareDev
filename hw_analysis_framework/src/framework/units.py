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

# Time
s = registry.second
ms = registry.millisecond
us = registry.microsecond
ns = registry.nanosecond
ps = registry.picosecond
minute = registry.minute   # NOT `min` -- would shadow the Python built-in
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
    "degC",
    "degF",
    "hour",
    "kHz",
    "kOhm",
    "kV",
    "kW",
    "mA",
    "mF",
    "mH",
    "mOhm",
    "mV",
    "mW",
    "minute",
    "ms",
    "nA",
    "nC",
    "nF",
    "nH",
    "ns",
    "pC",
    "pF",
    "percent",
    "ppm",
    "ps",
    "registry",
    "s",
    "uA",
    "uF",
    "uH",
    "uV",
    "uW",
    "us",
]
