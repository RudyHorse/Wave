export function serializeModule(mod) {
  const steps = []
  if (mod.id === 'fxdecont') {
        steps.push({ type: 'fxdecont', title: mod.title, params: { pred_order: mod.params.predOrder, retro_order: mod.params.retroOrder, reg: mod.params.reg, window_size: mod.params.windowSize, step: mod.params.step, nonlinear_plus: mod.params.nonlinearPlus, freq_min: mod.params.freqMin, freq_max: mod.params.freqMax } })
      } else if (mod.id === 'fxdecon') {
        steps.push({ type: 'fxdecon', title: mod.title, params: { filter_length: mod.params.filterLength } })
      } else if (mod.id === 'decons') {
        steps.push({ type: 'decons', title: mod.title, params: { operator_length: mod.params.operatorLength, prewhitening: mod.params.prewhitening, phase_mode: mod.params.phaseMode, bandwidth_min: mod.params.bandwidthMin, bandwidth_max: mod.params.bandwidthMax } })
      } else if (mod.id === 'agc') {
        steps.push({ type: 'agc', title: mod.title, params: { window_ms: mod.params.windowMs } })
      } else if (mod.id === 'psf') {
        steps.push({ type: 'psf', title: mod.title, params: { phase_deg: mod.params.phaseDeg } })
      } else if (mod.id === 'bandpass') {
        steps.push({ type: 'bandpass', title: mod.title, params: { lowcut: mod.params.lowcut, lowpass: mod.params.lowpass, highpass: mod.params.highpass, highcut: mod.params.highcut } })
      } else if (mod.id === 'resample') {
        steps.push({ type: 'resample', title: mod.title, params: { sample_interval: mod.params.sampleInterval === '' ? null : Number(mod.params.sampleInterval), start_time: mod.params.startTime === '' ? null : Number(mod.params.startTime), end_time: mod.params.endTime === '' ? null : Number(mod.params.endTime) } })
      } else if (mod.id === 'suppres') {
        steps.push({ type: 'suppres', title: mod.title, params: { fbeg_hz: Number(mod.params.fbeg), fend_hz: Number(mod.params.fend), factor: Number(mod.params.factor), tsmt_ms: Number(mod.params.tsmt), taper_ms: Number(mod.params.taper), gates_text: (mod.params.gates || '').trim() || null } })
      } else if (mod.id === 'nmo') {
        steps.push({ type: 'nmo', title: mod.title, params: { velocity_file_id: mod.params.velocityFileId || null, geometry: { offset_units: mod.params.offsetUnits, offset_convention: mod.params.offsetConvention, start_time_ms: Number(mod.params.startTimeMs) || 0 }, interpolation: mod.params.interpolation, sinc_half_width: 8, stretch_limit: (Number(mod.params.stretchLimit) || 30) / 100, stretch_taper: (Number(mod.params.stretchTaper) || 0) / 100, min_offset_m: Number(mod.params.minOffset) || 0, max_offset_m: mod.params.maxOffset === '' ? null : Number(mod.params.maxOffset), cdp_min: mod.params.cdpMin === '' ? null : Number(mod.params.cdpMin), cdp_max: mod.params.cdpMax === '' ? null : Number(mod.params.cdpMax), inline: mod.params.inline === '' ? null : Number(mod.params.inline) } })
      } else if (mod.id === 'stack') {
        steps.push({ type: 'stack', title: mod.title, params: { method: mod.params.method, trim_fraction: (Number(mod.params.trim) || 0) / 100, min_fold: Number(mod.params.minFold) || 1, input_already_nmo: !!mod.params.alreadyNmo } })
      } else if (mod.id === 'fk3d') {
        steps.push({ type: 'fk3d', title: mod.title, params: { wndw_inline: mod.params.wndwInline, wndw_xline: mod.params.wndwXline, overlap_inline: mod.params.overlapInline, overlap_xline: mod.params.overlapXline, min_dip_inline: mod.params.minDipInline, max_dip_inline: mod.params.maxDipInline, min_dip_xline: mod.params.minDipXline, max_dip_xline: mod.params.maxDipXline, pct_dip_taper: mod.params.pctDipTaper, wrap_filt: mod.params.wrapFilt } })
      } else if (mod.id === 'gain') {
        steps.push({ type: 'gain', title: mod.title, params: { voption: mod.params.voption, toption: mod.params.toption, factor: mod.params.factor, units: mod.params.units } })
      } else if (mod.id === 'lfaf') {
        steps.push({ type: 'lfaf', title: mod.title, params: { dx: mod.params.dx, vel: mod.params.vel, f1: mod.params.f1, f2: mod.params.f2, ftaper: mod.params.ftaper, maxmix: mod.params.maxmix } })
      } else if (mod.id === 'lfaf1') {
        steps.push({ type: 'lfaf1', title: mod.title, params: { vel: mod.params.vel, f1: mod.params.f1, f2: mod.params.f2, ftaper: mod.params.ftaper, maxmix: mod.params.maxmix, min_offset: mod.params.minOffset, mute_time: mod.params.muteTime, mute_zone_width: mod.params.muteZoneWidth } })
      } else if (mod.id === 'lfafn') {
        steps.push({ type: 'lfafn', title: mod.title, params: { dx: mod.params.dx, vel: mod.params.vel, f1: mod.params.f1, f2: mod.params.f2, ftaper: mod.params.ftaper, maxmix: mod.params.maxmix, direction: mod.params.direction, attenuation: mod.params.attenuation } })
      } else if (mod.id === 'dsout') {
        steps.push({ type: 'dsout', title: mod.title, params: { path: mod.params.path, sort_type: mod.params.sortType, first_min: mod.params.firstMin, first_max: mod.params.firstMax, second_min: mod.params.secondMin, second_max: mod.params.secondMax } })
      }
  return steps[0] || null
}
