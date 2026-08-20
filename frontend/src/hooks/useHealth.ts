import { useState, useEffect } from 'react'
import { apiGet } from '../api/client'

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
 */
export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>({ status: 'loading' })

  useEffect(() => {
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
