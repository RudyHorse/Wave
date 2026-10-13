import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { cmpApi, apiError, isCancelled, downloadUrl } from './api'
import { addPick, editPick, functionKey, fromFunctions, historyReducer, toFunctions } from './picks'
import { useLatestRequest } from './useLatestRequest'
import { VelocityPlot, GatherPlot, NmoQC } from './Plots'
import './velocity.css'

function readDraft(key) {
  try { return JSON.parse(localStorage.getItem(key) || 'null') } catch { return null }
}
function optionsFromDocument(doc) {
  const { functions, source_file_id, source_fingerprint, schema_version, type, ...options } = doc
  return options
}
function NumberField({ label, value, onChange, ...rest }) {
  return <label>{label}<input type="number" value={value} onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} {...rest} /></label>
}

function Session({ dataset }) {
  const draftKey = `wave-velocity-draft:${dataset.id}:${dataset.fingerprint}`
  const initialDraft = useRef(readDraft(draftKey)).current
  const [history, dispatch] = useReducer(historyReducer, { past: [], present: initialDraft?.picks || {}, future: [] })
  const [options, setOptions] = useState(initialDraft?.options || {
    name: `${dataset.name}_velocity`, geometry: dataset.geometry || { offset_units: 'm', offset_convention: 'full', start_time_ms: 0 },
    time_interpolation: 'linear', spatial_extrapolation: 'error', time_extrapolation: 'constant', supergather_size: 5, comment: '',
  })
  const [velocityId, setVelocityId] = useState(initialDraft?.velocityId || '')
  const [savedJSON, setSavedJSON] = useState(initialDraft?.savedJSON || '')
  const [velocityFiles, setVelocityFiles] = useState([])
  const [inline, setInline] = useState(dataset.inlines[0] ?? 0)
  const [cdp, setCdp] = useState('')
  const [cdps, setCdps] = useState([])
  const [page, setPage] = useState(0)
  const [totalCdps, setTotalCdps] = useState(0)
  const [vmin, setVmin] = useState(1200)
  const [vmax, setVmax] = useState(5000)
  const [dv, setDv] = useState(25)
  const [timeStride, setTimeStride] = useState(Math.max(1, Math.ceil(dataset.samples / 2000)))
  const [windowMs, setWindowMs] = useState(24)
  const [minOffset, setMinOffset] = useState(0)
  const [maxOffset, setMaxOffset] = useState('')
  const [nmo, setNmo] = useState({ interpolation: 'linear', sinc_half_width: 8, stretch_limit: 0.3, stretch_taper: 0.05 })
  const [spectrum, setSpectrum] = useState(null)
  const [preview, setPreview] = useState(null)
  const [autoPreview, setAutoPreview] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(initialDraft ? 'Local draft restored. This is not a database save.' : '')
  const compute = useLatestRequest(setError)
  const io = useLatestRequest(setError)
  const key = functionKey(inline, cdp)
  const picks = history.present[key] || []
  const functions = useMemo(() => toFunctions(history.present), [history.present])
  const document = useMemo(() => ({ schema_version: 1, type: 'stacking_velocity', ...options,
    source_file_id: dataset.id, source_fingerprint: dataset.velocity_fingerprint, functions,
  }), [options, dataset.id, dataset.velocity_fingerprint, functions])
  const documentJSON = JSON.stringify(document)
  const dirty = documentJSON !== savedJSON
  const selection = useMemo(() => ({ inline: Number(inline), cdp: Number(cdp), supergather_size: Number(options.supergather_size),
    min_offset_m: Number(minOffset), max_offset_m: maxOffset === '' ? null : Number(maxOffset), geometry: options.geometry,
  }), [inline, cdp, options.supergather_size, options.geometry, minOffset, maxOffset])
  const selectionKey = JSON.stringify(selection)
  const nmoKey = JSON.stringify(nmo)

  useEffect(() => {
    try { localStorage.setItem(draftKey, JSON.stringify({ picks: history.present, options, velocityId, savedJSON })) }
    catch { setNotice('Local draft could not be stored. Save a velocity-file revision to the database.') }
  }, [draftKey, history.present, options, velocityId, savedJSON])
  useEffect(() => {
    const beforeUnload = e => { if (dirty && functions.length) { e.preventDefault(); e.returnValue = '' } }
    window.addEventListener('beforeunload', beforeUnload)
    return () => window.removeEventListener('beforeunload', beforeUnload)
  }, [dirty, functions.length])
  const refreshVelocities = useCallback(async () => {
    try { const response = await cmpApi.get('/velocity-files', { params: { source_file_id: dataset.id } }); setVelocityFiles(response.data) }
    catch (e) { setError(apiError(e)) }
  }, [dataset.id])
  useEffect(() => { refreshVelocities() }, [refreshVelocities])
  useEffect(() => {
    const controller = new AbortController()
    setCdp(''); setCdps([])
    cmpApi.get(`/datasets/${dataset.id}/cdps`, { params: { inline, offset: page * 1000, limit: 1000 }, signal: controller.signal })
      .then(({ data }) => { setCdps(data.cdps); setTotalCdps(data.total); setCdp(data.cdps[0] ?? '') })
      .catch(e => { if (!isCancelled(e)) setError(apiError(e)) })
    return () => controller.abort()
  }, [dataset.id, inline, page])
  useEffect(() => {
    compute.invalidate(); setSpectrum(null); setPreview(null)
  }, [selectionKey, nmoKey, vmin, vmax, dv, windowMs, timeStride, compute.invalidate])

  useEffect(() => { compute.invalidate(); setPreview(null) }, [documentJSON, compute.invalidate])

  function commit(newPicks) {
    dispatch({ type: 'commit', value: { ...history.present, [key]: newPicks } })
  }
  function onPick(pick) {
    try { commit(addPick(picks, { time_ms: Math.round(pick.time_ms * 1000) / 1000, velocity_mps: Math.round(pick.velocity_mps * 1000) / 1000 }, dataset.dt_ms * 0.25)) }
    catch (e) { setError(e.message) }
  }
  function edit(index, field, value) {
    try { commit(editPick(picks, index, { [field]: Number(value) })) }
    catch (e) { setError(e.message) }
  }
  function calculateSpectrum() {
    setError('')
    compute.run(signal => cmpApi.post(`/datasets/${dataset.id}/spectrum`, {
      selection, velocity_min: Number(vmin), velocity_max: Number(vmax), velocity_step: Number(dv),
      window_ms: Number(windowMs), time_stride: Number(timeStride), min_fold: 2, nmo,
    }, { signal }), setSpectrum)
  }
  const calculatePreview = useCallback(() => {
    if (!functions.length || cdp === '') return
    setError('')
    compute.run(signal => cmpApi.post(`/datasets/${dataset.id}/nmo-preview`, {
      selection: { ...selection, supergather_size: 1 }, document, nmo,
    }, { signal }), setPreview)
  }, [functions.length, cdp, selectionKey, documentJSON, nmoKey, compute.run])
  useEffect(() => {
    if (!autoPreview || !functions.length || dataset.kind !== 'prestack') return undefined
    const timer = setTimeout(calculatePreview, 600)
    return () => clearTimeout(timer)
  }, [autoPreview, calculatePreview, functions.length, dataset.kind])

  function save() {
    setError('')
    const savedSnapshot = documentJSON
    io.run(signal => cmpApi.post('/velocity-files', { document, parent_id: velocityId || null }, { signal }), file => {
      setVelocityId(file.id); setSavedJSON(savedSnapshot)
      setNotice(`Saved revision ${file.revision}; SHA-256 ${file.sha256.slice(0, 16)}...`)
      refreshVelocities()
    })
  }
  function loadVelocity(fileId) {
    if (!fileId) { setVelocityId(''); setSavedJSON(''); setNotice('Current picks will be saved as a new independent model, not as a revision.'); return }
    if (dirty && functions.length && !window.confirm('Replace this local draft with the selected saved velocity file?')) return
    io.run(signal => cmpApi.get(`/velocity-files/${fileId}`, { signal }), result => {
      if (result.document.source_fingerprint !== dataset.velocity_fingerprint) { setError('Saved velocity file belongs to an earlier dataset revision'); return }
      const map = fromFunctions(result.document.functions)
      const opts = optionsFromDocument(result.document)
      const normalized = { schema_version: 1, type: 'stacking_velocity', ...opts, source_file_id: dataset.id,
        source_fingerprint: dataset.velocity_fingerprint, functions: toFunctions(map) }
      dispatch({ type: 'reset', value: map }); setOptions(opts); setVelocityId(fileId)
      setSavedJSON(JSON.stringify(normalized)); setNotice(`Loaded revision ${result.file.revision}`)
    })
  }
  function navigate(direction) {
    const pos = cdps.indexOf(Number(cdp))
    if (pos + direction >= 0 && pos + direction < cdps.length) setCdp(cdps[pos + direction])
  }
  const geometryChange = patch => setOptions(prev => ({ ...prev, geometry: { ...prev.geometry, ...patch } }))

  return <>
    <div className="cmp-meta">{dataset.trace_count} traces; {dataset.samples} samples; dt={dataset.dt_ms} ms; type: {dataset.kind}.
      <span className="cmp-mono"> Fingerprint {dataset.fingerprint.slice(0, 16)}...</span></div>
    {!dataset.headers_available && <p className="cmp-warning">Raw SEG-Y headers are unavailable. Export will contain minimal CDP/inline/crossline headers, not invented XY coordinates.</p>}
    <section className="cmp-block">
      <h3>Input geometry and CMP selection</h3>
      <p className="cmp-hint">Verify offset units, full/half offset and recording start time before picking. Neighboring existing CDPs are combined only within the selected inline.</p>
      <div className="cmp-controls">
        <label>Inline<select value={inline} onChange={e => { setInline(Number(e.target.value)); setPage(0) }}>
          {dataset.inlines.map(il => <option key={il}>{il}</option>)}</select></label>
        <NumberField label="CDP" value={cdp} onChange={setCdp} step="1" />
        <button onClick={() => navigate(-1)} disabled={cdps.indexOf(Number(cdp)) <= 0}>Previous CMP</button>
        <button onClick={() => navigate(1)} disabled={cdps.indexOf(Number(cdp)) >= cdps.length - 1}>Next CMP</button>
        <NumberField label="Supergather size (incl. center)" value={options.supergather_size} min="1" max="101" step="2" onChange={v => setOptions(p => ({ ...p, supergather_size: v }))} />
        <label>Offset units<select disabled={!!dataset.geometry} value={options.geometry.offset_units} onChange={e => geometryChange({ offset_units: e.target.value })}>
          <option value="m">m</option><option value="ft">ft</option></select></label>
        <label>Offset convention<select disabled={!!dataset.geometry} value={options.geometry.offset_convention} onChange={e => geometryChange({ offset_convention: e.target.value })}>
          <option value="full">Full source-receiver</option><option value="half">Half offset</option></select></label>
        <NumberField label="First sample time, ms" value={options.geometry.start_time_ms} disabled={!!dataset.geometry} min="0" onChange={v => geometryChange({ start_time_ms: v })} />
        <NumberField label="Min |offset|, m" value={minOffset} min="0" onChange={setMinOffset} />
        <NumberField label="Max |offset|, m (blank = all)" value={maxOffset} min="0" onChange={setMaxOffset} />
      </div>
      {totalCdps > 1000 && <div className="cmp-actions">
        <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous key page</button>
        <span>Keys {page * 1000 + 1}-{Math.min((page + 1) * 1000, totalCdps)} / {totalCdps}. Any exact CDP can be typed above.</span>
        <button disabled={(page + 1) * 1000 >= totalCdps} onClick={() => setPage(p => p + 1)}>Next key page</button>
      </div>}
    </section>
    {dataset.kind === 'prestack' && <>
      <section className="cmp-block">
        <h3>Velocity spectrum and NMO QC</h3>
        <div className="cmp-controls">
          <NumberField label="Vmin, m/s" value={vmin} min="1" onChange={setVmin} />
          <NumberField label="Vmax, m/s" value={vmax} min="1" onChange={setVmax} />
          <NumberField label="dV, m/s" value={dv} min="1" onChange={setDv} />
          <NumberField label="Semblance window, ms" value={windowMs} min="1" onChange={setWindowMs} />
          <NumberField label="Spectrum time stride" value={timeStride} min="1" max="128" onChange={setTimeStride} />
          <label>NMO interpolation<select value={nmo.interpolation} onChange={e => setNmo(p => ({ ...p, interpolation: e.target.value }))}>
            <option value="linear">Linear</option><option value="sinc">Windowed sinc, 16 taps</option></select></label>
          <NumberField label="Stretch mute, %" value={nmo.stretch_limit * 100} min="1" onChange={v => setNmo(p => ({ ...p, stretch_limit: v / 100 }))} />
          <NumberField label="Stretch transition, %-points" value={nmo.stretch_taper * 100} min="0" onChange={v => setNmo(p => ({ ...p, stretch_taper: v / 100 }))} />
        </div>
        <div className="cmp-actions">
          <button className="cmp-primary" disabled={compute.busy || cdp === ''} onClick={calculateSpectrum}>Calculate spectrum</button>
          <button disabled={compute.busy || !functions.length || cdp === ''} onClick={calculatePreview}>NMO preview from current picks</button>
          <label><input type="checkbox" checked={autoPreview} onChange={e => setAutoPreview(e.target.checked)} /> Auto NMO QC (600 ms debounce)</label>
          {compute.busy && <span role="status">Calculating...</span>}
        </div>
        {spectrum && <p>Actual supergather: {spectrum.members.map(m => `${m[0]}:${m[1]}`).join(', ')}; {spectrum.actual_trace_count} traces.</p>}
        <div className="cmp-plots">
          <GatherPlot panel={spectrum?.gather} title="Supergather (for velocity analysis only)" revisionKey={selectionKey} />
          <VelocityPlot spectrum={spectrum} picks={picks} onPick={onPick} revisionKey={selectionKey} />
        </div>
        <NmoQC preview={preview} revisionKey={key} />
      </section>
      <section className="cmp-block">
        <h3>Picks and immutable velocity files</h3>
        <div className="cmp-controls">
          <label>Velocity model name<input value={options.name} onChange={e => setOptions(p => ({ ...p, name: e.target.value }))} /></label>
          <label>Temporal interpolation<select value={options.time_interpolation} onChange={e => setOptions(p => ({ ...p, time_interpolation: e.target.value }))}>
            <option value="linear">Linear</option><option value="pchip">PCHIP</option></select></label>
          <label>Outside picked CDP range<select value={options.spatial_extrapolation} onChange={e => setOptions(p => ({ ...p, spatial_extrapolation: e.target.value }))}>
            <option value="error">Error (safe default)</option><option value="constant">Constant nearest function</option></select></label>
          <label>Outside picked time range<select value={options.time_extrapolation} onChange={e => setOptions(p => ({ ...p, time_extrapolation: e.target.value }))}>
            <option value="constant">Constant end velocity</option><option value="error">Error</option></select></label>
          <label>Saved velocity file<select value={velocityId} onChange={e => loadVelocity(e.target.value)} disabled={io.busy}>
            <option value="">New model</option>{velocityFiles.map(file => <option key={file.id} value={file.id}>{file.name} - r{file.revision}</option>)}</select></label>
        </div>
        <p>{functions.length} picked CMP functions. Current function: inline {inline}, CDP {cdp}. {dirty ? 'Unsaved changes.' : 'Matches the saved database revision.'}</p>
        <div className="cmp-actions">
          <button disabled={!history.past.length} onClick={() => dispatch({ type: 'undo' })}>Undo</button>
          <button disabled={!history.future.length} onClick={() => dispatch({ type: 'redo' })}>Redo</button>
          <button disabled={!picks.length} onClick={() => { if (window.confirm('Clear picks for this CMP only?')) commit([]) }}>Clear this CMP</button>
          <button className="cmp-primary" disabled={io.busy || !functions.length} onClick={save}>Save new revision to SQLite</button>
          {velocityId && <a href={downloadUrl(`/velocity-files/${velocityId}/download`)}>Download saved JSON file</a>}
        </div>
        <div className="cmp-pick-table"><table>
          <thead><tr><th>Time, ms</th><th>Velocity, m/s</th><th>Action</th></tr></thead>
          <tbody>{picks.map((pick, index) => <tr key={`${key}:${index}`}>
            <td><input aria-label={`Pick ${index + 1} time`} type="number" min="0" value={pick.time_ms} onChange={e => edit(index, 'time_ms', e.target.value)} /></td>
            <td><input aria-label={`Pick ${index + 1} velocity`} type="number" min="1" value={pick.velocity_mps} onChange={e => edit(index, 'velocity_mps', e.target.value)} /></td>
            <td><button onClick={() => commit(picks.filter((_, i) => i !== index))}>Delete</button></td>
          </tr>)}</tbody>
        </table></div>
        {notice && <p role="status" className="cmp-hint">{notice}</p>}
      </section>
    </>}
    {error && <div role="alert" className="cmp-error">{error}<button onClick={() => setError('')}>Dismiss</button></div>}
  </>
}

