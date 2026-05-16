"""Power supply block.

Per design doc 6.6, a block's ``__init__.py`` re-exports only public
Contracts. The power supply publishes ``rail_5v`` — the 5 V system rail
that the CAN transceiver and MCU consume.
"""
from blocks.power_supply.contracts import rail_5v

__all__ = ["rail_5v"]
