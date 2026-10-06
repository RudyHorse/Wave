import Plot from 'react-plotly.js'
import DraggableModal from './DraggableModal'

const SNR_COLORS = ['#00d4aa', '#ff6b35', '#3b82f6', '#a855f7', '#f59e0b', '#ef4444', '#14b8a6', '#ec4899']

function SnrModal({ data, onClose }) {
  if (!data || data.length === 0) return null

  return (
    <DraggableModal title="Signal / Noise" onClose={onClose} className="modal-content-wide">
      <div className="spectrum-toggles" style={{ marginBottom: '12px' }}>
        <span className="spectrum-info">
          Traces {data[0].trace_range[0]}–{data[0].trace_range[1]}, Samples {data[0].sample_range[0]}–{data[0].sample_range[1]}
        </span>
      </div>
      <div className="spectrum-plot-row">
        <div className="spectrum-plot">
          <Plot
            data={data.map((d, i) => ({
              x: Array.from({ length: d.stack.length }, (_, j) => j * d.sample_step),
              y: d.stack,
              type: 'scatter',
              mode: 'lines',
              name: d.label,
              line: { color: SNR_COLORS[i % SNR_COLORS.length], width: 2 },
            }))}
            layout={{
              autosize: true,
              margin: { l: 50, r: 20, t: 20, b: 50 },
              paper_bgcolor: '#151b24',
              plot_bgcolor: '#151b24',
              font: { color: '#8b949e', size: 11 },
              xaxis: { title: 'Sample', color: '#8b949e', gridcolor: '#30363d', zeroline: false },
              yaxis: { title: 'Amplitude', color: '#8b949e', gridcolor: '#30363d', zeroline: false },
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
        <div className="spectrum-sidebar">
          {data.map((d, i) => (
            <div
              key={d.label}
              className="spectrum-stat-block"
              style={{ borderLeftColor: SNR_COLORS[i % SNR_COLORS.length] }}
            >
              <div className="spectrum-stat-label" style={{ fontSize: '13px' }}>{d.label}</div>
              <div className="spectrum-stat-row" style={{ fontSize: '12px', marginTop: '4px' }}>
                <span className="spectrum-stat-key">S/N (linear):</span>
                <span className="spectrum-stat-val">{d.snr_linear.toFixed(2)}</span>
              </div>
              <div className="spectrum-stat-row" style={{ fontSize: '12px' }}>
                <span className="spectrum-stat-key">S/N (dB):</span>
                <span className="spectrum-stat-val">{d.snr_db.toFixed(1)} dB</span>
              </div>
              <div className="spectrum-stat-row" style={{ fontSize: '12px' }}>
                <span className="spectrum-stat-key">Signal RMS:</span>
                <span className="spectrum-stat-val">{d.signal_rms.toFixed(4)}</span>
              </div>
              <div className="spectrum-stat-row" style={{ fontSize: '12px' }}>
                <span className="spectrum-stat-key">Noise RMS:</span>
                <span className="spectrum-stat-val">{d.noise_rms.toFixed(4)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </DraggableModal>
  )
}

export default SnrModal
