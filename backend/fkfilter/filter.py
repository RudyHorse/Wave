"""High-level adaptive f-k velocity filter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .masks import VelocityMaskParameters, build_velocity_reject_mask
from .spectrum import SpectrumGeometry, fk_to_tx, make_geometry, tx_to_fk
from .utils import (
    as_1d_float_array,
    ensure_2d_gather,
    finite_or_raise,
    rms,
    validate_positive,
)


@dataclass(frozen=True)
class FKFilterDiagnostics:
    """Diagnostic information returned by :meth:`FKVelocityFilter.apply`."""

    freqs: np.ndarray
    kx: np.ndarray
    mask: np.ndarray
    geometry: SpectrumGeometry
    fk_before: np.ndarray | None = None
    fk_after: np.ndarray | None = None


@dataclass
class FKVelocityFilter:
    """Adaptive f-k velocity rejection filter for seismic gathers.

    Parameters
    ----------
    dt:
        Time sampling interval in seconds.
    dx:
        Trace spacing in metres or feet. The same distance unit must be used
        for ``velocities``.
    velocities:
        Apparent velocities to suppress. Use positive values with
        ``direction='both'`` for most shot gathers. Negative values can be used
        to flip the sign convention for a specific target.
    fmin, fmax:
        Frequency band in Hz where velocity rejection is active.
    direction:
        ``'both'``, ``'positive'`` or ``'negative'`` f-k branch.
    attenuation:
        Rejection strength: 1.0 means full notch at the centre, 0.5 means 50%
        amplitude attenuation at the centre.
    relative_width:
        Core notch half-width as a fraction of ``abs(f / velocity)``.
    min_width_bins:
        Minimum core notch half-width in spatial FFT bins.
    array_width_factor:
        Additional adaptive width derived from ``M = V / (f * DX)``. The core
        width contribution is ``array_width_factor / (M * DX)``.
    maxmix:
        Optional array-length limit analogous to LFAF's MAXMIX. Zero means no
        explicit limit.
    transition_width:
        Taper width expressed as a multiple of the core width.
    freq_taper:
        Smooth frequency taper length in Hz at the lower and upper band edges.
    taper:
        Mask-edge taper: ``'hann'``, ``'cosine'``, ``'tukey'``, ``'linear'``,
        ``'gaussian'`` or ``'boxcar'``.
    include_aliases:
        Fold target velocities into the sampled spatial Nyquist interval. This
        is important for spatially aliased slow ground roll.
    time_pad_factor, space_pad_factor:
        Zero-padding factors for time and space before FFT. Space padding is
        useful because f-k filtering is periodic in trace direction.
    nt_fft, nx_fft:
        Optional explicit FFT sizes. Must be at least input dimensions.
    use_next_fast_len:
        Use FFT-friendly sizes when resolving padding lengths.
    time_window, space_window:
        Optional data tapers before FFT. Defaults are ``None`` to preserve edge
        amplitudes. Available values: ``'hann'``, ``'tukey'``, ``'boxcar'``.
    restore_global_rms:
        If true, rescales the final result to the original global RMS. This is
        off by default because it can partially undo noise attenuation.
    nan_policy:
        ``'raise'`` or ``'zero'`` for NaN/Inf handling.
    """

    dt: float
    dx: float
    velocities: Sequence[float]
    fmin: float = 0.0
    fmax: float | None = 25.0
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
    time_pad_factor: float = 1.0
    space_pad_factor: float = 2.0
    nt_fft: int | None = None
    nx_fft: int | None = None
    use_next_fast_len: bool = True
    time_window: str | None = None
    space_window: str | None = None
    taper_alpha: float = 0.1
    restore_global_rms: bool = False
    nan_policy: str = "raise"

    def __post_init__(self) -> None:
        self.dt = validate_positive(self.dt, "dt")
        self.dx = validate_positive(self.dx, "dx")
        self.velocities = tuple(as_1d_float_array(self.velocities, "velocities").tolist())
        if any(abs(v) <= 0.0 for v in self.velocities):
            raise ValueError("velocities must be non-zero")
        validate_positive(self.fmin, "fmin", allow_zero=True)
        if self.fmax is not None:
            validate_positive(self.fmax, "fmax")
            if self.fmax <= self.fmin:
                raise ValueError("fmax must be greater than fmin")
        validate_positive(self.time_pad_factor, "time_pad_factor")
        validate_positive(self.space_pad_factor, "space_pad_factor")
        if self.nan_policy not in {"raise", "zero"}:
            raise ValueError("nan_policy must be 'raise' or 'zero'")
        # Validate mask parameters early so construction fails fast.
        self._mask_params().validate()

    @classmethod
    def from_lfaf_params(
        cls,
        *,
        dt: float,
        dx: float,
        vel: float | Sequence[float],
        f1: float = 0.0,
        f2: float = 20.0,
        ftaper: float = 5.0,
        maxmix: int = 0,
        **kwargs: Any,
    ) -> "FKVelocityFilter":
        """Create a filter using parameter names close to Paradigm LFAF.

        This is not a clone of Paradigm's proprietary implementation. It maps
        the common control parameters F1/F2/VEL/DX/FTAPER/MAXMIX to the modern
        adaptive f-k rejector implemented here.
        """

        velocities = [vel] if np.isscalar(vel) else vel
        return cls(
            dt=dt,
            dx=dx,
            velocities=velocities,
            fmin=f1,
            fmax=f2,
            freq_taper=ftaper,
            maxmix=maxmix,
            **kwargs,
        )

    def _mask_params(self) -> VelocityMaskParameters:
        return VelocityMaskParameters(
            velocities=self.velocities,
            fmin=self.fmin,
            fmax=self.fmax,
            direction=self.direction,
            attenuation=self.attenuation,
            relative_width=self.relative_width,
            min_width_bins=self.min_width_bins,
            array_width_factor=self.array_width_factor,
            maxmix=int(self.maxmix),
            transition_width=self.transition_width,
            freq_taper=self.freq_taper,
            taper=self.taper,
            include_aliases=self.include_aliases,
        )

    def geometry_for(self, data: np.ndarray) -> SpectrumGeometry:
        """Return FFT geometry that would be used for *data*."""

        arr = ensure_2d_gather(np.asarray(data))
        return make_geometry(
            arr.shape[0],
            arr.shape[1],
            dt=self.dt,
            dx=self.dx,
            nt_fft=self.nt_fft,
            nx_fft=self.nx_fft,
            time_pad_factor=self.time_pad_factor,
            space_pad_factor=self.space_pad_factor,
            use_next_fast_len=self.use_next_fast_len,
        )

    def build_mask_for(self, data: np.ndarray) -> tuple[np.ndarray, SpectrumGeometry]:
        """Build the f-k rejection mask for a given input gather shape."""

        geometry = self.geometry_for(data)
        mask = build_velocity_reject_mask(
            geometry.freqs,
            geometry.kx,
            self.dx,
            self._mask_params(),
        )
        return mask, geometry

    def apply(
        self,
        data: np.ndarray,
        *,
        return_diagnostics: bool = False,
        return_removed: bool = False,
        keep_fk: bool = False,
    ) -> np.ndarray | tuple[np.ndarray, FKFilterDiagnostics] | tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, FKFilterDiagnostics]:
        """Apply the adaptive f-k velocity filter.

        Parameters
        ----------
        data:
            Gather with shape ``(nt, nx)``.
        return_diagnostics:
            Return mask, axes and geometry alongside the filtered gather.
        return_removed:
            Also return ``data - filtered`` as a noise estimate.
        keep_fk:
            Store f-k arrays before and after filtering in diagnostics. This can
            use significant memory and is intended for debugging/plots.
        """

        arr = ensure_2d_gather(np.asarray(data))
        input_dtype = arr.dtype
        work = np.asarray(arr, dtype=float)

        if self.nan_policy == "raise":
            finite_or_raise(work)
        else:
            work = np.nan_to_num(work, copy=True)

        geometry = self.geometry_for(work)
        tr = tx_to_fk(
            work,
            geometry,
            time_window=self.time_window,
            space_window=self.space_window,
            taper_alpha=self.taper_alpha,
        )
        mask = build_velocity_reject_mask(
            geometry.freqs,
            geometry.kx,
            self.dx,
            self._mask_params(),
        )

        fk_before = tr.fk if keep_fk else None
        fk_after = tr.fk * mask
        filtered = fk_to_tx(fk_after, geometry)

        if self.restore_global_rms:
            in_rms = rms(work)
            out_rms = rms(filtered)
            if out_rms > 0.0 and in_rms > 0.0:
                filtered = filtered * (in_rms / out_rms)

        # Preserve float32 when possible, but do not cast integer input back to
        # integer because filtering produces meaningful fractional amplitudes.
        if np.issubdtype(input_dtype, np.floating) and input_dtype == np.float32:
            filtered = filtered.astype(np.float32, copy=False)

        diagnostics = FKFilterDiagnostics(
            freqs=geometry.freqs,
            kx=geometry.kx,
            mask=mask,
            geometry=geometry,
            fk_before=fk_before,
            fk_after=fk_after if keep_fk else None,
        )

        removed = work - np.asarray(filtered, dtype=float)

        if return_removed and return_diagnostics:
            return filtered, removed, diagnostics
        if return_removed:
            return filtered, removed
        if return_diagnostics:
            return filtered, diagnostics
        return filtered

    __call__ = apply
