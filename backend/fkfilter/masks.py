"""Construction of adaptive f-k velocity masks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .utils import as_1d_float_array, normalize_direction, validate_positive
from .windows import frequency_band_weight, smooth_notch_profile


@dataclass(frozen=True)
class VelocityMaskParameters:
    """Parameters controlling adaptive f-k rejection masks.

    Spatial frequency is expressed in cycles per distance unit, not radians per
    distance unit. The velocity line is therefore ``kx = f / v``.
    """

    velocities: Sequence[float]
    fmin: float = 0.0
    fmax: float | None = None
    direction: str = "both"
    attenuation: float = 1.0
    relative_width: float = 0.12
    min_width_bins: float = 1.5
    array_width_factor: float = 0.15
    maxmix: int = 0
    transition_width: float = 1.5
    freq_taper: float = 2.0
    taper: str = "hann"
    include_aliases: bool = True

    def validate(self) -> "VelocityMaskParameters":
        velocities = as_1d_float_array(self.velocities, "velocities")
        if np.any(np.abs(velocities) <= 0.0):
            raise ValueError("velocities must be non-zero")
        validate_positive(self.fmin, "fmin", allow_zero=True)
        if self.fmax is not None:
            validate_positive(self.fmax, "fmax")
            if self.fmax <= self.fmin:
                raise ValueError("fmax must be greater than fmin")
        validate_positive(self.attenuation, "attenuation", allow_zero=True)
        if not (0.0 <= self.attenuation <= 1.0):
            raise ValueError("attenuation must be in the interval [0, 1]")
        validate_positive(self.relative_width, "relative_width", allow_zero=True)
        validate_positive(self.min_width_bins, "min_width_bins", allow_zero=True)
        validate_positive(self.array_width_factor, "array_width_factor", allow_zero=True)
        if int(self.maxmix) < 0:
            raise ValueError("maxmix must be >= 0")
        validate_positive(self.transition_width, "transition_width", allow_zero=True)
        validate_positive(self.freq_taper, "freq_taper", allow_zero=True)
        normalize_direction(self.direction)
        return self


def alias_to_nyquist(k: np.ndarray | float, dx: float) -> np.ndarray | float:
    """Fold spatial frequency to the Nyquist interval [-1/(2dx), 1/(2dx))."""

    dx = validate_positive(dx, "dx")
    period = 1.0 / dx
    folded = (np.asarray(k) + 0.5 * period) % period - 0.5 * period
    if np.isscalar(k):
        return float(folded)
    return folded


def _adaptive_core_width(
    *,
    f: float,
    velocity: float,
    dx: float,
    dk: float,
    relative_width: float,
    min_width_bins: float,
    array_width_factor: float,
    maxmix: int,
) -> float:
    """Compute adaptive notch half-width in cycles per distance unit."""

    f = float(f)
    v = abs(float(velocity))
    k0_abs = abs(f / v)

    # Width proportional to the target dip. This makes higher-frequency notches
    # wider, which is useful because field ground roll is rarely a single exact
    # apparent velocity.
    width_rel = relative_width * k0_abs

    # Width inspired by array length M = V / (f * DX). A boxcar array of length M
    # has its first spatial-frequency zero near 1 / (M * DX). We only use a
    # fraction of that width for the fully rejected core, then a smooth taper.
    if f > 0.0:
        m = v / (f * dx)
        if maxmix > 0:
            m = min(m, float(maxmix))
        m = max(m, 1.0)
        width_array = array_width_factor / (m * dx)
    else:
        width_array = 0.0

    width_min = min_width_bins * abs(dk)
    return max(width_rel, width_array, width_min, np.finfo(float).eps)


def build_velocity_reject_mask(
    freqs: np.ndarray,
    kx: np.ndarray,
    dx: float,
    params: VelocityMaskParameters,
) -> np.ndarray:
    """Build a smooth adaptive f-k velocity rejection mask.

    Parameters
    ----------
    freqs:
        Non-negative temporal frequencies from ``np.fft.rfftfreq`` in Hz.
    kx:
        Spatial frequencies from ``np.fft.fftfreq`` in cycles per distance unit.
    dx:
        Trace spacing in the same distance unit as velocities.
    params:
        Mask parameters.

    Returns
    -------
    mask:
        Real array of shape ``(len(freqs), len(kx))``. Values are in [0, 1].
        A value of 1 passes the f-k coefficient unchanged; lower values suppress
        selected apparent velocities.
    """

    params.validate()
    dx = validate_positive(dx, "dx")
    freqs = np.asarray(freqs, dtype=float)
    kx = np.asarray(kx, dtype=float)

    if freqs.ndim != 1 or kx.ndim != 1:
        raise ValueError("freqs and kx must be one-dimensional")
    if freqs.size == 0 or kx.size == 0:
        raise ValueError("freqs and kx must be non-empty")

    velocities = as_1d_float_array(params.velocities, "velocities")
    signs = normalize_direction(params.direction)
    dk = float(np.median(np.diff(np.sort(kx)))) if kx.size > 1 else 1.0 / dx
    dk = abs(dk) if np.isfinite(dk) and dk != 0.0 else 1.0 / (kx.size * dx)

    mask = np.ones((freqs.size, kx.size), dtype=float)
    max_abs_k = 0.5 / dx

    for i, f in enumerate(freqs):
        if f <= 0.0:
            continue

        band_w = frequency_band_weight(f, params.fmin, params.fmax, params.freq_taper)
        if band_w <= 0.0:
            continue

        reject_strength = np.zeros(kx.size, dtype=float)

        for velocity in velocities:
            v_abs = abs(float(velocity))
            core = _adaptive_core_width(
                f=f,
                velocity=v_abs,
                dx=dx,
                dk=dk,
                relative_width=params.relative_width,
                min_width_bins=params.min_width_bins,
                array_width_factor=params.array_width_factor,
                maxmix=int(params.maxmix),
            )
            trans = core * float(params.transition_width)

            # A negative velocity explicitly flips the requested direction.
            velocity_sign = 1 if velocity >= 0.0 else -1
            for s in signs:
                k0 = velocity_sign * s * f / v_abs
                if params.include_aliases:
                    k0 = alias_to_nyquist(k0, dx)
                elif abs(k0) > max_abs_k:
                    continue

                distance = np.abs(kx - k0)
                profile = smooth_notch_profile(
                    distance,
                    core,
                    trans,
                    kind=params.taper,
                )
                reject_strength = np.maximum(reject_strength, profile)

        reject_strength *= params.attenuation * band_w
        mask[i, :] = np.minimum(mask[i, :], 1.0 - reject_strength)

    return np.clip(mask, 0.0, 1.0)
