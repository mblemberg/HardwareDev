"""Single shared Pint registry — `framework.units`.

Per design doc section 15.2: a single shared registry exposed as
`framework.units`; consumers must not instantiate their own UnitRegistry.

Importing from `framework.units` directly:

    from framework.units import V, A, mA, uA, Ohm, kOhm, mOhm, W, degC, F, uF, nF, pF

All of the bound symbols are `pint.Unit` instances (`5 * V` produces a
`pint.Quantity`). `framework.quantity` lifts `pint.Quantity` operands to
the framework's `Quantity` type when used in arithmetic.
"""
from __future__ import annotations

import pint

registry: pint.UnitRegistry = pint.UnitRegistry()
registry.formatter.default_format = "~P"

# Pint serializes quantities by unit *name*. On unpickle, pint looks up the
# name in the "application registry" -- which by default is the registry of
# the unpickling module, not the one that pickled the value. That causes
# "Cannot operate with Unit and Unit of different registries" errors when a
# cached Quantity is loaded and combined with a freshly constructed one.
# Pinning the application registry to ours globally fixes this.
pint.set_application_registry(registry)

# Engineering naming alias. The design doc (section 6.5) prescribes capitalized
# `Ohm` for Python identifiers; this lets strings like "5 Ohm" parse via
# `framework._toml.parse_pint`. Prefixed forms (`mOhm`, `kOhm`) can't be
# aliased the same way -- Pint constructs them at parse time, not as canonical
# names -- so in strings, use the spelled-out form ("5 milliohm", "10 kiloohm").
# Python code keeps the capitalized engineering form (the symbols exported below).
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

# Time
s = registry.second
ms = registry.millisecond
us = registry.microsecond
ns = registry.nanosecond
ps = registry.picosecond

# Dimensionless ratios
ppm = registry.ppm
percent = registry.percent

__all__ = [
    "A",
    "C",
    "F",
    "GHz",
    "H",
    "Hz",
    "K",
    "MHz",
    "MOhm",
    "Ohm",
    "V",
    "W",
    "degC",
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
