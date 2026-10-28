export const AVAILABLE_MODULES = [
  { id: 'dsin', title: 'DSIN', params: { path: '', traceLen: '', sampleRate: '' } },
  { id: 'fxdecont', title: 'FX-Decon-T', params: { predOrder: 10, retroOrder: 10, reg: 0.01, windowSize: 51, step: 1, nonlinearPlus: false, freqMin: 0, freqMax: 0 } },
  { id: 'fxdecon', title: 'FX-Decon', params: { filterLength: 5 } },
  { id: 'decons', title: 'DeconS', params: { operatorLength: 100, prewhitening: 0.1, phaseMode: 'minimum', bandwidthMin: 0, bandwidthMax: 0 } },
  { id: 'agc', title: 'AGC', params: { windowMs: 100 } },
  { id: 'psf', title: 'PSF', params: { phaseDeg: 30 } },
  { id: 'bandpass', title: 'Bandpass Filter', params: { lowcut: 5, lowpass: 10, highpass: 80, highcut: 100 } },
  { id: 'resample', title: 'Resample', params: { sampleInterval: '', startTime: '', endTime: '' } },
  { id: 'suppres', title: 'SUPPRES', params: { fbeg: 3, fend: 18, factor: 0.5, tsmt: 60, taper: 120, gates: '' } },
  { id: 'ampscal', title: 'AMPSCAL', params: { nTraces: 5, fmin: 5, fmax: 80, mode: 'spectral_median', threshold: 1.5, strength: 1, transition: 0, edge: 'shift', groupByFfid: true } },
  { id: 'nmo', title: 'NMO', params: { velocityFileId: '', offsetUnits: 'm', offsetConvention: 'full', startTimeMs: 0, interpolation: 'linear', stretchLimit: 30, stretchTaper: 5, minOffset: 0, maxOffset: '', cdpMin: '', cdpMax: '', inline: '' } },
  { id: 'stack', title: 'STACK', params: { method: 'mean', trim: 10, minFold: 1, alreadyNmo: false } },
  { id: 'fk3d', title: 'FK3D Dip Filter', params: { wndwInline: 48, wndwXline: 48, overlapInline: 12, overlapXline: 12, minDipInline: -12, maxDipInline: 12, minDipXline: -12, maxDipXline: 12, pctDipTaper: 10, wrapFilt: true } },
  { id: 'gain', title: 'GAIN', params: { voption: 2.0, toption: 1.0, factor: 1.0, units: 'feet' } },
  { id: 'lfaf', title: 'LFAF', params: { dx: 25, vel: 1500, f1: 0, f2: 20, ftaper: 5, maxmix: 0 } },
  { id: 'lfaf1', title: 'LFAF-1', params: { vel: 1500, f1: 0, f2: 20, ftaper: 5, maxmix: 15, minOffset: 10, muteTime: 0, muteZoneWidth: 50 } },
  { id: 'lfafn', title: 'LFAFN', params: { dx: 25, vel: 1500, f1: 0, f2: 20, ftaper: 5, maxmix: 0, direction: 'both', attenuation: 1 } },
  { id: 'dsout', title: 'DSOUT', params: { path: '', sortType: 'none', firstMin: '', firstMax: '', secondMin: '', secondMax: '' } },
]

export const SORT_OPTIONS = [
  { value: 'none', label: 'None (input order)' },
  { value: 'inline_xline', label: 'Inline / Xline' },
  { value: 'crossline_xline', label: 'Xline / Inline' },
  { value: 'cdp_offset', label: 'CDP / Offset' },
  { value: 'ffid_offset', label: 'FFID / Offset' },
  { value: 'ffid_chan', label: 'FFID / Chan' },
]

export const SORT_KEY_LABELS = {
  inline_xline: { first: 'Inline', second: 'Xline' },
  crossline_xline: { first: 'Xline', second: 'Inline' },
  cdp_offset: { first: 'CDP', second: 'Offset' },
  ffid_offset: { first: 'FFID', second: 'Offset' },
  ffid_chan: { first: 'FFID', second: 'Chan' },
}

export const DSIN_SAMPLE_RATES = [0.5, 1, 2, 4, 8]

