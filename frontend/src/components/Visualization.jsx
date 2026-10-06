import { memo, useRef } from 'react'
import Plot from 'react-plotly.js'

const Visualization = memo(function Visualization({ data, isLoading, compact, selectionMode, onSelection, syncView, onViewChange, colorscale, paletteMin, paletteMax, amplitudeScale, showColorbar, sortMode }) {
  const lastSel = useRef(0)

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="viz-canvas-container">
          <div className="loading">
            <div className="spinner"></div>
            <span>Processing...</span>
          </div>
        </div>
      )
    }

    if (!data) {
      return (
        <div className="viz-canvas-container">
          <div className="viz-placeholder">
            <div className="viz-placeholder-icon">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
              </svg>
            </div>
            <span>No data</span>
          </div>
        </div>
      )
    }

    const zData = []
    const scale = amplitudeScale !== undefined ? amplitudeScale / 100 : 1
    for (let s = 0; s < data.samples; s++) {
      const row = []
      for (let t = 0; t < data.traces; t++) {
        const v = data.data[t][s]
        row.push(v != null ? v * scale : NaN)
      }
      zData.push(row)
    }

    const isTimeSlice = sortMode === 'time_slice'
    const xAxisTitle = isTimeSlice ? 'Xline' : sortMode === 'inline_xline' ? 'Crossline' : sortMode === 'crossline_xline' ? 'Inline' : sortMode === 'cdp_offset' ? 'Offset' : sortMode === 'ffid_offset' ? 'Offset' : sortMode === 'ffid_chan' ? 'Chan' : 'Trace'

    const xTickLabels = isTimeSlice ? data.xline_labels : sortMode === 'inline_xline' && data?.xline_labels ? data.xline_labels : sortMode === 'crossline_xline' && data?.inline_labels ? data.inline_labels : sortMode === 'cdp_offset' && data?.offset_labels ? data.offset_labels : sortMode === 'ffid_offset' && data?.offset_labels_ffid ? data.offset_labels_ffid : sortMode === 'ffid_chan' && data?.chan_labels ? data.chan_labels : null

    const yAxisTitle = isTimeSlice ? 'Inline' : 'Sample'

    const emitSelection = (traceStart, traceEnd, sampleStart, sampleEnd) => {
      if (!onSelection) return
      const now = Date.now()
      if (now - lastSel.current < 300) return
      lastSel.current = now
      onSelection({
        trace_start: Math.floor(traceStart),
        trace_end: Math.floor(traceEnd),
        sample_start: Math.floor(sampleStart),
        sample_end: Math.floor(sampleEnd),
      })
    }

    const handleSelection = (eventData) => {
      let traceStart, traceEnd, sampleStart, sampleEnd

      if (eventData?.range) {
        const x0 = Math.min(eventData.range.x[0], eventData.range.x[1])
        const x1 = Math.max(eventData.range.x[0], eventData.range.x[1])
        const y0 = Math.min(eventData.range.y[0], eventData.range.y[1])
        const y1 = Math.max(eventData.range.y[0], eventData.range.y[1])
        traceStart = Math.floor(x0)
        traceEnd = Math.ceil(x1)
        sampleStart = Math.floor(y0)
        sampleEnd = Math.ceil(y1)
      } else if (eventData?.points && eventData.points.length > 0) {
        let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity
        for (const p of eventData.points) {
          const px = p.x !== undefined ? p.x : p.pointNumber % data.traces
          const py = p.y !== undefined ? p.y : Math.floor(p.pointNumber / data.traces)
          if (px < x0) x0 = px
          if (px > x1) x1 = px
          if (py < y0) y0 = py
          if (py > y1) y1 = py
        }
        traceStart = Math.floor(Math.min(x0, x1))
        traceEnd = Math.ceil(Math.max(x0, x1))
        sampleStart = Math.floor(Math.min(y0, y1))
        sampleEnd = Math.ceil(Math.max(y0, y1))
      } else {
        return
      }

      emitSelection(traceStart, traceEnd, sampleStart, sampleEnd)
    }

    const handleRelayout = (layout) => {
      const xr = layout['xaxis.range']
      const yr = layout['yaxis.range']
      let x0 = layout['xaxis.range[0]'] ?? xr?.[0]
      let x1 = layout['xaxis.range[1]'] ?? xr?.[1]
      let y0 = layout['yaxis.range[0]'] ?? yr?.[0]
      let y1 = layout['yaxis.range[1]'] ?? yr?.[1]

      if (x0 != null && x1 != null && x0 > x1) [x0, x1] = [x1, x0]
      if (y0 != null && y1 != null && y0 > y1) [y0, y1] = [y1, y0]

      if (onViewChange && !selectionMode) {
        if (x0 != null && x1 != null && y0 != null && y1 != null) {
          if (!(syncView &&
            Math.abs(x0 - syncView.xrange[0]) < 0.001 &&
            Math.abs(x1 - syncView.xrange[1]) < 0.001 &&
            Math.abs(y0 - syncView.yrange[0]) < 0.001 &&
            Math.abs(y1 - syncView.yrange[1]) < 0.001)) {
            onViewChange({ xrange: [x0, x1], yrange: [y0, y1] })
          }
        } else if (layout['xaxis.autorange'] === true || layout['yaxis.autorange'] === true) {
          onViewChange(null)
        }
      }

      if (onSelection && selectionMode) {
        if (x0 != null && x1 != null && y0 != null && y1 != null) {
          emitSelection(
            Math.floor(Math.min(x0, x1)),
            Math.ceil(Math.max(x0, x1)),
            Math.floor(Math.min(y0, y1)),
            Math.ceil(Math.max(y0, y1)),
          )
        }
      }
    }

    const modeBarButtonsToRemove = selectionMode
      ? ['sendDataToCloud', 'lasso2d']
      : ['sendDataToCloud', 'lasso2d', 'select2d']

    return (
      <div className="viz-canvas-container">
        <Plot
          data={[
            {
              z: zData,
              type: 'heatmap',
              colorscale: colorscale || 'RdBu',
              zmid: 0,
              zmin: paletteMin,
              zmax: paletteMax,
              showscale: showColorbar !== false,
              colorbar: {
                titleside: 'right',
                thickness: 15,
                len: 0.8,
              },
            },
          ]}
          layout={{
            autosize: true,
            margin: { l: 40, r: 20, t: 10, b: 40 },
            paper_bgcolor: '#151b24',
            plot_bgcolor: '#151b24',
            font: { color: '#8b949e', size: 9 },
            xaxis: {
              title: xAxisTitle,
              color: '#8b949e',
              gridcolor: '#30363d',
              zeroline: false,
              range: syncView ? syncView.xrange : undefined,
              tickvals: xTickLabels
                ? xTickLabels.map((_, i) => i).filter((_, i) => i % Math.max(1, Math.floor(xTickLabels.length / 10)) === 0)
                : undefined,
              ticktext: xTickLabels
                ? xTickLabels.filter((_, i) => i % Math.max(1, Math.floor(xTickLabels.length / 10)) === 0)
                : undefined,
            },
            yaxis: {
              title: yAxisTitle,
              color: '#8b949e',
              gridcolor: '#30363d',
              zeroline: false,
              autorange: 'reversed',
              range: syncView ? syncView.yrange : undefined,
              tickvals: isTimeSlice && data?.inline_labels
                ? data.inline_labels.map((_, i) => i).filter((_, i) => i % Math.max(1, Math.floor(data.inline_labels.length / 10)) === 0)
                : undefined,
              ticktext: isTimeSlice && data?.inline_labels
                ? data.inline_labels.filter((_, i) => i % Math.max(1, Math.floor(data.inline_labels.length / 10)) === 0)
                : undefined,
            },
            dragmode: selectionMode ? 'select' : 'pan',
            hovermode: 'closest',
          }}
          config={{
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove,
            scrollZoom: true,
          }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
          onSelected={handleSelection}
          onRelayout={handleRelayout}
        />
      </div>
    )
  }

  if (compact) {
    return renderContent()
  }

  return (
    <div className="card viz-card">
      <div className="card-header">Visualization</div>
      {renderContent()}
    </div>
  )
})

export default Visualization