import { useState, useMemo, useCallback } from 'react'
import Plot from 'react-plotly.js'
import DraggableModal from './DraggableModal'

const PALETTE = ['#00d4aa', '#ff6b35', '#3b82f6', '#a855f7', '#f59e0b', '#ef4444', '#14b8a6', '#ec4899']
const FILLS = ['rgba(0, 212, 170, 0.1)', 'rgba(255, 107, 53, 0.1)', 'rgba(59, 130, 246, 0.1)', 'rgba(168, 85, 247, 0.1)', 'rgba(245, 158, 11, 0.1)', 'rgba(239, 68, 68, 0.1)', 'rgba(20, 184, 166, 0.1)', 'rgba(236, 72, 153, 0.1)']

function calcStats(freqs, amps, useDb) {
  const idxMax = amps.indexOf(Math.max(...amps))
  const domFreq = freqs[idxMax]

  const halfMax = useDb ? amps[idxMax] - 6.0206 : amps[idxMax] / 2

  let leftIdx = idxMax
  while (leftIdx > 0 && amps[leftIdx - 1] >= halfMax) leftIdx--
  let rightIdx = idxMax
  while (rightIdx < amps.length - 1 && amps[rightIdx + 1] >= halfMax) rightIdx++

  let leftFreq, rightFreq
  if (leftIdx > 0) {
    const f = (halfMax - amps[leftIdx - 1]) / (amps[leftIdx] - amps[leftIdx - 1])
    leftFreq = freqs[leftIdx - 1] + f * (freqs[leftIdx] - freqs[leftIdx - 1])
  } else {
    leftFreq = freqs[0]
  }
  if (rightIdx < amps.length - 1) {
    const f = (halfMax - amps[rightIdx + 1]) / (amps[rightIdx] - amps[rightIdx + 1])
    rightFreq = freqs[rightIdx + 1] - f * (freqs[rightIdx + 1] - freqs[rightIdx])
  } else {
    rightFreq = freqs[amps.length - 1]
  }

  const freqWidth = rightFreq - leftFreq

  return { domFreq: domFreq.toFixed(1), freqWidth: Math.max(0, freqWidth).toFixed(1) }
}

