"""Amplitude median filtering with an explicit finite-record frequency band.

The Fourier coefficients outside the requested interval are copied unchanged
before synthesis. The returned samples preserve them within floating-point
reconstruction and optional output-encoding tolerance. No time padding,
cropping, windowing, or independent per-trace amplitude normalization is used.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import fft

from .config import AmpMedianConfig, finite_number, positive_integer
from .neighbors import contiguous_groups, lateral_median


@dataclass
class AmpMedianResult:
    """Processed samples and QC.

    Time arrays follow the input shape. ``frequencies_hz`` and ``band_weights``
    describe its entire real-FFT grid. Spectral ``median_reference`` contains
    magnitudes only at bins where ``band_weights > 0`` (forward-normalized
    Fourier coefficients in original amplitude units). In waveform mode it
    contains the signed time-sample median, before final band projection.
    Neighbor counts and the effective live mask always have one entry per
    trace, including when the input was a one-dimensional single trace.
    """

    data: NDArray
    removed: NDArray
    band_input: NDArray
    band_output: NDArray
    median_reference: NDArray
    frequencies_hz: NDArray
    band_weights: NDArray
    donor_counts: NDArray
    live_mask: NDArray
    metadata: dict[str, Any]


def band_weights(frequencies_hz: ArrayLike, fmin_hz: float, fmax_hz: float,
                 transition_hz: float = 0.0) -> NDArray[np.float64]:
    """Make a frequency selector; any cosine taper is wholly inside the band.

    A zero transition gives inclusive rectangular selection. A positive
    transition ramps the correction from0 to1 above fmin and from1 to0 below
    fmax. Bin centers outside the requested interval always have weight0.
    """
    fmin = finite_number(fmin_hz, "fmin_hz")
    fmax = finite_number(fmax_hz, "fmax_hz")
    transition = finite_number(transition_hz, "transition_hz")
    if not 0 <= fmin < fmax:
        raise ValueError("Require 0 <= fmin_hz < fmax_hz")
    if transition < 0 or transition > (fmax - fmin) / 2:
        raise ValueError("transition_hz must lie between0 and half the band width")
    raw = np.asarray(frequencies_hz)
    if raw.ndim != 1 or raw.size == 0 or raw.dtype.kind not in "iuf" or not np.isfinite(raw).all():
        raise ValueError("frequencies_hz must be a nonempty finite real one-dimensional array")
    freq = raw.astype(np.float64)
    if np.any(freq < 0) or np.any(np.diff(freq) <= 0):
        raise ValueError("frequencies_hz must be nonnegative and strictly increasing")
    selected = (freq >= fmin) & (freq <= fmax)
    result = selected.astype(np.float64)
    if transition > 0:
        lower = selected & (freq < fmin + transition)
        upper = selected & (freq > fmax - transition)
        result[lower] = 0.5 * (1.0 - np.cos(np.pi * (freq[lower] - fmin) / transition))
        result[upper] = 0.5 * (1.0 - np.cos(np.pi * (fmax - freq[upper]) / transition))
        np.clip(result, 0.0, 1.0, out=result)
    return result


def _array(data: ArrayLike) -> tuple[NDArray, bool]:
    raw = np.asarray(data)
    if raw.ndim not in (1, 2) or any(size == 0 for size in raw.shape):
        raise ValueError("data must be a nonempty trace or a 2D (traces, samples) array")
    if raw.dtype.kind not in "iuf" or raw.dtype.itemsize > 8:
        raise TypeError("data must contain real integer or float16/32/64 samples")
    if not np.isfinite(raw).all():
        raise ValueError("data contains NaN or infinity; repair invalid samples before processing")
    return (raw[None, :] if raw.ndim == 1 else raw), raw.ndim == 1


def _live_mask(raw: NDArray, live_mask: ArrayLike | None, exclude_dead: bool) -> NDArray:
    if live_mask is None:
        live = np.ones(raw.shape[0], dtype=bool)
    else:
        live = np.asarray(live_mask)
        if live.dtype.kind != "b" or live.shape != (raw.shape[0],):
            raise ValueError("live_mask must be a boolean array with one entry per trace")
        live = live.copy()
    if exclude_dead:
        live &= np.any(raw != 0, axis=-1)
    return live


def _restore(array: NDArray, single_trace: bool) -> NDArray:
    return array[0] if single_trace else array


def process(data: ArrayLike, dt_ms: float, *, config: AmpMedianConfig | None = None,
            group_ids: ArrayLike | None = None, live_mask: ArrayLike | None = None,
            feature_batch_size: int = 8192,
            return_diagnostics: bool = False) -> NDArray | AmpMedianResult:
    """Filter a requested band using neighboring trace amplitudes.

    The default compares full-record Fourier magnitudes and preserves each
    trace's original phase. ``spectral_clip`` only attenuates magnitudes above
    ``threshold * neighboring_median``. ``waveform_median`` filters signed
    samples of the isolated band and projects its correction back into that
    band, since a nonlinear median can generate additional frequencies.

    ``group_ids`` partitions CONTIGUOUS runs in input order; neighbors never
    cross those boundaries. The trace window includes the target; at edges it
    shifts inward by default, or clips with edge='shrink'. Windows in short
    groups use the available positions. Masked/dead traces reduce the donor
    count without expanding the window and remain unchanged. The API never
    sorts or modifies the input array.

    Frequency precision is the original-record spacing 1000/(N*dt_ms) Hz.
    No temporal padding or cropping is used. Float64 output is the default;
    float32 output adds quantization error, including outside the band.
    """
    config = AmpMedianConfig() if config is None else config
    if not isinstance(config, AmpMedianConfig):
        raise TypeError("config must be an AmpMedianConfig")
    feature_batch_size = positive_integer(feature_batch_size, "feature_batch_size")
    raw, single_trace = _array(data)
    n_traces, n_samples = raw.shape
    dt_ms = finite_number(dt_ms, "dt_ms")
    config.validate_sampling(dt_ms, n_samples)
    groups = contiguous_groups(n_traces, group_ids)
    live = _live_mask(raw, live_mask, config.exclude_dead)
    frequencies = fft.rfftfreq(n_samples, d=dt_ms / 1000.0)
    weights = band_weights(frequencies, config.fmin_hz, config.fmax_hz, config.transition_hz)
    requested = (frequencies >= config.fmin_hz) & (frequencies <= config.fmax_hz)
    active = weights > 0
    if not np.any(active):
        spacing = 1000.0 / (n_samples * dt_ms)
        raise ValueError(f"Requested band contains no nonzero-weight FFT bins (spacing {spacing:g} Hz); widen the band, reduce transition_hz, or use a longer record")
    original = raw.astype(np.float64)
    normalized = original.copy()
    scales = np.ones((n_traces, 1), dtype=np.float64)
    for begin, end in groups:
        scale = np.max(np.abs(original[begin:end]))
        if scale != 0:
            normalized[begin:end] /= scale
            scales[begin:end] = scale
    # A common scale within each group preserves the relative amplitudes on
    # which the lateral median depends. Per-trace normalization would not.
    spectrum = fft.rfft(normalized, n=n_samples, axis=-1, norm="forward")
    corrected = spectrum.copy()
    if config.mode in ("spectral_median", "spectral_clip"):
        coefficients = spectrum[:, active]
        amplitude = np.abs(coefficients)
        reference, counts = lateral_median(
            amplitude, config.n_traces, group_ids=group_ids, live_mask=live,
            edge=config.edge, feature_batch_size=feature_batch_size,
        )
        if config.mode == "spectral_clip":
            with np.errstate(over="ignore"):
                target_amplitude = np.minimum(amplitude, config.threshold * reference)
        else:
            target_amplitude = reference.copy()
            if config.max_gain is not None:
                with np.errstate(over="ignore"):
                    target_amplitude = np.minimum(target_amplitude, config.max_gain * amplitude)
        # A zero coefficient has no original phase to retain. Do not invent
        # one. Excluded targets stay unchanged independently of donor policy.
        target_amplitude[amplitude == 0] = 0.0
        target_amplitude[~live] = amplitude[~live]
        different = target_amplitude != amplitude
        target = coefficients.copy()
        if np.any(different):
            # Compute unit phase first: target/amplitude can overflow when a
            # finite target replaces a subnormal Fourier magnitude.
            # Divide real components separately: complex division can form
            # an overflowing reciprocal for a subnormal real denominator.
            unit_real = coefficients.real[different] / amplitude[different]
            unit_imag = coefficients.imag[different] / amplitude[different]
            target[different] = (unit_real + 1j * unit_imag) * target_amplitude[different]
        delta = config.strength * weights[active][None, :] * (target - coefficients)
        corrected[:, active] = coefficients + delta
    else:
        band_spectrum = np.zeros_like(spectrum)
        # Analyze the whole inclusive requested band. The transition taper
        # weights only the final correction, never the median reference.
        band_spectrum[:, requested] = spectrum[:, requested]
        band = fft.irfft(band_spectrum, n=n_samples, axis=-1, norm="forward")
        reference, counts = lateral_median(
            band, config.n_traces, group_ids=group_ids, live_mask=live,
            edge=config.edge, feature_batch_size=feature_batch_size,
        )
        candidate_delta = reference - band
        candidate_delta[~live] = 0.0
        delta_spectrum = fft.rfft(candidate_delta, n=n_samples, axis=-1, norm="forward")
        delta = config.strength * weights[active][None, :] * delta_spectrum[:, active]
        corrected[:, active] = spectrum[:, active] + delta
    changed = np.any(delta != 0, axis=-1)
    reconstructed = fft.irfft(corrected, n=n_samples, axis=-1, norm="forward")
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        try:
            output = (reconstructed * scales).astype(config.output_dtype)
        except FloatingPointError as exc:
            raise FloatingPointError("Output exceeds its dtype range; rescale all traces together or request float64 output") from exc
    # Exact identity in no-op cases and exact unchanged excluded/dead traces,
    # apart from an explicitly requested lower-precision dtype conversion.
    output[~changed] = raw[~changed]
    if not return_diagnostics:
        return _restore(output, single_trace)
    actual_spectrum = fft.rfft(output.astype(np.float64) / scales,
                               n=n_samples, axis=-1, norm="forward")
    input_band_spectrum = np.zeros_like(spectrum)
    output_band_spectrum = np.zeros_like(spectrum)
    input_band_spectrum[:, requested] = spectrum[:, requested]
    output_band_spectrum[:, requested] = actual_spectrum[:, requested]
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        band_input = fft.irfft(input_band_spectrum, n=n_samples, axis=-1, norm="forward") * scales
        band_output = fft.irfft(output_band_spectrum, n=n_samples, axis=-1, norm="forward") * scales
        median_reference = reference * scales
        removed = original - output.astype(np.float64)
    outside_requested = (frequencies < config.fmin_hz) | (frequencies > config.fmax_hz)
    differences = np.abs(actual_spectrum - spectrum)
    peak = np.max(np.abs(spectrum), axis=-1)
    if np.any(outside_requested):
        outside_per_trace = np.max(differences[:, outside_requested], axis=-1)
        normalized_error = float(np.max(outside_per_trace))
        relative_error = np.zeros(n_traces)
        np.divide(outside_per_trace, peak, out=relative_error, where=peak > 0)
        relative_error = float(np.max(relative_error))
    else:
        normalized_error, relative_error = 0.0, 0.0
    metadata = {
        "algorithm": "Frequency-selective lateral amplitude median",
        "version": "1.0.0", "config": asdict(config), "dt_ms": dt_ms,
        "trace_count": n_traces, "sample_count": n_samples,
        "fft_samples": n_samples, "fft_normalization": "forward",
        "frequency_spacing_hz": float(1000.0 / (n_samples * dt_ms)),
        "first_active_frequency_hz": float(frequencies[active][0]),
        "last_active_frequency_hz": float(frequencies[active][-1]),
        "active_frequency_bins": int(np.count_nonzero(active)),
        "out_of_band_frequency_bins": int(np.count_nonzero(outside_requested)),
        "reference_domain": "time" if config.mode == "waveform_median" else "frequency",
        "reference_definition": "median before cap, strength, and frequency taper; forward-normalized magnitude in spectral modes",
        "group_count": len(groups),
        "short_group_count": sum(end - begin < config.n_traces for begin, end in groups),
        "live_trace_count": int(np.count_nonzero(live)),
        "changed_trace_count": int(np.count_nonzero(changed)),
        "minimum_donor_count": int(np.min(counts[live])) if live.any() else 0,
        "maximum_donor_count": int(np.max(counts)) if counts.size else 0,
        "max_out_of_band_change_normalized_by_group_peak": normalized_error,
        "max_out_of_band_change_relative_to_trace_spectrum_peak": relative_error,
        "output_dtype": str(output.dtype),
        "frequency_contract": "Only original-record FFT-bin centers inside the requested interval are modified before synthesis; returned samples include numerical and dtype roundoff",
    }
    return AmpMedianResult(
        data=_restore(output, single_trace), removed=_restore(removed, single_trace),
        band_input=_restore(band_input, single_trace), band_output=_restore(band_output, single_trace),
        median_reference=_restore(median_reference, single_trace),
        frequencies_hz=frequencies, band_weights=weights, donor_counts=counts,
        live_mask=live, metadata=metadata,
    )

