import { memo, useMemo } from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
import Plotly from 'plotly.js/lib/core'
import heatmap from 'plotly.js/lib/heatmap'
import scatter from 'plotly.js/lib/scatter'

Plotly.register([heatmap, scatter])
const Plot = createPlotlyComponent(Plotly)
const config = { responsive: true, displaylogo: false, scrollZoom: true }
const base = {
  autosize: true, height: 470, margin: { t: 42, l: 65, r: 35, b: 55 },
  paper_bgcolor: '#172334', plot_bgcolor: '#172334', font: { color: '#e5edf5', size: 11 },
  yaxis: { title: 'Time, ms', autorange: 'reversed' },
}

export const VelocityPlot = memo(function VelocityPlot({ spectrum, picks, onPick, revisionKey }) {
  const data = useMemo(() => spectrum ? [
    { type: 'heatmap', x: spectrum.velocities_mps, y: spectrum.times_ms, z: spectrum.semblance,
      zmin: 0, zmax: 1, colorscale: 'Turbo', colorbar: { title: 'S', thickness: 10 },
      hovertemplate: 'V=%{x} m/s<br>T=%{y} ms<br>S=%{z:.3f}<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x: picks.map(p => p.velocity_mps), y: picks.map(p => p.time_ms),
      line: { color: '#fff', width: 2 }, marker: { color: '#fff', size: 9, line: { color: '#172334', width: 1 } },
      name: 'Velocity picks', hovertemplate: '%{x} m/s @ %{y} ms<extra>Pick</extra>' },
  ] : [], [spectrum, picks])
  const layout = useMemo(() => ({ ...base, title: 'Vertical velocity spectrum', showlegend: false,
    xaxis: { title: 'Stacking velocity, m/s' }, uirevision: revisionKey }), [revisionKey])
  if (!spectrum) return <div className="cmp-placeholder">Calculate a spectrum, then click to add velocity picks.</div>
  return <Plot data={data} layout={layout} config={config} style={{ width: '100%' }} useResizeHandler
    onClick={event => { const point = event.points?.[0]; if (point) onPick({ time_ms: Number(point.y), velocity_mps: Number(point.x) }) }} />
})

function maxAmplitude(panel) {
  let max = 0
  for (const row of panel?.data || []) for (const value of row) max = Math.max(max, Math.abs(value))
  return max || 1
}
export const GatherPlot = memo(function GatherPlot({ panel, title, amplitude, revisionKey }) {
  const x = useMemo(() => panel?.offsets_m?.map((_, i) => i) || [], [panel])
  const ticks = x.filter(i => i % Math.max(1, Math.ceil(x.length / 8)) === 0)
  const limit = amplitude || maxAmplitude(panel)
  const data = useMemo(() => panel ? [{ type: 'heatmap', x, y: panel.times_ms, z: panel.data,
    colorscale: 'RdBu', reversescale: true, zmin: -limit, zmax: limit, showscale: false,
    hovertemplate: 'Trace=%{x}<br>T=%{y} ms<br>A=%{z:.4g}<extra></extra>' }] : [], [panel, x, limit])
  const layout = { ...base, title, uirevision: revisionKey,
    xaxis: { title: 'Trace position (offset labels, m)', tickvals: ticks, ticktext: ticks.map(i => panel?.offsets_m[i]?.toFixed(0)) } }
  if (!panel) return <div className="cmp-placeholder">Gather preview</div>
  return <Plot data={data} layout={layout} config={config} style={{ width: '100%' }} useResizeHandler />
})

export const NmoQC = memo(function NmoQC({ preview, revisionKey }) {
  if (!preview) return null
  const amplitude = maxAmplitude(preview.before)
  return <div className="cmp-plots">
    <GatherPlot panel={preview.before} title="Before NMO (one CMP)" amplitude={amplitude} revisionKey={revisionKey} />
    <GatherPlot panel={preview.after} title="After NMO - identical amplitude scale" amplitude={amplitude} revisionKey={revisionKey} />
  </div>
})

export const SectionPlot = memo(function SectionPlot({ section }) {
  const data = useMemo(() => section ? [{ type: 'heatmap', x: section.cdps, y: section.times_ms, z: section.data,
    colorscale: section.kind === 'amplitude' ? 'RdBu' : 'Viridis', colorbar: { thickness: 12 },
    ...(section.kind === 'amplitude' ? { zmid: 0 } : {}),
    hovertemplate: 'CDP=%{x}<br>T=%{y} ms<br>%{z:.4g}<extra></extra>' }] : [], [section])
  if (!section) return null
  return <Plot data={data} layout={{ ...base, title: `Stack QC: ${section.kind}`, xaxis: { title: 'CDP' }, height: 540 }}
    config={config} style={{ width: '100%' }} useResizeHandler />
})
