"""Window and taper functions for velocity masks and data tapers."""

from __future__ import annotations

import numpy as np

from .utils import validate_positive


_SUPPORTED_MASK_WINDOWS = {"hann", "cosine", "tukey", "linear", "gaussian", "boxcar"}
_SUPPORTED_DATA_WINDOWS = {"hann", "cosine", "tukey", "boxcar", "none", None}


def smooth_notch_profile(
    distance: np.ndarray,
    core_width: float,
    transition_width: float,
    *,
    kind: str = "hann",
) -> np.ndarray:
    """Return a smooth notch profile from distance to target wavenumber.

    The returned profile is one at the centre of the rejected band and zero
    outside the transition. It is used as a *rejection strength* profile, not
    directly as a pass mask.

    Parameters
    ----------
    distance:
        Absolute distance from target spatial frequency, in cycles per unit.
    core_width:
        Half-width of the fully rejected core, in cycles per unit.
    transition_width:
        Additional half-width of the tapered transition, in cycles per unit.
    kind:
        ``"hann"``/``"cosine"``/``"tukey"`` for a raised-cosine edge,
        ``"linear"`` for a linear edge, ``"gaussian"`` for a Gaussian notch,
        or ``"boxcar"`` for a hard rectangular notch.
    """

    d = np.asarray(distance, dtype=float)
    core_width = float(max(core_width, 0.0))
    transition_width = float(max(transition_width, 0.0))
    kind = (kind or "hann").lower()
    if kind not in _SUPPORTED_MASK_WINDOWS:
        raise ValueError(
            f"Unsupported mask window {kind!r}. Supported: {sorted(_SUPPORTED_MASK_WINDOWS)}"
        )

    if kind == "gaussian":
        # A Gaussian notch does not have a flat top by design. Core width is
        # interpreted as approximately one standard deviation; transition_width
        # controls the cutoff support to keep masks sparse and predictable.
        sigma = max(core_width, np.finfo(float).eps)
        profile = np.exp(-0.5 * (d / sigma) ** 2)
        if transition_width > 0:
            cutoff = core_width + 3.0 * transition_width
            profile = np.where(d <= cutoff, profile, 0.0)
        return np.clip(profile, 0.0, 1.0)

    if transition_width <= 0 or kind == "boxcar":
        return (d <= core_width).astype(float)

    profile = np.zeros_like(d, dtype=float)
    inside = d <= core_width
    edge = (d > core_width) & (d < core_width + transition_width)
    profile[inside] = 1.0

    u = (d[edge] - core_width) / transition_width  # 0 at core edge, 1 outside
    if kind in {"hann", "cosine", "tukey"}:
        profile[edge] = 0.5 * (1.0 + np.cos(np.pi * u))
    elif kind == "linear":
        profile[edge] = 1.0 - u
    else:  # should be unreachable because of validation above
        raise ValueError(f"Unsupported mask window {kind!r}")

    return np.clip(profile, 0.0, 1.0)


def frequency_band_weight(
    f: float,
    fmin: float,
    fmax: float | None,
    taper: float,
) -> float:
    """Smooth frequency-domain weight in [0, 1].

    The weight is zero outside the requested band, one inside the flat part,
    ramps up from ``fmin`` to ``fmin + taper`` and ramps down from
    ``fmax - taper`` to ``fmax``. When ``fmin`` is zero, the lower ramp is not
    applied.
    """

    f = float(f)
    fmin = float(max(fmin, 0.0))
    taper = float(max(taper, 0.0))

    if f < fmin:
        return 0.0
    if fmax is not None:
        fmax = float(fmax)
        if f > fmax:
            return 0.0
        if fmax <= fmin:
            return 0.0

    w_low = 1.0
    if taper > 0.0 and fmin > 0.0 and f < fmin + taper:
        u = (f - fmin) / taper
        w_low = 0.5 * (1.0 - np.cos(np.pi * np.clip(u, 0.0, 1.0)))

    w_high = 1.0
    if taper > 0.0 and fmax is not None and f > fmax - taper:
        u = (fmax - f) / taper
        w_high = 0.5 * (1.0 - np.cos(np.pi * np.clip(u, 0.0, 1.0)))

    return float(np.clip(min(w_low, w_high), 0.0, 1.0))


def tukey_window(n: int, alpha: float = 0.1) -> np.ndarray:
    """Return a Tukey window without requiring SciPy's signal module."""

    n = int(n)
    if n < 1:
        raise ValueError("window length must be positive")
    alpha = float(alpha)
    if alpha <= 0.0:
        return np.ones(n, dtype=float)
    if alpha >= 1.0:
        return np.hanning(n)

    x = np.linspace(0.0, 1.0, n)
    w = np.ones(n, dtype=float)
    left = x < alpha / 2.0
    right = x >= 1.0 - alpha / 2.0
    w[left] = 0.5 * (1.0 + np.cos(2.0 * np.pi / alpha * (x[left] - alpha / 2.0)))
    w[right] = 0.5 * (
        1.0 + np.cos(2.0 * np.pi / alpha * (x[right] - 1.0 + alpha / 2.0))
    )
    return w


def data_window(n: int, kind: str | None = None, *, alpha: float = 0.1) -> np.ndarray:
    """Return a one-dimensional data taper.

    The default filter does not apply data tapers because they alter trace
    amplitudes. They are available for workflows that prefer less wrap-around
    leakage over exact edge amplitudes.
    """

    kind_norm = None if kind is None else kind.lower()
    if kind_norm not in _SUPPORTED_DATA_WINDOWS:
        raise ValueError(
            f"Unsupported data window {kind!r}. Supported: "
            f"{sorted(str(k) for k in _SUPPORTED_DATA_WINDOWS if k is not None)}"
        )
    if kind_norm in {None, "none", "boxcar"}:
        return np.ones(int(n), dtype=float)
    if kind_norm in {"hann", "cosine"}:
        return np.hanning(int(n))
    if kind_norm == "tukey":
        return tukey_window(int(n), alpha=alpha)
    raise ValueError(f"Unsupported data window {kind!r}")
