"""Small utilities used by the f-k filter."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

try:  # scipy is listed as a dependency, but keep a fallback for minimal installs.
    from scipy.fft import next_fast_len as _scipy_next_fast_len
except Exception:  # pragma: no cover
    _scipy_next_fast_len = None


_EPS = np.finfo(float).eps


def as_1d_float_array(values: Sequence[float] | np.ndarray, name: str) -> np.ndarray:
    """Return *values* as a finite one-dimensional float array."""

    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a scalar or a 1-D sequence")
    if arr.size == 0:
        raise ValueError(f"{name} must contain at least one value")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains NaN or infinite values")
    return arr


def validate_positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    """Validate a positive scalar and return it as float."""

    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if allow_zero:
        ok = value >= 0.0
        text = "non-negative"
    else:
        ok = value > 0.0
        text = "positive"
    if not ok:
        raise ValueError(f"{name} must be {text}")
    return value


def next_power_of_two(n: int) -> int:
    """Return the next power-of-two integer greater than or equal to *n*."""

    n = int(n)
    if n < 1:
        raise ValueError("n must be positive")
    return 1 << (n - 1).bit_length()


def next_fast_len(n: int) -> int:
    """Return a fast FFT length.

    Uses SciPy's ``next_fast_len`` when available, otherwise falls back to
    ``next_power_of_two``.
    """

    n = int(n)
    if n < 1:
        raise ValueError("n must be positive")
    if _scipy_next_fast_len is not None:
        return int(_scipy_next_fast_len(n))
    return next_power_of_two(n)


def resolve_fft_length(
    n: int,
    *,
    pad_factor: float = 1.0,
    explicit: int | None = None,
    use_next_fast_len: bool = True,
) -> int:
    """Resolve an FFT length from original length, factor and explicit value."""

    n = int(n)
    if n < 1:
        raise ValueError("input length must be positive")

    if explicit is not None:
        explicit = int(explicit)
        if explicit < n:
            raise ValueError(
                f"explicit FFT length {explicit} is smaller than input length {n}"
            )
        return explicit

    pad_factor = validate_positive(pad_factor, "pad_factor")
    target = int(math.ceil(n * pad_factor))
    target = max(target, n)
    return next_fast_len(target) if use_next_fast_len else target


def centered_pad_width(n: int, n_fft: int) -> tuple[int, int]:
    """Return left and right padding widths for centred spatial padding."""

    if n_fft < n:
        raise ValueError("n_fft must be >= n")
    total = n_fft - n
    left = total // 2
    right = total - left
    return left, right


def rms(x: np.ndarray, *, mask: np.ndarray | None = None) -> float:
    """Root mean square of an array, ignoring no samples by default."""

    arr = np.asarray(x)
    if mask is not None:
        arr = arr[np.asarray(mask, dtype=bool)]
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.abs(arr) ** 2)))


def safe_divide(a: np.ndarray | float, b: np.ndarray | float, default: float = 0.0):
    """Divide with finite output and a default value where denominator is zero."""

    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.divide(a, b)
    if np.isscalar(out):
        return out if np.isfinite(out) else default
    out = np.asarray(out)
    out[~np.isfinite(out)] = default
    return out


def normalize_direction(direction: str) -> tuple[int, ...]:
    """Convert a direction name to target f-k signs.

    The default filter uses ``both`` because field gathers often contain both
    propagation directions or a sign convention different from the modelling
    convention used by the caller.
    """

    d = direction.lower().strip()
    if d in {"both", "+-", "all"}:
        return (-1, 1)
    if d in {"positive", "plus", "+", "pos"}:
        return (1,)
    if d in {"negative", "minus", "-", "neg"}:
        return (-1,)
    raise ValueError(
        "direction must be one of 'both', 'positive' or 'negative', "
        f"got {direction!r}"
    )


def ensure_2d_gather(data: np.ndarray) -> np.ndarray:
    """Validate that data is a two-dimensional gather."""

    arr = np.asarray(data)
    if arr.ndim != 2:
        raise ValueError(
            "input gather must be a 2-D array with shape (time_samples, traces)"
        )
    if arr.shape[0] < 2 or arr.shape[1] < 2:
        raise ValueError("input gather must contain at least two samples and two traces")
    return arr


def finite_or_raise(data: np.ndarray, *, name: str = "data") -> None:
    """Raise a clear error if an array contains NaN or infinite values."""

    if not np.all(np.isfinite(data)):
        raise ValueError(f"{name} contains NaN or infinite values")


def axis_labels(nt: int, nx: int, dt: float, dx: float) -> tuple[np.ndarray, np.ndarray]:
    """Return time and offset axes for examples and plotting."""

    t = np.arange(nt, dtype=float) * dt
    x = np.arange(nx, dtype=float) * dx
    return t, x
