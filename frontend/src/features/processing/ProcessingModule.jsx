function Module({ title, enabled, onToggle, paramsOpen, onToggleParams, onDragStart, onDragOver, onDrop, dragIndex, onRemove, children }) {
  return (
    <div
      className="processing-module"
      draggable={!!onDragStart}
      onDragStart={(e) => onDragStart && onDragStart(e, dragIndex)}
      onDragOver={(e) => onDragOver && onDragOver(e, dragIndex)}
      onDrop={(e) => onDrop && onDrop(e, dragIndex)}
    >
      <div className="module-header">
        {onDragStart && <span className="drag-handle" title="Drag to reorder">⠿</span>}
        <span className="module-title">{title}</span>
        <div className="module-header-controls">
          {onToggle && (
            <label className="toggle-switch">
              <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
              <span className="toggle-slider"></span>
            </label>
          )}
          {onRemove && (
            <button className="module-remove" onClick={() => onRemove()} title="Remove">&times;</button>
          )}
          {onToggleParams && (
            <span
              className={`collapse-icon ${paramsOpen ? '' : 'collapsed'}`}
              onClick={(e) => { e.stopPropagation(); onToggleParams(!paramsOpen) }}
            >&#9660;</span>
          )}
        </div>
      </div>
      {(!onToggleParams || paramsOpen) && <div className="module-params">{children}</div>}
    </div>
  )
}


export default Module