function SpectrumModal({ spectra, onClose }) {
  if (!spectra || spectra.length === 0) return null

  const maxDataFreq = spectra[0].frequencies[spectra[0].frequencies.length - 1]
  const [maxFreq, setMaxFreq] = useState(Math.round(maxDataFreq))
  const [visible, setVisible] = useState(spectra.map(() => true))
  const [dbMode, setDbMode] = useState(false)
  const [showPhase, setShowPhase] = useState(false)

  const toDb = (arr) => arr.map(v => 20 * Math.log10(Math.max(v, 1e-12)))

  const stats = useMemo(() => {
    if (showPhase) return []
    return spectra.map((s, i) => {
      if (!visible[i]) return null
      const amps = dbMode ? toDb(s.amplitudes) : s.amplitudes
      return calcStats(s.frequencies, amps, dbMode)
    })
  }, [spectra, visible, dbMode, showPhase])

  const toggleVisible = (idx) => {
    setVisible((prev) => {
      const next = [...prev]
      next[idx] = !next[idx]
      return next
    })
  }

  const visibleTraces = spectra.map((s, i) => ({ s, origIdx: i })).filter(({ origIdx }) => visible[origIdx])
  const firstVisibleIdx = visibleTraces.length > 0 ? visibleTraces[0].origIdx : -1
  const traces = visibleTraces.map(({ s, origIdx }) => ({
      x: s.frequencies,
      y: showPhase ? s.phases : (dbMode ? toDb(s.amplitudes) : s.amplitudes),
      type: 'scatter',
      mode: 'lines',
      name: s.label,
      line: { color: PALETTE[origIdx % PALETTE.length], width: 1.5 },
      fill: !showPhase && origIdx === firstVisibleIdx ? 'tozeroy' : 'none',
      fillcolor: FILLS[origIdx % FILLS.length],
    }))

  const onPlotInitialized = useCallback((figure, graphDiv) => {
    const container = graphDiv.querySelector('.modebar-container')
    const modalContent = graphDiv.closest('.modal-content')
    if (container && modalContent) {
      const header = modalContent.querySelector('.modal-header')
      if (header) {
        const headerRect = header.getBoundingClientRect()
        const modalRect = modalContent.getBoundingClientRect()
        container.style.position = 'fixed'
        container.style.left = 'auto'
        container.style.right = (window.innerWidth - modalRect.right + 20) + 'px'
        container.style.top = (headerRect.bottom + 20) + 'px'
      }
    }
  }, [])

  return (
    <DraggableModal title="Spectrum Analysis" onClose={onClose} className="modal-content-wide"
      headerControls={
        <>
          <label className="freq-label">Max Frequency</label>
          <input type="number" className="freq-input" value={maxFreq}
            onChange={(e) => setMaxFreq(Math.max(0, Number(e.target.value)))}
            min={0} max={Math.round(maxDataFreq)} step={10} />
          <span className="freq-unit">Hz</span>
        </>
      }>
      <div className="spectrum-toggles">
        {spectra.map((s, i) => (
          <label key={s.label} className="spectrum-toggle" onClick={() => toggleVisible(i)}>
            <span className="toggle-dot" style={{ background: PALETTE[i % PALETTE.length] }}></span>
            <span className={`toggle-label${visible[i] ? '' : ' dim'}`}>{s.label}</span>
          </label>
        ))}
        <div className="mode-selector">
          <span className={`mode-option${!showPhase ? ' active' : ''}`} onClick={() => setShowPhase(false)}>Amplitude</span>
          <span className={`mode-option${showPhase ? ' active' : ''}`} onClick={() => setShowPhase(true)}>Phase</span>
        </div>
        {!showPhase && (
        <div className="mode-selector" style={{ marginLeft: '4px' }}>
          <span className={`mode-option${!dbMode ? ' active' : ''}`} onClick={() => setDbMode(false)}>Abs</span>
          <span className={`mode-option${dbMode ? ' active' : ''}`} onClick={() => setDbMode(true)}>Db</span>
        </div>
        )}
      </div>
      <div className="spectrum-plot-row">
        <div className="spectrum-plot">
          <Plot
            data={traces}
            layout={{
              autosize: true,
              margin: { l: 50, r: 20, t: 20, b: 50 },
              paper_bgcolor: '#151b24',
              plot_bgcolor: '#151b24',
              font: { color: '#8b949e', size: 11 },
              xaxis: {
                title: 'Frequency (Hz)',
                color: '#8b949e',
                gridcolor: '#30363d',
                zeroline: false,
                range: [0, maxFreq],
              },
              yaxis: {
                title: showPhase ? 'Phase (rad)' : (dbMode ? 'Amplitude (dB)' : 'Amplitude'),
                color: '#8b949e',
                gridcolor: '#30363d',
                zeroline: false,
              },
              dragmode: 'pan',
              hovermode: 'x',
              showlegend: false,
            }}
            config={{
              displayModeBar: true,
              displaylogo: false,
              scrollZoom: true,
              modeBarButtonsToRemove: ['sendDataToCloud', 'lasso2d', 'select2d'],
            }}
            style={{ width: '100%', height: '100%' }}
            useResizeHandler={true}
            onInitialized={onPlotInitialized}
            onUpdate={onPlotInitialized}
          />
        </div>
        <div className="spectrum-sidebar">
          {!showPhase && stats.map((s, i) => s && (
            <div key={i} className="spectrum-stat-block" style={{ borderLeftColor: PALETTE[i % PALETTE.length] }}>
              <div className="spectrum-stat-label">{spectra[i].label}</div>
              <div className="spectrum-stat-row">
                <span className="spectrum-stat-key">Dom Freq:</span>
                <span className="spectrum-stat-val">{s.domFreq} Hz</span>
              </div>
              <div className="spectrum-stat-row">
                <span className="spectrum-stat-key">Freq Width:</span>
                <span className="spectrum-stat-val">{s.freqWidth} Hz</span>
              </div>
            </div>
          ))}
          <div className="spectrum-stat-block" style={{ borderLeftColor: '#8b949e' }}>
            <div className="spectrum-stat-label">Selection</div>
            <div className="spectrum-stat-row">
              <span className="spectrum-stat-key">Traces:</span>
              <span className="spectrum-stat-val">{spectra[0].trace_range[0]}–{spectra[0].trace_range[1]}</span>
            </div>
            <div className="spectrum-stat-row">
              <span className="spectrum-stat-key">Samples:</span>
              <span className="spectrum-stat-val">{spectra[0].sample_range[0]}–{spectra[0].sample_range[1]}</span>
            </div>
          </div>
        </div>
      </div>
    </DraggableModal>
  )
}

export default SpectrumModal
