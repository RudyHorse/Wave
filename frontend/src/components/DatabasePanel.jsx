function DatabasePanel({ storedFiles, showDatabase, onToggle }) {
  return (
    <div className="card">
      <div className="card-header" style={{ cursor: 'default', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Database</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{storedFiles.length} file{storedFiles.length !== 1 ? 's' : ''}</span>
          <label className="toggle-switch" onClick={(e) => e.stopPropagation()}>
            <input type="checkbox" checked={showDatabase} onChange={(e) => onToggle(e.target.checked)} />
            <span className="toggle-slider"></span>
          </label>
        </div>
      </div>
    </div>
  )
}

export default DatabasePanel
