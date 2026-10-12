"""Stable gather indexing; neighboring *existing* CDPs, never across inlines."""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class GatherSelection:
    indices: np.ndarray
    members: tuple[tuple[int, int], ...]

class GatherIndex:
    def __init__(self, cdp, offsets, inline=None):
        self.cdp = np.asarray(cdp)
        self.offsets = np.asarray(offsets, dtype=np.float64)
        self.inline = np.zeros(len(self.cdp), dtype=np.int64) if inline is None else np.asarray(inline)
        if self.cdp.ndim != 1 or len(self.cdp) == 0 or self.offsets.shape != self.cdp.shape or self.inline.shape != self.cdp.shape:
            raise ValueError('CDP, offset and inline must be nonempty vectors of equal size')
        for values in (self.cdp, self.inline):
            if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
                raise ValueError('CDP and inline must be finite integer headers')
        if not np.isfinite(self.offsets).all():
            raise ValueError('Offsets contain non-finite values')
        self.order = np.lexsort((self.offsets, self.cdp, self.inline))
        il, cp = self.inline[self.order], self.cdp[self.order]
        starts = np.r_[0, 1 + np.flatnonzero((il[1:] != il[:-1]) | (cp[1:] != cp[:-1]))]
        ends = np.r_[starts[1:], len(cp)]
        self.ranges = {(int(il[a]), int(cp[a])): (int(a), int(b)) for a, b in zip(starts, ends)}
        self.lines = {}
        for line, c in self.ranges:
            self.lines.setdefault(line, []).append(c)

    def keys(self, inline=None, cdp_min=None, cdp_max=None):
        return [k for k in self.ranges if (inline is None or k[0] == inline)
                and (cdp_min is None or k[1] >= cdp_min) and (cdp_max is None or k[1] <= cdp_max)]

    def select(self, inline, cdp, size=1, offset_factor=1.0, min_offset_m=0, max_offset_m=None):
        if not isinstance(size, int) or size < 1 or size % 2 == 0:
            raise ValueError('Supergather size must be a positive odd integer')
        if not np.isfinite(offset_factor) or offset_factor <= 0 or min_offset_m < 0 or (max_offset_m is not None and max_offset_m < min_offset_m):
            raise ValueError('Invalid offset geometry or aperture')
        line = self.lines.get(inline, [])
        pos = int(np.searchsorted(line, cdp))
        if pos == len(line) or line[pos] != cdp:
            raise KeyError(f'No CMP ({inline}, {cdp})')
        members = tuple((inline, c) for c in line[max(0, pos-size//2):pos+size//2+1])
        arrays = [self.order[s:e] for s,e in (self.ranges[k] for k in members)]
        ids = np.concatenate(arrays)
        offsets = np.abs(self.offsets[ids] * offset_factor)
        live = offsets >= min_offset_m
        if max_offset_m is not None:
            live &= offsets <= max_offset_m
        ids = ids[live]
        ids = ids[np.argsort(self.offsets[ids], kind='stable')]
        return GatherSelection(ids, members)
