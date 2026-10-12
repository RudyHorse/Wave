"""Hyperbolic NMO with local-Jacobian stretch mute and independent weights.

Data invariant: Result.data is NOT multiplied by Result.weights. Apply weights
exactly once in display/export/stack. An amplitude of zero is a valid sample.
"""
from dataclasses import dataclass
import numpy as np
from .schemas import NMOParams

@dataclass
class NMOResult:
    data: np.ndarray
    weights: np.ndarray

    def display(self):
        return self.data * self.weights


def _sample(trace, weights, coordinates, mode, radius):
    n = len(trace)
    valid = np.isfinite(coordinates) & (coordinates >= -1e-9) & (coordinates <= n-1+1e-9)
    q = np.clip(np.nan_to_num(coordinates, nan=0, posinf=n, neginf=0), 0, n-1)
    # Eliminate floating-point residues at exact input sample positions.
    q = np.where(np.abs(q - np.rint(q)) < 1e-10, np.rint(q), q)
    base = np.floor(q).astype(np.int64)
    if mode == 'linear':
        right = np.minimum(base + 1, n-1)
        f = q - base
        out = trace[base] * (1-f) + trace[right] * f
        live = np.where(f == 0, weights[base], np.minimum(weights[base], weights[right]))
    else:
        out, norm, live = np.zeros_like(q), np.zeros_like(q), np.ones_like(q)
        for shift in range(1-radius, radius+1):
            idx = base + shift
            inside = (idx >= 0) & (idx < n)
            ix = np.clip(idx, 0, n-1)
            distance = q - idx
            coeff = np.sinc(distance) * np.sinc(distance / radius) * inside
            significant = np.abs(coeff) > 1e-10
            out += trace[ix] * coeff
            norm += coeff
            live = np.minimum(live, np.where(significant, weights[ix], 1.0))
        valid &= np.abs(norm) > 1e-10
        out = np.divide(out, norm, out=np.zeros_like(out), where=np.abs(norm)>1e-10)
    live = np.where(valid, live, 0)
    out = np.where(live > 0, out, 0)
    return out, live


def apply_nmo(data, offsets_m, dt_s, velocity_mps, params=None, *, start_time_s=0.0,
              input_weights=None, velocity_derivative=None, check_cancel=lambda: None):
    params = params or NMOParams()
    x = np.asarray(data)
    offsets = np.asarray(offsets_m, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] < 1 or x.shape[1] < 2:
        raise ValueError('NMO expects a nonempty (traces, samples>=2) matrix')
    nt = x.shape[1]
    if not np.isfinite(dt_s) or dt_s <= 0 or not np.isfinite(start_time_s) or start_time_s < 0:
        raise ValueError('Positive dt_s and nonnegative absolute start_time_s required')
    if offsets.shape != (x.shape[0],) or not np.isfinite(offsets).all():
        raise ValueError('One finite full source-receiver offset per trace is required')
    v = np.broadcast_to(np.asarray(velocity_mps, dtype=np.float64), (nt,))
    if not np.isfinite(v).all() or (v <= 0).any():
        raise ValueError('Velocity must be finite and positive')
    dv = np.gradient(v, dt_s) if velocity_derivative is None else np.broadcast_to(np.asarray(velocity_derivative, dtype=np.float64), (nt,))
    if not np.isfinite(dv).all():
        raise ValueError('Velocity derivative must be finite')
    if input_weights is not None and np.shape(input_weights) != x.shape:
        raise ValueError('input_weights must have the same shape as data')
    t0 = start_time_s + np.arange(nt) * dt_s
    out = np.zeros(x.shape, dtype=np.float32)
    out_w = np.zeros(x.shape, dtype=np.float32)
    for i, offset in enumerate(offsets):
        if i % 16 == 0:
            check_cancel()
        trace = np.asarray(x[i], dtype=np.float64)
        weight = np.ones(nt) if input_weights is None else np.array(input_weights[i], dtype=np.float64, copy=True)
        if not np.isfinite(weight).all() or (weight < 0).any() or (weight > 1).any():
            raise ValueError('Input sample weights must be finite and within [0,1]')
        weight[~np.isfinite(trace)] = 0
        trace = np.where(np.isfinite(trace), trace, 0)
        t = np.sqrt(t0*t0 + (offset/v)**2)
        if offset == 0:
            jacobian = np.ones(nt)
        else:
            jacobian = np.divide(t0 - offset*offset*dv/v**3, t, out=np.zeros(nt), where=t>0)
        if np.any(jacobian > 1.000001):
            raise ValueError('NMO time compression requires anti-alias resampling, not implemented; revise velocity function')
        # Positive local stretch of the output wavelet: 1 / (dt/dt0) - 1.
        stretch = np.divide(1., jacobian, out=np.full(nt, np.inf), where=jacobian>0)-1
        valid = (jacobian > 0) & (stretch <= params.stretch_limit)
        # Nonmonotone mappings are muted, never folded back into the record.
        valid &= np.r_[True, np.diff(t)>0]
        mute_weight = valid.astype(np.float64)
        if params.stretch_taper:
            phase = np.clip((params.stretch_limit-stretch)/params.stretch_taper, 0, 1)
            mute_weight *= 0.5 - 0.5*np.cos(np.pi*phase)
        values, live = _sample(trace, weight, (t-start_time_s)/dt_s, params.interpolation, params.sinc_half_width)
        w = live * mute_weight
        out[i] = np.where(w>0, values, 0)
        out_w[i] = w
    return NMOResult(out, out_w)
