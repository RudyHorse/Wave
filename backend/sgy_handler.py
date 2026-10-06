import numpy as np
import segyio
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile
import os
import concurrent.futures
import hashlib
from scipy.linalg import solve_toeplitz
from scipy.fft import fftn, ifftn, fftfreq, fftshift, ifftshift
from scipy.signal import windows as scipy_windows
from enum import Enum
from database import save_file_meta, list_files as db_list_files, get_file_meta, delete_file_meta, find_by_hash
from storage import save_data, load_data, save_inline_xline, load_inline_xline, save_cdp_offset, load_cdp_offset, save_ffid_offset, load_ffid_offset, save_ffid_chan, load_ffid_chan, save_processed, load_processed, delete_all as delete_storage, file_exists as storage_file_exists, data_path as storage_data_path
from fkfilter import FKVelocityFilter


_GAIN_VELOCITY_FEET = np.array([
    [0.0, 5000.0], [100.0, 5000.0], [700.0, 6314.0], [1000.0, 7166.0],
    [1400.0, 7676.0], [1800.0, 8780.0], [1950.0, 9480.0], [4200.0, 11700.0],
    [7000.0, 15700.0]
])

_GAIN_VELOCITY_METERS = np.array([
    [0.0, 1524.0], [100.0, 1524.0], [700.0, 1924.5], [1000.0, 2184.0],
    [1400.0, 2339.6], [1800.0, 2676.0], [1950.0, 2889.5], [4200.0, 3566.0],
    [7000.0, 4785.3]
])

_DSIN_SAMPLE_RATES = (0.5, 1.0, 2.0, 4.0, 8.0)


def _resample_traces(data: np.ndarray, orig_dt: float, new_dt: float) -> np.ndarray:
    if abs(orig_dt - new_dt) < 1e-9:
        return data
    n = data.shape[1]
    t_orig = np.arange(n, dtype=np.float64) * orig_dt
    new_n = max(1, int(round(n * orig_dt / new_dt)))
    t_new = np.arange(new_n, dtype=np.float64) * new_dt
    frac = t_new / orig_dt
    i0 = np.floor(frac).astype(int)
    w = (frac - i0).astype(np.float32)
    i0 = np.clip(i0, 0, n - 1)
    i1 = np.clip(i0 + 1, 0, n - 1)
    return (data[:, i0] * (1.0 - w) + data[:, i1] * w).astype(np.float32)


class CancelledError(Exception):
    pass


def _agc_chunk_worker(traces, window_samples, half, epsilon):
    num_traces, num_samples = traces.shape
    result = np.zeros_like(traces, dtype=np.float32)
    for t in range(num_traces):
        trace = traces[t]
        for i in range(num_samples):
            start = max(0, i - half)
            end = min(num_samples, i + half + 1)
            rms = np.sqrt(np.mean(trace[start:end] ** 2))
            result[t, i] = trace[i] / (rms + epsilon)
    return result


def _bandpass_chunk_worker(traces, mask):
    num_traces = traces.shape[0]
    result = np.zeros_like(traces, dtype=np.float32)
    for t in range(num_traces):
        spectrum = np.fft.rfft(traces[t])
        spectrum *= mask
        result[t] = np.fft.irfft(spectrum, n=traces.shape[1]).real
    return result


def _fxdecon_chunk_worker(fw_chunk, ntraces, P, tol, start_k):
    nfreqs = fw_chunk.shape[1]
    out = np.zeros_like(fw_chunk, dtype=np.complex128)
    for ki in range(nfreqs):
        k = start_k + ki
        x = fw_chunk[:, ki]
        if k == 0:
            out[:, ki] = x
            continue
        r = np.zeros(P + 1, dtype=np.complex128)
        for lag in range(P + 1):
            r[lag] = np.vdot(x[lag:], x[:ntraces - lag]) / ntraces
        if abs(r[0]) < tol:
            out[:, ki] = x
            continue
        r[0] *= 1.001
        a = np.zeros(P, dtype=np.complex128)
        E = r[0].real
        for i in range(P):
            rc = -r[i + 1]
            for j in range(i):
                rc -= a[j] * r[i - j]
            rc /= E
            anew = np.zeros(i + 1, dtype=np.complex128)
            anew[-1] = rc
            for j in range(i):
                anew[j] = a[j] + rc * np.conj(a[i - j - 1])
            a = anew
            E *= (1.0 - rc.real ** 2 - rc.imag ** 2)
        yf = np.zeros(ntraces, dtype=np.complex128)
        yf[:P] = x[:P]
        for n in range(P, ntraces):
            yf[n] = -np.dot(a, x[n - P:n][::-1])
        yb = np.zeros(ntraces, dtype=np.complex128)
        yb[-P:] = x[-P:]
        for n in range(ntraces - P - 1, -1, -1):
            yb[n] = -np.dot(np.conj(a), x[n + 1:n + P + 1])
        out[:, ki] = 0.5 * (yf + yb)
    return out


