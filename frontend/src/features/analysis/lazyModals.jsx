import { lazy, Suspense } from 'react'

function defer(loader) {
  const Modal = lazy(loader)
  return function DeferredModal(props) {
    return <Suspense fallback={<div role="status">Loading analysis...</div>}><Modal {...props} /></Suspense>
  }
}
export const SpectrumModal = defer(() => import('../../components/SpectrumModal'))
export const AutocorrelationModal = defer(() => import('../../components/AutocorrelationModal'))
export const FxSpectrumModal = defer(() => import('../../components/FxSpectrumModal'))
export const SnrModal = defer(() => import('../../components/SnrModal'))
export const FkSpectrumModal = defer(() => import('../../components/FkSpectrumModal'))
