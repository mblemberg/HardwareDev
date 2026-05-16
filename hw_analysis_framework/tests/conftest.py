"""Test-suite-wide configuration: put fixture block modules on sys.path."""
from __future__ import annotations

import sys
from pathlib import Path

# Make `tests/fixtures/blocks/*` importable as top-level packages so tests
# can do `from sample_block import leaves, analysis`. This mirrors how a
# real analysis project sees its own `blocks/` folder.
_FIXTURE_BLOCKS = Path(__file__).parent / "fixtures" / "blocks"
if str(_FIXTURE_BLOCKS) not in sys.path:
    sys.path.insert(0, str(_FIXTURE_BLOCKS))
