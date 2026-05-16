# example_analysis

Reference analysis project — exercises features of `hw_analysis_framework` and serves as both documentation and integration test (Section 16 of the design doc).

## Layout

```
example_analysis/
  project/
    __init__.py
    scenarios.toml         # operating corners        (design doc 6.2)
    modes.toml             # system modes             (design doc 6.3)
    requirements.py        # Jama-linked design constraints (design doc 6.4)
  blocks/
    __init__.py
    can_transceiver/       # per-block subpackage     (design doc 6.6)
      __init__.py
      leaves.py            # hand-coded leaf Quantities
      analysis.py          # derived nodes (Hamilton wires by parameter name)
  can_transceiver_analysis.ipynb   # the worked end-to-end demo
```

## Status

[`can_transceiver_analysis.ipynb`](can_transceiver_analysis.ipynb) loads the project, runs `project.run([leaves, analysis], targets=[...])` to execute the Hamilton DAG, and renders results / spec-checks the output. Steps 1–4 of the framework are exercised end-to-end.

Still missing from the full design (per the notebook's closing cell): per-block `contracts.py`, `verifications.py`, `report.ipynb`, and `components.py`. Those land with framework steps 5, 7, 9.

## Running

The notebook uses the framework venv directly — point Jupyter's kernel at `../hw_analysis_framework/.venv/Scripts/python.exe`.
