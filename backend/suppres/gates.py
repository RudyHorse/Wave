"""Spatial SUPPRES application gates and their linear time tapers.

The supplied Paradigm 18 manual names two interpolation headers but does not
specify the interpolation algorithm.  This implementation interpolates each
primary-key group's gate linearly in the secondary key, then interpolates
between neighboring primary-key groups.  Values beyond the supplied controls
use the nearest endpoint.  These are explicit compatibility assumptions, not
claims about undocumented proprietary behavior.

Gate times are absolute trace times in milliseconds.  A taper extends *outside*
the application interval; the entire closed interval [TBEG, TEND] has unit
weight (manual example two, page 14).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numbers
import operator
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _integer(value: object, name: str, *, positive: bool = False) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer, not a boolean")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if positive and result < 1:
        raise ValueError(f"{name} must be at least 1")
    # Interpolation runs in float64.  Refuse values it cannot represent
    # exactly instead of silently collapsing distinct integer control keys.
    try:
        as_float = float(result)
    except OverflowError as exc:
        raise ValueError(f"{name} is too large for interpolation") from exc
    if not math.isfinite(as_float) or int(as_float) != result:
        raise ValueError(f"{name} must be exactly representable as float64")
    return result


def _finite_scalar(value: object, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _finite_array(value: ArrayLike, name: str) -> NDArray[np.float64]:
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf":
        raise ValueError(f"{name} must contain real numeric values")
    array = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


@dataclass(frozen=True)
class GatePoint:
    """One spatial gate control, with times in milliseconds.

    ``None`` means the corresponding trace start/end time.  ``pkey`` must be
    a positive integer.  ``skey`` is an integer; negative secondary controls
    are supported (for example, signed offsets in a chosen trace header).
    """

    pkey: int
    skey: int
    tbeg_ms: float | None = None
    tend_ms: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "pkey", _integer(self.pkey, "pkey", positive=True))
        object.__setattr__(self, "skey", _integer(self.skey, "skey"))
        for name in ("tbeg_ms", "tend_ms"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite_scalar(value, name))
        if (
            self.tbeg_ms is not None
            and self.tend_ms is not None
            and self.tend_ms < self.tbeg_ms
        ):
            raise ValueError("tend_ms must be greater than or equal to tbeg_ms")


class GateTable:
    """A sorted, immutable set of gate controls on two trace-header axes.

    Duplicate ``(pkey, skey)`` controls are rejected.  Secondary controls may
    differ between primary-key groups; no rectangular grid is required.
    Controls are sorted internally, so their input order has no significance.

    ``evaluate`` uses linear interpolation within each group, followed by
    linear interpolation across primary keys, with constant endpoint
    extrapolation on both axes.  A single primary group therefore applies to
    every queried primary key, rather than acting as a trace selector.
    """

    __slots__ = ("_points", "_primary", "_groups")

    def __init__(self, points: Sequence[GatePoint]) -> None:
        try:
            values = tuple(points)
        except TypeError as exc:
            raise ValueError("points must be a nonempty sequence of GatePoint objects") from exc
        if not values:
            raise ValueError("a GateTable must contain at least one GatePoint")
        if any(not isinstance(point, GatePoint) for point in values):
            raise ValueError("every control must be a GatePoint")
        values = tuple(sorted(values, key=lambda point: (point.pkey, point.skey)))
        keys = [(point.pkey, point.skey) for point in values]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate (pkey, skey) gate controls are not allowed")
        self._points = values
        primary_keys = sorted({point.pkey for point in values})
        self._primary = np.asarray(primary_keys, dtype=np.float64)
        self._primary.flags.writeable = False
        grouped = {key: [] for key in primary_keys}
        for point in values:
            grouped[point.pkey].append(point)
        self._groups = tuple(tuple(grouped[key]) for key in primary_keys)

    @property
    def points(self) -> tuple[GatePoint, ...]:
        """Controls sorted by primary, then secondary key."""
        return self._points

    def __len__(self) -> int:
        return len(self._points)

    def __repr__(self) -> str:
        return f"GateTable(points={self._points!r})"

    def evaluate(
        self,
        pkey: ArrayLike,
        skey: ArrayLike,
        *,
        trace_start_ms: float,
        trace_end_ms: float,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Interpolate gate endpoints for broadcast-compatible header arrays.

        Scalar inputs return zero-dimensional arrays.  Query keys may be
        fractional, while control keys are integers.  Trace bounds must be
        finite and ordered.  TBEG controls must lie within these trace bounds;
        TEND may extend beyond the trace, as permitted by the manual.
        """
        trace_start = _finite_scalar(trace_start_ms, "trace_start_ms")
        trace_end = _finite_scalar(trace_end_ms, "trace_end_ms")
        if trace_end < trace_start:
            raise ValueError("trace_end_ms must be greater than or equal to trace_start_ms")

        primary_query = _finite_array(pkey, "pkey")
        secondary_query = _finite_array(skey, "skey")
        try:
            primary_query, secondary_query = np.broadcast_arrays(primary_query, secondary_query)
        except ValueError as exc:
            raise ValueError("pkey and skey must be broadcast-compatible") from exc
        shape = primary_query.shape
        primary_query = primary_query.ravel()
        secondary_query = secondary_query.ravel()

        # Resolve defaults and validate the complete design before evaluating
        # any particular trace subset; invalid unused controls still fail.
        controls = []
        for group in self._groups:
            secondary = np.asarray([point.skey for point in group], dtype=np.float64)
            starts = np.asarray([
                trace_start if point.tbeg_ms is None else point.tbeg_ms for point in group
            ], dtype=np.float64)
            ends = np.asarray([
                trace_end if point.tend_ms is None else point.tend_ms for point in group
            ], dtype=np.float64)
            if np.any(starts < trace_start) or np.any(starts > trace_end):
                raise ValueError("every tbeg_ms must lie within the trace time range")
            if np.any(ends < starts):
                raise ValueError("every tend_ms must be greater than or equal to tbeg_ms")
            controls.append((secondary, starts, ends))

        insertion = np.searchsorted(self._primary, primary_query, side="right")
        lower = np.clip(insertion - 1, 0, len(self._primary) - 1)
        upper = np.clip(insertion, 0, len(self._primary) - 1)

        def secondary_interpolate(indices: NDArray[np.intp]) -> tuple[np.ndarray, np.ndarray]:
            starts = np.empty(primary_query.size, dtype=np.float64)
            ends = np.empty(primary_query.size, dtype=np.float64)
            for group_index in np.unique(indices):
                mask = indices == group_index
                x, y_start, y_end = controls[int(group_index)]
                starts[mask] = np.interp(secondary_query[mask], x, y_start)
                ends[mask] = np.interp(secondary_query[mask], x, y_end)
            return starts, ends

        lower_start, lower_end = secondary_interpolate(lower)
        upper_start, upper_end = secondary_interpolate(upper)
        weight = np.zeros(primary_query.size, dtype=np.float64)
        between = lower != upper
        # Compute only interpolated values: this avoids division by zero at
        # clamped endpoints and supports a single primary-key group.
        weight[between] = (
            (primary_query[between] - self._primary[lower[between]])
            / (self._primary[upper[between]] - self._primary[lower[between]])
        )
        result_start = (1.0 - weight) * lower_start + weight * upper_start
        result_end = (1.0 - weight) * lower_end + weight * upper_end
        return result_start.reshape(shape), result_end.reshape(shape)


