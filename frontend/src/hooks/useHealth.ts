import { useState, useEffect } from 'react'
import { apiGet } from '../api/client'
import { STATIC_MODE } from '../api/staticMode'

interface HealthResponse {
  status: string
  version: string
}

type ConnectionStatus = 'loading' | 'connected' | 'error'

interface HealthState {
  status: ConnectionStatus
  version?: string
}

/**
 * Hook that calls /api/health on mount and returns connection status.
 *
 * In static mode there is no backend to ping, so report connected.
 */
export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>({ status: 'loading' })

  useEffect(() => {
    if (STATIC_MODE) {
      setState({ status: 'connected', version: 'static' })
      return
    }

    const controller = new AbortController()

    apiGet<HealthResponse>('/api/health', undefined, controller.signal)
      .then((data) => {
        setState({ status: 'connected', version: data.version })
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setState({ status: 'error' })
      })

    return () => controller.abort()
  }, [])

  return state
}
