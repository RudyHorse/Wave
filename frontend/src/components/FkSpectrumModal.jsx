import { useState } from 'react'
import Plot from 'react-plotly.js'
import DraggableModal from './DraggableModal'

const COLORS = ['#00d4aa', '#ff6b35', '#3fb950', '#f85149', '#d2a8ff', '#ffd700', '#58a6ff', '#e06c75']

export default function FkSpectrumModal({ data, onClose }) {
  const [visible, setVisible] = useState(data.map(() => true))
  const [colorscale, setColorscale] = useState('Greys')
  const maxDataFreq = data[0]?.frequencies?.at(-1) ?? 0
  const defaultMaxFreq = Math.min(maxDataFreq || Infinity, 100)
  const [maxFreq, setMaxFreq] = useState(defaultMaxFreq)

  const toggleWin = (idx) => {
    const next = [...visible]
    next[idx] = !next[idx]
    setVisible(next)
  }

  const allTraces = []
  data.forEach((d, i) => {
    if (!visible[i] || !d) return
    const cutIdx = d.frequencies.findIndex(f => f > maxFreq)
    const idx = cutIdx < 0 ? d.frequencies.length : cutIdx
    allTraces.push({
      z: d.amplitude.slice(0, idx),
      x: d.wavenumbers,
      y: d.frequencies.slice(0, idx),
      type: 'heatmap',
      colorscale,
      name: d.label || `Window ${i + 1}`,
      colorbar: { title: 'Amp' },
      hovertemplate: 'kx: %{x:.4f}<br>freq: %{y:.4f} Hz<br>amp: %{z:.3e}<extra></extra>',
    })
  })

  return (
    <DraggableModal title="FK Spectrum" onClose={onClose} className="modal-content-wide" initialWidth={860} initialHeight={500}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
          {data.map((d, i) => (
            <label key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', cursor: 'pointer' }}>
              <input type="checkbox" checked={visible[i]} onChange={() => toggleWin(i)} />
              <span style={{ color: COLORS[i % COLORS.length] }}>{d.label || `Window ${i + 1}`}</span>
            </label>
          ))}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Palette</span>
            <select className="param-select" style={{ width: '90px', fontSize: '10px' }}
              value={colorscale} onChange={(e) => setColorscale(e.target.value)}>
              <option value="Greys">Greyscale</option>
              <option value="Viridis">Viridis</option>
              <option value="RdYlBu">Red-Yellow-Blue</option>
              <option value="Hot">Hot</option>
              <option value="Electric">Electric</option>
              <option value="Portl">Portl</option>
            </select>
          </div>
        </div>
        {data[0] && (
          <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: 'var(--text-secondary)', alignItems: 'center' }}>
            <span>Traces: {data[0].trace_range?.[0]}–{data[0].trace_range?.[1]}</span>
            <span>Samples: {data[0].sample_range?.[0]}–{data[0].sample_range?.[1]}</span>
            <span>SR: {data[0].sample_rate} ms</span>
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>Max freq (Hz)</span>
              <input type="number" min={0} step={1}
                value={maxFreq} onChange={(e) => setMaxFreq(Number(e.target.value))}
                className="param-input" style={{ width: '70px', fontSize: '10px' }} />
            </span>
          </div>
        )}
        <div style={{ flex: 1, minHeight: 0 }}>
          <Plot
            data={allTraces}
            layout={{
              autosize: true,
              margin: { l: 60, r: 30, t: 20, b: 50 },
              paper_bgcolor: '#151b24',
              plot_bgcolor: '#151b24',
              font: { color: '#e6edf3', family: 'JetBrains Mono, monospace' },
              xaxis: { title: 'Wavenumber (kx)', gridcolor: '#30363d', zerolinecolor: '#30363d', tickformat: '.2f', nticks: 12 },
              yaxis: { title: 'Frequency (Hz)', gridcolor: '#30363d', zerolinecolor: '#30363d', range: [0, maxFreq], autorange: false },
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
      </div>
    </DraggableModal>
  )
}
