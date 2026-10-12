import ModuleParameters from '../features/processing/ModuleParameters'
import { serializeModule } from '../features/processing/serializeModule'
import { useState, useRef } from 'react'

import Module from '../features/processing/ProcessingModule'
import { AVAILABLE_MODULES, SORT_OPTIONS, SORT_KEY_LABELS, DSIN_SAMPLE_RATES } from '../features/processing/moduleDefinitions'
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
      const serialized = serializeModule(mod)
      if (serialized) steps.push(serialized)
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
              <ModuleParameters mod={mod} idx={idx} updateParam={updateParam} />
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
