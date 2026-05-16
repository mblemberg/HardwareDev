# components — for Claude Code sessions

Component library for the framework. Three layers: **types** (Pydantic schemas), **families** (parameter factories), **instances** (specific part numbers as named Python objects).

**Authoritative spec:** [`../hardware_analysis_framework_design.md`](../hardware_analysis_framework_design.md) section 6.5. The [CONTRIBUTING.md](CONTRIBUTING.md) in this repo has the day-to-day rules for adding new types / families / instances.

## Mental model

```
       framework.Component (base)
              │
              ▼
       components.types.*   ← team's vocabulary (Pydantic schemas)
              │
              ▼
   components.families.*    ← parameter factories for parametric parts
              │
              ▼
   components.instances.*   ← specific part numbers, named, importable
```

Every Quantity-typed field on a Component subclass uses `CoercedQuantity` from [`types/_helpers.py`](types/_helpers.py) so users can pass `framework.Quantity`, `pint.Quantity`, Pint-format string, or bare number (lifted to dimensionless).

## Things that bite

### 1. Offset-unit math (the recurring lesson)
Temperature coefficients use `ppm / K`, **not** `ppm / degC`. Pint refuses division by offset units. A tempco is unambiguously per-delta-kelvin anyway. Same applies to any "X per temperature delta" parameter.

### 2. `Ohm` capitalization
Python identifier: `Ohm` (capital O) — Pint has it as an alias for `ohm`. Prefixed forms (`mOhm`, `kOhm`, `MOhm`) work as identifiers but **not as parse strings** (Pint can't alias prefixed unit names). In strings, write `"5 milliohm"` / `"10 kiloohm"`.

### 3. Family member dicts must match `available_sizes`
`ResistorFamily.power_rating_by_size` and `max_voltage_by_size` must contain an entry for every size in `available_sizes`. The validator catches this at family construction time. Same for `CapacitorFamily.voltage_rating_by_size`.

### 4. Bare numbers are accepted but get dimensionless units
`tolerance=0.01` works (and is recommended — tolerance is a ratio). `v_ds_max=30` also works at construction but `30` becomes a dimensionless Quantity, which will fail loudly at the first arithmetic with `5 * V`. Prefer explicit units (`30 * V`) for dimensioned fields.

### 5. Scenario-varying parameters
For things like MOSFET `rds_on` that legitimately vary with junction temperature, use `Quantity(unit=Ohm, by_scenario={"nominal": 0.028, "max_temp": 0.038})`. The component library is designed for this — analysis code consumes the right scenario via `framework.Project.standard_inputs`. See [`instances/mosfets/irlml6344.py`](instances/mosfets/irlml6344.py) for the worked pattern.

## Dev workflow

This repo has no venv of its own — it uses the framework's. From this directory:

```powershell
..\hw_analysis_framework\.venv\Scripts\python.exe -m pytest         # 30+ tests
..\hw_analysis_framework\.venv\Scripts\python.exe -m pytest -v
```

`conftest.py` puts the workspace root on `sys.path` so `from components.types import ...` resolves.

## Don'ts

- **Don't introduce a new component type for a single part.** The bar is "three real instances would adopt it" — until then, the existing types + `metadata` escape hatch are enough.
- **Don't redefine units inline.** Always `from framework.units import V, A, K, ...` — there's exactly one Pint registry in this project.
- **Don't read `framework.units.registry` directly.** Use the exported unit symbols. Mixing registries breaks unit equality silently.
- **Don't put part-specific behavior in the type schema.** Schemas are data; behavior belongs in the analysis layer.

## When adding a new type

See CONTRIBUTING.md. The short version:
1. Subclass `framework.Component`.
2. Annotate Quantity fields with `CoercedQuantity` from `types/_helpers.py`.
3. Required / standardized-optional / free-form `metadata` field separation per design doc 6.5.
4. Re-export from `types/__init__.py`.
5. Smoke test in `tests/test_types.py`.
