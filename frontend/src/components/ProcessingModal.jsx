function ProcessingModal({ steps, onCancel }) {
  return (
    <div className="modal-overlay">
      <div className="processing-modal">
        <div className="processing-modal-title">Processing</div>
        <div className="processing-modal-steps">
          {steps.map((s, i) => (
            <span key={i} className="step-badge">{s.title || s.type}</span>
          ))}
        </div>
        <div className="progress-bar-track">
          <div className="progress-bar-fill"></div>
        </div>
        <button className="btn btn-cancel" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  )
}

export default ProcessingModal