def gate_weights(
    times_ms: ArrayLike,
    starts_ms: ArrayLike,
    ends_ms: ArrayLike,
    taper_ms: float,
) -> NDArray[np.float64]:
    """Return application weights with linear tapers outside each gate.

    ``times_ms`` is a nonempty, strictly increasing, one-dimensional sample
    coordinate array.  ``starts_ms`` and ``ends_ms`` must broadcast; the result
    has their common shape followed by the number of time samples.  Its values
    are exactly one in the closed gate, zero at and beyond the outer taper
    boundaries, and linearly varying in each taper.  ``taper_ms=0`` gives a
    rectangular gate, including a possible zero-length gate at one time.
    """
    times = _finite_array(times_ms, "times_ms")
    if times.ndim != 1 or times.size == 0:
        raise ValueError("times_ms must be a nonempty one-dimensional array")
    if np.any(np.diff(times) <= 0):
        raise ValueError("times_ms must be strictly increasing")
    starts = _finite_array(starts_ms, "starts_ms")
    ends = _finite_array(ends_ms, "ends_ms")
    try:
        starts, ends = np.broadcast_arrays(starts, ends)
    except ValueError as exc:
        raise ValueError("starts_ms and ends_ms must be broadcast-compatible") from exc
    if np.any(ends < starts):
        raise ValueError("ends_ms must be greater than or equal to starts_ms")
    taper = _finite_scalar(taper_ms, "taper_ms")
    if taper < 0:
        raise ValueError("taper_ms must be nonnegative")
    starts = starts[..., np.newaxis]
    ends = ends[..., np.newaxis]
    if taper == 0:
        return ((times >= starts) & (times <= ends)).astype(np.float64)

    # Evaluate distances only on the appropriate side of each gate.  This
    # formulation also covers zero-duration gates without overlapping ramps.
    weights = np.ones(starts.shape[:-1] + (times.size,), dtype=np.float64)
    before = times < starts
    after = times > ends
    with np.errstate(over="ignore"):
        before_weights = np.clip(1.0 - (starts - times) / taper, 0.0, 1.0)
        after_weights = np.clip(1.0 - (times - ends) / taper, 0.0, 1.0)
    np.copyto(weights, before_weights, where=before)
    np.copyto(weights, after_weights, where=after)
    return weights


__all__ = ["GatePoint", "GateTable", "gate_weights"]
