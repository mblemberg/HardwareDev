# Standard Analyses Library — Day-One Scope

**Companion to:** `hardware_analysis_framework_design.md` and `design_methodologies_and_philosophies.md`
**Purpose:** Enumerates every helper shipped in `framework.analysis` at v1.0 — the engineer's day-one vocabulary. Functions are named with consistent conventions, accept Quantities (and Components where natural), return Quantities (or small result dataclasses), and never assert pass/fail themselves (that is the verification test's job).

---

## Library is Small on Purpose

The library is deliberately minimal. A helper earns a place in `framework.analysis` only when:

1. **It is called repeatedly in real analyses** — not a formula someone might want once a year.
2. **It encodes a non-obvious or convention-driven correctness rule** (worst-case droop, margin definitions, derating curves), or it handles an annoying parameter shape (lists-as-series, component-as-Quantity polymorphism).
3. **It has a clean Quantity-in, Quantity-out shape** with no hidden state, no domain modeling, no datasheet interpretation beyond what a typed Component already encodes.

If a formula is a one-liner that an engineer can write inline, **it does not become a helper**. Wheatstone bridges, simple arithmetic identities, and academic-completeness functions all belong in the engineer's block, not in the framework.

The library **grows when a project hits a real need**, not by pre-emptive coverage. Adding a helper is a PR with three things: the implementation, the unit tests, and a brief note in the PR description explaining the actual analysis where it was needed. No speculation. No "we might want this someday."

This principle is enforced in code review.

---

## Scope at v1.0

**In day-one:**

- `passive` — series/parallel combinators, dividers, RC and LC cutoffs
- `power` — LDO and buck regulator helpers, ripple, worst-case droop
- `thermal` — junction temperature, thermal resistance chains, derating
- `switching` — MOSFET conduction loss, switching loss, gate drive current
- `diodes` — forward drop, rectifier dissipation, reverse leakage
- `tvs` — clamping voltage, peak power
- `bjt` — base current, saturation check, dissipation, base-resistor sizing
- `ferrite` — impedance, DC drop, saturation
- `communication` — CAN: termination, bus loading, short-to-battery
- `analog` — op-amp gains (inverting, non-inverting, difference), offset
- `margin` — voltage / current / timing margin, generic spec check
- `spice` — thin LTSpice subprocess shim (DC op, AC sweep, transient)

**Anticipated growth (not a commitment, added when a real need surfaces):**

- `transients` — ISO 16750-2 load dump (pulse 5a), cold crank (pulse 4), reverse polarity dissipation
- `protection.fuse_i2t` — fuse blow time for automotive fuse sizing
- `decoupling.decoupling_cap_for_load_step` — sizing for load-step response
- `communication.i2c_pullup_calc` — pull-up sizing from bus capacitance and rise-time target

Anything else (SOC, signal-integrity reflection coefficients, transmission-line math, LIN/RS485/SPI helpers, eFuse modeling, bypass-impedance curves, etc.) is **not** on the roadmap. Not because they don't exist — they just don't earn their keep until a project says otherwise.

---

## Conventions

- **Inputs and outputs are `Quantity`** with Pint units mandatory. Helpers never accept raw floats.
- **Multi-argument functions use keyword-only arguments** (the `*,` in every signature below). Prevents positional-argument confusion at call sites.
- **Names start with the quantity computed.** `voltage_divider` returns a voltage. `mosfet_conduction_loss` returns a power. `junction_temp_ja` returns a temperature.
- **Standard EE acronyms lowercased:** `rc`, `lc`, `rms`, `esr`, `esl`, `ldo`, `mosfet`, `ja`, `jc`, `bjt`, `tvs`, `psrr`.
- **Lists are series-combined.** Any R/C/L argument that accepts a sequence treats the sequence as series. For parallel, call `parallel_resistance()`, `parallel_capacitance()`, `parallel_inductance()` explicitly.
- **Passive helpers accept Quantity or Component interchangeably** for R, C, L arguments.
- **Parameter-heavy helpers (MOSFET, TVS, BJT, etc.) provide curated `_for(component, ...)` convenience variants** for the most common use cases. The primary form always takes explicit parameters.
- **Helpers never assert pass/fail.** They compute Quantities. The verification test does the asserting.

---

## `framework.analysis.passive`

### Series and parallel combinators

