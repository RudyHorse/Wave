import { useState } from 'react'
import { cmpApi, downloadUrl } from './api'
import { SectionPlot } from './Plots'
import { useLatestRequest } from './useLatestRequest'

export default function StackViewer({ dataset }) {
  const [inline, setInline] = useState(dataset.inlines[0] ?? 0)
  const [kind, setKind] = useState('amplitude')
  const [section, setSection] = useState(null)
  const [error, setError] = useState('')
  const request = useLatestRequest(setError)
  function load() {
    setError('')
    request.run(signal => cmpApi.get(`/outputs/${dataset.id}/section`, { signal, params: { inline, kind } }), setSection)
  }
  return <section className="cmp-block">
    <h3>Saved stack and sample-fold QC</h3>
    <p>One trace per CMP. Repeated NMO/STACK is disabled for stacked outputs.</p>
    <div className="cmp-controls">
      <label>Inline<select value={inline} onChange={e => { request.invalidate(); setSection(null); setInline(Number(e.target.value)) }}>
        {dataset.inlines.map(il => <option key={il}>{il}</option>)}
      </select></label>
      <label>QC view<select value={kind} onChange={e => { request.invalidate(); setSection(null); setKind(e.target.value) }}>
        {['amplitude', 'fold', 'input_fold', 'weight_sum'].map(k => <option key={k}>{k}</option>)}
      </select></label>
      <button onClick={load} disabled={request.busy}>Show section</button>
      <a href={downloadUrl(`/outputs/${dataset.id}/segy`)}>Download SEG-Y</a>
      <a href={downloadUrl(`/outputs/${dataset.id}/qc/fold`)}>Fold .npy</a>
      <a href={downloadUrl(`/outputs/${dataset.id}/qc/weight_sum`)}>Weight sum .npy</a>
    </div>
    {error && <p role="alert" className="cmp-error">{error}</p>}
    <SectionPlot section={section} />
  </section>
}
