"""AMPSCAL frequency-selective lateral amplitude median (imported verbatim).

Only the numerical core is re-exported; the NPZ/SEG-Y adapters and CLI are
intentionally omitted.
"""

from .config import AmpMedianConfig
from .core import AmpMedianResult, band_weights, process
from .neighbors import contiguous_groups, lateral_median, neighbor_windows

__all__ = [
    "AmpMedianConfig",
    "AmpMedianResult",
    "band_weights",
    "process",
    "contiguous_groups",
    "lateral_median",
    "neighbor_windows",
]
