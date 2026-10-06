"""Adaptive f-k velocity filter (imported verbatim for the LFAFN module).

Only the core filtering API is re-exported here; plotting and synthetic
helpers are intentionally omitted so the backend does not depend on matplotlib.
"""

from .filter import FKVelocityFilter, FKFilterDiagnostics
from .masks import VelocityMaskParameters, build_velocity_reject_mask

__all__ = [
    "FKVelocityFilter",
    "FKFilterDiagnostics",
    "VelocityMaskParameters",
    "build_velocity_reject_mask",
]
