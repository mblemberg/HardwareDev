# components

Component library for the hardware analysis framework — Pydantic schemas (types), parametric families, and per-part instances. Design doc reference: [`../hardware_analysis_framework_design.md`](../hardware_analysis_framework_design.md) section 6.5.

## Status

Step 5 of the framework's implementation order. Currently shipping:

- **Types:** [`Resistor`](types/resistor.py), [`Capacitor`](types/capacitor.py), [`MOSFET`](types/mosfet.py), [`BJT`](types/bjt.py), [`Diode`](types/diode.py), [`LDO`](types/ldo.py), [`BuckConverter`](types/buck_converter.py), [`IntegratedCircuit`](types/integrated_circuit.py). Shared enums [`SmtSize`](types/resistor.py) and [`Dielectric`](types/capacitor.py).
- **Families:** [`ERJ3`](families/resistors/erj3_panasonic.py) (Panasonic resistors), [`GRM_X7R`](families/capacitors/grm_murata_x7r.py) (Murata X7R MLCCs).
- **Instances:** [`TJA1051T_3`](instances/semiconductors/tja1051t_3.py) (NXP CAN transceiver, consumed by the example_analysis), [`IRLML6344`](instances/mosfets/irlml6344.py) (Infineon N-channel MOSFET).

## Layout

```
components/
  types/                 # what each part category IS (Pydantic schemas)
  families/              # shared parameter factories for parametric parts
    resistors/
    capacitors/
  instances/             # specific part numbers as named Python objects
    mosfets/
    semiconductors/
  tests/                 # type, family, and instance smoke tests
  CONTRIBUTING.md        # how to add types / families / instances
  CLAUDE.md              # mental model + gotchas for Claude Code sessions
```

## Quick examples

```python
# A specific MOSFET — one of many "one-off" parts.
from components.instances.mosfets.irlml6344 import IRLML6344
print(IRLML6344.rds_on.at(scenario="max_temp"))   # 0.038 (38 mOhm at 125 C)

# Mint a 10 kΩ 0603 resistor from a parametric family.
from components.families.resistors.erj3_panasonic import ERJ3
from components.types import SmtSize
from framework.units import Ohm
R_10K = ERJ3.instance(value=10_000 * Ohm, size=SmtSize.IMP0603)
```

## Running tests

Uses the framework venv (this repo has no venv of its own):

```powershell
cd components
..\hw_analysis_framework\.venv\Scripts\python.exe -m pytest
```

`conftest.py` adds the workspace root to `sys.path` so `from components.types import ...` resolves.
