import { AVAILABLE_MODULES, SORT_OPTIONS, SORT_KEY_LABELS, DSIN_SAMPLE_RATES } from './moduleDefinitions'
export default function ModuleParameters({ mod, idx, updateParam }) {
  return (<>
{mod.id === 'fxdecont' && (
                <>
                  <div className="module-param">
                    <label className="param-label">Forward order</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="100" step="1"
                      value={mod.params.predOrder} onChange={(e) => updateParam(idx, 'predOrder', Math.max(1, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Backward order</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="100" step="1"
                      value={mod.params.retroOrder} onChange={(e) => updateParam(idx, 'retroOrder', Math.max(1, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Regularization</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1" step="0.001"
                      value={mod.params.reg} onChange={(e) => updateParam(idx, 'reg', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Window size</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="3" max="501" step="2"
                      value={mod.params.windowSize} onChange={(e) => updateParam(idx, 'windowSize', Math.max(3, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Step</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="50" step="1"
                      value={mod.params.step} onChange={(e) => updateParam(idx, 'step', Math.max(1, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Freq min (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" step="0.1"
                      value={mod.params.freqMin} onChange={(e) => updateParam(idx, 'freqMin', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Freq max (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" step="0.1" placeholder="Nyquist"
                      value={mod.params.freqMax} onChange={(e) => updateParam(idx, 'freqMax', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <label className="toggle-row" style={{ fontSize: '12px', padding: '4px 0' }}>
                    <span>Nonlinear +</span>
                    <label className="toggle-switch">
                      <input type="checkbox" checked={mod.params.nonlinearPlus} onChange={(e) => updateParam(idx, 'nonlinearPlus', e.target.checked)} disabled={!mod.enabled} />
                      <span className="toggle-slider"></span>
                    </label>
                  </label>
                </>
              )}
              {mod.id === 'fxdecon' && (
                <div className="module-param">
                  <label className="param-label">Filter length</label>
                  <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="50" step="1"
                    value={mod.params.filterLength} onChange={(e) => updateParam(idx, 'filterLength', Math.max(1, Math.min(50, Number(e.target.value))))} disabled={!mod.enabled} />
                </div>
              )}
              {mod.id === 'decons' && (
                <>
                  <div className="module-param">
                    <label className="param-label">Operator length</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="500" step="1"
                      value={mod.params.operatorLength} onChange={(e) => updateParam(idx, 'operatorLength', Math.max(1, Math.min(500, Number(e.target.value))))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Prewhitening (%)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="100" step="0.1"
                      value={mod.params.prewhitening} onChange={(e) => updateParam(idx, 'prewhitening', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Phase mode</label>
                    <div className="mode-selector" style={{ marginTop: '4px' }}>
                      <span className={`mode-option${mod.params.phaseMode === 'minimum' ? ' active' : ''}`}
                        onClick={() => !mod.enabled ? null : updateParam(idx, 'phaseMode', 'minimum')}>Min</span>
                      <span className={`mode-option${mod.params.phaseMode === 'zero' ? ' active' : ''}`}
                        onClick={() => !mod.enabled ? null : updateParam(idx, 'phaseMode', 'zero')}>Zero</span>
                    </div>
                  </div>
                  <div className="module-param">
                    <label className="param-label">Bandwidth min (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" step="1"
                      value={mod.params.bandwidthMin} onChange={(e) => updateParam(idx, 'bandwidthMin', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Bandwidth max (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" step="1"
                      value={mod.params.bandwidthMax} onChange={(e) => updateParam(idx, 'bandwidthMax', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                </>
              )}
              {mod.id === 'agc' && (
                <div className="module-param">
                  <label className="param-label">Window length (ms)</label>
                  <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="10000"
                    value={mod.params.windowMs} onChange={(e) => updateParam(idx, 'windowMs', Math.max(1, Number(e.target.value)))} disabled={!mod.enabled} />
                </div>
              )}
              {mod.id === 'psf' && (
                <div className="module-param">
                  <label className="param-label">Phase shift (deg)</label>
                  <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="-360" max="360" step="0.1"
                    value={mod.params.phaseDeg} onChange={(e) => updateParam(idx, 'phaseDeg', Number(e.target.value))} disabled={!mod.enabled} />
                </div>
              )}
              {mod.id === 'bandpass' && (
                <>
                  <div className="module-param">
                    <label className="param-label">Low cut (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.lowcut} onChange={(e) => updateParam(idx, 'lowcut', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Low pass (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.lowpass} onChange={(e) => updateParam(idx, 'lowpass', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">High pass (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.highpass} onChange={(e) => updateParam(idx, 'highpass', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">High cut (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.highcut} onChange={(e) => updateParam(idx, 'highcut', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                </>
              )}
              {mod.id === 'fk3d' && (
                <>
                  <div className="module-param">
                    <label className="param-label">Inline window</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="4" max="500" step="2"
                      value={mod.params.wndwInline} onChange={(e) => updateParam(idx, 'wndwInline', Math.max(4, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Xline window</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="4" max="500" step="2"
                      value={mod.params.wndwXline} onChange={(e) => updateParam(idx, 'wndwXline', Math.max(4, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Overlap inline</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="250" step="1"
                      value={mod.params.overlapInline} onChange={(e) => updateParam(idx, 'overlapInline', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Overlap xline</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="250" step="1"
                      value={mod.params.overlapXline} onChange={(e) => updateParam(idx, 'overlapXline', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Min dip inline</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="-100" max="100" step="0.5"
                      value={mod.params.minDipInline} onChange={(e) => updateParam(idx, 'minDipInline', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Max dip inline</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="-100" max="100" step="0.5"
                      value={mod.params.maxDipInline} onChange={(e) => updateParam(idx, 'maxDipInline', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Min dip xline</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="-100" max="100" step="0.5"
                      value={mod.params.minDipXline} onChange={(e) => updateParam(idx, 'minDipXline', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Max dip xline</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="-100" max="100" step="0.5"
                      value={mod.params.maxDipXline} onChange={(e) => updateParam(idx, 'maxDipXline', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Taper %</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="100" step="1"
                      value={mod.params.pctDipTaper} onChange={(e) => updateParam(idx, 'pctDipTaper', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <label className="toggle-row" style={{ fontSize: '12px', padding: '4px 0' }}>
                    <span>Wrap filter</span>
                    <label className="toggle-switch">
                      <input type="checkbox" checked={mod.params.wrapFilt} onChange={(e) => updateParam(idx, 'wrapFilt', e.target.checked)} disabled={!mod.enabled} />
                      <span className="toggle-slider"></span>
                    </label>
                  </label>
                </>
              )}
              {mod.id === 'gain' && (
                <>
                  <div className="module-param">
                    <label className="param-label">V exponent</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="10" step="0.1"
                      value={mod.params.voption} onChange={(e) => updateParam(idx, 'voption', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">T exponent</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="10" step="0.1"
                      value={mod.params.toption} onChange={(e) => updateParam(idx, 'toption', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Scale factor</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.01"
                      value={mod.params.factor} onChange={(e) => updateParam(idx, 'factor', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Velocity units</label>
                    <div className="mode-selector" style={{ marginTop: '4px' }}>
                      <span className={`mode-option${mod.params.units === 'feet' ? ' active' : ''}`}
                        onClick={() => !mod.enabled ? null : updateParam(idx, 'units', 'feet')}>Feet</span>
                      <span className={`mode-option${mod.params.units === 'meters' ? ' active' : ''}`}
                        onClick={() => !mod.enabled ? null : updateParam(idx, 'units', 'meters')}>Meters</span>
                    </div>
                  </div>
                </>
              )}
              {mod.id === 'lfaf' && (
                <>
                  <div className="module-param">
                    <label className="param-label">Trace spacing</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0.1" max="1000" step="0.1"
                      value={mod.params.dx} onChange={(e) => updateParam(idx, 'dx', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Ground roll vel</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="10000" step="1"
                      value={mod.params.vel} onChange={(e) => updateParam(idx, 'vel', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Low freq (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.f1} onChange={(e) => updateParam(idx, 'f1', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">High freq (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.f2} onChange={(e) => updateParam(idx, 'f2', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Taper (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="500" step="0.1"
                      value={mod.params.ftaper} onChange={(e) => updateParam(idx, 'ftaper', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Max mix traces</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="1"
                      value={mod.params.maxmix} onChange={(e) => updateParam(idx, 'maxmix', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                </>
              )}
              {mod.id === 'lfaf1' && (
                <>
                  <div className="module-param">
                    <label className="param-label">Ground roll vel</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="10000" step="1"
                      value={mod.params.vel} onChange={(e) => updateParam(idx, 'vel', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Low freq (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.f1} onChange={(e) => updateParam(idx, 'f1', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">High freq (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.f2} onChange={(e) => updateParam(idx, 'f2', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Taper (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="500" step="0.1"
                      value={mod.params.ftaper} onChange={(e) => updateParam(idx, 'ftaper', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Max mix traces</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="1"
                      value={mod.params.maxmix} onChange={(e) => updateParam(idx, 'maxmix', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Min offset</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="10000" step="1"
                      value={mod.params.minOffset} onChange={(e) => updateParam(idx, 'minOffset', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Mute time (ms)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="10000" step="10"
                      value={mod.params.muteTime} onChange={(e) => updateParam(idx, 'muteTime', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Mute zone width</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="10000" step="10"
                      value={mod.params.muteZoneWidth} onChange={(e) => updateParam(idx, 'muteZoneWidth', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                </>
              )}
              {mod.id === 'lfafn' && (
                <>
                  <div className="module-param">
                    <label className="param-label">Trace spacing</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0.1" max="1000" step="0.1"
                      value={mod.params.dx} onChange={(e) => updateParam(idx, 'dx', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Ground roll vel</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" max="10000" step="1"
                      value={mod.params.vel} onChange={(e) => updateParam(idx, 'vel', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Low freq (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.f1} onChange={(e) => updateParam(idx, 'f1', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">High freq (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="0.1"
                      value={mod.params.f2} onChange={(e) => updateParam(idx, 'f2', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Taper (Hz)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="500" step="0.1"
                      value={mod.params.ftaper} onChange={(e) => updateParam(idx, 'ftaper', Number(e.target.value))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Max mix traces</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1000" step="1"
                      value={mod.params.maxmix} onChange={(e) => updateParam(idx, 'maxmix', Math.max(0, Number(e.target.value)))} disabled={!mod.enabled} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Direction</label>
                    <div className="mode-selector" style={{ marginTop: '4px' }}>
                      <span className={`mode-option${mod.params.direction === 'both' ? ' active' : ''}`}
                        onClick={() => !mod.enabled ? null : updateParam(idx, 'direction', 'both')}>Both</span>
                      <span className={`mode-option${mod.params.direction === 'positive' ? ' active' : ''}`}
                        onClick={() => !mod.enabled ? null : updateParam(idx, 'direction', 'positive')}>Positive</span>
                      <span className={`mode-option${mod.params.direction === 'negative' ? ' active' : ''}`}
                        onClick={() => !mod.enabled ? null : updateParam(idx, 'direction', 'negative')}>Negative</span>
                    </div>
                  </div>
                  <div className="module-param">
                    <label className="param-label">Attenuation</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="0" max="1" step="0.01"
                      value={mod.params.attenuation} onChange={(e) => updateParam(idx, 'attenuation', Math.max(0, Math.min(1, Number(e.target.value))))} disabled={!mod.enabled} />
                  </div>
                </>
              )}
              {mod.id === 'dsin' && (
                <>
                  <div className="module-param">
                    <label className="param-label">File path</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="text"
                      value={mod.params.path} onChange={(e) => updateParam(idx, 'path', e.target.value)} disabled={!mod.enabled}
                      placeholder="/path/to/input.sgy" style={{ width: '100%' }} />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Trace length (samples)</label>
                    <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" min="1" step="1"
                      value={mod.params.traceLen} onChange={(e) => updateParam(idx, 'traceLen', e.target.value)} disabled={!mod.enabled}
                      placeholder="As input" />
                  </div>
                  <div className="module-param">
                    <label className="param-label">Sample rate (ms)</label>
                    <select className={`param-select ${!mod.enabled ? 'param-disabled' : ''}`} value={mod.params.sampleRate}
                      onChange={(e) => updateParam(idx, 'sampleRate', e.target.value)} disabled={!mod.enabled} style={{ width: '100%' }}>
                      <option value="">As input</option>
                      {DSIN_SAMPLE_RATES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
                </>
              )}
              {mod.id === 'dsout' && (() => {
                const keys = SORT_KEY_LABELS[mod.params.sortType]
                return (
                  <>
                    <div className="module-param">
                      <label className="param-label">Output path</label>
                      <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="text"
                        value={mod.params.path} onChange={(e) => updateParam(idx, 'path', e.target.value)} disabled={!mod.enabled}
                        placeholder="/path/to/output.sgy" style={{ width: '100%' }} />
                    </div>
                    <div className="module-param">
                      <label className="param-label">Sort order</label>
                      <select className={`param-select ${!mod.enabled ? 'param-disabled' : ''}`} value={mod.params.sortType}
                        onChange={(e) => updateParam(idx, 'sortType', e.target.value)} disabled={!mod.enabled} style={{ width: '100%' }}>
                        {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </div>
                    {keys && (
                      <>
                        <div className="module-param">
                          <label className="param-label">{keys.first} range (first key)</label>
                          <div className="param-row" style={{ gap: '6px' }}>
                            <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" placeholder="min"
                              value={mod.params.firstMin} onChange={(e) => updateParam(idx, 'firstMin', e.target.value)} disabled={!mod.enabled} />
                            <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" placeholder="max"
                              value={mod.params.firstMax} onChange={(e) => updateParam(idx, 'firstMax', e.target.value)} disabled={!mod.enabled} />
                          </div>
                        </div>
                        <div className="module-param">
                          <label className="param-label">{keys.second} range (second key)</label>
                          <div className="param-row" style={{ gap: '6px' }}>
                            <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" placeholder="min"
                              value={mod.params.secondMin} onChange={(e) => updateParam(idx, 'secondMin', e.target.value)} disabled={!mod.enabled} />
                            <input className={`param-input ${!mod.enabled ? 'param-disabled' : ''}`} type="number" placeholder="max"
                              value={mod.params.secondMax} onChange={(e) => updateParam(idx, 'secondMax', e.target.value)} disabled={!mod.enabled} />
                          </div>
                        </div>
                      </>
                    )}
                  </>
                )
              })()}
  </>)
}
