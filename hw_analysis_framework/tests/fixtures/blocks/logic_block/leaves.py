"""Logic block: spec + actual truth tables."""
from __future__ import annotations

from framework import TruthTable


def decoder_spec() -> TruthTable:
    """2-to-4 decoder spec from the datasheet: Y0..Y3 active-high one-hot."""
    return TruthTable.from_rows(
        inputs=["A0", "A1"],
        outputs=["Y0", "Y1", "Y2", "Y3"],
        rows=[
            (0, 0, 1, 0, 0, 0),
            (1, 0, 0, 1, 0, 0),
            (0, 1, 0, 0, 1, 0),
            (1, 1, 0, 0, 0, 1),
        ],
    )


def decoder_actual() -> TruthTable:
    """What the implementation actually computes — enumerated from a function."""
    def fn(A0: bool, A1: bool) -> dict[str, bool]:
        idx = (1 if A1 else 0) * 2 + (1 if A0 else 0)
        return {f"Y{i}": (i == idx) for i in range(4)}

    return TruthTable.from_function(
        inputs=["A0", "A1"],
        outputs=["Y0", "Y1", "Y2", "Y3"],
        fn=fn,
    )
