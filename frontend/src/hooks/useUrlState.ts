import { useEffect, useRef } from 'react'
import type { ViewerState, ViewerAction } from '../context/ViewerContext'
import type { RenderingMode } from '../components/RenderingSelector'
import type { Dispatch } from 'react'

// --------------------------------------------------------------------------
// URL param keys
// --------------------------------------------------------------------------

const PARAM_PRODUCT = 'product'
const PARAM_DATE = 'date'
const PARAM_RUN = 'run'
const PARAM_VARIABLE = 'variable'
const PARAM_LEVEL = 'level'
const PARAM_FHR = 'fhr'
const PARAM_MODE = 'mode'

// --------------------------------------------------------------------------
// Defaults (matching INITIAL_STATE in ViewerContext)
// --------------------------------------------------------------------------

const DEFAULT_PRODUCT = 'air'
const DEFAULT_FHR = 0
const DEFAULT_MODE: RenderingMode = 'filled+contours'

const VALID_MODES: RenderingMode[] = ['contours', 'filled', 'filled+contours']

function isValidMode(value: string): value is RenderingMode {
  return (VALID_MODES as string[]).includes(value)
}

// --------------------------------------------------------------------------
// Encoding helpers (exported for testing / property tests)
// --------------------------------------------------------------------------

export interface UrlStateParams {
  product: string
  date: string | null
  run: string | null
  variable: string | null
  level: number | null
  fhr: number
  mode: RenderingMode
}

/**
 * Encode viewer state to URL search params string.
 * Omits params that match defaults or are null to keep URLs clean.
 */
export function encodeStateToUrl(state: UrlStateParams): string {
  const params = new URLSearchParams()

  // Always encode product (even if default, since it identifies the view)
  params.set(PARAM_PRODUCT, state.product)

  if (state.date !== null) {
    params.set(PARAM_DATE, state.date)
  }
  if (state.run !== null) {
    params.set(PARAM_RUN, state.run)
  }
  if (state.variable !== null) {
    params.set(PARAM_VARIABLE, state.variable)
  }
  if (state.level !== null) {
    params.set(PARAM_LEVEL, String(state.level))
  }
  if (state.fhr !== DEFAULT_FHR) {
    params.set(PARAM_FHR, String(state.fhr))
  }
  if (state.mode !== DEFAULT_MODE) {
    params.set(PARAM_MODE, state.mode)
  }

  return params.toString()
}

/**
 * Decode URL search params string into a partial viewer state.
 * Invalid or missing values are returned as defaults/null.
 */
export function decodeStateFromUrl(search: string): UrlStateParams {
  const params = new URLSearchParams(search)

  const product = params.get(PARAM_PRODUCT) || DEFAULT_PRODUCT
  const date = params.get(PARAM_DATE) || null
  const run = params.get(PARAM_RUN) || null
  const variable = params.get(PARAM_VARIABLE) || null

  const levelStr = params.get(PARAM_LEVEL)
  let level: number | null = null
  if (levelStr !== null) {
    const parsed = Number(levelStr)
    if (Number.isFinite(parsed)) {
      level = parsed
    }
  }

  const fhrStr = params.get(PARAM_FHR)
  let fhr = DEFAULT_FHR
  if (fhrStr !== null) {
    const parsed = Number(fhrStr)
    if (Number.isFinite(parsed) && Number.isInteger(parsed) && parsed >= 0) {
      fhr = parsed
    }
  }

  const modeStr = params.get(PARAM_MODE)
  let mode: RenderingMode = DEFAULT_MODE
  if (modeStr !== null && isValidMode(modeStr)) {
    mode = modeStr
  }

  return { product, date, run, variable, level, fhr, mode }
}

// --------------------------------------------------------------------------
// Hook
// --------------------------------------------------------------------------

/**
 * Synchronizes ViewerState ↔ URL query parameters.
 *
 * On mount: reads URL params and dispatches actions to restore state.
 * On state change: updates URL via replaceState (no history entries added).
 *
 * Only encodes: product, date, run, variable, level, fhr, rendering mode.
 * Transient state (map viewport, inspector point) is NOT encoded.
 */
export function useUrlState(state: ViewerState, dispatch: Dispatch<ViewerAction>): void {
  const initializedRef = useRef(false)

  // On mount: parse URL and dispatch state restoration
  useEffect(() => {
    const search = window.location.search
    if (!search) {
      initializedRef.current = true
      return
    }

    const parsed = decodeStateFromUrl(search)

    // Dispatch in hierarchical order (product → date → run → variable → level)
    // so cascading resets don't wipe out downstream values we want to set.
    // We dispatch all at once; the reducer handles each action independently.
    if (parsed.product !== state.product) {
      dispatch({ type: 'SET_PRODUCT', payload: parsed.product })
    }
    if (parsed.date !== null) {
      dispatch({ type: 'SET_DATE', payload: parsed.date })
    }
    if (parsed.run !== null) {
      dispatch({ type: 'SET_RUN', payload: parsed.run })
    }
    if (parsed.variable !== null) {
      dispatch({ type: 'SET_VARIABLE', payload: parsed.variable })
    }
    if (parsed.level !== null) {
      dispatch({ type: 'SET_LEVEL', payload: parsed.level })
    }
    if (parsed.fhr !== DEFAULT_FHR) {
      dispatch({ type: 'SET_FORECAST_HOUR', payload: parsed.fhr })
    }
    if (parsed.mode !== DEFAULT_MODE) {
      dispatch({ type: 'SET_RENDERING_MODE', payload: parsed.mode })
    }

    initializedRef.current = true
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Run once on mount only

  // On state change: update URL
  useEffect(() => {
    if (!initializedRef.current) return

    const encoded = encodeStateToUrl({
      product: state.product,
      date: state.date,
      run: state.run,
      variable: state.variable,
      level: state.level,
      fhr: state.forecastHour,
      mode: state.renderingMode,
    })

    const newUrl = encoded ? `${window.location.pathname}?${encoded}` : window.location.pathname
    window.history.replaceState(null, '', newUrl)
  }, [
    state.product,
    state.date,
    state.run,
    state.variable,
    state.level,
    state.forecastHour,
    state.renderingMode,
  ])
}
