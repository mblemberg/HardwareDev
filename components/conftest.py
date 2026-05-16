"""Pytest config: put the components parent dir on sys.path so tests can
``from components.types import Resistor`` etc.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PARENT = Path(__file__).parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
