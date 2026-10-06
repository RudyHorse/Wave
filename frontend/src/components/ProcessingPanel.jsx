import { useState, useRef } from 'react'

const AVAILABLE_MODULES = [
  { id: 'dsin', title: 'DSIN', params: { path: '', traceLen: '', sampleRate: '' } },
  { id: 'fxdecont', title: 'FX-Decon-T', params: { predOrder: 10, retroOrder: 10, reg: 0.01, windowSize: 51, step: 1, nonlinearPlus: false, freqMin: 0, freqMax: 0 } },
  { id: 'fxdecon', title: 'FX-Decon', params: { filterLength: 5 } },
  { id: 'decons', title: 'DeconS', params: { operatorLength: 100, prewhitening: 0.1, phaseMode: 'minimum', bandwidthMin: 0, bandwidthMax: 0 } },
  { id: 'agc', title: 'AGC', params: { windowMs: 100 } },
  { id: 'psf', title: 'PSF', params: { phaseDeg: 30 } },
  { id: 'bandpass', title: 'Bandpass Filter', params: { lowcut: 5, lowpass: 10, highpass: 80, highcut: 100 } },
  { id: 'fk3d', title: 'FK3D Dip Filter', params: { wndwInline: 48, wndwXline: 48, overlapInline: 12, overlapXline: 12, minDipInline: -12, maxDipInline: 12, minDipXline: -12, maxDipXline: 12, pctDipTaper: 10, wrapFilt: true } },
  { id: 'gain', title: 'GAIN', params: { voption: 2.0, toption: 1.0, factor: 1.0, units: 'feet' } },
  { id: 'lfaf', title: 'LFAF', params: { dx: 25, vel: 1500, f1: 0, f2: 20, ftaper: 5, maxmix: 0 } },
  { id: 'lfaf1', title: 'LFAF-1', params: { vel: 1500, f1: 0, f2: 20, ftaper: 5, maxmix: 15, minOffset: 10, muteTime: 0, muteZoneWidth: 50 } },
  { id: 'lfafn', title: 'LFAFN', params: { dx: 25, vel: 1500, f1: 0, f2: 20, ftaper: 5, maxmix: 0, direction: 'both', attenuation: 1 } },
  { id: 'dsout', title: 'DSOUT', params: { path: '', sortType: 'none', firstMin: '', firstMax: '', secondMin: '', secondMax: '' } },
]

const SORT_OPTIONS = [
  { value: 'none', label: 'None (input order)' },
  { value: 'inline_xline', label: 'Inline / Xline' },
  { value: 'crossline_xline', label: 'Xline / Inline' },
  { value: 'cdp_offset', label: 'CDP / Offset' },
  { value: 'ffid_offset', label: 'FFID / Offset' },
  { value: 'ffid_chan', label: 'FFID / Chan' },
]

const SORT_KEY_LABELS = {
  inline_xline: { first: 'Inline', second: 'Xline' },
  crossline_xline: { first: 'Xline', second: 'Inline' },
  cdp_offset: { first: 'CDP', second: 'Offset' },
  ffid_offset: { first: 'FFID', second: 'Offset' },
  ffid_chan: { first: 'FFID', second: 'Chan' },
}

const DSIN_SAMPLE_RATES = [0.5, 1, 2, 4, 8]

function Module({ title, enabled, onToggle, paramsOpen, onToggleParams, onDragStart, onDragOver, onDrop, dragIndex, onRemove, children }) {
  return (
    <div
      className="processing-module"
      draggable={!!onDragStart}
      onDragStart={(e) => onDragStart && onDragStart(e, dragIndex)}
      onDragOver={(e) => onDragOver && onDragOver(e, dragIndex)}
      onDrop={(e) => onDrop && onDrop(e, dragIndex)}
    >
      <div className="module-header">
        {onDragStart && <span className="drag-handle" title="Drag to reorder">⠿</span>}
        <span className="module-title">{title}</span>
        <div className="module-header-controls">
          {onToggle && (
            <label className="toggle-switch">
              <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
              <span className="toggle-slider"></span>
            </label>
          )}
          {onRemove && (
            <button className="module-remove" onClick={() => onRemove()} title="Remove">&times;</button>
          )}
          {onToggleParams && (
            <span
              className={`collapse-icon ${paramsOpen ? '' : 'collapsed'}`}
              onClick={(e) => { e.stopPropagation(); onToggleParams(!paramsOpen) }}
            >&#9660;</span>
          )}
        </div>
      </div>
      {(!onToggleParams || paramsOpen) && <div className="module-params">{children}</div>}
    </div>
  )
}

