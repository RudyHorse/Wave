"""Fold-aware stack: mean, sum, weighted median, weighted trimmed mean."""
from dataclasses import dataclass
import numpy as np
from .schemas import StackParams

@dataclass
class StackResult:
    data: np.ndarray
    fold: np.ndarray
    input_fold: np.ndarray
    weight_sum: np.ndarray


def stack_gather(data, weights=None, params=None):
    params = params or StackParams()
    a = np.asarray(data, dtype=np.float64)
    if a.ndim != 2 or not len(a):
        raise ValueError('STACK expects a nonempty (traces, samples) array')
    w = np.ones_like(a) if weights is None else np.array(weights, dtype=np.float64, copy=True)
    if w.shape != a.shape or not np.isfinite(w).all() or (w<0).any() or (w>1).any():
        raise ValueError('Weights must match data and be finite within [0,1]')
    w[~np.isfinite(a)] = 0
    a = np.where(np.isfinite(a), a, 0)
    input_fold = np.count_nonzero(w>0, axis=0).astype(np.int32)
    if params.method in ('median', 'trimmed_mean'):
        order = np.argsort(a, axis=0, kind='stable')
        a, w = np.take_along_axis(a, order, axis=0), np.take_along_axis(w, order, axis=0)
        cumulative = np.cumsum(w, axis=0)
        total = cumulative[-1]
        if params.method == 'trimmed_mean':
            low, high = params.trim_fraction*total, (1-params.trim_fraction)*total
            w = np.maximum(0, np.minimum(cumulative, high) - np.maximum(cumulative-w, low))
    weight_sum = w.sum(axis=0)
    fold = np.count_nonzero(w>0, axis=0).astype(np.int32)
    if params.method == 'median':
        midpoint = total*0.5
        lower = np.argmax((cumulative>=midpoint) & (w>0), axis=0)
        upper = np.argmax((cumulative>midpoint) & (w>0), axis=0)
        cols = np.arange(a.shape[1])
        values = (a[lower, cols] + a[upper, cols]) * 0.5
    else:
        values = np.sum(a*w, axis=0)
        if params.method != 'sum':
            values = np.divide(values, weight_sum, out=np.zeros_like(values), where=weight_sum>0)
    values = np.where((fold>=params.min_fold) & (weight_sum>0), values, 0)
    return StackResult(values.astype(np.float32), fold, input_fold, weight_sum.astype(np.float32))
