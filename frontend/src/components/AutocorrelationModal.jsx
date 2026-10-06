import { useState } from 'react'
import Plot from 'react-plotly.js'
import DraggableModal from './DraggableModal'

const AC_COLORS = ['#00d4aa', '#ff6b35', '#3b82f6', '#a855f7', '#f59e0b', '#ef4444', '#14b8a6', '#ec4899']

function AutocorrelationModal({ data, onClose }) {
  if (!data || data.length === 0) return null

  const [mode, setMode] = useState('sum')
  const [visible, setVisible] = useState(data.map(() => true))

  const toggleVisible = (idx) => {
    setVisible((prev) => {
      const next = [...prev]
      next[idx] = !next[idx]
      return next
    })
  }

  if (mode === 'sum') {
    const visibleItems = data.map((d, i) => ({ d, origIdx: i })).filter(({ origIdx }) => visible[origIdx])
    const traces = visibleItems.map(({ d, origIdx }) => ({
      x: d.lags,
      y: d.autocorrelation_sum,
      type: 'scatter',
      mode: 'lines',
      name: d.label,
      line: { color: AC_COLORS[origIdx % AC_COLORS.length], width: 1.5 },
    }))

    return (
      <DraggableModal title="Autocorrelation" onClose={onClose}>
        <div className="spectrum-toggles">
          {data.map((d, i) => (
            <label key={d.label} className="spectrum-toggle" onClick={() => toggleVisible(i)}>
              <span className="toggle-dot" style={{ background: AC_COLORS[i % AC_COLORS.length] }}></span>
              <span className={`toggle-label${visible[i] ? '' : ' dim'}`}>{d.label}</span>
            </label>
          ))}
          <div className="mode-selector">
            <span className={`mode-option${mode === 'sum' ? ' active' : ''}`} onClick={() => setMode('sum')}>Sum</span>
            <span className={`mode-option${mode === 'all' ? ' active' : ''}`} onClick={() => setMode('all')}>All Traces</span>
          </div>
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
              xaxis: { title: 'Lag (samples)', color: '#8b949e', gridcolor: '#30363d', zeroline: false },
              yaxis: { title: 'Correlation', color: '#8b949e', gridcolor: '#30363d', zeroline: false },
              dragmode: 'pan',
              hovermode: 'x',
              showlegend: true,
              legend: { font: { color: '#8b949e', size: 10 }, bgcolor: 'rgba(21, 27, 36, 0.8)' },
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

  return (
    <DraggableModal title="Autocorrelation — All Traces" onClose={onClose} className="modal-content-wide">
      <div className="spectrum-toggles">
        {data.map((d, i) => (
          <label key={d.label} className="spectrum-toggle" onClick={() => toggleVisible(i)}>
            <span className="toggle-dot" style={{ background: AC_COLORS[i % AC_COLORS.length] }}></span>
            <span className={`toggle-label${visible[i] ? '' : ' dim'}`}>{d.label}</span>
          </label>
        ))}
        <div className="mode-selector">
          <span className={`mode-option${mode === 'sum' ? ' active' : ''}`} onClick={() => setMode('sum')}>Sum</span>
          <span className={`mode-option${mode === 'all' ? ' active' : ''}`} onClick={() => setMode('all')}>All Traces</span>
        </div>
        <span className="spectrum-info">
          Traces {data[0].trace_range[0]}–{data[0].trace_range[1]}, Samples {data[0].sample_range[0]}–{data[0].sample_range[1]}
        </span>
      </div>
      <div className="spectrum-plot">
        <Plot
          data={data.map((d, i) => ({ d, origIdx: i })).filter(({ origIdx }) => visible[origIdx]).map(({ d, origIdx }) => ({
            z: d.autocorrelations,
            x: d.lags,
            y: Array.from({ length: d.autocorrelations.length }, (_, i) => d.trace_range[0] + i),
            type: 'heatmap',
            name: d.label,
            colorscale: 'RdBu',
            zmid: 0,
            zsmooth: 'best',
          }))}
          layout={{
            autosize: true,
            margin: { l: 50, r: 20, t: 20, b: 50 },
            paper_bgcolor: '#151b24',
            plot_bgcolor: '#151b24',
            font: { color: '#8b949e', size: 11 },
            xaxis: { title: 'Lag (samples)', color: '#8b949e', gridcolor: '#30363d', zeroline: false },
            yaxis: { title: 'Trace', color: '#8b949e', gridcolor: '#30363d', zeroline: false },
            dragmode: 'pan',
            hovermode: 'x',
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

export default AutocorrelationModal
