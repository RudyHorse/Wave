"""Forward and inverse transforms between t-x and f-k domains."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .utils import centered_pad_width, resolve_fft_length, validate_positive
from .windows import data_window


@dataclass(frozen=True)
class SpectrumGeometry:
    """Geometry and padding metadata for a t-x <-> f-k transform."""

    nt: int
    nx: int
    nt_fft: int
    nx_fft: int
    dt: float
    dx: float
    x_pad_left: int
    x_pad_right: int

    @property
    def freqs(self) -> np.ndarray:
        return np.fft.rfftfreq(self.nt_fft, d=self.dt)

    @property
    def kx(self) -> np.ndarray:
        return np.fft.fftfreq(self.nx_fft, d=self.dx)


@dataclass(frozen=True)
class FKTransformResult:
    """Forward transform result."""

    fk: np.ndarray
    geometry: SpectrumGeometry


def make_geometry(
    nt: int,
    nx: int,
    *,
    dt: float,
    dx: float,
    nt_fft: int | None = None,
    nx_fft: int | None = None,
    time_pad_factor: float = 1.0,
    space_pad_factor: float = 2.0,
    use_next_fast_len: bool = True,
) -> SpectrumGeometry:
    """Create FFT geometry for a gather with shape ``(nt, nx)``."""

    nt = int(nt)
    nx = int(nx)
    if nt < 2 or nx < 2:
        raise ValueError("nt and nx must both be at least 2")
    dt = validate_positive(dt, "dt")
    dx = validate_positive(dx, "dx")
    nt_resolved = resolve_fft_length(
        nt,
        pad_factor=time_pad_factor,
        explicit=nt_fft,
        use_next_fast_len=use_next_fast_len,
    )
    nx_resolved = resolve_fft_length(
        nx,
        pad_factor=space_pad_factor,
        explicit=nx_fft,
        use_next_fast_len=use_next_fast_len,
    )
    left, right = centered_pad_width(nx, nx_resolved)
    return SpectrumGeometry(
        nt=nt,
        nx=nx,
        nt_fft=nt_resolved,
        nx_fft=nx_resolved,
        dt=dt,
        dx=dx,
        x_pad_left=left,
        x_pad_right=right,
    )


def tx_to_fk(
    data: np.ndarray,
    geometry: SpectrumGeometry,
    *,
    time_window: str | None = None,
    space_window: str | None = None,
    taper_alpha: float = 0.1,
) -> FKTransformResult:
    """Transform a real t-x gather to f-k domain.

    Parameters
    ----------
    data:
        Real array with shape ``(nt, nx)``.
    geometry:
        FFT geometry produced by :func:`make_geometry`.
    time_window, space_window:
        Optional data tapers. Defaults are ``None`` because tapers alter edge
        amplitudes; zero-padding is usually enough for the intended workflow.
    """

    arr = np.asarray(data)
    if arr.shape != (geometry.nt, geometry.nx):
        raise ValueError(
            f"data shape {arr.shape} does not match geometry "
            f"({geometry.nt}, {geometry.nx})"
        )

    work = np.asarray(arr, dtype=float)

    tw = data_window(geometry.nt, time_window, alpha=taper_alpha)
    xw = data_window(geometry.nx, space_window, alpha=taper_alpha)
    if not np.allclose(tw, 1.0) or not np.allclose(xw, 1.0):
        work = work * tw[:, None] * xw[None, :]

    padded = np.pad(
        work,
        pad_width=((0, geometry.nt_fft - geometry.nt), (geometry.x_pad_left, geometry.x_pad_right)),
        mode="constant",
    )

    fx = np.fft.rfft(padded, n=geometry.nt_fft, axis=0)
    fk = np.fft.fft(fx, n=geometry.nx_fft, axis=1)
    return FKTransformResult(fk=fk, geometry=geometry)


def fk_to_tx(fk: np.ndarray, geometry: SpectrumGeometry) -> np.ndarray:
    """Inverse transform from f-k domain back to the original t-x window."""

    fk = np.asarray(fk)
    expected = (geometry.nt_fft // 2 + 1, geometry.nx_fft)
    if fk.shape != expected:
        raise ValueError(f"fk shape {fk.shape} does not match expected {expected}")

    fx = np.fft.ifft(fk, n=geometry.nx_fft, axis=1)
    tx_padded = np.fft.irfft(fx, n=geometry.nt_fft, axis=0)
    x0 = geometry.x_pad_left
    x1 = x0 + geometry.nx
    return np.asarray(tx_padded[: geometry.nt, x0:x1].real)


def amplitude_spectrum(data: np.ndarray, geometry: SpectrumGeometry | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convenience helper returning ``freqs, kx, abs(FK)`` for plotting."""

    arr = np.asarray(data)
    if arr.ndim != 2:
        raise ValueError("data must be 2-D")
    if geometry is None:
        geometry = make_geometry(arr.shape[0], arr.shape[1], dt=1.0, dx=1.0)
    tr = tx_to_fk(arr, geometry)
    return geometry.freqs, geometry.kx, np.abs(tr.fk)
