"""Validated controls for amplitude median filtering."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral, Real


def finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real scalar")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


@dataclass(frozen=True)
class AmpMedianConfig:
    """Frequency-selective lateral median parameters.

    ``n_traces`` counts neighboring trace positions, including the target.
    The frequency interval includes its endpoints on the original-record
    Fourier grid. Times supplied to the processing API are milliseconds.

    Modes:
      spectral_median: median Fourier magnitude, preserving original phase.
      spectral_clip: attenuation only, capped at threshold * median magnitude.
      waveform_median: signed time-sample median of the isolated band, with
                       its correction projected back into the selected band.
    """

    n_traces: int = 5
    fmin_hz: float = 5.0
    fmax_hz: float = 80.0
    mode: str = "spectral_median"
    threshold: float = 1.5
    strength: float = 1.0
    transition_hz: float = 0.0
    edge: str = "shift"
    max_gain: float | None = None
    output_dtype: str = "float64"
    exclude_dead: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "n_traces", positive_integer(self.n_traces, "n_traces"))
        for name in ("fmin_hz", "fmax_hz", "threshold", "strength", "transition_hz"):
            object.__setattr__(self, name, finite_number(getattr(self, name), name))
        if not 0 <= self.fmin_hz < self.fmax_hz:
            raise ValueError("Require 0 <= fmin_hz < fmax_hz")
        if self.mode not in ("spectral_median", "spectral_clip", "waveform_median"):
            raise ValueError("mode must be 'spectral_median', 'spectral_clip', or 'waveform_median'")
        if self.threshold < 1:
            raise ValueError("threshold must be at least 1 (a multiple of the median in spectral_clip mode)")
        if not 0 <= self.strength <= 1:
            raise ValueError("strength must be between 0 and 1")
        if self.transition_hz < 0 or self.transition_hz > (self.fmax_hz - self.fmin_hz) / 2:
            raise ValueError("transition_hz must be nonnegative and no greater than half the band width")
        if self.edge not in ("shift", "shrink"):
            raise ValueError("edge must be 'shift' or 'shrink'")
        if self.max_gain is not None:
            object.__setattr__(self, "max_gain", finite_number(self.max_gain, "max_gain"))
            if self.max_gain < 1:
                raise ValueError("max_gain must be at least 1")
            if self.mode != "spectral_median":
                raise ValueError("max_gain applies only to spectral_median mode")
        if self.output_dtype not in ("float64", "float32"):
            raise ValueError("output_dtype must be 'float64' or 'float32'")
        if not isinstance(self.exclude_dead, bool):
            raise TypeError("exclude_dead must be boolean")

    def validate_sampling(self, dt_ms: float, n_samples: int) -> None:
        dt = finite_number(dt_ms, "dt_ms")
        if dt <= 0:
            raise ValueError("dt_ms must be positive")
        if n_samples < 2:
            raise ValueError("At least two time samples are required")
        if not math.isfinite(n_samples * dt) or dt / 1000.0 == 0:
            raise ValueError("The sampling interval or record duration is not representable")
        nyquist = 500.0 / dt
        if self.fmax_hz > nyquist:
            raise ValueError(f"fmax_hz={self.fmax_hz:g} exceeds Nyquist {nyquist:g} Hz")

