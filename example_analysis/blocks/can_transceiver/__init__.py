"""CAN transceiver block.

Per design doc 6.6, a block's ``__init__.py`` re-exports only public
Contracts. Other blocks should ``from blocks.can_transceiver import
can_5v_draw`` rather than reaching into ``leaves`` / ``analysis`` directly
— the framework's cycle detector enforces this.
"""
from blocks.can_transceiver.contracts import can_5v_draw

__all__ = ["can_5v_draw"]
