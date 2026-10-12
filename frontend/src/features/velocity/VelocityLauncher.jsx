import { Component, lazy, Suspense, useState } from 'react'
const Workbench = lazy(() => import('./VelocityWorkbench'))

class Boundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (this.state.error) return <div role="alert">CMP window failed to load: {this.state.error.message}
      <button onClick={this.props.onClose}>Close</button></div>
    return this.props.children
  }
}
export default function VelocityLauncher({ fileId, onOutputCreated }) {
  const [open, setOpen] = useState(false)
  return <>
    <div className="card">
      <div className="card-header">CMP processing</div>
      <div className="card-body">
        <button className="btn btn-primary" onClick={() => setOpen(true)}>Velocity / NMO / STACK</button>
      </div>
    </div>
    {open && <Boundary onClose={() => setOpen(false)}>
      <Suspense fallback={<div role="status">Loading CMP workspace...</div>}>
        <Workbench initialFileId={fileId} onClose={() => setOpen(false)} onOutputCreated={onOutputCreated} />
      </Suspense>
    </Boundary>}
  </>
}
