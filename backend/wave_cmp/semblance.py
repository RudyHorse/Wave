"""Windowed live-fold weighted semblance; memory O(Ntrace * Nsample)."""
import numpy as np
from .nmo import apply_nmo


def window_sum(values, half_width):
    values = np.asarray(values, dtype=np.float64)
    positions = np.arange(values.shape[-1])
    lo, hi = np.maximum(positions-half_width, 0), np.minimum(positions+half_width+1, values.shape[-1])
    cs = np.concatenate((np.zeros((*values.shape[:-1], 1)), np.cumsum(values, axis=-1)), axis=-1)
    return cs[..., hi] - cs[..., lo]


def scan_semblance(data, offsets_m, dt_s, velocities, *, window_ms=24, min_fold=2,
                   start_time_s=0, input_weights=None, nmo_params=None, time_indices=None,
                   check_cancel=lambda: None):
    velocities = np.asarray(velocities, dtype=np.float64)
    if velocities.ndim != 1 or len(velocities) == 0 or not np.isfinite(velocities).all() or (velocities<=0).any():
        raise ValueError('Trial velocities must be positive finite values')
    if min_fold < 2 or not np.isfinite(window_ms) or window_ms <= 0:
        raise ValueError('Positive window_ms and min_fold>=2 required')
    ns = np.shape(data)[1]
    keep = np.arange(ns) if time_indices is None else np.asarray(time_indices, dtype=np.int64)
    if keep.ndim != 1 or (keep<0).any() or (keep>=ns).any():
        raise ValueError('Invalid time_indices')
    half = max(0, int(round(window_ms / (1000*dt_s))) // 2)
    spectrum = np.zeros((len(keep), len(velocities)), dtype=np.float32)
    for j,v in enumerate(velocities):
        check_cancel()
        corrected = apply_nmo(data, offsets_m, dt_s, v, nmo_params, start_time_s=start_time_s,
                              input_weights=input_weights, velocity_derivative=0., check_cancel=check_cancel)
        a, w = corrected.data.astype(np.float64), corrected.weights.astype(np.float64)
        fold = np.count_nonzero(w>0, axis=0)
        good = fold >= min_fold
        sum_a = np.sum(w*a, axis=0)
        sum_a2 = np.sum(w*a*a, axis=0)
        sum_w = np.sum(w, axis=0)
        numerator = window_sum(np.where(good, sum_a*sum_a, 0), half)
        denominator = window_sum(np.where(good, sum_w*sum_a2, 0), half)
        sem = np.divide(numerator, denominator, out=np.zeros(ns), where=denominator>np.finfo(float).tiny)
        spectrum[:, j] = np.clip(sem[keep], 0, 1)
    return spectrum