```python
def series_resistance(*resistors: Quantity | Resistor | Sequence) -> Quantity: ...
def parallel_resistance(*resistors: Quantity | Resistor | Sequence) -> Quantity: ...
def series_capacitance(*caps: Quantity | Capacitor | Sequence) -> Quantity: ...
def parallel_capacitance(*caps: Quantity | Capacitor | Sequence) -> Quantity: ...
def series_inductance(*inductors: Quantity | Inductor | Sequence) -> Quantity: ...
def parallel_inductance(*inductors: Quantity | Inductor | Sequence) -> Quantity: ...
```

Accept either varargs (`parallel_resistance(R1, R2, R3)`) or a single sequence (`parallel_resistance([R1, R2, R3])`). Accept Components or Quantities interchangeably.

```python
r_eq = parallel_resistance(R5, R6, R7)
c_eq = series_capacitance([C12, C13])
```

### `voltage_divider`

```python
def voltage_divider(
    *,
    vin: Quantity,
    r_top: Quantity | Resistor | Sequence,
    r_bottom: Quantity | Resistor | Sequence,
) -> Quantity: ...
```

Output voltage of a resistive divider. `V_out = V_in × R_bottom / (R_top + R_bottom)`.

Each leg accepts a single value, a Resistor component, or a sequence (series-combined). For parallel networks, build the equivalent with `parallel_resistance()` first.

```python
v_sense = voltage_divider(vin=VBAT, r_top=[R5, R6], r_bottom=R7)
v_fb    = voltage_divider(vin=v_rail, r_top=R10, r_bottom=parallel_resistance(R11, R12))
```

### `current_divider`

```python
def current_divider(
    *,
    i_total: Quantity,
    branch_r: Quantity | Resistor | Sequence,
    other_branches: Sequence[Quantity | Resistor],
) -> Quantity: ...
```

Current through one branch given total current and resistances of all parallel branches. Computes the parallel combination of `other_branches` and applies the standard divider formula.

```python
i_through_R5 = current_divider(i_total=i_node, branch_r=R5, other_branches=[R6, R7])
```

### `rc_filter_cutoff`

```python
def rc_filter_cutoff(
    *,
    r: Quantity | Resistor | Sequence,
    c: Quantity | Capacitor | Sequence,
) -> Quantity: ...
```

–3 dB cutoff frequency of a first-order RC filter. `f_c = 1 / (2π R C)`.

For full magnitude/phase response, use `framework.analysis.spice.run_ac_sweep` or compute inline.

### `lc_filter_cutoff`

```python
def lc_filter_cutoff(
    *,
    l: Quantity | Inductor | Sequence,
    c: Quantity | Capacitor | Sequence,
) -> Quantity: ...
```

Resonant frequency of an undamped LC filter. `f_0 = 1 / (2π √(L C))`.

---

## `framework.analysis.power`

### `ldo_dropout`

```python
def ldo_dropout(
    *,
    ldo: LDO,
    i_load: Quantity,
    t_junction: Quantity | None = None,
) -> Quantity: ...
```

Dropout voltage of an LDO at a given load (and optionally junction temperature, if the LDO carries a temperature curve). Minimum input voltage required for regulation is `V_out + dropout`.

```python
dropout = ldo_dropout(ldo=board.refdes("U3"), i_load=i_3v3_total)
v_in_min = V_3V3 + dropout
```

### `ldo_efficiency`

```python
def ldo_efficiency(*, ldo: LDO, v_in: Quantity, v_out: Quantity, i_out: Quantity) -> Quantity: ...
```

`η ≈ V_out/V_in × I_out/(I_out + I_q)`.

### `buck_efficiency`

```python
def buck_efficiency(*, buck: BuckConverter, v_in: Quantity, v_out: Quantity, i_out: Quantity) -> Quantity: ...
```

Reads the converter's efficiency curve (linearly interpolated at the operating point) if available; falls back to a parametric estimate.

### `regulator_dissipation`

```python
def regulator_dissipation(*, regulator: LDO | BuckConverter, v_in: Quantity, v_out: Quantity, i_out: Quantity) -> Quantity: ...
```

For LDO: `(V_in − V_out) × I_out + V_in × I_q`. For buck: `V_in × I_in × (1 − η)`. Dispatches on the component type.

### `worst_case_droop`

```python
def worst_case_droop(
    *,
    v_nominal: Quantity,
    load_step: Quantity,
    output_impedance: Quantity,
    bulk_capacitance: Quantity | Capacitor | Sequence,
    loop_bandwidth: Quantity,
) -> Quantity: ...
```

First-order estimate of regulator output droop during a load step.
`ΔV ≈ I_step × (Z_out + 1/(2π × f_loop × C_bulk))`

