# Contributing to `components`

The component library is shared across every analysis project that consumes the framework. Changes here ripple — a new MOSFET parameter, or a new component type, is a vocabulary change for the entire team. Two rules: **review before merge**, and **everything carries units**.

## Adding a new component type (Pydantic schema)

A new type defines a new noun in the team's vocabulary — "we now talk about *Inductors*" or "*Transformers*." Add one when:

- At least three real instances are already being modeled with `metadata` dict workarounds.
- The same set of parameters (with the same dimensionality) is showing up across multiple instances.

How:

1. Create `components/types/<your_type>.py`.
2. Subclass [`framework.Component`](../hw_analysis_framework/src/framework/component.py).
3. Annotate every Quantity-valued field with `CoercedQuantity` from [`components/types/_helpers.py`](types/_helpers.py) — this is what gives users the "accept pint.Quantity / framework.Quantity / Pint-format string" ergonomics for free.
4. Separate fields into three buckets, following the design doc 6.5 pattern:
   - **Required:** the parameters every analysis touches. CI fails on missing.
   - **Standardized optional:** well-known names with consistent capitalization across instances (e.g. `q_g_total`, not `qg` or `gate_charge`).
   - **Free-form:** the `metadata: dict[str, Any]` inherited from `Component` is the escape hatch. Don't add ad-hoc typed fields here.
5. Add the type to [`types/__init__.py`](types/__init__.py) re-exports.
6. Add a smoke test in `tests/test_types.py` exercising construction + at least one optional-field path.

Reviewer checklist:
- Required fields really are required by analysis (not just present in the datasheet).
- Field names match existing conventions across other types (`r_thermal_ja`, not `RThJA`).
- Units are correct dimensionally — the framework will catch mismatches at use time, but get them right at definition time.

## Adding a new family

A family defines a *parametric series* — Panasonic ERJ-3, Vishay CRCW, Murata GRM X7R. Adds when you have a series whose tolerance, tempco, and size-dependent ratings are shared across many specific values.

How:

1. Decide whether you need a new family class (`SomethingFamily` in `components/types/<type>.py`) or can use an existing one. For resistors and capacitors, the existing `ResistorFamily` / `CapacitorFamily` should fit.
2. Create `components/families/<category>/<series>_<manufacturer>.py`. File name: lowercased series + manufacturer joined with `_` (`erj3_panasonic.py`, `grm_murata_x7r.py`).
3. The exported Python identifier is `UPPER_SNAKE` matching the series (`ERJ3`, `GRM_X7R`).
4. Populate `available_sizes` + the `*_by_size` dicts. The validator will reject a family that lists an `available_size` without a matching entry in `power_rating_by_size` / `voltage_rating_by_size`.

## Adding a new instance (one-off part)

A one-off instance is a specific part number — `IRLML6344`, `TJA1051T/3`. Use the relevant existing type (`MOSFET`, `IntegratedCircuit`, etc.) — don't define a new type for a single part.

How:

1. Pick the right category: `instances/mosfets/`, `instances/semiconductors/`, `instances/regulators/`, etc.
2. File name: lowercased part number with hyphens / slashes replaced by underscores (`irlml6344.py`, `tja1051t_3.py`).
3. Exported Python identifier: `UPPER_SNAKE_CASE` of the part number with hyphens / slashes replaced by underscores (`IRLML6344`, `TJA1051T_3`).
4. Fill in required fields from the datasheet. For parameters that legitimately vary with temperature or operating condition, use `framework.Quantity(by_scenario=...)` with named corners.
5. Reference the datasheet in a docstring (manufacturer, document number, revision, date).
6. Add a smoke test in `tests/test_instances.py` verifying construction succeeds and a couple of expected values are present.

Family-minted resistor / capacitor identifiers follow the design doc convention: `R_<value>_<size>_<tol>` and `C_<value>_<size>_<voltage>`. Values use engineering prefixes (10K not 10000, 100N not 0.0000001, 4N7 not 4.7N).

## Unit hygiene rules

- **Mandatory Pint** — every Quantity-typed field carries its unit. `value=10_000` may load (bare numbers become dimensionless), but it'll fail loudly at the first arithmetic with a real-unit Quantity. Better to be explicit.
- **Use `K` not `degC` for tempcos.** `100 * ppm / degC` raises in Pint (offset units can't be divided). Use `100 * ppm / K` — a tempco is unambiguously per-delta-kelvin anyway.
- **Capitalize correctly in code:** `V`, `A`, `mA`, `uF`, `nF`, `mOhm`, `Ohm`. In strings (TOML, validator input), prefixed forms like `mOhm` aren't aliased — use the spelled-out Pint form (`"5 milliohm"`).

## PR checklist

- [ ] Type / family / instance follows the file-naming and Python-identifier conventions above.
- [ ] Required fields populated from a cited datasheet.
- [ ] Smoke test added.
- [ ] If a new type is being introduced, three existing one-off parts that would adopt it are listed in the PR description.
- [ ] `pytest` passes in this repo (framework venv).