export default function VelocityWorkbench({ initialFileId, onClose }) {
  const dialog = useRef(null)
  const [datasets, setDatasets] = useState([])
  const [selected, setSelected] = useState(initialFileId || '')
  const [dataset, setDataset] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const refresh = useCallback(async () => {
    try {
      const { data } = await cmpApi.get('/datasets'); setDatasets(data)
      setSelected(current => data.some(d => d.id === current) ? current : data[0]?.id || '')
    } catch (e) { setError(apiError(e)) }
  }, [])
  useEffect(() => {
    const element = dialog.current
    if (!element.open) element.showModal()
    refresh()
    return () => element.close()
  }, [refresh])
  useEffect(() => {
    if (!selected) { setDataset(null); return undefined }
    const controller = new AbortController()
    setDataset(null); setLoading(true); setError('')
    cmpApi.get(`/datasets/${selected}`, { signal: controller.signal }).then(({ data }) => setDataset(data))
      .catch(e => { if (!isCancelled(e)) setError(apiError(e)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [selected])
  return <dialog ref={dialog} className="cmp-dialog" onCancel={e => { e.preventDefault(); onClose() }} aria-labelledby="cmp-title">
    <header className="cmp-topbar"><h2 id="cmp-title">Wave - Velocity Analysis</h2><button onClick={onClose}>Close</button></header>
    <div className="cmp-workspace">
      <div className="cmp-controls">
        <label>Stored input dataset<select value={selected} onChange={e => setSelected(e.target.value)}>
          <option value="">Select a saved dataset</option>{datasets.map(d => <option key={d.id} value={d.id}>{d.name} ({d.trace_count} traces)</option>)}</select></label>
        <button onClick={refresh}>Refresh database</button>
      </div>
      <p className="cmp-hint">Picks have a local browser draft. Only "Save new revision to SQLite" creates a velocity file in the database. NMO and STACK now run in the Processing panel.</p>
      {loading && <p role="status">Opening memory-mapped dataset and checking its fingerprint...</p>}
      {error && <p role="alert" className="cmp-error">{error}</p>}
      {!loading && !dataset && <p>Import/save a SEG-Y dataset using the existing Wave database controls first.</p>}
      {dataset && <Session key={`${dataset.id}:${dataset.fingerprint}`} dataset={dataset} />}
    </div>
  </dialog>
}
