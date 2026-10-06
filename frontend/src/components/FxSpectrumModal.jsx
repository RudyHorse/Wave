import { useState } from 'react'
import Plot from 'react-plotly.js'
import DraggableModal from './DraggableModal'

const FX_COLORS = ['#00d4aa', '#ff6b35', '#3b82f6', '#a855f7', '#f59e0b', '#ef4444', '#14b8a6', '#ec4899']
const PALETTES = ['Greys', 'RdBu', 'Viridis', 'Plasma', 'Jet', 'Hot', 'YlOrRd', 'Blues']

function FxSpectrumModal({ data, onClose }) {
  if (!data || data.length === 0) return null

  const maxDataFreq = data[0].frequencies[data[0].frequencies.length - 1]
  const [maxFreq, setMaxFreq] = useState(Math.round(maxDataFreq))
  const [visible, setVisible] = useState(data.map(() => true))
  const [palette, setPalette] = useState('Greys')

  const toggleVisible = (idx) => {
    setVisible((prev) => {
      const next = [...prev]
      next[idx] = !next[idx]
      return next
    })
  }

  const maxFreqIdx = maxFreq > 0 ? [...data[0].frequencies].findIndex(f => f >= maxFreq) : data[0].frequencies.length
  const effectiveMax = maxFreqIdx > 0 ? maxFreqIdx : data[0].frequencies.length

  const traces = data
    .filter((_, i) => visible[i])
    .map((d) => {
      const sliced = d.fx_spectrum.map(row => row.slice(0, effectiveMax + 1))
      return {
        z: sliced[0].map((_, ci) => sliced.map(row => row[ci])),
        x: Array.from({ length: sliced.length }, (_, i) => d.trace_range[0] + i),
        y: d.frequencies.slice(0, effectiveMax + 1),
        type: 'heatmap',
        name: d.label,
        colorscale: palette,
        zsmooth: 'best',
      }
    })

  return (
    <DraggableModal title="FX Spectrum" onClose={onClose} className="modal-content-wide">
      <div className="spectrum-toggles">
        {data.map((d, i) => (
          <label key={d.label} className="spectrum-toggle" onClick={() => toggleVisible(i)}>
            <span className="toggle-dot" style={{ background: FX_COLORS[i % FX_COLORS.length] }}></span>
            <span className={`toggle-label${visible[i] ? '' : ' dim'}`}>{d.label}</span>
          </label>
        ))}
        <label className="freq-label" style={{ marginLeft: '12px' }}>Palette</label>
        <select className="param-input" value={palette} onChange={(e) => setPalette(e.target.value)} style={{ width: '80px', fontSize: '11px', padding: '2px 4px' }}>
          {PALETTES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <label className="freq-label" style={{ marginLeft: '12px' }}>Max Frequency</label>
        <input type="number" className="freq-input" value={maxFreq}
          onChange={(e) => setMaxFreq(Math.max(0, Number(e.target.value)))}
          min={0} max={Math.round(maxDataFreq)} step={10} />
        <span className="freq-unit">Hz</span>
        <span className="spectrum-info">
          Traces {data[0].trace_range[0]}–{data[0].trace_range[1]}, Samples {data[0].sample_range[0]}–{data[0].sample_range[1]}
        </span>
      </div>
      <div className="spectrum-plot">
        <Plot
          data={traces}
          layout={{
            autosize: true,
            margin: { l: 50, r: 20, t: 20, b: 50 },
            paper_bgcolor: '#151b24',
            plot_bgcolor: '#151b24',
            font: { color: '#8b949e', size: 11 },
            xaxis: { title: 'Trace', color: '#8b949e', gridcolor: '#30363d', zeroline: false },
            yaxis: { title: 'Frequency (Hz)', color: '#8b949e', gridcolor: '#30363d', zeroline: false, autorange: 'reversed' },
            dragmode: 'pan',
            hovermode: false,
          }}
          config={{
            displayModeBar: true,
            displaylogo: false,
            scrollZoom: true,
            modeBarButtonsToRemove: ['sendDataToCloud', 'lasso2d', 'select2d'],
          }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
        />
      </div>
    </DraggableModal>
  )
}

export default FxSpectrumModal
