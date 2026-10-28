"""Trace-wise band-limited envelope suppression following the SUPPRES manual.

This is an independent implementation of the described method. It does not
claim sample-for-sample compatibility with a proprietary executable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from numbers import Integral
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import fft, ndimage, signal

from .config import SuppresConfig, finite_number
from .gates import GateTable, gate_weights


@dataclass
class SuppresResult:
    """Output and QC arrays, all with the same layout as the input.

    ``gain`` is the unconstrained-by-gates suppression control;
    ``effective_gain`` includes the application gate and its tapers.
    The envelopes are smoothed input-component envelopes, not remeasured
    envelopes of the modulated output. ``removed`` is input minus the actual
    returned (possibly float32) output.
    """

    data: NDArray
    noise: NDArray
    signal: NDArray
    noise_envelope: NDArray
    signal_envelope: NDArray
    gain: NDArray
    effective_gain: NDArray
    gate_weight: NDArray
    removed: NDArray
    metadata: dict[str, Any]


def butterworth_response(frequencies_hz: ArrayLike, fbeg_hz: float = 3.0,
                         fend_hz: float = 18.0) -> NDArray[np.float64]:
    """Return manual p. 4's *amplitude* response, using orders 3 and 6.

    A(f) = [(1 + (FBEG/|f|)^6) (1 + (|f|/FEND)^12)]**(-1/2).
    FBEG=0 omits the high-pass factor and passes DC. Log-domain evaluation
    avoids overflowing powers for extreme frequency ratios. No peak
    normalization is applied. Negative input frequencies are supported.
    """
    lo, hi = finite_number(fbeg_hz, "fbeg_hz"), finite_number(fend_hz, "fend_hz")
    if lo < 0 or hi <= 0 or lo > hi:
        raise ValueError("Require 0 <= fbeg_hz <= fend_hz and fend_hz > 0")
    raw = np.asarray(frequencies_hz)
    if raw.dtype.kind not in "iuf" or not np.all(np.isfinite(raw)):
        raise ValueError("frequencies_hz must be finite real numeric values")
    freq = np.abs(raw.astype(np.float64))
    with np.errstate(divide="ignore", under="ignore"):
        logf = np.log(freq)
        logden = np.logaddexp(0.0, 12.0 * (logf - math.log(hi)))
        if lo > 0:
            logden = logden + np.logaddexp(0.0, 6.0 * (math.log(lo) - logf))
        result = np.exp(-0.5 * logden)
    return result


def _window(config: SuppresConfig, dt_ms: float) -> NDArray[np.float64]:
    # Choose the nearest ODD number of samples; exact even-width ties round up.
    count = max(1, 2 * int(math.floor(config.tsmt_ms / dt_ms / 2.0)) + 1)
    if config.smoothing == "boxcar":
        return np.full(count, 1.0 / count)
    # An interior Hann has nonzero endpoints, including meaningful 3-point
    # windows. Its definition is sin(pi*(j+1)/(count+1))**2, normalized to1.
    weights = np.hanning(count + 2)[1:-1]
    return weights / weights.sum()


def _padding_samples(config: SuppresConfig, dt_ms: float, n: int) -> int:
    if config.padding == "periodic":
        return 0
    # At most one trace minus one sample per edge, avoiding pathological
    # allocations for extremely low cutoffs. See diagnostics for actual size.
    duration_ms = (n - 1) * dt_ms
    if config.pad_ms is None:
        corner = config.fbeg_hz if config.fbeg_hz > 0 else config.fend_hz
        # Compare before dividing so tiny finite corner frequencies are safe.
        if corner <= 3000.0 / duration_ms:
            return n - 1
        requested = max(3000.0 / corner, config.tsmt_ms)
    else:
        requested = config.pad_ms
    return min(n - 1, int(math.ceil(min(requested, duration_ms) / dt_ms)))


def _smooth(envelope: NDArray, window: NDArray, config: SuppresConfig) -> NDArray:
    if window.size == 1:
        return envelope
    mode = {"reflect": "mirror", "zero": "constant", "periodic": "wrap"}[config.padding]
    if config.smoothing == "boxcar":
        smooth = ndimage.uniform_filter1d(envelope, window.size, axis=-1, mode=mode)
    elif window.size <= 129:
        smooth = ndimage.convolve1d(envelope, window, axis=-1, mode=mode)
    else:
        half = window.size // 2
        pad_mode = {"reflect": "reflect", "zero": "constant", "periodic": "wrap"}[config.padding]
        padded = np.pad(envelope, ((0, 0), (half, half)), mode=pad_mode)
        smooth = signal.fftconvolve(padded, window[None, :], mode="valid", axes=-1)
    # Roundoff in cumulative sums / FFT convolution can yield tiny negatives.
    return np.maximum(smooth, 0.0)


def _restore(array: NDArray, trace_shape: tuple[int, ...], n: int, axis: int) -> NDArray:
    return np.moveaxis(array.reshape(trace_shape + (n,)), -1, axis)


def process(data: ArrayLike, dt_ms: float, *, config: SuppresConfig | None = None,
            headers: Mapping[str, ArrayLike] | None = None, gates: GateTable | None = None,
            t0_ms: float = 0.0, axis: int = -1, batch_size: int = 64,
            return_diagnostics: bool = False) -> NDArray | SuppresResult:
    """Suppress a noise band on one trace, a gather, or an N-D trace collection.

    Parameters
    ----------
    data:
        Finite real values. Default shape is (..., time). Input is never changed.
        Float32 stays float32; float16 becomes float32; integers become float64.
    dt_ms, t0_ms:
        Common sample interval and first-sample time in milliseconds.
    headers:
        A mapping keyed by config.pkeynam/config.skeynam. Required only with
        gates; values must broadcast to the shape with the time axis removed.
    gates:
        A GateTable. Without gates, all samples are eligible for processing.
    batch_size:
        Number of traces in a work batch. All samples of each trace are
        processed together; time-domain chunks are not interchangeable.
    return_diagnostics:
        Allocate and return full QC arrays. False minimizes retained memory.

    Notes
    -----
    The filter is a zero-phase real-FFT magnitude multiplier. Padding,
    smoothing, and interpolation are explicit implementation choices because
    the manual does not specify them. Strict TSMT limits use trace duration
    (n_samples-1)*dt_ms. No global demeaning, AGC, or amplitude normalization
    remains in the output: internal per-trace scaling only prevents overflow.
    """
    config = SuppresConfig() if config is None else config
    if not isinstance(config, SuppresConfig):
        raise TypeError("config must be a SuppresConfig")
    raw = np.asarray(data)
    if raw.ndim < 1 or raw.dtype.kind not in "iuf" or raw.dtype.itemsize > 8:
        raise TypeError("data must be a real numeric array (integer, float16/32/64), with at least one dimension")
    if not np.all(np.isfinite(raw)):
        raise ValueError("data contains NaN or infinity; repair or mask invalid samples before processing")
    if isinstance(axis, bool) or not isinstance(axis, Integral) or not -raw.ndim <= axis < raw.ndim:
        raise ValueError("axis must identify a valid time axis")
    axis = int(axis) % raw.ndim
    if isinstance(batch_size, bool) or not isinstance(batch_size, Integral) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    dt_ms, t0_ms = finite_number(dt_ms, "dt_ms"), finite_number(t0_ms, "t0_ms")
    moved = np.moveaxis(raw, axis, -1)
    trace_shape, n = moved.shape[:-1], moved.shape[-1]
    if any(size == 0 for size in trace_shape):
        raise ValueError("Empty trace collections are not supported")
    config.validate_sampling(dt_ms, n)
    trace_end = t0_ms + (n - 1) * dt_ms
    if not math.isfinite(trace_end) or trace_end <= t0_ms:
        raise ValueError("Trace time range is not representable; check t0_ms and dt_ms")
    flat = moved.reshape(-1, n)
    n_traces = flat.shape[0]
    if gates is not None:
        if not isinstance(gates, GateTable):
            raise TypeError("gates must be a GateTable or None")
        if not isinstance(headers, Mapping):
            raise ValueError("headers are required when gates are supplied")
        missing = [key for key in (config.pkeynam, config.skeynam) if key not in headers]
        if missing:
            raise ValueError(f"Missing gate header(s): {', '.join(missing)}")
        try:
            primary = np.broadcast_to(np.asarray(headers[config.pkeynam]), trace_shape)
            secondary = np.broadcast_to(np.asarray(headers[config.skeynam]), trace_shape)
        except ValueError as exc:
            raise ValueError(f"Gate headers must broadcast to trace shape {trace_shape}") from exc
        begins, ends = gates.evaluate(primary, secondary, trace_start_ms=t0_ms, trace_end_ms=trace_end)
        begins, ends = begins.reshape(-1), ends.reshape(-1)
    output_dtype = np.float32 if raw.dtype.kind == "f" and raw.dtype.itemsize <= 4 else np.float64
    output = np.empty((n_traces, n), dtype=output_dtype)
    fields = ("noise", "signal", "noise_envelope", "signal_envelope", "gain",
              "effective_gain", "gate_weight", "removed")
    diagnostics = {key: np.empty((n_traces, n), dtype=np.float64) for key in fields} if return_diagnostics else {}
    pad = _padding_samples(config, dt_ms, n)
    n_fft = n + 2 * pad
    response = butterworth_response(fft.rfftfreq(n_fft, d=dt_ms / 1000.0), config.fbeg_hz, config.fend_hz)
    window = _window(config, dt_ms)
    times = t0_ms + np.arange(n, dtype=np.float64) * dt_ms
    crop = slice(pad, pad + n)
    for start in range(0, n_traces, int(batch_size)):
        stop = min(start + int(batch_size), n_traces)
        original = flat[start:stop].astype(np.float64)
        scale = np.max(np.abs(original), axis=-1, keepdims=True)
        scale[scale == 0] = 1.0
        normalized = original / scale
        if pad:
            pad_mode = "reflect" if config.padding == "reflect" else "constant"
            extended = np.pad(normalized, ((0, 0), (pad, pad)), mode=pad_mode)
        else:
            extended = normalized
        noise_extended = fft.irfft(fft.rfft(extended, axis=-1) * response, n=n_fft, axis=-1)
        signal_extended = extended - noise_extended
        en = _smooth(np.abs(signal.hilbert(noise_extended, axis=-1)), window, config)[:, crop]
        es = _smooth(np.abs(signal.hilbert(signal_extended, axis=-1)), window, config)[:, crop]
        gain = np.ones_like(en)
        # Infinite positive ratios simply mean no attenuation. Zero envelope
        # keeps gain1, including entirely dead traces; no absolute epsilon
        # compromises invariance under a change in seismic amplitude units.
        with np.errstate(over="ignore", divide="ignore", invalid="raise", under="ignore"):
            np.divide(config.factor * es, en, out=gain, where=en > 0)
        np.clip(gain, 0.0, 1.0, out=gain)
        weight = np.ones_like(gain) if gates is None else gate_weights(times, begins[start:stop], ends[start:stop], config.taper_ms)
        attenuation = weight * (1.0 - gain)
        noise_normalized = noise_extended[:, crop]
        normalized_out = normalized - attenuation * noise_normalized
        with np.errstate(over="raise", invalid="raise", under="ignore"):
            try:
                result = (normalized_out * scale).astype(output_dtype)
            except FloatingPointError as exc:
                raise FloatingPointError("Output exceeds its floating-point range; rescale input amplitudes or use float64") from exc
        # Copy inactive samples exactly, including outside every gate/taper.
        np.copyto(result, flat[start:stop], where=attenuation == 0, casting="unsafe")
        output[start:stop] = result
        if return_diagnostics:
            with np.errstate(over="raise", invalid="raise", under="ignore"):
                physical_noise = noise_normalized * scale
                diagnostics["noise"][start:stop] = physical_noise
                diagnostics["signal"][start:stop] = original - physical_noise
                diagnostics["noise_envelope"][start:stop] = en * scale
                diagnostics["signal_envelope"][start:stop] = es * scale
                diagnostics["removed"][start:stop] = original - result.astype(np.float64)
            diagnostics["gain"][start:stop] = gain
            diagnostics["effective_gain"][start:stop] = 1.0 - attenuation
            diagnostics["gate_weight"][start:stop] = weight
    final = _restore(output, trace_shape, n, axis)
    if not return_diagnostics:
        return final
    metadata = {
        "algorithm": "SUPPRES manual-based independent implementation",
        "config": asdict(config), "dt_ms": dt_ms, "t0_ms": t0_ms,
        "n_samples": n, "n_traces": n_traces, "time_axis": axis,
        "padding_samples_per_side": pad, "fft_samples": n_fft,
        "smoothing_samples": int(window.size),
        "smoothing_sample_span_ms": float((window.size - 1) * dt_ms),
        "factor_definition": "threshold = factor * smoothed signal envelope",
        "interpolation": "linear secondary then primary; constant endpoint extrapolation",
        "output_dtype": str(final.dtype),
    }
    restored = {key: _restore(value, trace_shape, n, axis) for key, value in diagnostics.items()}
    return SuppresResult(data=final, metadata=metadata, **restored)

