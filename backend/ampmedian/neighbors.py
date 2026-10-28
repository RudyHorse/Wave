"""Local trace neighborhoods and memory-bounded lateral median estimation.

Traces are neighbors in their supplied order. Contiguous equal group IDs form
independent groups; separated occurrences of an ID are never joined. No trace
amplitude normalization or reordering is performed here.
"""

from __future__ import annotations

import operator
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a positive integer, not a boolean")
    try:
        number = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if number < 1:
        raise ValueError(f"{name} must be a positive integer")
    return number


def contiguous_groups(
    n_traces_total: int, group_ids: ArrayLike | None = None,
) -> tuple[tuple[int, int], ...]:
    """Return half-open contiguous group intervals without sorting the input.

    IDs must be a one-dimensional numeric, boolean, Unicode, or byte-string
    array of length ``n_traces_total``. Floating IDs must be finite. Integer
    IDs are compared in their original dtype, including values above 2**53.
    Object arrays and implicit scalar broadcasting are deliberately rejected.
    """
    total = _positive_integer(n_traces_total, "n_traces_total")
    if group_ids is None:
        return ((0, total),)
    ids = np.asarray(group_ids)
    if ids.ndim != 1 or ids.size != total:
        raise ValueError("group_ids must be one-dimensional with one ID per trace")
    if ids.dtype.kind not in "biufUS":
        raise ValueError("group_ids must contain numeric, boolean, Unicode, or byte-string IDs")
    if ids.dtype.kind == "f" and not np.all(np.isfinite(ids)):
        raise ValueError("group_ids must contain only finite numeric IDs")
    boundaries = [0, *(int(i) for i in np.flatnonzero(ids[1:] != ids[:-1]) + 1), total]
    return tuple(zip(boundaries[:-1], boundaries[1:]))