function ProcessingPanel({ fileId, onRun, isRunning, storedFiles }) {
  const [isOpen, setIsOpen] = useState(false)
  const [parallel, setParallel] = useState(false)
  const [numWorkers, setNumWorkers] = useState(4)
  const [showAddDropdown, setShowAddDropdown] = useState(false)
  const dragIdx = useRef(null)

  const [inputModule, setInputModule] = useState({ id: 'input', title: 'Input', params: { selectedFileId: '', sortType: 'none', firstMin: '', firstMax: '', secondMin: '', secondMax: '' } })
  const [procModules, setProcModules] = useState([])
  const [outputModule, setOutputModule] = useState({ id: 'output', title: 'Output', params: { outputName: '' } })
  const [inputOpen, setInputOpen] = useState(true)
  const [outputOpen, setOutputOpen] = useState(true)

  const hasInput = inputModule.params.selectedFileId
  const hasDsin = procModules.some(m => m.id === 'dsin' && m.enabled && (m.params.path || '').trim())
  const canRun = !!(fileId || hasInput || hasDsin)
  const hasEnabledProc = procModules.some(m => m.enabled)
  const hasOutput = !!outputModule.params.outputName

  const updateParam = (idx, key, val) => {
    setProcModules(prev => {
      const next = [...prev]
      next[idx] = { ...next[idx], params: { ...next[idx].params, [key]: val } }
      return next
    })
  }

  const updateField = (idx, key, val) => {
    setProcModules(prev => {
      const next = [...prev]
      next[idx] = { ...next[idx], [key]: val }
      return next
    })
  }

  const addModule = (modDef) => {
    setProcModules(prev => [...prev, {
      id: modDef.id,
      title: modDef.title,
      enabled: true,
      paramsOpen: false,
      params: { ...modDef.params },
    }])
    setShowAddDropdown(false)
  }

  const removeModule = (idx) => {
    setProcModules(prev => prev.filter((_, i) => i !== idx))
  }

  const handleDragStart = (e, idx) => {
    dragIdx.current = idx
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e, idx) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  const handleDrop = (e, idx) => {
    e.preventDefault()
    const from = dragIdx.current
    if (from === null || from === idx) return
    setProcModules(prev => {
      const next = [...prev]
      const [moved] = next.splice(from, 1)
      next.splice(idx, 0, moved)
      return next
    })
    dragIdx.current = null
  }

  const handleRun = () => {
    if (isRunning || (!hasEnabledProc && !hasOutput)) return
    const steps = []
    let inputFileId = null
    let dsinConfig = null
    let inputSortConfig = null
    let outputName = null
    if (inputModule.params.selectedFileId) {
      inputFileId = inputModule.params.selectedFileId
      const st = inputModule.params.sortType
      if (st && st !== 'none') {
        inputSortConfig = {
          sort_type: st,
          first_min: inputModule.params.firstMin === '' ? null : Number(inputModule.params.firstMin),
          first_max: inputModule.params.firstMax === '' ? null : Number(inputModule.params.firstMax),
          second_min: inputModule.params.secondMin === '' ? null : Number(inputModule.params.secondMin),
          second_max: inputModule.params.secondMax === '' ? null : Number(inputModule.params.secondMax),
        }
      }
    }
    if (outputModule.params.outputName) {
      outputName = outputModule.params.outputName
    }
    for (const mod of procModules) {
      if (!mod.enabled) continue
      if (mod.id === 'dsin') {
        const p = (mod.params.path || '').trim()
        if (p) {
          dsinConfig = {
            path: p,
            trace_len: mod.params.traceLen === '' ? null : Math.max(1, Number(mod.params.traceLen)),
            sample_rate: mod.params.sampleRate === '' ? null : Number(mod.params.sampleRate),
          }
        }
        continue
      }
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
    }
    if (steps.length === 0 && !dsinConfig && !outputName) return
    if (!dsinConfig && !inputFileId && !fileId) return
    onRun(steps, parallel, numWorkers, inputFileId, outputName, dsinConfig, inputSortConfig)
  }

  return (
    <div className="card">
      <div className="card-header collapsible" onClick={() => setIsOpen(!isOpen)}>
        <span className={`collapse-icon ${isOpen ? '' : 'collapsed'}`} style={{ fontSize: '10px' }}>&#9660;</span>
        <span>Processing</span>
      </div>
      {isOpen && (
        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Module title="Input" paramsOpen={inputOpen} onToggleParams={setInputOpen}>
            <div className="module-param">
              <label className="param-label">Source file</label>
              <select
                className="param-select"
                value={inputModule.params.selectedFileId}
                onChange={(e) => setInputModule({ ...inputModule, params: { ...inputModule.params, selectedFileId: e.target.value } })}
                style={{ width: '100%' }}
              >
                <option value="">-- Select --</option>
                {(storedFiles || []).map((f) => (
                  <option key={f.id} value={f.id}>{f.name.replace(/\.sgy$/i, '')}</option>
                ))}
              </select>
            </div>
            <div className="module-param">
              <label className="param-label">Sort order</label>
              <select className="param-select" value={inputModule.params.sortType}
                onChange={(e) => setInputModule({ ...inputModule, params: { ...inputModule.params, sortType: e.target.value } })}
                style={{ width: '100%' }}>
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            {inputModule.params.sortType !== 'none' && (() => {
              const keys = SORT_KEY_LABELS[inputModule.params.sortType]
              const setP = (key, val) => setInputModule({ ...inputModule, params: { ...inputModule.params, [key]: val } })
              return (
                <>
                  <div className="module-param">
                    <label className="param-label">{keys.first} range (first key)</label>
                    <div className="param-row" style={{ gap: '6px' }}>
                      <input className="param-input" type="number" placeholder="min"
                        value={inputModule.params.firstMin} onChange={(e) => setP('firstMin', e.target.value)} />
                      <input className="param-input" type="number" placeholder="max"
                        value={inputModule.params.firstMax} onChange={(e) => setP('firstMax', e.target.value)} />
                    </div>
                  </div>
                  <div className="module-param">
                    <label className="param-label">{keys.second} range (second key)</label>
                    <div className="param-row" style={{ gap: '6px' }}>
                      <input className="param-input" type="number" placeholder="min"
                        value={inputModule.params.secondMin} onChange={(e) => setP('secondMin', e.target.value)} />
                      <input className="param-input" type="number" placeholder="max"
                        value={inputModule.params.secondMax} onChange={(e) => setP('secondMax', e.target.value)} />
                    </div>
                  </div>
                </>
              )
            })()}
          </Module>

          {procModules.map((mod, idx) => (
            <Module
              key={mod.id}
              title={mod.title}
              enabled={mod.enabled}
              onToggle={(v) => updateField(idx, 'enabled', v)}
              paramsOpen={mod.paramsOpen}
              onToggleParams={(v) => updateField(idx, 'paramsOpen', v)}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              dragIndex={idx}
              onRemove={() => removeModule(idx)}
            >
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
            </Module>
          ))}

          <div style={{ position: 'relative' }}>
            <button className="btn btn-secondary" style={{ width: '100%', fontSize: '12px', padding: '6px 0' }}
              onClick={() => setShowAddDropdown(!showAddDropdown)}>
              + Add Module
            </button>
            {showAddDropdown && (
              <div className="add-module-dropdown" style={{
                position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10,
                background: 'var(--bg-surface)', border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius)', maxHeight: '200px', overflowY: 'auto',
                marginTop: '2px', boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
              }}>
                {AVAILABLE_MODULES.filter(a => !procModules.find(p => p.id === a.id)).map(m => (
                  <div key={m.id} style={{
                    padding: '6px 10px', cursor: 'pointer', fontSize: '12px', color: 'var(--text-primary)',
                    borderBottom: '1px solid var(--border-color)',
                  }}
                    onClick={() => addModule(m)}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-main)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  >{m.title}</div>
                ))}
              </div>
            )}
          </div>

          <Module title="Output" paramsOpen={outputOpen} onToggleParams={setOutputOpen}>
            <div className="module-param">
              <label className="param-label">Output name</label>
              <input className="param-input" type="text"
                value={outputModule.params.outputName}
                onChange={(e) => setOutputModule({ ...outputModule, params: { outputName: e.target.value } })}
                placeholder="e.g. Processed v1"
                style={{ width: '100%' }} />
            </div>
          </Module>

          <div className="hr"></div>
          <label className="toggle-row" style={{ fontSize: '12px' }}>
            <span>Parallel</span>
            <label className="toggle-switch">
              <input type="checkbox" checked={parallel} onChange={(e) => setParallel(e.target.checked)} />
              <span className="toggle-slider"></span>
            </label>
          </label>
          {parallel && (
            <div className="param-row">
              <span className="param-label">Cores</span>
              <input className="param-input" type="number" min="1" max="16" step="1"
                value={numWorkers} onChange={(e) => setNumWorkers(Math.max(1, Math.min(16, Number(e.target.value))))}
                style={{ width: '60px' }} />
            </div>
          )}

          <button className="btn btn-primary" onClick={handleRun}
            disabled={!canRun || isRunning || !(hasEnabledProc || hasOutput)}
            style={{ width: '100%' }}>
            {isRunning ? 'Running...' : 'Run'}
          </button>
        </div>
      )}
    </div>
  )
}

export default ProcessingPanel
