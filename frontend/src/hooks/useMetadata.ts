import { useState, useEffect } from 'react'
import { apiGet } from '../api/client'
import type {
  DatesResponse,
  RunsResponse,
  VariablesResponse,
  LevelsResponse,
  TimesResponse,
  VariableInfo,
  LevelInfo,
  ForecastHourEntry,
} from '../api/types'

// --------------------------------------------------------------------------
// Shared types
// --------------------------------------------------------------------------

type FetchStatus = 'idle' | 'loading' | 'success' | 'error'

interface FetchState<T> {
  status: FetchStatus
  data: T | null
  error: string | null
}

// --------------------------------------------------------------------------
// useDates
// --------------------------------------------------------------------------

export function useDates(product: string | null): FetchState<string[]> {
  const [state, setState] = useState<FetchState<string[]>>({
    status: 'idle',
    data: null,
    error: null,
  })

  useEffect(() => {
    if (!product) {
      setState({ status: 'idle', data: null, error: null })
      return
    }

    const controller = new AbortController()
    setState({ status: 'loading', data: null, error: null })

    apiGet<DatesResponse>('/api/dates', { product }, controller.signal)
      .then((res) => {
        setState({ status: 'success', data: res.dates, error: null })
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setState({ status: 'error', data: null, error: String(err) })
      })

    return () => controller.abort()
  }, [product])

  return state
}

// --------------------------------------------------------------------------
// useRuns
// --------------------------------------------------------------------------

export function useRuns(
  product: string | null,
  date: string | null
): FetchState<string[]> {
  const [state, setState] = useState<FetchState<string[]>>({
    status: 'idle',
    data: null,
    error: null,
  })

  useEffect(() => {
    if (!product || !date) {
      setState({ status: 'idle', data: null, error: null })
      return
    }

    const controller = new AbortController()
    setState({ status: 'loading', data: null, error: null })

    apiGet<RunsResponse>('/api/runs', { product, date }, controller.signal)
      .then((res) => {
        setState({ status: 'success', data: res.runs, error: null })
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setState({ status: 'error', data: null, error: String(err) })
      })

    return () => controller.abort()
  }, [product, date])

  return state
}

// --------------------------------------------------------------------------
// useVariables
// --------------------------------------------------------------------------

export function useVariables(
  product: string | null,
  date: string | null,
  run: string | null
): FetchState<VariableInfo[]> {
  const [state, setState] = useState<FetchState<VariableInfo[]>>({
    status: 'idle',
    data: null,
    error: null,
  })

  useEffect(() => {
    if (!product || !date || !run) {
      setState({ status: 'idle', data: null, error: null })
      return
    }

    const controller = new AbortController()
    setState({ status: 'loading', data: null, error: null })

    apiGet<VariablesResponse>(
      '/api/variables',
      { product, date, run },
      controller.signal
    )
      .then((res) => {
        setState({ status: 'success', data: res.variables, error: null })
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setState({ status: 'error', data: null, error: String(err) })
      })

    return () => controller.abort()
  }, [product, date, run])

  return state
}

// --------------------------------------------------------------------------
// useLevels
// --------------------------------------------------------------------------

export function useLevels(
  product: string | null,
  date: string | null,
  run: string | null,
  variable: string | null
): FetchState<LevelInfo[]> {
  const [state, setState] = useState<FetchState<LevelInfo[]>>({
    status: 'idle',
    data: null,
    error: null,
  })

  useEffect(() => {
    if (!product || !date || !run || !variable) {
      setState({ status: 'idle', data: null, error: null })
      return
    }

    const controller = new AbortController()
    setState({ status: 'loading', data: null, error: null })

    apiGet<LevelsResponse>(
      '/api/levels',
      { product, date, run, variable },
      controller.signal
    )
      .then((res) => {
        setState({ status: 'success', data: res.levels, error: null })
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setState({ status: 'error', data: null, error: String(err) })
      })

    return () => controller.abort()
  }, [product, date, run, variable])

  return state
}

// --------------------------------------------------------------------------
// useTimes
// --------------------------------------------------------------------------

export interface TimesData {
  initTime: string
  forecastHours: ForecastHourEntry[]
}

export function useTimes(
  product: string | null,
  date: string | null,
  run: string | null
): FetchState<TimesData> {
  const [state, setState] = useState<FetchState<TimesData>>({
    status: 'idle',
    data: null,
    error: null,
  })

  useEffect(() => {
    if (!product || !date || !run) {
      setState({ status: 'idle', data: null, error: null })
      return
    }

    const controller = new AbortController()
    setState({ status: 'loading', data: null, error: null })

    apiGet<TimesResponse>('/api/times', { product, date, run }, controller.signal)
      .then((res) => {
        setState({
          status: 'success',
          data: { initTime: res.init_time, forecastHours: res.forecast_hours },
          error: null,
        })
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setState({ status: 'error', data: null, error: String(err) })
      })

    return () => controller.abort()
  }, [product, date, run])

  return state
}

// --------------------------------------------------------------------------
// useMetadata — combined orchestrating hook
// --------------------------------------------------------------------------

export interface MetadataState {
  dates: FetchState<string[]>
  runs: FetchState<string[]>
  variables: FetchState<VariableInfo[]>
  levels: FetchState<LevelInfo[]>
  times: FetchState<TimesData>
}

/**
 * Combined metadata hook that orchestrates dependent fetches.
 *
 * When a parent selector value changes, downstream hooks automatically
 * refetch because their dependency parameters change (or become null,
 * resetting them to idle).
 */
export function useMetadata(
  product: string | null,
  date: string | null,
  run: string | null,
  variable: string | null
): MetadataState {
  const dates = useDates(product)
  const runs = useRuns(product, date)
  const variables = useVariables(product, date, run)
  const levels = useLevels(product, date, run, variable)
  const times = useTimes(product, date, run)

  return { dates, runs, variables, levels, times }
}
