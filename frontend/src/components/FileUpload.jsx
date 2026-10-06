import { useState, useRef } from 'react'

function FileUpload({ onUpload, isLoading }) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [isOpen, setIsOpen] = useState(true)
  const fileInputRef = useRef(null)

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragOver(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      onUpload(files[0])
    }
  }

  const handleFileSelect = (e) => {
    const files = e.target.files
    if (files.length > 0) {
      onUpload(files[0])
    }
  }

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="card">
      <div className="card-header collapsible" onClick={() => setIsOpen(!isOpen)}>
        <span className={`collapse-icon ${isOpen ? '' : 'collapsed'}`} style={{ fontSize: '10px' }}>&#9660;</span>
        <span>Upload SGY File</span>
      </div>
      {isOpen && (
        <div className="card-body">
          <input
            ref={fileInputRef}
            type="file"
            accept=".sgy,.segy"
            onChange={handleFileSelect}
            disabled={isLoading}
          />

          <div
            className={`upload-zone ${isDragOver ? 'drag-over' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleClick}
          >
            <div className="upload-icon">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <p>{isLoading ? 'Processing...' : 'Drag & drop SGY file here'}</p>
            <p className="formats">Supported: .sgy, .segy</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default FileUpload