Assumes single-pole loop response and resistive output impedance. For multi-stage networks or rigorous transient response, use `framework.analysis.spice.run_transient`.

### `output_ripple_buck`

```python
def output_ripple_buck(
    *,
    buck: BuckConverter,
    i_out: Quantity,
    c_out: Capacitor | Sequence[Capacitor],
    l_out: Inductor,
) -> Quantity: ...
```

Peak-to-peak output voltage ripple of a buck converter.
`ΔV_pp = (I_ripple / 8) / (f_sw × C_out) + I_ripple × ESR_C_out`
where `I_ripple` is derived from the inductor and converter switching frequency.

---

## `framework.analysis.thermal`

### `junction_temp_ja`

```python
def junction_temp_ja(*, p: Quantity, r_theta_ja: Quantity, t_ambient: Quantity) -> Quantity: ...
```

`T_j = T_amb + P × θ_JA`.

### `junction_temp_jc`

```python
def junction_temp_jc(*, p: Quantity, r_theta_jc: Quantity, t_case: Quantity) -> Quantity: ...
```

`T_j = T_case + P × θ_JC`.

### `thermal_resistance_series`

```python
def thermal_resistance_series(*r_thermals: Quantity | Sequence[Quantity]) -> Quantity: ...
```

Sum thermal resistances in series — for junction → case → solder → PCB → ambient chains.

### `junction_temp_via_chain`

```python
def junction_temp_via_chain(
    *,
    p: Quantity,
    r_thermal_chain: Sequence[Quantity],
    t_far: Quantity,
) -> Quantity: ...
```

Junction temperature through a multi-stage thermal path. `T_j = T_far + P × Σθ_i`.

### `derated_dissipation`

```python
def derated_dissipation(
    *,
    p_nominal: Quantity,
    t_ambient: Quantity,
    derating_curve: DeratingCurve | None = None,
    linear_derating_above: Quantity | None = None,
    linear_derating_slope: Quantity | None = None,
) -> Quantity: ...
```

Effective allowable dissipation under temperature derating. Either a full `DeratingCurve` (interpolated) or a linear-derating-above-knee parametric form.

---

## `framework.analysis.switching` (MOSFET)

### `mosfet_conduction_loss`

```python
def mosfet_conduction_loss(*, rds_on: Quantity, i_drain: Quantity, duty: Quantity = 1.0) -> Quantity: ...
def mosfet_conduction_loss_for(mosfet: MOSFET, *, i_drain: Quantity, duty: Quantity = 1.0) -> Quantity: ...
```

`P = R_DS(on) × I_drain² × duty`. The `_for` variant reads R_DS(on) directly from the MOSFET component, including any temperature curve if present.

```python
p_q1 = mosfet_conduction_loss_for(board.refdes("Q1"), i_drain=i_load, duty=0.4)
```

### `mosfet_switching_loss`

```python
def mosfet_switching_loss(
    *,
    v_ds: Quantity,
    i_drain: Quantity,
    t_rise: Quantity,
    t_fall: Quantity,
    f_sw: Quantity,
) -> Quantity: ...
def mosfet_switching_loss_for(
    mosfet: MOSFET,
    *,
    v_ds: Quantity,
    i_drain: Quantity,
    f_sw: Quantity,
    gate_drive_resistance: Quantity,
) -> Quantity: ...
```

Linear-edge approximation: `P_sw = 0.5 × V_DS × I_D × (t_rise + t_fall) × f_sw`.
The `_for` variant computes `t_rise` and `t_fall` from `Q_g_total` and gate-drive resistance.

### `gate_drive_current`

```python
def gate_drive_current(*, q_g: Quantity, t_rise: Quantity) -> Quantity: ...
def gate_drive_current_for(mosfet: MOSFET, *, t_rise: Quantity) -> Quantity: ...
```

Average drive current required: `I_gate_avg = Q_g / t_rise`. Used for sizing the gate-driver source/sink capability.

---

## `framework.analysis.diodes`

### `diode_forward_drop`

```python
def diode_forward_drop(*, diode: Diode, i_forward: Quantity, t_junction: Quantity | None = None) -> Quantity: ...
def diode_forward_drop_for(diode: Diode, *, i_forward: Quantity, t_junction: Quantity | None = None) -> Quantity: ...
```

Forward voltage at a given current. Interpolates the diode's `v_f_at_i` curve if available; falls back to a single point with optional temperature coefficient.

### `rectifier_dissipation`

