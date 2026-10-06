import { useState } from 'react'

function StatisticsPanel({ fileName, statistics }) {
  const [isOpen, setIsOpen] = useState(false)
  const [fileStatsOpen, setFileStatsOpen] = useState(false)
  const [headerStatsOpen, setHeaderStatsOpen] = useState(false)

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  const formatNumber = (num) => {
    return num.toLocaleString()
  }

  const formatValue = (val) => {
    if (Math.abs(val) < 0.01 || Math.abs(val) > 9999) {
      return val.toExponential(2)
    }
    return val.toLocaleString(undefined, { maximumFractionDigits: 4 })
  }

  const renderBody = () => {
    if (!statistics) {
      return (
        <div className="card-body">
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
            Upload and analyze a file to see statistics
          </p>
        </div>
      )
    }

    return (
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '8px' }}>
        <div className="sub-block-header collapsible" onClick={(e) => { e.stopPropagation(); setFileStatsOpen(!fileStatsOpen) }}>
          <span className={`collapse-icon ${fileStatsOpen ? '' : 'collapsed'}`} style={{ fontSize: '10px' }}>&#9660;</span>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>File Stats</span>
        </div>
        {fileStatsOpen && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <div className="stat-row">
              <span className="stat-label">File</span>
              <span className="stat-value" style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {statistics.file_name}
              </span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Size</span>
              <span className="stat-value">{formatFileSize(statistics.file_size)}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Traces</span>
              <span className="stat-value">{formatNumber(statistics.trace_count)}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Samples/Trace</span>
              <span className="stat-value">{formatNumber(statistics.samples_per_trace)}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Sample Rate</span>
              <span className="stat-value">{statistics.sample_rate} ms</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Min Amplitude</span>
              <span className="stat-value">{formatValue(statistics.min_amplitude)}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Max Amplitude</span>
              <span className="stat-value">{formatValue(statistics.max_amplitude)}</span>
            </div>
          </div>
        )}
        <div className="sub-block-header collapsible" onClick={(e) => { e.stopPropagation(); setHeaderStatsOpen(!headerStatsOpen) }}>
          <span className={`collapse-icon ${headerStatsOpen ? '' : 'collapsed'}`} style={{ fontSize: '10px' }}>&#9660;</span>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>Header Stats</span>
        </div>
        {headerStatsOpen && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <div className="stat-row" style={{ display: 'grid', gridTemplateColumns: '1fr 60px 60px', gap: '8px', fontSize: '11px', color: 'var(--text-secondary)' }}>
              <span>Header</span>
              <span style={{ textAlign: 'right' }}>Min</span>
              <span style={{ textAlign: 'right' }}>Max</span>
            </div>
            {[ 
              ['SHOT', 'shot'],
              ['FFID', 'ffid'],
              ['CDP', 'cdp'],
              ['OFFSET', 'offset'],
              ['INLINE', 'inline'],
              ['XLINE', 'xline'],
            ].map(([label, key]) => (
              <div key={key} className="stat-row" style={{ display: 'grid', gridTemplateColumns: '1fr 60px 60px', gap: '8px' }}>
                <span className="stat-label">{label}</span>
                <span className="stat-value" style={{ textAlign: 'right' }}>{statistics[`${key}_min`] || '—'}</span>
                <span className="stat-value" style={{ textAlign: 'right' }}>{statistics[`${key}_max`] || '—'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header collapsible" onClick={() => setIsOpen(!isOpen)}>
        <span>Statistics</span>
        <span className={`collapse-icon ${isOpen ? '' : 'collapsed'}`}>&#9660;</span>
      </div>
      {isOpen && renderBody()}
    </div>
  )
}

export default StatisticsPanel