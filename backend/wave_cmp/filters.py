"""Blockwise O(N) RMS AGC and vectorized FFT bandpass; no process copies."""
import numpy as np
from scipy.fft import rfft, irfft, rfftfreq
from .semblance import window_sum
from .schemas import BandpassParams


def agc(data, dt_ms, window_ms, *, block_traces=64, check_cancel=lambda: None):
    a = np.asarray(data)
    if a.ndim != 2 or min(a.shape)<1 or dt_ms<=0 or window_ms<=0 or not np.isfinite([dt_ms, window_ms]).all():
        raise ValueError('Nonempty matrix, positive dt_ms and window_ms required')
    if block_traces < 1:
        raise ValueError('block_traces must be positive')
    # Matches the legacy odd window and clipped-edge normalization.
    n = max(1, int(window_ms/dt_ms))
    half = (n + (1 if n%2 == 0 else 0)) // 2
    positions = np.arange(a.shape[1])
    count = np.minimum(positions+half+1,a.shape[1]) - np.maximum(positions-half,0)
    out = np.empty(a.shape, dtype=np.float32)
    for first in range(0,len(a),block_traces):
        check_cancel()
        x = np.asarray(a[first:first+block_traces], dtype=np.float64)
        if not np.isfinite(x).all():
            raise ValueError('AGC requires finite samples; repair or mask invalid data before filtering')
        energy = np.maximum(window_sum(x*x,half), 0)
        out[first:first+len(x)] = x / (np.sqrt(energy/count) + 1e-10)
    return out


def bandpass(data, dt_ms, params: BandpassParams, *, block_traces=64, workers=1, check_cancel=lambda: None):
    a = np.asarray(data)
    if a.ndim != 2 or min(a.shape)<1 or not np.isfinite(dt_ms) or dt_ms<=0 or block_traces<1:
        raise ValueError('Invalid bandpass input')
    nyquist = 500/dt_ms
    if params.highcut > nyquist:
        raise ValueError(f'highcut exceeds Nyquist ({nyquist:g} Hz)')
    freqs = rfftfreq(a.shape[1], dt_ms/1000)
    mask = np.interp(freqs, [params.lowcut,params.lowpass,params.highpass,params.highcut], [0,1,1,0], left=0,right=0)
    out = np.empty(a.shape,dtype=np.float32)
    for first in range(0,len(a),block_traces):
        check_cancel()
        x = np.asarray(a[first:first+block_traces],dtype=np.float32)
        if not np.isfinite(x).all():
            raise ValueError('Bandpass requires finite samples')
        spectrum = rfft(x,axis=1,workers=workers)
        spectrum *= mask[None,:]
        out[first:first+len(x)] = irfft(spectrum,n=a.shape[1],axis=1,workers=workers)
    return out
