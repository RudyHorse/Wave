"""V(inline, CDP, t): temporal linear/PCHIP, lateral linear in velocity."""
import numpy as np
from scipy.interpolate import PchipInterpolator
from .schemas import VelocityDocument

class VelocityModel:
    def __init__(self, document: VelocityDocument):
        self.document = document
        self.lines = {}
        for fun in document.functions:
            t = np.array([p.time_ms / 1000 for p in fun.picks], dtype=np.float64)
            v = np.array([p.velocity_mps for p in fun.picks], dtype=np.float64)
            pchip = PchipInterpolator(t, v, extrapolate=False) if document.time_interpolation == 'pchip' and len(t) > 1 else None
            self.lines.setdefault(fun.inline, []).append((fun.cdp, t, v, pchip))
        for fs in self.lines.values():
            fs.sort(key=lambda f: f[0])

    def _time(self, fun, times):
        _, t, v, pchip = fun
        if self.document.time_extrapolation == 'error' and (np.min(times) < t[0] or np.max(times) > t[-1]):
            raise ValueError(f'Time lies outside picks for CDP {fun[0]}')
        tt = np.clip(times, t[0], t[-1])
        if len(t) == 1:
            return np.full_like(tt, v[0]), np.zeros_like(tt)
        if pchip is not None:
            vel, dv = pchip(tt), pchip.derivative()(tt)
        else:
            vel = np.interp(tt, t, v)
            slopes = np.diff(v) / np.diff(t)
            k = np.clip(np.searchsorted(t, tt, side='right') - 1, 0, len(slopes) - 1)
            dv = slopes[k]
        dv = np.where((times < t[0]) | (times > t[-1]), 0.0, dv)
        return vel, dv

    def evaluate(self, inline: int, cdp: int, time_s):
        times = np.asarray(time_s, dtype=np.float64)
        if times.ndim != 1 or not len(times) or not np.isfinite(times).all() or (times < 0).any():
            raise ValueError('time_s must be a finite nonnegative vector')
        fs = self.lines.get(int(inline))
        if not fs:
            raise ValueError(f'No velocity functions for inline {inline}; no cross-inline extrapolation')
        keys = np.array([f[0] for f in fs])
        j = int(np.searchsorted(keys, cdp))
        if j < len(keys) and keys[j] == cdp:
            return self._time(fs[j], times)
        if j == 0 or j == len(keys):
            if self.document.spatial_extrapolation == 'error':
                raise ValueError(f'CDP {cdp} outside picked range {keys[0]}..{keys[-1]} on inline {inline}')
            return self._time(fs[0 if j == 0 else -1], times)
        a = (cdp - keys[j-1]) / (keys[j] - keys[j-1])
        v0, d0 = self._time(fs[j-1], times)
        v1, d1 = self._time(fs[j], times)
        return v0 + a*(v1-v0), d0 + a*(d1-d0)