```python
def rectifier_dissipation(
    *,
    diode: Diode,
    i_avg: Quantity,
    i_rms: Quantity | None = None,
    duty: Quantity = 1.0,
) -> Quantity: ...
```

`P = V_F × I_avg × duty`. If `i_rms` is provided, adds the dynamic-resistance contribution: `+ R_d × I_rms² × duty`.

### `diode_reverse_leakage`

```python
def diode_reverse_leakage(*, diode: Diode, v_r: Quantity, t_junction: Quantity) -> Quantity: ...
```

Reverse leakage current at a given reverse voltage and junction temperature. Approximately doubles every 10 °C above 25 °C if a temperature curve isn't on the part.

---

## `framework.analysis.tvs`

### `tvs_clamping_voltage`

```python
def tvs_clamping_voltage(*, tvs: TVS, i_peak: Quantity) -> Quantity: ...
def tvs_clamping_voltage_for(tvs: TVS, *, i_peak: Quantity) -> Quantity: ...
```

Clamp voltage at a given peak current. Interpolates the TVS V–I curve if available; otherwise extrapolates from `v_c_at_ipp` using the dynamic resistance.

### `tvs_peak_power`

```python
def tvs_peak_power(*, tvs: TVS, i_peak: Quantity) -> Quantity: ...
```

`P_peak = V_clamp(i_peak) × I_peak`. Compare against `tvs.p_pp` in a verification test.

---

## `framework.analysis.bjt`

### `bjt_base_current`

```python
def bjt_base_current(*, bjt: BJT, i_collector: Quantity, t_junction: Quantity | None = None) -> Quantity: ...
```

`I_B = I_C / β`. Uses the BJT's β at the operating point (interpolated from β-vs-I_C curve if present).

### `bjt_saturation_check`

```python
def bjt_saturation_check(*, bjt: BJT, i_base: Quantity, i_collector_actual: Quantity) -> SaturationResult: ...
```

Saturation margin: `margin = I_B × β_min − I_C_actual`. Positive → hard saturation; negative → linear region.
Returns `SaturationResult(margin, in_saturation, headroom)`.

### `bjt_dissipation`

```python
def bjt_dissipation(
    *,
    v_ce: Quantity,
    i_collector: Quantity,
    v_be: Quantity = 0.7 * V,
    i_base: Quantity = 0 * A,
) -> Quantity: ...
def bjt_dissipation_for(bjt: BJT, *, v_ce: Quantity, i_collector: Quantity, i_base: Quantity | None = None) -> Quantity: ...
```

`P = V_CE × I_C + V_BE × I_B`. The `_for` variant uses the BJT's V_BE(on) from the datasheet.

### `bjt_base_resistor`

```python
def bjt_base_resistor(
    *,
    bjt: BJT,
    v_drive: Quantity,
    i_collector_required: Quantity,
    saturation_factor: Quantity = 2.0,
) -> Quantity: ...
```

Recommended base resistor to drive into saturation with a chosen overdrive margin.
`R_B = (V_drive − V_BE_sat) × β_min / (saturation_factor × I_C)`

---

## `framework.analysis.ferrite`

### `bead_impedance_at`

```python
def bead_impedance_at(*, bead: FerriteBead, freq: Quantity) -> Quantity: ...
def bead_impedance_at_for(bead: FerriteBead, *, freq: Quantity) -> Quantity: ...
```

Impedance at a given frequency, interpolated from the bead's Z-vs-frequency curve. Curve-driven because bead impedance varies hugely with frequency.

### `bead_dc_voltage_drop`

```python
def bead_dc_voltage_drop(*, bead: FerriteBead, i_dc: Quantity) -> Quantity: ...
```

`V_drop = I_DC × DCR`. Matters for power-rail beads where the DCR loss eats into headroom.

### `bead_saturation_check`

```python
def bead_saturation_check(*, bead: FerriteBead, i_dc: Quantity, i_peak: Quantity | None = None) -> SaturationResult: ...
```

Compares DC (and optionally peak) current against the bead's saturation current. Above `i_sat`, impedance collapses and the bead is no longer effective.

---

## `framework.analysis.communication` (CAN only at v1)

### `can_termination_resistance`

```python
def can_termination_resistance(*, r1: Quantity | Resistor, r2: Quantity | Resistor) -> Quantity: ...
```

Series-combined termination resistance for split termination. Named for self-documenting call sites at the bus interface.

### `can_bus_loading`

