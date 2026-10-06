import { useState, useRef, useEffect } from 'react'

export default function DraggableModal({ title, onClose, headerControls, children, initialWidth = 700, initialHeight = 500, className = '' }) {
  const [pos, setPos] = useState(() => ({
    x: Math.max(0, (window.innerWidth - initialWidth) / 2),
    y: Math.max(0, (window.innerHeight - initialHeight) / 2),
  }))
  const dragging = useRef(false)
  const dragOff = useRef({ x: 0, y: 0 })

  const onMove = useRef((e) => {
    if (!dragging.current) return
    setPos({ x: Math.max(0, e.clientX - dragOff.current.x), y: Math.max(0, e.clientY - dragOff.current.y) })
  })

  const onUp = useRef(() => { dragging.current = false })

  useEffect(() => {
    const move = (e) => onMove.current(e)
    const up = () => onUp.current()
    document.addEventListener('mousemove', move)
    document.addEventListener('mouseup', up)
    return () => { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up) }
  }, [])

  const handleMouseDown = (e) => {
    if (e.target.closest('.modal-close') || e.target.closest('input, select, button, label, a')) return
    dragging.current = true
    dragOff.current = { x: e.clientX - pos.x, y: e.clientY - pos.y }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`modal-content ${className}`}
        style={{ left: pos.x, top: pos.y, width: initialWidth, height: initialHeight }}
        onClick={(e) => e.stopPropagation()}>
        <div className="modal-header" onMouseDown={handleMouseDown}>
          <span>{title}</span>
          <div className="modal-header-controls">
            {headerControls}
            <button className="modal-close" onClick={onClose}>&#10005;</button>
          </div>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}
