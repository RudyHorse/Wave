import { useCallback, useEffect, useRef, useState } from 'react'
import { apiError, isCancelled } from './api'

// Abort stale requests and never let old responses overwrite a new CMP's plots.
export function useLatestRequest(onError) {
  const active = useRef(null)
  const [busy, setBusy] = useState(false)
  const invalidate = useCallback(() => {
    active.current?.abort()
    active.current = null
    setBusy(false)
  }, [])
  useEffect(() => () => { active.current?.abort(); active.current = null }, [])
  const run = useCallback(async (request, receive) => {
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    setBusy(true)
    try {
      const result = await request(controller.signal)
      if (active.current === controller) receive(result.data)
    } catch (error) {
      if (active.current === controller && !isCancelled(error)) onError(apiError(error))
    } finally {
      if (active.current === controller) { active.current = null; setBusy(false) }
    }
  }, [onError])
  return { run, invalidate, busy }
}