```python
def can_bus_loading(
    *,
    transceivers: Sequence[CANTransceiver],
    bus_length: Quantity,
    bit_rate: Quantity,
) -> CANBusLoad: ...
```

Aggregate bus loading from all transceivers on the network.
Returns `CANBusLoad(node_count, capacitance_total, attenuation_db, recommended_max_bit_rate)`.

### `can_short_to_battery_check`

```python
def can_short_to_battery_check(*, transceiver: CANTransceiver, v_battery_max: Quantity) -> CANFaultResult: ...
```

Verifies the transceiver's bus-fault tolerance covers the worst-case battery voltage on CANH or CANL. Returns `CANFaultResult(tolerated, margin)`.

---

## `framework.analysis.analog` (op-amps)

### `opamp_inverting_gain`

```python
def opamp_inverting_gain(
    *,
    r_feedback: Quantity | Resistor | Sequence,
    r_input: Quantity | Resistor | Sequence,
) -> Quantity: ...
```

`G = −R_f / R_in`.

### `opamp_noninverting_gain`

```python
def opamp_noninverting_gain(
    *,
    r_feedback: Quantity | Resistor | Sequence,
    r_ground: Quantity | Resistor | Sequence,
) -> Quantity: ...
```

`G = 1 + R_f / R_g`.

### `opamp_difference_gain`

```python
def opamp_difference_gain(
    *,
    r_input_inv: Quantity | Resistor,
    r_feedback: Quantity | Resistor,
    r_input_noninv: Quantity | Resistor,
    r_ground: Quantity | Resistor,
) -> OpAmpDifferenceResult: ...
```

Difference amplifier gain and common-mode rejection. Returns `OpAmpDifferenceResult(differential_gain, common_mode_gain, cmrr_db)`. CMRR is sensitive to resistor matching — the result quantifies it.

### `opamp_offset_at_output`

```python
def opamp_offset_at_output(
    *,
    opamp: OpAmp,
    gain: Quantity,
    source_z: Quantity | None = None,
) -> Quantity: ...
```

DC offset referred to output: `V_off_out = (V_off_input + I_B × R_source) × gain`. Uses the op-amp's `v_offset_input` and `i_bias_input` specs.

---

## `framework.analysis.margin`

### `voltage_margin`

```python
def voltage_margin(*, actual: Quantity, spec_min: Quantity, spec_max: Quantity) -> MarginResult: ...
```

Returns `MarginResult(margin_low, margin_high, within_spec)`. Margins are signed — negative means out of spec.

### `current_margin`

```python
def current_margin(*, actual: Quantity, limit: Quantity) -> Quantity: ...
```

Signed margin from a limit: `margin = limit − actual`.

### `timing_margin`

```python
def timing_margin(*, actual: Quantity, spec_min: Quantity, spec_max: Quantity) -> MarginResult: ...
```

Same shape as `voltage_margin`, for timing analyses.

### `spec_check`

```python
def spec_check(*, value: Quantity, range_spec: Range) -> SpecResult: ...
```

Generic predicate: is `value` entirely within `range_spec` across all scenarios and modes? Returns `SpecResult(passed, failing_scenarios, margin_in_failing_scenarios)`. Used by the assertion helpers in `VerificationContext`.

---

## `framework.analysis.spice`

Thin LTSpice subprocess wrapper for cases where analytical helpers don't fit. Engineer invokes explicitly. All three functions take a path to an `.asc` LTSpice schematic, optionally parameterize values, run in subprocess, parse `.raw` output, and lift results into Quantities.

### `run_dc_operating_point`

```python
def run_dc_operating_point(
    *,
    circuit: Path,
    parameters: dict[str, Quantity] | None = None,
    measure: Sequence[str],
) -> dict[str, Quantity]: ...
```

### `run_ac_sweep`

```python
def run_ac_sweep(
    *,
    circuit: Path,
    parameters: dict[str, Quantity] | None = None,
    measure: Sequence[str],
    freq_range: tuple[Quantity, Quantity],
    points_per_decade: int = 100,
) -> dict[str, FrequencyResponse]: ...
```

### `run_transient`

```python
def run_transient(
    *,
    circuit: Path,
    parameters: dict[str, Quantity] | None = None,
    measure: Sequence[str],
    duration: Quantity,
    step: Quantity | None = None,
    stimulus: TransientProfile | None = None,
) -> dict[str, TimeSeries]: ...
```

