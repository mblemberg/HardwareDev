# example_analysis

Reference analysis project — exercises features of `hw_analysis_framework` and serves as both documentation and integration test (Section 16 of the design doc).

## Layout

```
example_analysis/
  project/
    scenarios.toml         # operating corners (design doc 6.2)
    modes.toml             # system modes      (design doc 6.3)
  can_transceiver_analysis.ipynb   # worked block analysis using steps 1-2
```

## Status

Worked block example available: [`can_transceiver_analysis.ipynb`](can_transceiver_analysis.ipynb) computes power dissipation and junction temperature for a CAN transceiver across all (scenario × mode) pairs using the framework's `Quantity` + scenario/mode propagation.

The proper `blocks/<name>/{leaves,analysis,contracts,verifications,report}` subpackage layout (design doc 6.6) lands once the Hamilton DAG, Contracts, and VerificationTests are implemented in the framework (steps 4 + 7 + 9). For now the analysis lives inline in the notebook.

## Running

The notebook uses the framework venv directly — point Jupyter's kernel at `../hw_analysis_framework/.venv/Scripts/python.exe`.
