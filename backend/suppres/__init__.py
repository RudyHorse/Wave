"""SUPPRES band-limited noise suppression (imported verbatim for the module).

Only the numerical core is re-exported; the NPZ/SEG-Y adapters, parameter-card
parser and CLI are intentionally omitted.
"""

from .config import SuppresConfig
from .core import SuppresResult, butterworth_response, process
from .gates import GatePoint, GateTable, gate_weights

__all__ = [
    "SuppresConfig",
    "SuppresResult",
    "GatePoint",
    "GateTable",
    "butterworth_response",
    "gate_weights",
    "process",
]