def _fxdecont_chunk_worker(spec_chunk, n_traces, pred_order, retro_order, reg, window_size, step, nonlinear_plus, start_freq, freq_mask):
    n_freqs = spec_chunk.shape[1]
    out = np.zeros_like(spec_chunk, dtype=np.complex64)
    for ki in range(n_freqs):
        if not freq_mask[start_freq + ki]:
            out[:, ki] = spec_chunk[:, ki]
            continue
        for center in range(0, n_traces, step):
            start = max(0, center - window_size // 2)
            end = min(n_traces, center + window_size // 2)
            if end - start < max(pred_order, retro_order) + 1:
                out[center, ki] = spec_chunk[center, ki]
                continue
            x = spec_chunk[start:end, ki]
            if pred_order > 0 and len(x) > pred_order:
                r = np.correlate(x, x, mode='full')[len(x) - 1:]
                r = r / r[0]
                r[0] += reg * r[0]
                try:
                    a = solve_toeplitz(r[:pred_order], r[1:pred_order + 1])
                except Exception:
                    a = np.zeros(pred_order, dtype=np.complex64)
                if center >= pred_order:
                    past = spec_chunk[center - pred_order:center, ki][::-1]
                    pred_forward = np.dot(a, past)
                else:
                    pred_forward = x[center - start] if 0 <= center - start < len(x) else 0
            else:
                pred_forward = x[center - start] if 0 <= center - start < len(x) else 0
            if retro_order > 0 and len(x) > retro_order:
                x_rev = x[::-1]
                r_rev = np.correlate(x_rev, x_rev, mode='full')[len(x_rev) - 1:]
                r_rev = r_rev / r_rev[0]
                r_rev[0] += reg * r_rev[0]
                try:
                    b = solve_toeplitz(r_rev[:retro_order], r_rev[1:retro_order + 1])
                except Exception:
                    b = np.zeros(retro_order, dtype=np.complex64)
                if n_traces - center - 1 >= retro_order:
                    future = spec_chunk[center + 1:center + retro_order + 1, ki]
                    pred_backward = np.dot(b, future)
                else:
                    pred_backward = x[center - start] if 0 <= center - start < len(x) else 0
            else:
                pred_backward = x[center - start] if 0 <= center - start < len(x) else 0
            orig_val = spec_chunk[center, ki]
            if nonlinear_plus:
                err_f = np.abs(orig_val - pred_forward) if pred_order > 0 else np.inf
                err_b = np.abs(orig_val - pred_backward) if retro_order > 0 else np.inf
                out[center, ki] = pred_forward if err_f < err_b else pred_backward
            else:
                out[center, ki] = (pred_forward + pred_backward) * 0.5
    return out


class PassRejectType(Enum):
    PASS = 'PASS'
    REJECT = 'REJECT'


class FilterShape(Enum):
    ELLIPSES = 'ELLIPSES'
    RECTANGLES = 'RECTANGLES'


def _cosine_taper_dip(r, r1, r2):
    taper = np.ones_like(r)
    mask = (r > r1) & (r < r2)
    rn = (r2 - r[mask]) / (r2 - r1)
    taper[mask] = 1 - 0.5 * (1 + np.cos(np.pi * rn))
    taper[r >= r2] = 0.0
    return taper


def _normalized_radial_distance(kx, ky, k0x, k0y, h1x, h1y):
    return np.sqrt(((kx - k0x) / h1x)**2 + ((ky - k0y) / h1y)**2)


class FKFilter3D:
    def __init__(self, sampling_interval, inline_interval=1.0, xline_interval=1.0):
        self.sampling_interval = sampling_interval
        self.inline_interval = inline_interval
        self.xline_interval = xline_interval
        self.min_freq = 0.0
        self.max_freq = None

    def _create_windows(self, nx, ny, wndw_inline, wndw_xline, overlap_inline, overlap_xline):
        xstarts = list(range(0, nx - wndw_inline + 1, wndw_inline - overlap_inline))
        ystarts = list(range(0, ny - wndw_xline + 1, wndw_xline - overlap_xline))
        windows = []
        for xs in xstarts:
            for ys in ystarts:
                windows.append((slice(xs, xs + wndw_inline), slice(ys, ys + wndw_xline)))
        return windows

    def _apply_taper(self, data_window):
        nt, nx, ny = data_window.shape
        tw = scipy_windows.hann(nt, sym=False).reshape(-1, 1, 1)
        xw = scipy_windows.hann(nx, sym=False).reshape(1, -1, 1)
        yw = scipy_windows.hann(ny, sym=False).reshape(1, 1, -1)
        return data_window * tw * xw * yw

    def _create_dip_filter(self, kx, ky, freq, min_dip_inline, max_dip_inline,
                            min_dip_xline, max_dip_xline, pct_dip_taper,
                            wrap_filt, shape=FilterShape.ELLIPSES):
        dx = (min_dip_inline + max_dip_inline) / 2 * 0.001
        dy = (min_dip_xline + max_dip_xline) / 2 * 0.001
        ax = (max_dip_inline - min_dip_inline) / 2 * 0.001
        ay = (max_dip_xline - min_dip_xline) / 2 * 0.001
        k0x = freq * dx
        k0y = freq * dy
        h1x = freq * ax
        h1y = freq * ay
        tf = 1 + pct_dip_taper / 100
        h2x = h1x * tf
        h2y = h1y * tf
        KX, KY = np.meshgrid(kx, ky, indexing='ij')
        r1 = _normalized_radial_distance(KX, KY, k0x, k0y, h1x, h1y)
        r2 = _normalized_radial_distance(KX, KY, k0x, k0y, h2x, h2y)
        filt = _cosine_taper_dip(r1, 1.0, 2.0)
        if wrap_filt:
            for sx in (-1, 0, 1):
                for sy in (-1, 0, 1):
                    if sx == 0 and sy == 0:
                        continue
                    r1w = _normalized_radial_distance(KX + sx, KY + sy, k0x, k0y, h1x, h1y)
                    filt = np.maximum(filt, _cosine_taper_dip(r1w, 1.0, 2.0))
        return filt

    def filter(self, data_3d, wndw_inline=48, wndw_xline=48,
               overlap_inline=12, overlap_xline=12,
               min_dip_inline=-12, max_dip_inline=12,
               min_dip_xline=-12, max_dip_xline=12,
               pct_dip_taper=10, wrap_filt=True):
        nt, nx, ny = data_3d.shape
        wni = min(wndw_inline, nx)
        wny = min(wndw_xline, ny)
        ovi = min(overlap_inline, wni - 1) if wni > 1 else 0
        ovy = min(overlap_xline, wny - 1) if wny > 1 else 0
        output = np.zeros_like(data_3d)
        weight = np.zeros_like(data_3d)
        windows = self._create_windows(nx, ny, wni, wny, ovi, ovy)
        fs = 1000.0 / self.sampling_interval
        freq = fftfreq(nt, d=self.sampling_interval / 1000.0)
        kx = fftfreq(wni, d=self.inline_interval)
        ky = fftfreq(wny, d=self.xline_interval)
        freq_mask = np.abs(freq) >= self.min_freq
        if self.max_freq is not None:
            freq_mask &= np.abs(freq) <= self.max_freq

        for xs, ys in windows:
            dw = data_3d[:, xs, ys].copy()
            dw = self._apply_taper(dw)
            spec = fftshift(fftn(dw), axes=0)
            for i in range(nt):
                if freq_mask[i]:
                    fv = self._create_dip_filter(kx, ky, abs(freq[i]),
                        min_dip_inline, max_dip_inline, min_dip_xline, max_dip_xline,
                        pct_dip_taper, wrap_filt)
                    spec[i] *= fv
            fw = np.real(ifftn(ifftshift(spec, axes=0)))
            output[:, xs, ys] += fw
            weight[:, xs, ys] += 1

        weight[weight == 0] = 1
        return output / weight


class SGYHandler:
    def __init__(self):
        self.files: Dict[str, Dict[str, Any]] = {}
        self.cancel_flags: Dict[str, bool] = {}

    def set_cancel(self, file_id: str):
        self.cancel_flags[file_id] = True

    def clear_cancel(self, file_id: str):
        self.cancel_flags.pop(file_id, None)

    def _check_cancel(self, file_id: str):
        if self.cancel_flags.get(file_id):
            self.clear_cancel(file_id)
            self._remove_processed(file_id)
            raise CancelledError("Processing cancelled by user")

    def _remove_processed(self, file_id: str):
        if file_id in self.files and 'processed' in self.files[file_id]:
            del self.files[file_id]['processed']

    def load_file(self, file_path: str, file_name: str, trace_len: Optional[int] = None, sample_rate: Optional[float] = None, dedup: bool = True, persist: bool = True) -> str:
        file_id = str(len(self.files))
        
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    sha256.update(chunk)
            file_hash = sha256.hexdigest()

            if dedup:
                existing = find_by_hash(file_hash)
                if existing:
                    raise ValueError(f"File already exists in database as: {existing['name']}")

            with segyio.open(file_path, 'r', ignore_geometry=True) as segyfile:
                traces = segyfile.trace
                samples = segyfile.samples
                
                trace_count = len(traces)
                orig_samples_per_trace = len(samples)
                orig_sample_rate = segyio.dt(segyfile) / 1000.0
                
                all_data = segyfile.trace.raw[:]

                def get_header_stats(field):
                    try:
                        vals = segyfile.attributes(field)[:]
                        return int(np.min(vals)), int(np.max(vals))
                    except Exception:
                        return 0, 0

                ffid_min, ffid_max = get_header_stats(segyio.TraceField.FieldRecord)
                shot_min, shot_max = get_header_stats(segyio.TraceField.TRACE_SEQUENCE_FILE)
                cdp_min, cdp_max = get_header_stats(segyio.TraceField.CDP)
                offset_min, offset_max = get_header_stats(segyio.TraceField.offset)
                inline_min, inline_max = get_header_stats(segyio.TraceField.INLINE_3D)
                xline_min, xline_max = get_header_stats(segyio.TraceField.CROSSLINE_3D)

                if trace_len is not None:
                    trace_len = int(trace_len)
                    if trace_len <= 0:
                        raise ValueError("trace length must be positive")
                    if trace_len < all_data.shape[1]:
                        all_data = all_data[:, :trace_len]

                req_sr = sample_rate
                sample_rate = orig_sample_rate
                if req_sr is not None:
                    req_sr = float(req_sr)
                    if req_sr <= 0:
                        raise ValueError("sample rate must be positive")
                    if req_sr not in _DSIN_SAMPLE_RATES:
                        raise ValueError(f"sample rate must be one of {list(_DSIN_SAMPLE_RATES)} ms")
                    if abs(req_sr - orig_sample_rate) > 1e-9:
                        all_data = _resample_traces(all_data, orig_sample_rate, req_sr)
                    sample_rate = req_sr

                samples_per_trace = all_data.shape[1]
                samples = np.arange(samples_per_trace, dtype=np.float64) * sample_rate

                min_val = float(np.min(all_data))
                max_val = float(np.max(all_data))
                
                file_size = os.path.getsize(file_path)
                
                inline_arr = segyfile.attributes(segyio.TraceField.INLINE_3D)[:]
                xline_arr = segyfile.attributes(segyio.TraceField.CROSSLINE_3D)[:]
                cdp_arr = segyfile.attributes(segyio.TraceField.CDP)[:]
                offset_arr = segyfile.attributes(segyio.TraceField.offset)[:]
                sort_indices = np.lexsort((xline_arr, inline_arr))
                inline_sorted = inline_arr[sort_indices]
                xline_sorted = xline_arr[sort_indices]

                unique_inlines, counts = np.unique(inline_sorted, return_counts=True)
                inline_ranges = {}
                start = 0
                for il, cnt in zip(unique_inlines, counts):
                    inline_ranges[int(il)] = (start, start + cnt)
                    start += cnt

                xline_sort_indices = np.lexsort((inline_arr, xline_arr))
                xline_sorted2 = xline_arr[xline_sort_indices]
                inline_sorted2 = inline_arr[xline_sort_indices]
                unique_xlines, xcounts = np.unique(xline_sorted2, return_counts=True)
                xline_ranges = {}
                start = 0
                for xl, cnt in zip(unique_xlines, xcounts):
                    xline_ranges[int(xl)] = (start, start + cnt)
                    start += cnt
                inline_sorted_by_xline = inline_sorted2

                cdp_sort_indices = np.lexsort((offset_arr, cdp_arr))
                cdp_sorted = cdp_arr[cdp_sort_indices]
                offset_sorted = offset_arr[cdp_sort_indices]
                unique_cdps, cdp_counts = np.unique(cdp_sorted, return_counts=True)
                cdp_ranges = {}
                start = 0
                for c, cnt in zip(unique_cdps, cdp_counts):
                    cdp_ranges[int(c)] = (start, start + cnt)
                    start += cnt
                unique_offsets = np.unique(offset_sorted)

                ffid_arr = segyfile.attributes(segyio.TraceField.FieldRecord)[:]
                ffid_sort_indices = np.lexsort((offset_arr, ffid_arr))
                ffid_sorted = ffid_arr[ffid_sort_indices]
                offset_sorted_ffid = offset_arr[ffid_sort_indices]
                unique_ffids, ffid_counts = np.unique(ffid_sorted, return_counts=True)
                ffid_ranges = {}
                start = 0
                for f_, cnt in zip(unique_ffids, ffid_counts):
                    ffid_ranges[int(f_)] = (start, start + cnt)
                    start += cnt
                unique_offsets_ffid = np.unique(offset_sorted_ffid)

                sample_sizes = {1: 4, 2: 4, 3: 2, 4: 4, 5: 4, 8: 1}
                fmt = segyfile.bin[segyio.BinField.Format]
                sample_bytes = sample_sizes.get(fmt, 4)
                trace_stride = 240 + orig_samples_per_trace * sample_bytes
                mm = np.memmap(file_path, dtype='uint8', mode='r')
                chan_arr = np.ndarray(trace_count, dtype='>i4', buffer=mm, offset=3612, strides=(trace_stride,)).astype(np.int32)
                chan_min = int(chan_arr.min())
                chan_max = int(chan_arr.max())
                del mm

                ffid_chan_sort_indices = np.lexsort((chan_arr, ffid_arr))
                ffid_chan_sorted = ffid_arr[ffid_chan_sort_indices]
                chan_sorted = chan_arr[ffid_chan_sort_indices]
                unique_ffids_chan, ffid_chan_counts = np.unique(ffid_chan_sorted, return_counts=True)
                ffid_chan_ranges = {}
                start = 0
                for f_, cnt in zip(unique_ffids_chan, ffid_chan_counts):
                    ffid_chan_ranges[int(f_)] = (start, start + cnt)
                    start += cnt
                unique_chans = np.unique(chan_sorted)

                self.files[file_id] = {
                    'file_name': file_name,
                    'file_path': file_path,
                    'file_size': file_size,
                    'trace_count': trace_count,
                    'samples_per_trace': samples_per_trace,
                    'sample_rate': sample_rate,
                    'min_amplitude': min_val,
                    'max_amplitude': max_val,
                    'ffid_min': ffid_min,
                    'ffid_max': ffid_max,
                    'shot_min': shot_min,
                    'shot_max': shot_max,
                    'cdp_min': cdp_min,
                    'cdp_max': cdp_max,
                    'offset_min': offset_min,
                    'offset_max': offset_max,
                    'inline_min': inline_min,
                    'inline_max': inline_max,
                    'xline_min': xline_min,
                    'xline_max': xline_max,
                    'data': all_data,
                    'samples': samples,
                    'sort_indices': sort_indices,
                    'inline_sorted': inline_sorted,
                    'xline_sorted': xline_sorted,
                    'unique_inlines': unique_inlines.tolist(),
                    'inline_ranges': inline_ranges,
                    'xline_sort_indices': xline_sort_indices,
                    'unique_xlines': unique_xlines.tolist(),
                    'xline_ranges': xline_ranges,
                    'inline_sorted_by_xline': inline_sorted_by_xline,
                    'offset_arr': offset_arr,
                    'inline_arr': inline_arr,
                    'xline_arr': xline_arr,
                    'cdp_arr': cdp_arr,
                    'ffid_arr': ffid_arr,
                    'cdp_sort_indices': cdp_sort_indices,
                    'cdp_sorted': cdp_sorted,
                    'offset_sorted': offset_sorted,
                    'unique_cdps': unique_cdps.tolist(),
                    'cdp_ranges': cdp_ranges,
                    'unique_offsets': unique_offsets.tolist(),
                    'ffid_sort_indices': ffid_sort_indices,
                    'ffid_sorted': ffid_sorted,
                    'offset_sorted_ffid': offset_sorted_ffid,
                    'unique_ffids': unique_ffids.tolist(),
                    'ffid_ranges': ffid_ranges,
                    'unique_offsets_ffid': unique_offsets_ffid.tolist(),
                    'file_hash': file_hash,
                    'chan_min': chan_min,
                    'chan_max': chan_max,
                    'chan_arr': chan_arr,
                    'ffid_chan_sort_indices': ffid_chan_sort_indices,
                    'ffid_chan_sorted': ffid_chan_sorted,
                    'chan_sorted': chan_sorted,
                    'unique_ffids_chan': unique_ffids_chan.tolist(),
                    'ffid_chan_ranges': ffid_chan_ranges,
                    'unique_chans': unique_chans.tolist(),
                }

                if persist:
                    save_data(file_id, all_data)
                    save_inline_xline(file_id, inline_arr, xline_arr)
                    save_cdp_offset(file_id, cdp_arr, offset_arr)
                    save_ffid_offset(file_id, ffid_arr, offset_arr)
                    save_ffid_chan(file_id, ffid_arr, chan_arr)
                    save_file_meta(file_id, self.files[file_id])
                
                return file_id
        except Exception as e:
            raise ValueError(f"Failed to load SGY file: {str(e)}")

    def get_statistics(self, file_id: str) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None
        
        f = self.files[file_id]
        return {
            'file_name': f['file_name'],
            'file_size': f['file_size'],
            'trace_count': f['trace_count'],
            'samples_per_trace': f['samples_per_trace'],
            'sample_rate': f['sample_rate'],
            'min_amplitude': f['min_amplitude'],
            'max_amplitude': f['max_amplitude'],
            'ffid_min': f['ffid_min'],
            'ffid_max': f['ffid_max'],
            'shot_min': f['shot_min'],
            'shot_max': f['shot_max'],
            'cdp_min': f['cdp_min'],
            'cdp_max': f['cdp_max'],
            'offset_min': f['offset_min'],
            'offset_max': f['offset_max'],
            'inline_min': f['inline_min'],
            'inline_max': f['inline_max'],
            'xline_min': f['xline_min'],
            'xline_max': f['xline_max'],
            'chan_min': f.get('chan_min', 0),
            'chan_max': f.get('chan_max', 0),
        }

    def _get_sorted_indices_and_labels(self, file_id: str):
        f = self.files[file_id]
        if 'sort_indices' not in f:
            return None, None, None
        return f['sort_indices'], f['inline_sorted'], f['xline_sorted']

    def get_visualization_data(self, file_id: str, max_traces: int = 500, max_samples: int = 2000, sort_mode: str = 'none', inline: int = None, crossline: int = None, num_gathers: int = 1) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None
        
        f = self.files[file_id]
        data = f['data']
        
        num_traces = data.shape[0]
        num_samples = data.shape[1] if len(data.shape) > 1 else 1
        
        sample_step = max(1, num_samples // max_samples)
        
        line_label = None
        line_labels_list = None
        
        if sort_mode == 'inline_xline' and f.get('inline_ranges'):
            if inline is None:
                inline = f['unique_inlines'][0]
            ranges = f['inline_ranges']
            if inline not in ranges:
                inline = f['unique_inlines'][0]
            unique_keys = f['unique_inlines']
            kidx = unique_keys.index(inline)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['sort_indices'][s:e]])
                gathered_labels.extend(f['xline_sorted'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = inline
            line_labels_list = gathered_labels[::trace_step]
        elif sort_mode == 'crossline_xline' and f.get('xline_ranges'):
            if crossline is None:
                crossline = f['unique_xlines'][0]
            ranges = f['xline_ranges']
            if crossline not in ranges:
                crossline = f['unique_xlines'][0]
            unique_keys = f['unique_xlines']
            kidx = unique_keys.index(crossline)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['xline_sort_indices'][s:e]])
                gathered_labels.extend(f['inline_sorted_by_xline'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = crossline
            line_labels_list = gathered_labels[::trace_step]
        elif sort_mode == 'cdp_offset' and f.get('cdp_ranges'):
            if inline is None:
                cdp = f['unique_cdps'][0]
            else:
                cdp = inline
            ranges = f['cdp_ranges']
            if cdp not in ranges:
                cdp = f['unique_cdps'][0]
            unique_keys = f['unique_cdps']
            kidx = unique_keys.index(cdp)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['cdp_sort_indices'][s:e]])
                gathered_labels.extend(f['offset_sorted'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = cdp
            line_labels_list = gathered_labels[::trace_step]
        elif sort_mode == 'ffid_offset' and f.get('ffid_ranges'):
            if inline is None:
                ffid = f['unique_ffids'][0]
            else:
                ffid = inline
            ranges = f['ffid_ranges']
            if ffid not in ranges:
                ffid = f['unique_ffids'][0]
            unique_keys = f['unique_ffids']
            kidx = unique_keys.index(ffid)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['ffid_sort_indices'][s:e]])
                gathered_labels.extend(f['offset_sorted_ffid'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = ffid
            line_labels_list = gathered_labels[::trace_step]
        elif sort_mode == 'ffid_chan' and f.get('ffid_chan_ranges'):
            if inline is None:
                ffid = f['unique_ffids_chan'][0]
            else:
                ffid = inline
            ranges = f['ffid_chan_ranges']
            if ffid not in ranges:
                ffid = f['unique_ffids_chan'][0]
            unique_keys = f['unique_ffids_chan']
            kidx = unique_keys.index(ffid)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['ffid_chan_sort_indices'][s:e]])
                gathered_labels.extend(f['chan_sorted'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = ffid
            line_labels_list = gathered_labels[::trace_step]
        else:
            trace_step = max(1, num_traces // max_traces)
        
        data_subset = data[::trace_step, ::sample_step]
        
        result = {
            'traces': data_subset.shape[0],
            'samples': data_subset.shape[1],
            'data': data_subset.astype(np.float32).tolist(),
            'data_min': float(data_subset.min()),
            'data_max': float(data_subset.max()),
            'trace_step': trace_step,
            'sample_step': sample_step,
            'samples_original': num_samples,
            'sample_rate': f['sample_rate'],
            'sort_mode': sort_mode,
        }
        
        if sort_mode == 'inline_xline' and line_label is not None:
            result['inline_label'] = line_label
            result['xline_labels'] = line_labels_list
        elif sort_mode == 'crossline_xline' and line_label is not None:
            result['crossline_label'] = line_label
            result['inline_labels'] = line_labels_list
        elif sort_mode == 'cdp_offset' and line_label is not None:
            result['cdp_label'] = line_label
            result['offset_labels'] = line_labels_list
        elif sort_mode == 'ffid_offset' and line_label is not None:
            result['ffid_label'] = line_label
            result['offset_labels_ffid'] = line_labels_list
        elif sort_mode == 'ffid_chan' and line_label is not None:
            result['ffid_label'] = line_label
            result['chan_labels'] = line_labels_list
        
        return result

    def apply_agc(self, file_id: str, window_ms: float) -> Optional[Dict[str, Any]]:
        return self._apply_agc(file_id, window_ms, from_processed=False)

    def _apply_agc(self, file_id: str, window_ms: float, from_processed: bool = False, parallel: bool = False, num_workers: int = 4) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        sample_rate = f['sample_rate']
        window_samples = max(1, int(window_ms / sample_rate))

        if window_samples % 2 == 0:
            window_samples += 1

        half = window_samples // 2
        num_traces, num_samples = data.shape
        epsilon = 1e-10

        if parallel and num_workers > 1 and num_traces > 1:
            nw = min(num_workers, num_traces)
            chunks = np.array_split(data, nw, axis=0)
            with concurrent.futures.ProcessPoolExecutor(max_workers=nw) as executor:
                futures = [executor.submit(_agc_chunk_worker, c, window_samples, half, epsilon) for c in chunks]
                results = [f.result() for f in futures]
            result = np.concatenate(results, axis=0).astype(np.float32)
        else:
            result = np.zeros_like(data, dtype=np.float32)
            for t in range(num_traces):
                self._check_cancel(file_id)
                trace = data[t]
                for i in range(num_samples):
                    start = max(0, i - half)
                    end = min(num_samples, i + half + 1)
                    rms = np.sqrt(np.mean(trace[start:end] ** 2))
                    result[t, i] = trace[i] / (rms + epsilon)

        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'agc',
            'params': {'window_ms': window_ms},
        }

        return {'status': 'ok', 'type': 'agc', 'params': {'window_ms': window_ms}}

    def apply_bandpass(self, file_id: str, lowcut: float, lowpass: float, highpass: float, highcut: float) -> Optional[Dict[str, Any]]:
        return self._apply_bandpass(file_id, lowcut, lowpass, highpass, highcut, from_processed=False)

    def _apply_bandpass(self, file_id: str, lowcut: float, lowpass: float, highpass: float, highcut: float, from_processed: bool = False, parallel: bool = False, num_workers: int = 4) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        sample_rate_ms = f['sample_rate']
        dt_s = sample_rate_ms / 1000.0
        num_traces, num_samples = data.shape

        freqs = np.fft.rfftfreq(num_samples, d=dt_s)
        mask = np.zeros_like(freqs, dtype=np.float32)

        for i, fr in enumerate(freqs):
            if fr < lowcut:
                mask[i] = 0.0
            elif fr < lowpass:
                mask[i] = (fr - lowcut) / (lowpass - lowcut)
            elif fr < highpass:
                mask[i] = 1.0
            elif fr < highcut:
                mask[i] = (highcut - fr) / (highcut - highpass)
            else:
                mask[i] = 0.0

        if parallel and num_workers > 1 and num_traces > 1:
            nw = min(num_workers, num_traces)
            chunks = np.array_split(data, nw, axis=0)
            with concurrent.futures.ProcessPoolExecutor(max_workers=nw) as executor:
                futures = [executor.submit(_bandpass_chunk_worker, c, mask) for c in chunks]
                results = [f.result() for f in futures]
            result = np.concatenate(results, axis=0).astype(np.float32)
        else:
            result = np.zeros_like(data, dtype=np.float32)
            for t in range(num_traces):
                self._check_cancel(file_id)
                spectrum = np.fft.rfft(data[t])
                spectrum *= mask
                result[t] = np.fft.irfft(spectrum, n=num_samples).real.astype(np.float32)

        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'bandpass',
            'params': {'lowcut': lowcut, 'lowpass': lowpass, 'highpass': highpass, 'highcut': highcut},
        }

        return {'status': 'ok', 'type': 'bandpass', 'params': {'lowcut': lowcut, 'lowpass': lowpass, 'highpass': highpass, 'highcut': highcut}}

    def apply_fxdecon(self, file_id: str, filter_length: int = 5) -> Optional[Dict[str, Any]]:
        return self._apply_fxdecon(file_id, filter_length, from_processed=False)

    def _apply_fxdecon(self, file_id: str, filter_length: int = 5, from_processed: bool = False, parallel: bool = False, num_workers: int = 4) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        ntraces, nsamples = data.shape

        if ntraces < 3:
            return data

        P = min(filter_length, ntraces // 2 - 1)
        if P < 1:
            P = 1

        nfft = 2 ** int(np.ceil(np.log2(nsamples)))
        fw = np.fft.rfft(data, n=nfft, axis=1)
        nfreqs = fw.shape[1]
        tol = 1e-12

        if parallel and num_workers > 1 and nfreqs > 2:
            nw = min(num_workers, nfreqs)
            freq_chunks = np.array_split(fw, nw, axis=1)
            starts = np.cumsum([0] + [c.shape[1] for c in freq_chunks[:-1]]).tolist()
            with concurrent.futures.ProcessPoolExecutor(max_workers=nw) as executor:
                futures = [executor.submit(_fxdecon_chunk_worker, c, ntraces, P, tol, s) for c, s in zip(freq_chunks, starts)]
                out_chunks = [f.result() for f in futures]
            out_f = np.concatenate(out_chunks, axis=1)
        else:
            out_f = np.zeros_like(fw, dtype=np.complex128)
            for k in range(nfreqs):
                self._check_cancel(file_id)
                x = fw[:, k]

                if k == 0:
                    out_f[:, k] = x
                    continue

                r = np.zeros(P + 1, dtype=np.complex128)
                for lag in range(P + 1):
                    r[lag] = np.vdot(x[lag:], x[:ntraces - lag]) / ntraces

                if abs(r[0]) < tol:
                    out_f[:, k] = x
                    continue

                r[0] *= 1.001

                a = np.zeros(P, dtype=np.complex128)
                E = r[0].real

                for i in range(P):
                    rc = -r[i + 1]
                    for j in range(i):
                        rc -= a[j] * r[i - j]
                    rc /= E

                    anew = np.zeros(i + 1, dtype=np.complex128)
                    anew[-1] = rc
                    for j in range(i):
                        anew[j] = a[j] + rc * np.conj(a[i - j - 1])
                    a = anew
                    E *= (1.0 - rc.real ** 2 - rc.imag ** 2)

                yf = np.zeros(ntraces, dtype=np.complex128)
                yf[:P] = x[:P]
                for n in range(P, ntraces):
                    yf[n] = -np.dot(a, x[n - P:n][::-1])

                yb = np.zeros(ntraces, dtype=np.complex128)
                yb[-P:] = x[-P:]
                for n in range(ntraces - P - 1, -1, -1):
                    yb[n] = -np.dot(np.conj(a), x[n + 1:n + P + 1])

                out_f[:, k] = 0.5 * (yf + yb)

        out = np.fft.irfft(out_f, n=nfft, axis=1)[:, :nsamples].real.astype(np.float32)

        self.files[file_id]['processed'] = {
            'data': out,
            'type': 'fxdecon',
            'params': {'filter_length': filter_length},
        }

        return {'status': 'ok', 'type': 'fxdecon', 'params': {'filter_length': filter_length}}

    def apply_fxdecont(self, file_id: str, pred_order: int = 10, retro_order: int = 10, reg: float = 0.01, window_size: int = 51, step: int = 1, nonlinear_plus: bool = False, freq_min: float = 0.0, freq_max: float = 0.0) -> Optional[Dict[str, Any]]:
        return self._apply_fxdecont(file_id, pred_order, retro_order, reg, window_size, step, nonlinear_plus, freq_min, freq_max, from_processed=False)

    def _apply_fxdecont(self, file_id: str, pred_order: int = 10, retro_order: int = 10, reg: float = 0.01, window_size: int = 51, step: int = 1, nonlinear_plus: bool = False, freq_min: float = 0.0, freq_max: float = 0.0, from_processed: bool = False, parallel: bool = False, num_workers: int = 4) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        n_traces, n_time = data.shape

        if n_traces < max(pred_order, retro_order) + 2:
            return data

        spec = np.fft.rfft(data, axis=1)
        n_freqs = spec.shape[1]
        freqs = np.fft.rfftfreq(n_time, d=f['sample_rate'] / 1000.0)
        if freq_max <= 0:
            freq_mask = np.ones(n_freqs, dtype=bool)
        else:
            freq_mask = (freqs >= freq_min) & (freqs <= freq_max)

        if parallel and num_workers > 1 and n_freqs > 2:
            nw = min(num_workers, n_freqs)
            freq_chunks = np.array_split(spec, nw, axis=1)
            starts = np.cumsum([0] + [c.shape[1] for c in freq_chunks[:-1]]).tolist()
            with concurrent.futures.ProcessPoolExecutor(max_workers=nw) as executor:
                futures = [
                    executor.submit(_fxdecont_chunk_worker, c, n_traces, pred_order, retro_order, reg, window_size, step, nonlinear_plus, s, freq_mask)
                    for c, s in zip(freq_chunks, starts)
                ]
                out_chunks = [f.result() for f in futures]
            spec_out = np.concatenate(out_chunks, axis=1)
        else:
            spec_out = np.zeros_like(spec, dtype=np.complex64)
            for center in range(0, n_traces, step):
                self._check_cancel(file_id)
                start = max(0, center - window_size // 2)
                end = min(n_traces, center + window_size // 2)
                if end - start < max(pred_order, retro_order) + 1:
                    spec_out[center, :] = spec[center, :]
                    continue
                for f_idx in range(n_freqs):
                    if not freq_mask[f_idx]:
                        spec_out[center, f_idx] = spec[center, f_idx]
                        continue
                    x = spec[start:end, f_idx]
                    if pred_order > 0 and len(x) > pred_order:
                        r = np.correlate(x, x, mode='full')[len(x) - 1:]
                        r = r / r[0]
                        r[0] += reg * r[0]
                        try:
                            a = solve_toeplitz(r[:pred_order], r[1:pred_order + 1])
                        except Exception:
                            a = np.zeros(pred_order, dtype=np.complex64)
                        if center >= pred_order:
                            past = spec[center - pred_order:center, f_idx][::-1]
                            pred_forward = np.dot(a, past)
                        else:
                            pred_forward = x[center - start] if 0 <= center - start < len(x) else 0
                    else:
                        pred_forward = x[center - start] if 0 <= center - start < len(x) else 0
                    if retro_order > 0 and len(x) > retro_order:
                        x_rev = x[::-1]
                        r_rev = np.correlate(x_rev, x_rev, mode='full')[len(x_rev) - 1:]
                        r_rev = r_rev / r_rev[0]
                        r_rev[0] += reg * r_rev[0]
                        try:
                            b = solve_toeplitz(r_rev[:retro_order], r_rev[1:retro_order + 1])
                        except Exception:
                            b = np.zeros(retro_order, dtype=np.complex64)
                        if n_traces - center - 1 >= retro_order:
                            future = spec[center + 1:center + retro_order + 1, f_idx]
                            pred_backward = np.dot(b, future)
                        else:
                            pred_backward = x[center - start] if 0 <= center - start < len(x) else 0
                    else:
                        pred_backward = x[center - start] if 0 <= center - start < len(x) else 0
                    orig_val = spec[center, f_idx]
                    if nonlinear_plus:
                        err_f = np.abs(orig_val - pred_forward) if pred_order > 0 else np.inf
                        err_b = np.abs(orig_val - pred_backward) if retro_order > 0 else np.inf
                        spec_out[center, f_idx] = pred_forward if err_f < err_b else pred_backward
                    else:
                        spec_out[center, f_idx] = (pred_forward + pred_backward) * 0.5

        result = np.fft.irfft(spec_out, n=n_time, axis=1).astype(np.float32)

        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'fxdecont',
            'params': {'pred_order': pred_order, 'retro_order': retro_order, 'reg': reg, 'window_size': window_size, 'step': step, 'nonlinear_plus': nonlinear_plus, 'freq_min': freq_min, 'freq_max': freq_max},
        }

        return {'status': 'ok', 'type': 'fxdecont', 'params': {'pred_order': pred_order, 'retro_order': retro_order, 'reg': reg, 'window_size': window_size, 'step': step, 'nonlinear_plus': nonlinear_plus, 'freq_min': freq_min, 'freq_max': freq_max}}

    def apply_psf(self, file_id: str, phase_deg: float = 30.0) -> Optional[Dict[str, Any]]:
        return self._apply_psf(file_id, phase_deg, from_processed=False)

    def _apply_psf(self, file_id: str, phase_deg: float = 30.0, from_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        n_traces, n_samples = data.shape

        phi = np.float64(phase_deg) * np.pi / 180.0
        c = np.cos(phi)
        s = np.sin(phi)

        result = np.zeros_like(data, dtype=np.float32)
        for t in range(n_traces):
            self._check_cancel(file_id)
            spec = np.fft.rfft(data[t].astype(np.float64))
            spec *= (c + 1j * s)
            result[t] = np.fft.irfft(spec, n=n_samples).real.astype(np.float32)

        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'psf',
            'params': {'phase_deg': phase_deg},
        }

        return {'status': 'ok', 'type': 'psf', 'params': {'phase_deg': phase_deg}}

    def apply_fk3d(self, file_id: str, wndw_inline: int = 48, wndw_xline: int = 48,
                   overlap_inline: int = 12, overlap_xline: int = 12,
                   min_dip_inline: float = -12.0, max_dip_inline: float = 12.0,
                   min_dip_xline: float = -12.0, max_dip_xline: float = 12.0,
                   pct_dip_taper: float = 10.0, wrap_filt: bool = True) -> Optional[Dict[str, Any]]:
        return self._apply_fk3d(file_id, wndw_inline, wndw_xline,
                                overlap_inline, overlap_xline,
                                min_dip_inline, max_dip_inline,
                                min_dip_xline, max_dip_xline,
                                pct_dip_taper, wrap_filt, from_processed=False)

    def _apply_fk3d(self, file_id: str,
                    wndw_inline: int = 48, wndw_xline: int = 48,
                    overlap_inline: int = 12, overlap_xline: int = 12,
                    min_dip_inline: float = -12.0, max_dip_inline: float = 12.0,
                    min_dip_xline: float = -12.0, max_dip_xline: float = 12.0,
                    pct_dip_taper: float = 10.0, wrap_filt: bool = True,
                    from_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        if 'sort_indices' not in f or not f.get('unique_inlines'):
            raise RuntimeError("FK3D requires inline/xline sort data")

        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        sorted_data = data[f['sort_indices']]
        inline_sorted = f['inline_sorted']
        xline_sorted = f['xline_sorted']
        inline_ranges = f['inline_ranges']
        unique_inlines = f['unique_inlines']
        all_xlines = sorted(np.unique(xline_sorted).tolist())
        xline_to_col = {xl: i for i, xl in enumerate(all_xlines)}
        nx = len(unique_inlines)
        ny = len(all_xlines)
        nt = data.shape[1]

        volume = np.zeros((nt, nx, ny), dtype=np.float32)
        for inline_idx, inline in enumerate(unique_inlines):
            start, end = inline_ranges[inline]
            for i in range(start, end):
                xl = int(xline_sorted[i])
                col = xline_to_col.get(xl)
                if col is not None:
                    volume[:, inline_idx, col] = sorted_data[i, :]

        dt_ms = f['sample_rate']
        filt = FKFilter3D(dt_ms, 1.0, 1.0)
        filtered = filt.filter(volume,
                               wndw_inline=wndw_inline, wndw_xline=wndw_xline,
                               overlap_inline=overlap_inline, overlap_xline=overlap_xline,
                               min_dip_inline=min_dip_inline, max_dip_inline=max_dip_inline,
                               min_dip_xline=min_dip_xline, max_dip_xline=max_dip_xline,
                               pct_dip_taper=pct_dip_taper, wrap_filt=wrap_filt)

        output = np.zeros_like(sorted_data)
        for inline_idx, inline in enumerate(unique_inlines):
            start, end = inline_ranges[inline]
            for i in range(start, end):
                xl = int(xline_sorted[i])
                col = xline_to_col.get(xl)
                if col is not None:
                    output[i, :] = filtered[:, inline_idx, col]
                else:
                    output[i, :] = sorted_data[i, :]

        unsorter = np.argsort(f['sort_indices'])
        result = output[unsorter]

        params = {
            'wndw_inline': wndw_inline, 'wndw_xline': wndw_xline,
            'overlap_inline': overlap_inline, 'overlap_xline': overlap_xline,
            'min_dip_inline': min_dip_inline, 'max_dip_inline': max_dip_inline,
            'min_dip_xline': min_dip_xline, 'max_dip_xline': max_dip_xline,
            'pct_dip_taper': pct_dip_taper, 'wrap_filt': wrap_filt,
        }
        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'fk3d',
            'params': params,
        }
        return {'status': 'ok', 'type': 'fk3d', 'params': params}

    def _apply_gain(self, file_id: str, voption: float = 2.0, toption: float = 1.0, factor: float = 1.0, units: str = 'feet', from_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        sample_rate_ms = f['sample_rate']
        n_traces, n_samples = data.shape
        sample_times = np.arange(n_samples) * sample_rate_ms
        vel_table = _GAIN_VELOCITY_FEET if units == 'feet' else _GAIN_VELOCITY_METERS
        v_interp = np.interp(sample_times, vel_table[:, 0], vel_table[:, 1],
                             left=vel_table[0, 1], right=vel_table[-1, 1])
        t = np.maximum(sample_times, 1e-6)
        correction = (t ** toption) * (v_interp ** voption)
        norm = np.mean(correction)
        if norm <= 0:
            norm = 1.0
        gain = factor * (correction / norm)
        result = data * gain[np.newaxis, :]
        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'gain',
            'params': {'voption': voption, 'toption': toption, 'factor': factor, 'units': units},
        }
        return {'status': 'ok', 'type': 'gain', 'params': {'voption': voption, 'toption': toption, 'factor': factor, 'units': units}}

    def _apply_lfaf(self, file_id: str, dx: float = 25.0, vel: float = 1500.0, f1: float = 0.0, f2: float = 20.0, ftaper: float = 5.0, maxmix: int = 0, from_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        dt_s = f['sample_rate'] / 1000.0
        n_traces, n_samples = data.shape
        nyquist = 0.5 / dt_s
        if f1 < 0:
            f1 = 0.0
        if f2 > nyquist:
            f2 = nyquist
        if f1 >= f2:
            raise ValueError("f1 must be less than f2")
        taper_start = max(f1, f2 - ftaper)
        freqs = np.fft.rfftfreq(n_samples, d=dt_s)
        n_freqs = len(freqs)
        spec = np.fft.rfft(data, axis=1)
        filtered_spec = spec.copy()
        for i_f, freq in enumerate(freqs):
            if freq < f1 or freq > f2:
                continue
            array_len = vel / (dx * max(freq, 1e-6))
            mix_len = int(np.round(array_len))
            if maxmix > 0:
                mix_len = min(mix_len, maxmix)
            mix_len = max(1, mix_len)
            if mix_len % 2 == 0:
                mix_len += 1
            half = mix_len // 2
            col = spec[:, i_f].copy()
            filtered_col = np.zeros_like(col)
            for t_idx in range(n_traces):
                start = max(0, t_idx - half)
                end = min(n_traces, t_idx + half + 1)
                filtered_col[t_idx] = np.mean(col[start:end])
            if freq >= taper_start and ftaper > 0:
                weight = np.clip((f2 - freq) / ftaper, 0.0, 1.0)
                filtered_col = weight * filtered_col + (1.0 - weight) * col
            filtered_spec[:, i_f] = filtered_col
        result = np.fft.irfft(filtered_spec, n=n_samples, axis=1)
        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'lfaf',
            'params': {'dx': dx, 'vel': vel, 'f1': f1, 'f2': f2, 'ftaper': ftaper, 'maxmix': maxmix},
        }
        return {'status': 'ok', 'type': 'lfaf', 'params': {'dx': dx, 'vel': vel, 'f1': f1, 'f2': f2, 'ftaper': ftaper, 'maxmix': maxmix}}

    def _apply_lfaf1(self, file_id: str, vel: float = 1500.0, f1: float = 0.0, f2: float = 20.0, ftaper: float = 5.0, maxmix: int = 15, min_offset: float = 10.0, mute_time: float = 0.0, mute_zone_width: float = 50.0, from_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        dt_s = f['sample_rate'] / 1000.0
        n_traces, n_samples = data.shape
        nyquist = 0.5 / dt_s
        if f1 < 0:
            f1 = 0.0
        if f2 > nyquist:
            f2 = nyquist
        if f1 >= f2:
            raise ValueError("f1 must be less than f2")
        offsets = f.get('offset_arr')
        if offsets is not None:
            dx_valid = np.diff(offsets)
            dx_valid = dx_valid[dx_valid > 0]
            median_dx = np.median(dx_valid) if len(dx_valid) > 0 else f.get('dx', 25.0)
        else:
            offsets = np.arange(n_traces, dtype=np.float64) * f.get('dx', 25.0)
            median_dx = 1.0
        taper_start = max(f1, f2 - ftaper)
        freqs = np.fft.rfftfreq(n_samples, d=dt_s)
        spec = np.fft.rfft(data, axis=1)
        filtered_spec = spec.copy()
        mix_lengths = []
        for freq in freqs:
            if freq < f1 or freq > f2 or freq < 0.5:
                mix_lengths.append(1)
            else:
                array_len = vel / (median_dx * freq)
                mix_len = int(np.round(array_len))
                mix_len = min(mix_len, maxmix)
                mix_len = max(3, mix_len)
                if mix_len % 2 == 0:
                    mix_len += 1
                mix_lengths.append(mix_len)
        for i_f, freq in enumerate(freqs):
            if freq < f1 or freq > f2:
                continue
            mix_len = mix_lengths[i_f]
            if mix_len == 1:
                continue
            half = mix_len // 2
            col = spec[:, i_f].copy()
            filtered_col = np.zeros_like(col)
            for t_idx in range(n_traces):
                offset = offsets[t_idx] if isinstance(offsets, np.ndarray) and len(offsets) == n_traces else 0.0
                if offset < min_offset:
                    scale = max(0.3, offset / min_offset)
                    adaptive_half = max(1, int(half * scale))
                else:
                    adaptive_half = half
                start = max(0, t_idx - adaptive_half)
                end = min(n_traces, t_idx + adaptive_half + 1)
                if end - start >= 3:
                    filtered_col[t_idx] = np.median(col[start:end])
                else:
                    filtered_col[t_idx] = col[t_idx]
            if freq >= taper_start and ftaper > 0:
                weight = np.clip((f2 - freq) / ftaper, 0.0, 1.0)
                filtered_col = weight * filtered_col + (1.0 - weight) * col
            filtered_spec[:, i_f] = filtered_col
        result = np.fft.irfft(filtered_spec, n=n_samples, axis=1)
        if mute_time > 0:
            offsets = f.get('offset_arr')
            if offsets is None:
                offsets = np.arange(n_traces, dtype=np.float64)
            sr_ms = f['sample_rate']
            mute_samples = min(int(mute_time / sr_ms) if sr_ms > 0 else 0, n_samples)
            for i in range(n_traces):
                off = offsets[i] if isinstance(offsets, np.ndarray) and len(offsets) == n_traces else 0.0
                if off < mute_zone_width:
                    scale = max(0.0, min(1.0, 1.0 - off / mute_zone_width))
                    sm = max(0, min(n_samples, int(mute_samples * scale)))
                    if sm > 1:
                        result[i, :sm] *= np.linspace(0, 1, sm)
        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'lfaf1',
            'params': {'vel': vel, 'f1': f1, 'f2': f2, 'ftaper': ftaper, 'maxmix': maxmix, 'min_offset': min_offset, 'mute_time': mute_time, 'mute_zone_width': mute_zone_width},
        }
        return {'status': 'ok', 'type': 'lfaf1', 'params': {'vel': vel, 'f1': f1, 'f2': f2, 'ftaper': ftaper, 'maxmix': maxmix, 'min_offset': min_offset, 'mute_time': mute_time, 'mute_zone_width': mute_zone_width}}

    def _apply_lfafn(self, file_id: str, dx: float = 25.0, vel: float = 1500.0, f1: float = 0.0, f2: float = 20.0, ftaper: float = 5.0, maxmix: int = 0, direction: str = 'both', attenuation: float = 1.0, from_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        n_traces, n_samples = data.shape
        dt_s = float(f.get('sample_rate', 1.0)) / 1000.0
        if dt_s <= 0:
            dt_s = 0.001

        if n_traces < 2 or n_samples < 2:
            result = np.asarray(data, dtype=np.float32)
        else:
            nyquist = 0.5 / dt_s
            if f1 < 0.0:
                f1 = 0.0
            if f2 <= 0.0 or f2 > nyquist:
                f2 = nyquist
            if f1 >= f2:
                raise ValueError("f1 must be less than f2")

            gather = np.asarray(data, dtype=np.float32).T
            flt = FKVelocityFilter.from_lfaf_params(
                dt=dt_s,
                dx=dx,
                vel=vel,
                f1=f1,
                f2=f2,
                ftaper=ftaper,
                maxmix=int(maxmix),
                direction=direction,
                attenuation=attenuation,
            )
            filtered = flt.apply(gather)
            result = np.asarray(filtered, dtype=np.float32).T

        params = {'dx': dx, 'vel': vel, 'f1': f1, 'f2': f2, 'ftaper': ftaper, 'maxmix': maxmix, 'direction': direction, 'attenuation': attenuation}
        self.files[file_id]['processed'] = {
            'data': result,
            'type': 'lfafn',
            'params': params,
        }
        return {'status': 'ok', 'type': 'lfafn', 'params': params}

    def _apply_dsout(self, file_id: str, path: str, sort_type: str = 'none', first_min=None, first_max=None, second_min=None, second_max=None, from_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if from_processed and 'processed' in f else f['data']
        data = np.asarray(data, dtype=np.float32)
        if data.ndim == 1:
            data = data.reshape(1, -1)
        n_traces, n_samples = data.shape

        def _parse_int(v):
            if v is None or v == '':
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        first_min = _parse_int(first_min)
        first_max = _parse_int(first_max)
        second_min = _parse_int(second_min)
        second_max = _parse_int(second_max)

        inline_arr = f.get('inline_arr')
        xline_arr = f.get('xline_arr')
        cdp_arr = f.get('cdp_arr')
        offset_arr = f.get('offset_arr')
        ffid_arr = f.get('ffid_arr')
        chan_arr = f.get('chan_arr')

        if inline_arr is None or xline_arr is None:
            li, lx = load_inline_xline(file_id)
            inline_arr = inline_arr if inline_arr is not None else li
            xline_arr = xline_arr if xline_arr is not None else lx
        if cdp_arr is None or offset_arr is None:
            lc, lo = load_cdp_offset(file_id)
            cdp_arr = cdp_arr if cdp_arr is not None else lc
            offset_arr = offset_arr if offset_arr is not None else lo
        if ffid_arr is None:
            lf, _ = load_ffid_offset(file_id)
            ffid_arr = lf
        if chan_arr is None:
            _, lch = load_ffid_chan(file_id)
            chan_arr = lch

        key_map = {
            'inline_xline': ('inline', 'xline'),
            'crossline_xline': ('xline', 'inline'),
            'cdp_offset': ('cdp', 'offset'),
            'ffid_offset': ('ffid', 'offset'),
            'ffid_chan': ('ffid', 'chan'),
        }
        arrays = {
            'inline': inline_arr,
            'xline': xline_arr,
            'cdp': cdp_arr,
            'offset': offset_arr,
            'ffid': ffid_arr,
            'chan': chan_arr,
        }

        sort_type = (sort_type or 'none').strip() or 'none'
        if sort_type == 'none':
            indices = np.arange(n_traces)
        else:
            if sort_type not in key_map:
                raise ValueError(f"Unknown DSOUT sort type: {sort_type}")
            k1_name, k2_name = key_map[sort_type]
            k1 = arrays.get(k1_name)
            k2 = arrays.get(k2_name)
            if k1 is None or len(k1) != n_traces:
                raise ValueError(f"DSOUT: sorting key '{k1_name}' is not available for this file")
            if k2 is None or len(k2) != n_traces:
                raise ValueError(f"DSOUT: sorting key '{k2_name}' is not available for this file")
            mask = np.ones(n_traces, dtype=bool)
            if first_min is not None:
                mask &= k1 >= first_min
            if first_max is not None:
                mask &= k1 <= first_max
            if second_min is not None:
                mask &= k2 >= second_min
            if second_max is not None:
                mask &= k2 <= second_max
            selected = np.where(mask)[0]
            order = np.lexsort((k2[selected], k1[selected]))
            indices = selected[order]

        indices = np.asarray(indices, dtype=int)
        if len(indices) == 0:
            raise ValueError("DSOUT: no traces match the selected sorting key ranges")

        path = (path or '').strip()
        if not path:
            raise ValueError("DSOUT: output path is empty")
        out_dir = os.path.dirname(os.path.abspath(path))
        os.makedirs(out_dir, exist_ok=True)

        sample_rate = float(f.get('sample_rate') or 1.0)
        if sample_rate <= 0:
            sample_rate = 1.0
        dt_us = max(1, int(round(sample_rate * 1000.0)))
        samples_ms = np.round(np.arange(n_samples) * sample_rate, 6)

        spec = segyio.spec()
        spec.samples = samples_ms
        spec.format = 5
        spec.tracecount = len(indices)

        out_data = data[indices]

        with segyio.create(path, spec) as dst:
            dst.text[0] = 'Created by SeisViz DSOUT'
            dst.trace = out_data
            for j, idx in enumerate(indices):
                hdr = {
                    segyio.TraceField.TRACE_SEQUENCE_LINE: j + 1,
                    segyio.TraceField.TRACE_SEQUENCE_FILE: j + 1,
                    segyio.TraceField.TRACE_SAMPLE_COUNT: n_samples,
                    segyio.TraceField.TRACE_SAMPLE_INTERVAL: dt_us,
                }
                if inline_arr is not None and len(inline_arr) == n_traces:
                    hdr[segyio.TraceField.INLINE_3D] = int(inline_arr[idx])
                if xline_arr is not None and len(xline_arr) == n_traces:
                    hdr[segyio.TraceField.CROSSLINE_3D] = int(xline_arr[idx])
                if cdp_arr is not None and len(cdp_arr) == n_traces:
                    hdr[segyio.TraceField.CDP] = int(cdp_arr[idx])
                if offset_arr is not None and len(offset_arr) == n_traces:
                    hdr[segyio.TraceField.offset] = int(offset_arr[idx])
                if ffid_arr is not None and len(ffid_arr) == n_traces:
                    hdr[segyio.TraceField.FieldRecord] = int(ffid_arr[idx])
                if chan_arr is not None and len(chan_arr) == n_traces:
                    hdr[segyio.TraceField.TraceNumber] = int(chan_arr[idx])
                dst.header[j] = hdr

        return {'path': path, 'traces': int(len(indices)), 'samples': int(n_samples)}

    def run_sequence(self, file_id: str, steps: list, parallel: bool = False, num_workers: int = 4) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        if file_id in self.files and 'processed' in self.files[file_id]:
            del self.files[file_id]['processed']

        dsout_results = []
        for step in steps:
            self._check_cancel(file_id)
            t = step['type']
            try:
                if t == 'agc':
                    self._apply_agc(file_id, step['params']['window_ms'], from_processed=True, parallel=parallel, num_workers=num_workers)
                elif t == 'bandpass':
                    self._apply_bandpass(file_id, step['params']['lowcut'], step['params']['lowpass'], step['params']['highpass'], step['params']['highcut'], from_processed=True, parallel=parallel, num_workers=num_workers)
                elif t == 'fxdecon':
                    self._apply_fxdecon(file_id, step['params']['filter_length'], from_processed=True, parallel=parallel, num_workers=num_workers)
                elif t == 'fxdecont':
                    self._apply_fxdecont(file_id, step['params']['pred_order'], step['params']['retro_order'], step['params']['reg'], step['params']['window_size'], step['params']['step'], step['params']['nonlinear_plus'], step['params']['freq_min'], step['params']['freq_max'], from_processed=True, parallel=parallel, num_workers=num_workers)
                elif t == 'decons':
                    self._apply_decons(file_id, step['params']['operator_length'], step['params']['prewhitening'], step['params']['phase_mode'], step['params']['bandwidth_min'], step['params']['bandwidth_max'], from_processed=True)
                elif t == 'psf':
                    self._apply_psf(file_id, step['params']['phase_deg'], from_processed=True)
                elif t == 'fk3d':
                    self._apply_fk3d(file_id,
                                     wndw_inline=step['params'].get('wndw_inline', 48),
                                     wndw_xline=step['params'].get('wndw_xline', 48),
                                     overlap_inline=step['params'].get('overlap_inline', 12),
                                     overlap_xline=step['params'].get('overlap_xline', 12),
                                     min_dip_inline=step['params'].get('min_dip_inline', -12.0),
                                     max_dip_inline=step['params'].get('max_dip_inline', 12.0),
                                     min_dip_xline=step['params'].get('min_dip_xline', -12.0),
                                     max_dip_xline=step['params'].get('max_dip_xline', 12.0),
                                     pct_dip_taper=step['params'].get('pct_dip_taper', 10.0),
                                     wrap_filt=step['params'].get('wrap_filt', True),
                                     from_processed=True)
                elif t == 'gain':
                    self._apply_gain(file_id,
                                     voption=step['params'].get('voption', 2.0),
                                     toption=step['params'].get('toption', 1.0),
                                     factor=step['params'].get('factor', 1.0),
                                     units=step['params'].get('units', 'feet'),
                                     from_processed=True)
                elif t == 'lfaf':
                    self._apply_lfaf(file_id,
                                     dx=step['params'].get('dx', 25.0),
                                     vel=step['params'].get('vel', 1500.0),
                                     f1=step['params'].get('f1', 0.0),
                                     f2=step['params'].get('f2', 20.0),
                                     ftaper=step['params'].get('ftaper', 5.0),
                                     maxmix=step['params'].get('maxmix', 0),
                                     from_processed=True)
                elif t == 'lfaf1':
                    self._apply_lfaf1(file_id,
                                      vel=step['params'].get('vel', 1500.0),
                                      f1=step['params'].get('f1', 0.0),
                                      f2=step['params'].get('f2', 20.0),
                                      ftaper=step['params'].get('ftaper', 5.0),
                                      maxmix=step['params'].get('maxmix', 15),
                                       min_offset=step['params'].get('min_offset', 10.0),
                                       mute_time=step['params'].get('mute_time', 0.0),
                                       mute_zone_width=step['params'].get('mute_zone_width', 50.0),
                                       from_processed=True)
                elif t == 'lfafn':
                    self._apply_lfafn(file_id,
                                      dx=step['params'].get('dx', 25.0),
                                      vel=step['params'].get('vel', 1500.0),
                                      f1=step['params'].get('f1', 0.0),
                                      f2=step['params'].get('f2', 20.0),
                                      ftaper=step['params'].get('ftaper', 5.0),
                                      maxmix=step['params'].get('maxmix', 0),
                                      direction=step['params'].get('direction', 'both'),
                                      attenuation=step['params'].get('attenuation', 1.0),
                                      from_processed=True)
                elif t == 'dsout':
                    dsout_results.append(self._apply_dsout(
                        file_id,
                        step['params'].get('path', ''),
                        sort_type=step['params'].get('sort_type', 'none'),
                        first_min=step['params'].get('first_min'),
                        first_max=step['params'].get('first_max'),
                        second_min=step['params'].get('second_min'),
                        second_max=step['params'].get('second_max'),
                        from_processed=True,
                    ))
            except Exception as e:
                raise RuntimeError(f"Step '{t}' failed: {str(e)}")

        return {'status': 'ok', 'steps': steps, 'dsout': dsout_results}

    def get_processed_visualization(self, file_id: str, max_traces: int = 500, max_samples: int = 2000, sort_mode: str = 'none', inline: int = None, crossline: int = None, num_gathers: int = 1) -> Optional[Dict[str, Any]]:
        if file_id not in self.files or 'processed' not in self.files[file_id]:
            return None

        f = self.files[file_id]
        data = f['processed']['data']

        num_traces = data.shape[0]
        num_samples = data.shape[1] if len(data.shape) > 1 else 1

        sample_step = max(1, num_samples // max_samples)

        line_label = None
        line_labels_list = None

        if sort_mode == 'inline_xline' and f.get('inline_ranges'):
            if inline is None:
                inline = f['unique_inlines'][0]
            ranges = f['inline_ranges']
            if inline not in ranges:
                inline = f['unique_inlines'][0]
            unique_keys = f['unique_inlines']
            kidx = unique_keys.index(inline)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['sort_indices'][s:e]])
                gathered_labels.extend(f['xline_sorted'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = inline
            line_labels_list = gathered_labels[::trace_step]
        elif sort_mode == 'crossline_xline' and f.get('xline_ranges'):
            if crossline is None:
                crossline = f['unique_xlines'][0]
            ranges = f['xline_ranges']
            if crossline not in ranges:
                crossline = f['unique_xlines'][0]
            unique_keys = f['unique_xlines']
            kidx = unique_keys.index(crossline)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['xline_sort_indices'][s:e]])
                gathered_labels.extend(f['inline_sorted_by_xline'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = crossline
            line_labels_list = gathered_labels[::trace_step]
        elif sort_mode == 'cdp_offset' and f.get('cdp_ranges'):
            if inline is None:
                cdp = f['unique_cdps'][0]
            else:
                cdp = inline
            ranges = f['cdp_ranges']
            if cdp not in ranges:
                cdp = f['unique_cdps'][0]
            unique_keys = f['unique_cdps']
            kidx = unique_keys.index(cdp)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['cdp_sort_indices'][s:e]])
                gathered_labels.extend(f['offset_sorted'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = cdp
            line_labels_list = gathered_labels[::trace_step]
        elif sort_mode == 'ffid_offset' and f.get('ffid_ranges'):
            if inline is None:
                ffid = f['unique_ffids'][0]
            else:
                ffid = inline
            ranges = f['ffid_ranges']
            if ffid not in ranges:
                ffid = f['unique_ffids'][0]
            unique_keys = f['unique_ffids']
            kidx = unique_keys.index(ffid)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['ffid_sort_indices'][s:e]])
                gathered_labels.extend(f['offset_sorted_ffid'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = ffid
            line_labels_list = gathered_labels[::trace_step]
        elif sort_mode == 'ffid_chan' and f.get('ffid_chan_ranges'):
            if inline is None:
                ffid = f['unique_ffids_chan'][0]
            else:
                ffid = inline
            ranges = f['ffid_chan_ranges']
            if ffid not in ranges:
                ffid = f['unique_ffids_chan'][0]
            unique_keys = f['unique_ffids_chan']
            kidx = unique_keys.index(ffid)
            selected_keys = unique_keys[kidx:min(kidx + num_gathers, len(unique_keys))]
            gathered_data = []
            gathered_labels = []
            for k in selected_keys:
                s, e = ranges[k]
                gathered_data.append(data[f['ffid_chan_sort_indices'][s:e]])
                gathered_labels.extend(f['chan_sorted'][s:e].tolist())
            data = np.concatenate(gathered_data, axis=0)
            n_traces_total = data.shape[0]
            trace_step = max(1, n_traces_total // max_traces)
            line_label = ffid
            line_labels_list = gathered_labels[::trace_step]
        else:
            trace_step = max(1, num_traces // max_traces)

        data_subset = data[::trace_step, ::sample_step]

        result = {
            'traces': data_subset.shape[0],
            'samples': data_subset.shape[1],
            'data': data_subset.astype(np.float32).tolist(),
            'data_min': float(data_subset.min()),
            'data_max': float(data_subset.max()),
            'trace_step': trace_step,
            'sample_step': sample_step,
            'samples_original': num_samples,
            'sample_rate': f['sample_rate'],
            'sort_mode': sort_mode,
        }

        if sort_mode == 'inline_xline' and line_label is not None:
            result['inline_label'] = line_label
            result['xline_labels'] = line_labels_list
        elif sort_mode == 'crossline_xline' and line_label is not None:
            result['crossline_label'] = line_label
            result['inline_labels'] = line_labels_list
        elif sort_mode == 'cdp_offset' and line_label is not None:
            result['cdp_label'] = line_label
            result['offset_labels'] = line_labels_list
        elif sort_mode == 'ffid_offset' and line_label is not None:
            result['ffid_label'] = line_label
            result['offset_labels_ffid'] = line_labels_list
        elif sort_mode == 'ffid_chan' and line_label is not None:
            result['ffid_label'] = line_label
            result['chan_labels'] = line_labels_list

        return result

    def compute_spectrum(self, file_id: str, trace_start: int, trace_end: int, sample_start: int, sample_end: int, use_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if use_processed and 'processed' in f else f['data']
        sample_rate_ms = f['sample_rate']
        dt_s = sample_rate_ms / 1000.0

        t_start = max(0, trace_start)
        t_end = min(data.shape[0], trace_end)
        s_start = max(0, sample_start)
        s_end = min(data.shape[1], sample_end)

        if t_end <= t_start or s_end <= s_start:
            return None

        region = data[t_start:t_end, s_start:s_end]
        num_freq = (s_end - s_start) // 2 + 1
        freqs = np.fft.rfftfreq(s_end - s_start, d=dt_s)
        amp_sum = np.zeros(num_freq, dtype=np.float64)
        spec_sum = np.zeros(num_freq, dtype=np.complex128)

        for t in range(region.shape[0]):
            spectrum = np.fft.rfft(region[t])
            amp_sum += np.abs(spectrum)
            spec_sum += spectrum

        amp_avg = (amp_sum / region.shape[0]).tolist()
        phase_avg = np.angle(spec_sum).tolist()

        return {
            'frequencies': freqs.tolist(),
            'amplitudes': [float(a) for a in amp_avg],
            'phases': [float(p) for p in phase_avg],
            'trace_range': [t_start, t_end],
            'sample_range': [s_start, s_end],
        }

    def compute_autocorrelation(self, file_id: str, trace_start: int, trace_end: int, sample_start: int, sample_end: int, use_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if use_processed and 'processed' in f else f['data']
        sample_rate_ms = f['sample_rate']

        t_start = max(0, trace_start)
        t_end = min(data.shape[0], trace_end)
        s_start = max(0, sample_start)
        s_end = min(data.shape[1], sample_end)

        if t_end <= t_start or s_end <= s_start:
            return None

        region = data[t_start:t_end, s_start:s_end]
        n_samples = s_end - s_start
        lags = np.arange(-(n_samples - 1), n_samples)

        autocors = np.zeros((region.shape[0], 2 * n_samples - 1), dtype=np.float64)
        for t in range(region.shape[0]):
            trace = region[t]
            trace = trace - np.mean(trace)
            ac = np.correlate(trace, trace, mode='full')
            center = n_samples - 1
            if ac[center] != 0:
                ac = ac / ac[center]
            autocors[t] = ac

        return {
            'lags': lags.tolist(),
            'autocorrelations': autocors.tolist(),
            'autocorrelation_sum': np.sum(autocors, axis=0).tolist(),
            'trace_range': [t_start, t_end],
            'sample_range': [s_start, s_end],
            'sample_rate': sample_rate_ms,
        }

    def compute_fx_spectrum(self, file_id: str, trace_start: int, trace_end: int, sample_start: int, sample_end: int, use_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if use_processed and 'processed' in f else f['data']
        sample_rate_ms = f['sample_rate']
        dt_s = sample_rate_ms / 1000.0

        t_start = max(0, trace_start)
        t_end = min(data.shape[0], trace_end)
        s_start = max(0, sample_start)
        s_end = min(data.shape[1], sample_end)

        if t_end <= t_start or s_end <= s_start:
            return None

        region = data[t_start:t_end, s_start:s_end]
        n_traces, n_samples = region.shape

        freqs = np.fft.rfftfreq(n_samples, d=dt_s)
        n_freqs = len(freqs)

        fx_spectrum = np.zeros((n_traces, n_freqs), dtype=np.float64)
        for t in range(n_traces):
            spec = np.fft.rfft(region[t])
            fx_spectrum[t] = np.abs(spec)

        return {
            'frequencies': freqs.tolist(),
            'fx_spectrum': fx_spectrum.tolist(),
            'trace_range': [t_start, t_end],
            'sample_range': [s_start, s_end],
            'sample_rate': sample_rate_ms,
        }

    def compute_signal_noise(self, file_id: str, trace_start: int, trace_end: int, sample_start: int, sample_end: int, use_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if use_processed and 'processed' in f else f['data']

        t_start = max(0, trace_start)
        t_end = min(data.shape[0], trace_end)
        s_start = max(0, sample_start)
        s_end = min(data.shape[1], sample_end)

        if t_end <= t_start or s_end <= s_start:
            return None

        region = data[t_start:t_end, s_start:s_end].astype(np.float64)
        n_traces, n_samples = region.shape

        max_plot_traces = 100
        max_plot_samples = 2000
        trace_step = max(1, n_traces // max_plot_traces)
        sample_step = max(1, n_samples // max_plot_samples)

        region_sub = region[::trace_step, ::sample_step]
        stack = np.mean(region, axis=0)
        stack_sub = stack[::sample_step]

        signal_rms = np.sqrt(np.mean(stack ** 2))
        residuals = region - stack[None, :]
        noise_rms_per_trace = np.sqrt(np.mean(residuals ** 2, axis=1))
        noise_rms = float(np.mean(noise_rms_per_trace))

        snr_linear = signal_rms / max(noise_rms, 1e-30)
        snr_db = 20.0 * np.log10(max(snr_linear, 1e-30))

        return {
            'snr_linear': float(snr_linear),
            'snr_db': float(snr_db),
            'signal_rms': float(signal_rms),
            'noise_rms': float(noise_rms),
            'trace_range': [t_start, t_end],
            'sample_range': [s_start, s_end],
            'traces': region_sub.astype(np.float32).tolist(),
            'stack': stack_sub.astype(np.float32).tolist(),
            'trace_step': trace_step,
            'sample_step': sample_step,
        }

    def compute_fk_spectrum(self, file_id: str, trace_start: int, trace_end: int, sample_start: int, sample_end: int, use_processed: bool = False) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None

        f = self.files[file_id]
        data = f['processed']['data'] if use_processed and 'processed' in f else f['data']
        sample_rate_ms = f['sample_rate']
        dt_s = sample_rate_ms / 1000.0

        t_start = max(0, trace_start)
        t_end = min(data.shape[0], trace_end)
        s_start = max(0, sample_start)
        s_end = min(data.shape[1], sample_end)

        if t_end <= t_start or s_end <= s_start:
            return None

        region = data[t_start:t_end, s_start:s_end]
        n_traces, n_samples = region.shape

        fk = np.fft.fftshift(np.fft.fft2(region), axes=(0, 1))
        amplitude = np.abs(fk)

        kx = np.fft.fftshift(np.fft.fftfreq(n_traces))
        freqs = np.fft.fftshift(np.fft.fftfreq(n_samples, d=dt_s))

        pos_mask = freqs >= 0
        freqs = freqs[pos_mask]
        amplitude = amplitude[:, pos_mask]

        return {
            'wavenumbers': kx.tolist(),
            'frequencies': freqs.tolist(),
            'amplitude': amplitude.T.astype(np.float64).tolist(),
            'trace_range': [t_start, t_end],
            'sample_range': [s_start, s_end],
            'sample_rate': sample_rate_ms,
        }

    def get_inline_list(self, file_id: str):
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        if 'unique_inlines' not in f:
            return {'inlines': []}
        return {
            'inlines': f['unique_inlines'],
            'default_inline': f['unique_inlines'][0] if f['unique_inlines'] else None,
        }

    def get_crossline_list(self, file_id: str):
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        if 'unique_xlines' not in f:
            return {'crosslines': []}
        return {
            'crosslines': f['unique_xlines'],
            'default_crossline': f['unique_xlines'][0] if f['unique_xlines'] else None,
        }

    def get_cdp_list(self, file_id: str):
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        if 'unique_cdps' not in f:
            return {'cdps': []}
        return {
            'cdps': f['unique_cdps'],
            'default_cdp': f['unique_cdps'][0] if f['unique_cdps'] else None,
        }

    def get_ffid_list(self, file_id: str):
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        ffids = f.get('unique_ffids')
        if not ffids:
            ffids = f.get('unique_ffids_chan')
        if not ffids:
            return {'ffids': []}
        return {
            'ffids': ffids,
            'default_ffid': ffids[0] if ffids else None,
        }

    def get_chan_list(self, file_id: str):
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        if 'unique_chans' not in f or not f['unique_chans']:
            return {'chans': []}
        return {
            'chans': f['unique_chans'],
            'default_chan': f['unique_chans'][0] if f['unique_chans'] else None,
        }

    def delete_file(self, file_id: str) -> bool:
        if file_id in self.files:
            del self.files[file_id]
        delete_file_meta(file_id)
        delete_storage(file_id)
        return True

    def list_stored_files(self):
        return db_list_files()

    def load_from_db(self, db_file_id: str) -> Optional[str]:
        meta = get_file_meta(db_file_id)
        if not meta:
            return None
        existing = [k for k, v in self.files.items() if v.get('file_name') == meta['name'] and k == db_file_id]
        if existing:
            return existing[0]
        data = load_data(db_file_id)
        if data is None:
            return None
        inline_arr, xline_arr = load_inline_xline(db_file_id)
        cdp_arr, offset_arr = load_cdp_offset(db_file_id)
        ffid_arr, _ = load_ffid_offset(db_file_id)
        orig_ffid_arr, chan_arr = load_ffid_chan(db_file_id)
        if ffid_arr is None:
            ffid_arr = orig_ffid_arr
        fp = meta.get('file_path')
        tc = meta.get('trace_count', data.shape[0])
        sp = meta.get('samples_per_trace', data.shape[1])
        need_chan = chan_arr is None or meta.get('chan_min', 0) == 0
        if need_chan and ffid_arr is not None and fp and os.path.exists(fp):
            try:
                with segyio.open(fp, 'r', ignore_geometry=True) as segyf:
                    fmt = segyf.bin[segyio.BinField.Format]
                    sample_sizes = {1: 4, 2: 4, 3: 2, 4: 4, 5: 4, 8: 1}
                    sb = sample_sizes.get(fmt, 4)
                    ts = 240 + sp * sb
                mm = np.memmap(fp, dtype='uint8', mode='r')
                chan_arr = np.ndarray(tc, dtype='>i4', buffer=mm, offset=3612, strides=(ts,)).astype(np.int32)
                del mm
                save_ffid_chan(db_file_id, ffid_arr, chan_arr)
            except Exception:
                pass
        samples = np.arange(data.shape[1])
        sort_indices = None
        inline_sorted = None
        xline_sorted = None
        unique_inlines = []
        inline_ranges = {}
        xline_sort_indices = None
        unique_xlines = []
        xline_ranges = {}
        cdp_sort_indices = None
        cdp_sorted = None
        offset_sorted = None
        unique_cdps = []
        cdp_ranges = {}
        unique_offsets = []
        ffid_sort_indices = None
        ffid_sorted = None
        offset_sorted_ffid = None
        unique_ffids = []
        ffid_ranges = {}
        unique_offsets_ffid = []
        ffid_chan_sort_indices = None
        ffid_chan_sorted = None
        chan_sorted = None
        unique_ffids_chan = []
        ffid_chan_ranges = {}
        unique_chans = []
        if inline_arr is not None and xline_arr is not None:
            sort_indices = np.lexsort((xline_arr, inline_arr))
            inline_sorted = inline_arr[sort_indices]
            xline_sorted = xline_arr[sort_indices]
            unique, counts = np.unique(inline_sorted, return_counts=True)
            start = 0
            for il, cnt in zip(unique, counts):
                inline_ranges[int(il)] = (start, start + cnt)
                start += cnt
            unique_inlines = unique.tolist()

            xline_sort_indices = np.lexsort((inline_arr, xline_arr))
            xline_sorted2 = xline_arr[xline_sort_indices]
            inline_sorted2 = inline_arr[xline_sort_indices]
            unique_x, xcounts = np.unique(xline_sorted2, return_counts=True)
            start = 0
            for xl, cnt in zip(unique_x, xcounts):
                xline_ranges[int(xl)] = (start, start + cnt)
                start += cnt
            unique_xlines = unique_x.tolist()
            inline_sorted_by_xline = inline_sorted2
        file_id = db_file_id
        if cdp_arr is not None and offset_arr is not None:
            cdp_sort_indices = np.lexsort((offset_arr, cdp_arr))
            cdp_sorted = cdp_arr[cdp_sort_indices]
            offset_sorted = offset_arr[cdp_sort_indices]
            ucdps, cdp_counts = np.unique(cdp_sorted, return_counts=True)
            start = 0
            for c, cnt in zip(ucdps, cdp_counts):
                cdp_ranges[int(c)] = (start, start + cnt)
                start += cnt
            unique_cdps = ucdps.tolist()
            unique_offsets = np.unique(offset_sorted).tolist()
        if ffid_arr is not None and offset_arr is not None:
            ffid_sort_indices = np.lexsort((offset_arr, ffid_arr))
            ffid_sorted = ffid_arr[ffid_sort_indices]
            offset_sorted_ffid = offset_arr[ffid_sort_indices]
            uffids, ffid_counts = np.unique(ffid_sorted, return_counts=True)
            start = 0
            for f_, cnt in zip(uffids, ffid_counts):
                ffid_ranges[int(f_)] = (start, start + cnt)
                start += cnt
            unique_ffids = uffids.tolist()
            unique_offsets_ffid = np.unique(offset_sorted_ffid).tolist()
        if ffid_arr is not None and chan_arr is not None:
            ffid_chan_sort_indices = np.lexsort((chan_arr, ffid_arr))
            ffid_chan_sorted = ffid_arr[ffid_chan_sort_indices]
            chan_sorted = chan_arr[ffid_chan_sort_indices]
            uffids_c, ffid_chan_counts = np.unique(ffid_chan_sorted, return_counts=True)
            start = 0
            for f_, cnt in zip(uffids_c, ffid_chan_counts):
                ffid_chan_ranges[int(f_)] = (start, start + cnt)
                start += cnt
            unique_ffids_chan = uffids_c.tolist()
            unique_chans = np.unique(chan_sorted).tolist()
        self.files[file_id] = {
            'file_name': meta['name'],
            'file_path': meta.get('file_path', ''),
            'file_size': meta.get('file_size', 0),
            'trace_count': meta.get('trace_count', data.shape[0]),
            'samples_per_trace': meta.get('samples_per_trace', data.shape[1]),
            'sample_rate': meta.get('sample_rate', 1.0),
            'min_amplitude': meta.get('min_amplitude', float(data.min())),
            'max_amplitude': meta.get('max_amplitude', float(data.max())),
            'ffid_min': meta.get('ffid_min', 0), 'ffid_max': meta.get('ffid_max', 0),
            'shot_min': meta.get('shot_min', 0), 'shot_max': meta.get('shot_max', 0),
            'cdp_min': meta.get('cdp_min', 0), 'cdp_max': meta.get('cdp_max', 0),
            'offset_min': meta.get('offset_min', 0), 'offset_max': meta.get('offset_max', 0),
            'inline_min': meta.get('inline_min', 0), 'inline_max': meta.get('inline_max', 0),
            'xline_min': meta.get('xline_min', 0), 'xline_max': meta.get('xline_max', 0),
            'data': data,
            'samples': samples,
            'sort_indices': sort_indices,
            'inline_sorted': inline_sorted,
            'xline_sorted': xline_sorted,
            'unique_inlines': unique_inlines,
            'inline_ranges': inline_ranges,
            'xline_sort_indices': xline_sort_indices,
            'unique_xlines': unique_xlines,
            'xline_ranges': xline_ranges,
            'inline_sorted_by_xline': inline_sorted_by_xline if inline_arr is not None else None,
            'offset_arr': offset_arr,
            'inline_arr': inline_arr,
            'xline_arr': xline_arr,
            'cdp_arr': cdp_arr,
            'ffid_arr': ffid_arr,
            'cdp_sort_indices': cdp_sort_indices,
            'cdp_sorted': cdp_sorted,
            'offset_sorted': offset_sorted,
            'unique_cdps': unique_cdps,
            'cdp_ranges': cdp_ranges,
            'unique_offsets': unique_offsets,
            'ffid_sort_indices': ffid_sort_indices,
            'ffid_sorted': ffid_sorted,
            'offset_sorted_ffid': offset_sorted_ffid,
            'unique_ffids': unique_ffids,
            'ffid_ranges': ffid_ranges,
            'unique_offsets_ffid': unique_offsets_ffid,
            'chan_min': int(chan_arr.min()) if chan_arr is not None else 0,
            'chan_max': int(chan_arr.max()) if chan_arr is not None else 0,
            'chan_arr': chan_arr,
            'ffid_chan_sort_indices': ffid_chan_sort_indices,
            'ffid_chan_sorted': ffid_chan_sorted,
            'chan_sorted': chan_sorted,
            'unique_ffids_chan': unique_ffids_chan,
            'ffid_chan_ranges': ffid_chan_ranges,
            'unique_chans': unique_chans,
        }
        save_file_meta(file_id, self.files[file_id])
        return file_id

    def _get_original_key_arrays(self, file_id: str):
        f = self.files[file_id]
        inline = f.get('inline_arr')
        xline = f.get('xline_arr')
        if inline is None or xline is None:
            inline, xline = load_inline_xline(file_id)
        cdp = f.get('cdp_arr')
        offset = f.get('offset_arr')
        if cdp is None or offset is None:
            cdp, offset = load_cdp_offset(file_id)
        ffid = f.get('ffid_arr')
        if ffid is None:
            ffid, _ = load_ffid_offset(file_id)
        chan = f.get('chan_arr')
        if chan is None:
            _, chan = load_ffid_chan(file_id)
        return inline, xline, cdp, offset, ffid, chan

    def _compute_sort_metadata(self, inline_arr, xline_arr, cdp_arr, offset_arr, ffid_arr, chan_arr):
        meta = {}
        if inline_arr is not None and xline_arr is not None:
            sort_indices = np.lexsort((xline_arr, inline_arr))
            inline_sorted = inline_arr[sort_indices]
            xline_sorted = xline_arr[sort_indices]
            meta['sort_indices'] = sort_indices
            meta['inline_sorted'] = inline_sorted
            meta['xline_sorted'] = xline_sorted
            unique_inlines, counts = np.unique(inline_sorted, return_counts=True)
            inline_ranges = {}
            start = 0
            for il, cnt in zip(unique_inlines, counts):
                inline_ranges[int(il)] = (start, start + cnt)
                start += cnt
            meta['unique_inlines'] = unique_inlines.tolist()
            meta['inline_ranges'] = inline_ranges
            meta['inline_min'] = int(inline_arr.min())
            meta['inline_max'] = int(inline_arr.max())

            xline_sort_indices = np.lexsort((inline_arr, xline_arr))
            xline_sorted2 = xline_arr[xline_sort_indices]
            inline_sorted2 = inline_arr[xline_sort_indices]
            meta['xline_sort_indices'] = xline_sort_indices
            meta['inline_sorted_by_xline'] = inline_sorted2
            unique_xlines, xcounts = np.unique(xline_sorted2, return_counts=True)
            xline_ranges = {}
            start = 0
            for xl, cnt in zip(unique_xlines, xcounts):
                xline_ranges[int(xl)] = (start, start + cnt)
                start += cnt
            meta['unique_xlines'] = unique_xlines.tolist()
            meta['xline_ranges'] = xline_ranges
            meta['xline_min'] = int(xline_arr.min())
            meta['xline_max'] = int(xline_arr.max())

        if cdp_arr is not None and offset_arr is not None:
            cdp_sort_indices = np.lexsort((offset_arr, cdp_arr))
            meta['cdp_sort_indices'] = cdp_sort_indices
            meta['cdp_sorted'] = cdp_arr[cdp_sort_indices]
            meta['offset_sorted'] = offset_arr[cdp_sort_indices]
            unique_cdps, cdp_counts = np.unique(cdp_arr[cdp_sort_indices], return_counts=True)
            cdp_ranges = {}
            start = 0
            for c, cnt in zip(unique_cdps, cdp_counts):
                cdp_ranges[int(c)] = (start, start + cnt)
                start += cnt
            meta['unique_cdps'] = unique_cdps.tolist()
            meta['cdp_ranges'] = cdp_ranges
            meta['unique_offsets'] = np.unique(offset_arr[cdp_sort_indices]).tolist()
            meta['cdp_min'] = int(cdp_arr.min())
            meta['cdp_max'] = int(cdp_arr.max())
            meta['offset_min'] = int(offset_arr.min())
            meta['offset_max'] = int(offset_arr.max())

        if ffid_arr is not None and offset_arr is not None:
            ffid_sort_indices = np.lexsort((offset_arr, ffid_arr))
            meta['ffid_sort_indices'] = ffid_sort_indices
            meta['ffid_sorted'] = ffid_arr[ffid_sort_indices]
            meta['offset_sorted_ffid'] = offset_arr[ffid_sort_indices]
            unique_ffids, ffid_counts = np.unique(ffid_arr[ffid_sort_indices], return_counts=True)
            ffid_ranges = {}
            start = 0
            for f_, cnt in zip(unique_ffids, ffid_counts):
                ffid_ranges[int(f_)] = (start, start + cnt)
                start += cnt
            meta['unique_ffids'] = unique_ffids.tolist()
            meta['ffid_ranges'] = ffid_ranges
            meta['unique_offsets_ffid'] = np.unique(offset_arr[ffid_sort_indices]).tolist()
            meta['ffid_min'] = int(ffid_arr.min())
            meta['ffid_max'] = int(ffid_arr.max())

        if ffid_arr is not None and chan_arr is not None:
            ffid_chan_sort_indices = np.lexsort((chan_arr, ffid_arr))
            meta['ffid_chan_sort_indices'] = ffid_chan_sort_indices
            meta['ffid_chan_sorted'] = ffid_arr[ffid_chan_sort_indices]
            meta['chan_sorted'] = chan_arr[ffid_chan_sort_indices]
            unique_ffids_chan, ffid_chan_counts = np.unique(ffid_arr[ffid_chan_sort_indices], return_counts=True)
            ffid_chan_ranges = {}
            start = 0
            for f_, cnt in zip(unique_ffids_chan, ffid_chan_counts):
                ffid_chan_ranges[int(f_)] = (start, start + cnt)
                start += cnt
            meta['unique_ffids_chan'] = unique_ffids_chan.tolist()
            meta['ffid_chan_ranges'] = ffid_chan_ranges
            meta['unique_chans'] = np.unique(chan_arr[ffid_chan_sort_indices]).tolist()
            meta['chan_min'] = int(chan_arr.min())
            meta['chan_max'] = int(chan_arr.max())

        return meta

    def apply_input_sort(self, file_id: str, sort_type: str = 'none', first_min=None, first_max=None, second_min=None, second_max=None) -> Optional[Dict[str, Any]]:
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        data = np.asarray(f['data'])
        n_traces = data.shape[0]

        inline, xline, cdp, offset, ffid, chan = self._get_original_key_arrays(file_id)

        sort_type = (sort_type or 'none').strip() or 'none'
        if sort_type == 'none':
            indices = np.arange(n_traces, dtype=int)
        else:
            key_map = {
                'inline_xline': ('inline', 'xline'),
                'crossline_xline': ('xline', 'inline'),
                'cdp_offset': ('cdp', 'offset'),
                'ffid_offset': ('ffid', 'offset'),
                'ffid_chan': ('ffid', 'chan'),
            }
            if sort_type not in key_map:
                raise ValueError(f"Unknown sort type: {sort_type}")
            k1_name, k2_name = key_map[sort_type]
            arrays = {'inline': inline, 'xline': xline, 'cdp': cdp, 'offset': offset, 'ffid': ffid, 'chan': chan}
            k1 = arrays[k1_name]
            k2 = arrays[k2_name]
            if k1 is None or k2 is None or len(k1) != n_traces or len(k2) != n_traces:
                raise ValueError(f"sorting keys '{k1_name}' and '{k2_name}' are not available for this file")
            mask = np.ones(n_traces, dtype=bool)
            if first_min is not None:
                mask &= (k1 >= first_min)
            if first_max is not None:
                mask &= (k1 <= first_max)
            if second_min is not None:
                mask &= (k2 >= second_min)
            if second_max is not None:
                mask &= (k2 <= second_max)
            selected = np.where(mask)[0]
            if len(selected) == 0:
                raise ValueError("No traces match the selected sorting key ranges")
            order = np.lexsort((k2[selected], k1[selected]))
            indices = selected[order].astype(int)

        indices = np.asarray(indices, dtype=int)
        if len(indices) == 0:
            raise ValueError("No traces match the selected sorting key ranges")

        new_data = data[indices]
        if inline is not None and len(inline) == n_traces:
            inline = inline[indices]
        if xline is not None and len(xline) == n_traces:
            xline = xline[indices]
        if cdp is not None and len(cdp) == n_traces:
            cdp = cdp[indices]
        if offset is not None and len(offset) == n_traces:
            offset = offset[indices]
        if ffid is not None and len(ffid) == n_traces:
            ffid = ffid[indices]
        if chan is not None and len(chan) == n_traces:
            chan = chan[indices]

        meta = self._compute_sort_metadata(inline, xline, cdp, offset, ffid, chan)
        f['data'] = new_data
        f['trace_count'] = int(len(indices))
        f['samples_per_trace'] = int(new_data.shape[1])
        f['min_amplitude'] = float(new_data.min())
        f['max_amplitude'] = float(new_data.max())
        f['inline_arr'] = inline
        f['xline_arr'] = xline
        f['cdp_arr'] = cdp
        f['offset_arr'] = offset
        f['ffid_arr'] = ffid
        f['chan_arr'] = chan
        f.update(meta)
        f.pop('processed', None)
        return {'status': 'ok', 'traces': int(len(indices)), 'sort_type': sort_type}

    def save_processed_to_db(self, file_id: str, output_name: str) -> Optional[str]:
        if file_id not in self.files:
            return None
        f = self.files[file_id]
        has_processed = 'processed' in f and f['processed'] is not None
        data = f['processed']['data'] if has_processed else f['data']
        new_id = f'{file_id}_proc_{len([x for x in self.list_stored_files() if x["source_file_id"] == file_id])}'
        save_data(new_id, data)

        inline_arr, xline_arr, cdp_arr, offset_arr, ffid_arr, chan_arr = self._get_original_key_arrays(file_id)

        if inline_arr is not None and xline_arr is not None:
            save_inline_xline(new_id, inline_arr, xline_arr)
        if cdp_arr is not None and offset_arr is not None:
            save_cdp_offset(new_id, cdp_arr, offset_arr)
        if ffid_arr is not None and offset_arr is not None:
            save_ffid_offset(new_id, ffid_arr, offset_arr)
        if ffid_arr is not None and chan_arr is not None:
            save_ffid_chan(new_id, ffid_arr, chan_arr)

        npy_path = storage_data_path(new_id)
        file_size = os.path.getsize(npy_path) if os.path.exists(npy_path) else 0
        meta = {
            'file_name': output_name,
            'file_path': '',
            'file_size': file_size,
            'trace_count': data.shape[0],
            'samples_per_trace': data.shape[1],
            'sample_rate': f.get('sample_rate', 1.0),
            'min_amplitude': float(data.min()),
            'max_amplitude': float(data.max()),
            'ffid_min': f.get('ffid_min', 0), 'ffid_max': f.get('ffid_max', 0),
            'shot_min': f.get('shot_min', 0), 'shot_max': f.get('shot_max', 0),
            'cdp_min': f.get('cdp_min', 0), 'cdp_max': f.get('cdp_max', 0),
            'offset_min': f.get('offset_min', 0), 'offset_max': f.get('offset_max', 0),
            'inline_min': f.get('inline_min', 0), 'inline_max': f.get('inline_max', 0),
            'xline_min': f.get('xline_min', 0), 'xline_max': f.get('xline_max', 0),
            'chan_min': f.get('chan_min', 0), 'chan_max': f.get('chan_max', 0),
            'is_processed': has_processed,
            'source_file_id': file_id,
            'processing_desc': f.get('processed', {}).get('type', '') if has_processed else '',
        }
        save_file_meta(new_id, meta)
        return new_id


    def get_time_slice(self, file_id: str, sample: int, max_cells: int = 500000) -> Optional[Dict[str, Any]]:
        if file_id not in self.files or 'sort_indices' not in self.files[file_id]:
            return None

        f = self.files[file_id]
        data = f['data']
        if sample < 0 or sample >= data.shape[1]:
            return None

        inline_sorted = f['inline_sorted']
        xline_sorted = f['xline_sorted']
        inline_ranges = f['inline_ranges']
        unique_inlines = f['unique_inlines']
        unique_xlines = sorted(np.unique(xline_sorted).tolist())

        xline_to_col = {xl: i for i, xl in enumerate(unique_xlines)}
        matrix = np.full((len(unique_inlines), len(unique_xlines)), np.nan)

        for inline_idx, inline in enumerate(unique_inlines):
            start, end = inline_ranges[inline]
            for i in range(start, end):
                xl = int(xline_sorted[i])
                col = xline_to_col.get(xl)
                if col is not None:
                    matrix[inline_idx, col] = float(data[i, sample])

        inline_step = max(1, len(unique_inlines) // 200) if len(unique_inlines) > 200 else 1
        xline_step = max(1, len(unique_xlines) // 200) if len(unique_xlines) > 200 else 1
        if len(unique_inlines) * len(unique_xlines) > max_cells:
            ratio = ((len(unique_inlines) * len(unique_xlines)) / max_cells) ** 0.5
            inline_step = max(1, int(ratio))
            xline_step = max(1, int(ratio))

        matrix = matrix[::inline_step, ::xline_step]
        result_inlines = unique_inlines[::inline_step]
        result_xlines = unique_xlines[::xline_step]

        data_series = []
        for xl_idx in range(matrix.shape[1]):
            col = []
            for il_idx in range(matrix.shape[0]):
                v = matrix[il_idx, xl_idx]
                col.append(v if not np.isnan(v) else None)
            data_series.append(col)

        return {
            'traces': matrix.shape[1],
            'samples': matrix.shape[0],
            'data': data_series,
            'xline_labels': result_xlines,
            'inline_labels': result_inlines,
            'sort_mode': 'time_slice',
            'selected_sample': sample,
            'samples_original': data.shape[1],
        }


sgy_handler = SGYHandler()