import { useState, useEffect } from 'react'
import { apiGet } from '../api/client'
import type { FilledFeatureCollection } from '../api/types'

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

type FetchStatus = 'idle' | 'loading' | 'success' | 'error'

interface FetchState<T> {
  status: FetchStatus
  data: T | null
  error: string | null
}

export interface UseFilledParams {
  product: string | null
  date: string | null
  run: string | null
  variable: string | null
  level: number | null
  fhr: number | null
}

// --------------------------------------------------------------------------
// useFilled
// --------------------------------------------------------------------------

/**
 * Fetches filled contour GeoJSON from the backend `/api/filled` endpoint.
 *
 * Only fires the request when all required parameters are provided
 * (product, date, run, variable, fhr). Uses AbortController to cancel
 * in-flight requests when dependencies change.
 */
export function useFilled(params: UseFilledParams): FetchState<FilledFeatureCollection> {
  const { product, date, run, variable, level, fhr } = params

  const [state, setState] = useState<FetchState<FilledFeatureCollection>>({
    status: 'idle',
    data: null,
    error: null,
  })

  useEffect(() => {
    // All required params must be present
    if (!product || !date || !run || !variable || fhr == null) {
      setState({ status: 'idle', data: null, error: null })
      return
    }

    const controller = new AbortController()
    setState({ status: 'loading', data: null, error: null })

    // Build query params — only include non-null values
    const queryParams: Record<string, string> = {
      product,
      date,
      run,
      variable,
      fhr: String(fhr),
    }

    if (level != null) {
      queryParams.level = String(level)
    }

    apiGet<FilledFeatureCollection>('/api/filled', queryParams, controller.signal)
      .then((res) => {
        setState({ status: 'success', data: res, error: null })
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setState({ status: 'error', data: null, error: String(err) })
      })

    return () => controller.abort()
  }, [product, date, run, variable, level, fhr])

  return state
}