The `stimulus` argument accepts a `TransientProfile` from `framework.analysis.transients` (anticipated-growth module; the type lives in v1 so the SPICE interface doesn't change when the profiles ship).

---

## Component Types Referenced

| Type | Key parameters used by day-one helpers |
|---|---|
| `Resistor` | `resistance`, `tolerance`, `power_rating`, `tcr`, `package` |
| `Capacitor` | `capacitance`, `tolerance`, `voltage_rating`, `esr`, `dielectric`, `package` |
| `Inductor` | `inductance`, `dcr`, `i_saturation`, `i_rms_max`, `srf` |
| `MOSFET` | `rds_on`, `v_gs_th`, `v_ds_max`, `i_d_max`, `q_g_total`, `r_thermal_jc`, `r_thermal_ja`, `body_diode_vf` |
| `BJT` | `beta`, `v_be_on`, `v_ce_sat`, `i_c_max`, `p_d_max`, `f_t` |
| `Diode` | `v_f_at_i`, `i_r_leakage`, `i_f_max`, `i_fsm_surge`, `v_br_min`, `c_j_typ` |
| `TVS` | `v_rwm`, `v_br`, `v_c_at_ipp`, `i_pp`, `p_pp`, `c_typ`, `t_response` |
| `FerriteBead` | `z_vs_freq`, `dcr`, `i_sat`, `i_rated` |
| `LDO` | `v_dropout_at_i`, `i_quiescent`, `psrr_db`, regulation specs |
| `BuckConverter` | `f_sw`, `i_out_max`, `efficiency_curve`, `v_in_range` |
| `OpAmp` | `v_offset_input`, `i_bias_input`, `gbw`, `slew_rate`, `cmrr_db`, `psrr_db` |
| `CANTransceiver` | `i_supply_active`, `i_supply_sleep`, `v_diff_dominant`, `v_cm_range`, `esd_hbm`, `bus_fault_tolerance_v` |

---

## Result Dataclasses

Small typed return objects. All are pickleable, JSON-serializable, and renderable by `framework.plotting`.

| Dataclass | Fields |
|---|---|
| `MarginResult` | `margin_low`, `margin_high`, `within_spec` (bool) |
| `SpecResult` | `passed` (bool), `failing_scenarios`, `margin_in_failing_scenarios` |
| `SaturationResult` | `margin`, `in_saturation` (bool), `headroom` |
| `OpAmpDifferenceResult` | `differential_gain`, `common_mode_gain`, `cmrr_db` |
| `CANBusLoad` | `node_count`, `capacitance_total`, `attenuation_db`, `recommended_max_bit_rate` |
| `CANFaultResult` | `tolerated` (bool), `margin` |
| `FrequencyResponse` | `magnitude` (Quantity vs freq), `phase` (Quantity vs freq) |
| `TimeSeries` | `time`, `value` (both Quantity arrays) |

---

## Quality Bar Per Helper

Every shipped helper has:

1. **Type-hinted signature** with keyword-only arguments for multi-arg helpers.
2. **Google-style docstring** including formula, assumptions, and at least one runnable doctest.
3. **Pint-unit-checked** inputs and outputs.
4. **Pure function** — no global state, no side effects, deterministic for a given input.
5. **Unit tests** with 100% line coverage on the helper.
6. **At least one integration test** in `tests/integration/` that exercises the helper inside a real block analysis.
7. **An entry in the Claude Code agent's index** so the agent can suggest it when an engineer describes the math they want to do.

---

## Anticipated Growth (Planning Hint, Not a Commitment)

These are the helpers we currently anticipate adding next, in priority order based on real automotive electronics work. Each ships only when an actual project surfaces the need.

- **`framework.analysis.transients`** — ISO 16750-2 load dump (pulse 5a), cold crank (pulse 4), reverse polarity dissipation. The `TransientProfile` type is already in v1 (so `spice.run_transient` works with it from day one); the profile *data* and analytical helpers ship in this module.
- **`framework.analysis.protection.fuse_i2t`** — i²t fuse-blow calculation for automotive fuse sizing.
- **`framework.analysis.decoupling.decoupling_cap_for_load_step`** — minimum decoupling cap for a target load-step response.
- **`framework.analysis.communication.i2c_pullup_calc`** — pull-up sizing from bus capacitance and rise-time target.

**Not on the roadmap:** SOC estimation, battery runtime, signal-integrity reflection coefficients, LIN/RS485/SPI helpers, crystal load calc, transmission-line propagation, eFuse modeling, bypass-impedance curves, and similar. Any of these can still be added if a project actually needs them — but they ship under the same gate as anything else: real need, real PR, real tests.