def neighbor_windows(
    n_traces_total: int,
    n_traces: int,
    *,
    group_ids: ArrayLike | None = None,
    edge: str = "shift",
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """Return the start and exclusive stop of each physical trace window.

    ``edge='shift'`` retains ``min(n_traces, group_length)`` physical positions
    by shifting windows inward at group boundaries. Its center uses that
    effective window size. ``edge='shrink'`` clips the nominal centered window
    at each boundary. An even centered window includes one more following
    trace than preceding trace. Missing/dead donors do not expand a window.
    """
    total = _positive_integer(n_traces_total, "n_traces_total")
    requested = _positive_integer(n_traces, "n_traces")
    if not isinstance(edge, str) or edge not in ("shift", "shrink"):
        raise ValueError("edge must be 'shift' or 'shrink'")
    groups = contiguous_groups(total, group_ids)
    starts = np.empty(total, dtype=np.intp)
    stops = np.empty(total, dtype=np.intp)
    for first, stop in groups:
        if edge == "shift":
            count = min(requested, stop - first)
            left = (count - 1) // 2
            for i in range(first, stop):
                start = max(first, min(i - left, stop - count))
                starts[i], stops[i] = start, start + count
        else:
            left = (requested - 1) // 2
            right = requested // 2
            for i in range(first, stop):
                starts[i] = max(first, i - left)
                stops[i] = min(stop, i + right + 1)
    return starts, stops


def _median_inplace(block: NDArray[np.float64]) -> NDArray[np.float64]:
    """Median over axis zero, modifying only the private donor block.

    The usual ``(lower + upper) / 2`` can overflow although both inputs and
    the mathematical median are finite. Same-sign inputs use a difference
    midpoint; opposite-sign inputs use a sum midpoint. The formulas also
    retain equal subnormal values that would underflow under ``a/2+b/2``.
    """
    count = block.shape[0]
    upper = count // 2
    if count % 2:
        block.partition(upper, axis=0)
        return block[upper].copy()
    lower = upper - 1
    block.partition((lower, upper), axis=0)
    low, high = block[lower], block[upper]
    same_sign = np.signbit(low) == np.signbit(high)
    midpoint = np.empty_like(low)
    midpoint[same_sign] = low[same_sign] + (high[same_sign] - low[same_sign]) * 0.5
    midpoint[~same_sign] = (low[~same_sign] + high[~same_sign]) * 0.5
    return midpoint


def lateral_median(
    values: ArrayLike,
    n_traces: int,
    *,
    group_ids: ArrayLike | None = None,
    live_mask: ArrayLike | None = None,
    edge: str = "shift",
    feature_batch_size: int = 8192,
) -> tuple[NDArray[np.float64], NDArray[np.intp]]:
    """Estimate a median across neighboring traces for every feature.

    Parameters
    ----------
    values:
        Finite real samples with shape ``(n_traces_total, ...)``. The remaining
        dimensions may represent time, frequency, or time-frequency features.
        A one-dimensional input treats each trace as one scalar feature.
    n_traces:
        Positive number of physical trace positions in the nominal window,
        including the target trace. Even values are supported.
    group_ids:
        Optional one-dimensional IDs. Windows stay within contiguous groups.
    live_mask:
        Boolean array of length ``n_traces_total``. False entries are excluded
        from every donor set and returned unchanged, with a donor count of
        zero. There is no implicit zero/dead-trace detection in this helper.
    edge:
        ``'shift'`` maintains the requested number of physical positions when
        the group is large enough. ``'shrink'`` clips centered windows.
    feature_batch_size:
        Maximum number of flattened feature columns copied into one private
        median-work block. The temporary donor block is bounded by roughly
        ``8 * min(n_traces, group_length) * feature_batch_size`` bytes, in
        addition to output and per-feature reduction arrays.

    Returns
    -------
    medians, donor_counts:
        A float64 array with the input shape and an integer count per trace.
        Counts reflect live donors within the physical window. Missing donors
        are not replaced by more distant traces. A window without donors
        retains the original target value and reports zero.

    Notes
    -----
    The conventional median averages the two middle values for an even donor
    count. Float64 conversion is intentional; very large integer input values
    may lose integer precision. The input array and its ordering are unchanged.
    This implementation loops over target traces and partitions donor blocks;
    it does not materialize the full trace-window-by-feature tensor.
    """
    raw = np.asarray(values)
    if raw.ndim < 1 or any(dimension == 0 for dimension in raw.shape):
        raise ValueError("values must contain at least one trace and one feature")
    if raw.dtype.kind not in "iuf":
        raise ValueError("values must contain real numeric samples")
    if not np.all(np.isfinite(raw)):
        raise ValueError("values must contain only finite samples")
    with np.errstate(over="ignore", invalid="ignore"):
        converted = raw.astype(np.float64, copy=False)
    if not np.all(np.isfinite(converted)):
        raise ValueError("values must be representable as finite float64 samples")
    total = raw.shape[0]
    starts, stops = neighbor_windows(total, n_traces, group_ids=group_ids, edge=edge)
    batch = _positive_integer(feature_batch_size, "feature_batch_size")
    if live_mask is None:
        live = np.ones(total, dtype=bool)
    else:
        live = np.asarray(live_mask)
        if live.dtype.kind != "b" or live.shape != (total,):
            raise ValueError("live_mask must be a one-dimensional boolean array with one entry per trace")
    flat = converted.reshape(total, -1)
    result = flat.copy()
    counts = np.zeros(total, dtype=np.intp)
    for target in range(total):
        if not live[target]:
            continue
        start, stop = int(starts[target]), int(stops[target])
        donors = np.flatnonzero(live[start:stop]) + start
        count = donors.size
        counts[target] = count
        if count == 0:
            continue
        for first in range(0, flat.shape[1], batch):
            last = min(first + batch, flat.shape[1])
            # Advanced indexing allocates only this feature block. Partition
            # is in-place on that private copy, so caller data stays intact.
            block = flat[donors, first:last]
            result[target, first:last] = _median_inplace(block)
    return result.reshape(raw.shape), counts


__all__ = ["contiguous_groups", "neighbor_windows", "lateral_median"]
