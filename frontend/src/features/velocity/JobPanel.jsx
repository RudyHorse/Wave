import { useCallback, useEffect, useRef, useState } from 'react'
import { cmpApi, apiError, downloadUrl } from './api'
import { SectionPlot } from './Plots'
import { useLatestRequest } from './useLatestRequest'

export default function JobPanel({ dataset, geometry, selection, velocityId, velocityDirty, nmoParams, onCreated }) {
  const [mode, setMode] = useState(dataset.kind === 'nmo' ? 'stack' : 'nmo_stack')
  const [method, setMethod] = useState('mean')
  const [trim, setTrim] = useState(10)
  const [minFold, setMinFold] = useState(1)
  const [name, setName] = useState(`${dataset.name}_CMP`)
  const [allLines, setAllLines] = useState(false)
  const [cdpMin, setCdpMin] = useState('')
  const [cdpMax, setCdpMax] = useState('')
  const [alreadyNmo, setAlreadyNmo] = useState(dataset.kind === 'nmo')
  const [agcEnabled, setAgcEnabled] = useState(false)
  const [agcWindow, setAgcWindow] = useState(500)
  const [bandEnabled, setBandEnabled] = useState(false)
  const [band, setBand] = useState({ lowcut: 5, lowpass: 10, highpass: 80, highcut: 100 })
  const [jobId, setJobId] = useState(() => { try { return localStorage.getItem(`wave-cmp-job:${dataset.id}`) || '' } catch { return '' } })
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [pollVersion, setPollVersion] = useState(0)
  const [section, setSection] = useState(null)
  const [qcLine, setQcLine] = useState(selection.inline)
  const [qcKind, setQcKind] = useState('amplitude')
  const notified = useRef('')
  const latestCreated = useRef(onCreated)
  latestCreated.current = onCreated
  const request = useLatestRequest(setError)
  const running = submitting || job?.status === 'queued' || job?.status === 'running'
  const needsVelocity = mode !== 'stack'

  useEffect(() => {
    if (!jobId) return undefined
    let stopped = false; let timer; let failures = 0
    const controller = new AbortController()
    async function poll() {
      try {
        const { data } = await cmpApi.get(`/jobs/${jobId}`, { signal: controller.signal })
        if (stopped) return
        setJob(data); failures = 0
        if (data.status === 'succeeded' && notified.current !== data.id) {
          notified.current = data.id
          latestCreated.current?.(data.result_id)
        }
        if (['queued', 'running'].includes(data.status)) timer = setTimeout(poll, 700)
      } catch (e) {
        if (stopped) return
        setError(apiError(e)); failures += 1
        if (failures < 5) timer = setTimeout(poll, 2000)
      }
    }
    poll()
    return () => { stopped = true; clearTimeout(timer); controller.abort() }
  }, [jobId, pollVersion])

  async function submit() {
    setSubmitting(true); setError(''); setSection(null)
    try {
      const steps = []
      if (agcEnabled) steps.push({ type: 'agc', params: { window_ms: agcWindow } })
      if (bandEnabled) steps.push({ type: 'bandpass', params: band })
      if (needsVelocity) steps.push({ type: 'nmo', params: nmoParams })
      if (mode !== 'nmo') steps.push({ type: 'stack', params: { method, trim_fraction: trim / 100, min_fold: minFold } })
      const { data } = await cmpApi.post('/jobs', {
        dataset_id: dataset.id, output_name: name, velocity_file_id: needsVelocity ? velocityId : null,
        geometry, inline: allLines ? null : selection.inline,
        cdp_min: cdpMin === '' ? null : Number(cdpMin), cdp_max: cdpMax === '' ? null : Number(cdpMax),
        min_offset_m: selection.min_offset_m, max_offset_m: selection.max_offset_m,
        input_already_nmo: alreadyNmo, steps,
      })
      setJob(data); setJobId(data.id)
      try { localStorage.setItem(`wave-cmp-job:${dataset.id}`, data.id) } catch { /* Polling still works without local storage. */ }
    } catch (e) { setError(apiError(e)) } finally { setSubmitting(false) }
  }
  const loadSection = useCallback(() => {
    if (!job?.result_id) return
    request.run(signal => cmpApi.get(`/outputs/${job.result_id}/section`, { params: { inline: Number(qcLine), kind: qcKind }, signal }), setSection)
  }, [job?.result_id, qcLine, qcKind, request.run])

  return <section className="cmp-block">
    <h3>Dataset processing - results are new, persistent datasets</h3>
    <fieldset disabled={running}>
      <div className="cmp-controls">
        <label>Output name<input value={name} onChange={e => setName(e.target.value)} /></label>
        <label>Sequence<select value={mode} onChange={e => setMode(e.target.value)}>
          {dataset.kind !== 'nmo' && <><option value="nmo_stack">NMO - STACK</option><option value="nmo">NMO only</option></>}
          <option value="stack">STACK corrected input</option>
        </select></label>
        <label>Stack method<select value={method} onChange={e => setMethod(e.target.value)}>
          {['mean', 'sum', 'median', 'trimmed_mean'].map(m => <option key={m}>{m}</option>)}
        </select></label>
        {method === 'trimmed_mean' && <label>Trim each tail, %<input type="number" min="0" max="49" value={trim} onChange={e => setTrim(Number(e.target.value))} /></label>}
        <label>Minimum fold<input type="number" min="1" value={minFold} onChange={e => setMinFold(Number(e.target.value))} /></label>
        <label>CDP from (blank = all)<input type="number" value={cdpMin} onChange={e => setCdpMin(e.target.value)} /></label>
        <label>CDP to<input type="number" value={cdpMax} onChange={e => setCdpMax(e.target.value)} /></label>
        <label><input type="checkbox" checked={allLines} onChange={e => setAllLines(e.target.checked)} /> All inlines (otherwise current inline)</label>
      </div>
      {mode === 'stack' && <label><input type="checkbox" checked={alreadyNmo} onChange={e => setAlreadyNmo(e.target.checked)} /> I confirm that input is already NMO corrected</label>}
      {dataset.kind !== 'nmo' && <details><summary>Optional pre-NMO filters</summary>
        <div className="cmp-controls">
          <label><input type="checkbox" checked={agcEnabled} onChange={e => setAgcEnabled(e.target.checked)} /> AGC</label>
          <label>RMS window, ms<input type="number" min="1" value={agcWindow} onChange={e => setAgcWindow(Number(e.target.value))} /></label>
          <label><input type="checkbox" checked={bandEnabled} onChange={e => setBandEnabled(e.target.checked)} /> Bandpass</label>
          {Object.entries(band).map(([key, value]) => <label key={key}>{key}, Hz<input type="number" min="0" value={value} onChange={e => setBand(prev => ({ ...prev, [key]: Number(e.target.value) }))} /></label>)}
        </div><p>AGC changes relative amplitudes. Leave it off for amplitude-preserving processing.</p>
      </details>}
      {needsVelocity && (!velocityId || velocityDirty) && <p className="cmp-warning">Save the current picks as a velocity-file revision before running NMO.</p>}
      <button className="cmp-primary" onClick={submit} disabled={!name.trim() || (needsVelocity && (!velocityId || velocityDirty)) || (mode === 'stack' && !alreadyNmo)}>Run sequence</button>
    </fieldset>
    {job && <div className="cmp-job" role="status">
      <strong>{job.status}</strong> <progress value={job.progress} max="1" /> {Math.round(job.progress * 100)}%
      {['running', 'queued'].includes(job.status) && <button onClick={async () => { try { await cmpApi.post(`/jobs/${job.id}/cancel`) } catch (e) { setError(apiError(e)) } }}>Cancel job</button>}
      <button onClick={() => setPollVersion(v => v + 1)}>Refresh status</button>
      {job.error && <p>{job.error}</p>}
      {job.status === 'succeeded' && <>
        <p>Result ID: <code>{job.result_id}</code>. Available in the original Wave database panel.</p>
        <a href={downloadUrl(`/outputs/${job.result_id}/segy`)}>Download SEG-Y</a>
        {job.request?.steps?.at(-1)?.type === 'stack' && <>
          {' | '}<a href={downloadUrl(`/outputs/${job.result_id}/qc/fold`)}>Sample fold .npy</a>
          {' | '}<a href={downloadUrl(`/outputs/${job.result_id}/qc/weight_sum`)}>Weight sum .npy</a>
          <div className="cmp-controls">
            <label>QC inline<input type="number" value={qcLine} onChange={e => setQcLine(e.target.value)} /></label>
            <label>QC view<select value={qcKind} onChange={e => setQcKind(e.target.value)}>
              {['amplitude', 'fold', 'input_fold', 'weight_sum'].map(k => <option key={k}>{k}</option>)}
            </select></label><button onClick={loadSection} disabled={request.busy}>Show stack / fold</button>
          </div>
        </>}
      </>}
    </div>}
    {error && <p role="alert" className="cmp-error">{error}</p>}
    <SectionPlot section={section} />
  </section>
}
