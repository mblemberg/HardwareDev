# hw_analysis_framework

Framework for collaborative worst-case circuit analysis: a typed `Quantity` with scenario/mode axes, Pint-enforced units, traceable provenance, and a Hamilton-based DAG.

See [`../hardware_analysis_framework_design.md`](../hardware_analysis_framework_design.md) for the full spec.

## Status

Step 1 of [Section 14 implementation order](../hardware_analysis_framework_design.md): `Quantity` + Pint + arithmetic with scenario propagation.

## Development

```powershell
poetry install --with dev    # if using groups
# or
poetry install -E dev

poetry run pytest --cov
```
