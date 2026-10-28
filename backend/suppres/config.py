"""Validated manual parameters and explicitly chosen numerical settings."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real


def finite_number(value: object, name: str) -> float:
    """Return a finite real scalar, rejecting booleans and numeric strings."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True)
class SuppresConfig:
    """SUPPRES settings; frequency in Hz and all times in milliseconds.

    FACTOR follows the explicit examples on manual pp. 14-15: the maximum
    allowed smoothed noise envelope is ``factor * signal_envelope``.
    ``smoothing``, ``padding``, and ``pad_ms`` are implementation choices,
    not parameters documented by Paradigm.
    """

    fbeg_hz: float = 3.0
    fend_hz: float = 18.0
    factor: float = 0.5
    tsmt_ms: float = 60.0
    taper_ms: float = 120.0
    pkeynam: str = "shot"
    skeynam: str = "chan"
    smoothing: str = "hann"
    padding: str = "reflect"
    pad_ms: float | None = None

    def __post_init__(self) -> None:
        for name in ("fbeg_hz", "fend_hz", "factor", "tsmt_ms", "taper_ms"):
            object.__setattr__(self, name, finite_number(getattr(self, name), name))
        if self.fbeg_hz < 0 or self.fend_hz <= 0 or self.fbeg_hz > self.fend_hz:
            raise ValueError("Cutoffs must satisfy 0 <= fbeg_hz <= fend_hz and fend_hz > 0")
        if self.factor < 0:
            raise ValueError("factor must be nonnegative")
        if self.tsmt_ms < 1:
            raise ValueError("tsmt_ms must be at least 1 ms (manual restriction)")
        if self.taper_ms < 0:
            raise ValueError("taper_ms must be nonnegative")
        for name in ("pkeynam", "skeynam"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value) > 8 or not value.isascii() or any(c.isspace() for c in value):
                raise ValueError(f"{name} must be a nonempty ASCII header name of at most 8 characters, without spaces")
        if self.pkeynam == self.skeynam:
            raise ValueError("pkeynam and skeynam must name different headers")
        if self.smoothing not in ("hann", "boxcar"):
            raise ValueError("smoothing must be 'hann' or 'boxcar'")
        if self.padding not in ("reflect", "zero", "periodic"):
            raise ValueError("padding must be 'reflect', 'zero', or 'periodic'")
        if self.pad_ms is not None:
            object.__setattr__(self, "pad_ms", finite_number(self.pad_ms, "pad_ms"))
            if self.pad_ms < 0:
                raise ValueError("pad_ms must be nonnegative")
            if self.padding == "periodic" and self.pad_ms != 0:
                raise ValueError("Periodic processing has no padding; use pad_ms=None or 0")

    def validate_sampling(self, dt_ms: float, n_samples: int) -> None:
        dt_ms = finite_number(dt_ms, "dt_ms")
        if dt_ms <= 0:
            raise ValueError("dt_ms must be positive")
        if n_samples < 2:
            raise ValueError("At least two time samples are required")
        nyquist = 500.0 / dt_ms
        if self.fend_hz > nyquist:
            raise ValueError(f"fend_hz={self.fend_hz:g} exceeds Nyquist {nyquist:g} Hz")
        duration_ms = (n_samples - 1) * dt_ms
        if not math.isfinite(duration_ms):
            raise ValueError("Trace duration is not representable; check dt_ms")
        limit = duration_ms / 2.0
        if self.tsmt_ms > limit + 1e-12 * max(1.0, limit):
            raise ValueError(f"tsmt_ms={self.tsmt_ms:g} exceeds half the trace duration ({limit:g} ms); choose a shorter smoothing window")

