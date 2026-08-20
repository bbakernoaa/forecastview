import { useState, useEffect, useRef, useCallback } from 'react'
import type { Dispatch } from 'react'
import type { ViewerAction } from '../context/ViewerContext'

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

/** Supported playback speeds (ms per frame) */
export const PLAYBACK_SPEEDS = [500, 750, 1000, 1500, 2000] as const
export type PlaybackSpeed = (typeof PLAYBACK_SPEEDS)[number]

export interface UseAnimationParams {
  /** Ordered list of available forecast hours */
  forecastHours: number[]
  /** Currently displayed forecast hour */
  currentFhr: number
  /** Dispatch function from ViewerContext */
  dispatch: Dispatch<ViewerAction>
}

export interface UseAnimationReturn {
  /** Whether animation is currently playing */
  playing: boolean
  /** Start playback */
  play: () => void
  /** Stop playback */
  pause: () => void
  /** Toggle play/pause */
  toggle: () => void
  /** Current playback speed in ms */
  speed: PlaybackSpeed
  /** Set a new playback speed */
  setSpeed: (speed: PlaybackSpeed) => void
}

// --------------------------------------------------------------------------
// useAnimation
// --------------------------------------------------------------------------

/**
 * Animation engine hook for stepping through forecast hours.
 *
 * Features:
 * - Configurable playback speed (500ms – 2000ms per frame)
 * - Sequence tagging: each play session gets a unique ID to ignore stale ticks
 * - Wraps around from last frame to first
 * - Pauses automatically when forecastHours becomes empty
 * - Skips missing frames gracefully (the list only contains available hours)
 *
 * The hook does NOT manage data fetching — it only dispatches SET_FORECAST_HOUR.
 * The existing useContours/useFilled hooks react to forecastHour changes and
 * handle their own fetch lifecycle (including keeping old data visible until
 * new data arrives via MapLibre's source.setData atomic update).
 */
export function useAnimation(params: UseAnimationParams): UseAnimationReturn {
  const { forecastHours, currentFhr, dispatch } = params

  const [playing, setPlaying] = useState(false)
  const [speed, setSpeedState] = useState<PlaybackSpeed>(1000)

  // Sequence tag: incremented each time play() starts a new session.
  // If a tick fires with an outdated sequence, it is ignored.
  const sequenceRef = useRef(0)

  // Interval handle ref for cleanup
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Keep mutable refs for values accessed inside the interval callback
  // to avoid stale closures without adding them to dependencies that
  // would restart the interval.
  const forecastHoursRef = useRef(forecastHours)
  const currentFhrRef = useRef(currentFhr)

  useEffect(() => {
    forecastHoursRef.current = forecastHours
  }, [forecastHours])

  useEffect(() => {
    currentFhrRef.current = currentFhr
  }, [currentFhr])

  // Detect external navigation while playing (e.g. user clicks Next/Previous/slider).
  // We track what the animation last dispatched. If currentFhr changes to something
  // different from what we dispatched, it means the user manually navigated → pause.
  const lastDispatchedFhrRef = useRef<number | null>(null)

  useEffect(() => {
    if (playing && lastDispatchedFhrRef.current !== null) {
      if (currentFhr !== lastDispatchedFhrRef.current) {
        // External navigation detected while playing → pause
        stopPlayback()
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentFhr])

  // --------------------------------------------------------------------------
  // Internal helpers
  // --------------------------------------------------------------------------

  const stopPlayback = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setPlaying(false)
    lastDispatchedFhrRef.current = null
  }, [])

  const startPlayback = useCallback(() => {
    // Bump sequence to invalidate any stale interval callbacks
    const seq = ++sequenceRef.current

    // Don't start if no hours available
    if (forecastHoursRef.current.length === 0) return

    setPlaying(true)
    lastDispatchedFhrRef.current = currentFhrRef.current

    // Clear any existing interval (shouldn't happen, but be safe)
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
    }

    intervalRef.current = setInterval(() => {
      // Stale-request protection: if the sequence has moved on, this tick is stale
      if (sequenceRef.current !== seq) {
        return
      }

      const hours = forecastHoursRef.current
      if (hours.length === 0) {
        // No frames available — stop
        stopPlayback()
        return
      }

      const curFhr = currentFhrRef.current
      const curIdx = hours.indexOf(curFhr)

      // Determine next index, wrapping around
      let nextIdx: number
      if (curIdx < 0 || curIdx >= hours.length - 1) {
        // Current hour not found or at end → wrap to beginning
        nextIdx = 0
      } else {
        nextIdx = curIdx + 1
      }

      const nextFhr = hours[nextIdx]
      lastDispatchedFhrRef.current = nextFhr
      dispatch({ type: 'SET_FORECAST_HOUR', payload: nextFhr })
    }, speed)
  }, [dispatch, speed, stopPlayback])

  // --------------------------------------------------------------------------
  // Public API
  // --------------------------------------------------------------------------

  const play = useCallback(() => {
    if (!playing) {
      startPlayback()
    }
  }, [playing, startPlayback])

  const pause = useCallback(() => {
    if (playing) {
      stopPlayback()
    }
  }, [playing, stopPlayback])

  const toggle = useCallback(() => {
    if (playing) {
      stopPlayback()
    } else {
      startPlayback()
    }
  }, [playing, startPlayback, stopPlayback])

  const setSpeed = useCallback(
    (newSpeed: PlaybackSpeed) => {
      setSpeedState(newSpeed)
      // If currently playing, restart with new speed
      if (playing) {
        // Increment sequence to invalidate old interval
        sequenceRef.current++
        if (intervalRef.current !== null) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        // Re-start with updated speed on next render (speed state will update)
      }
    },
    [playing],
  )

  // Restart the interval whenever speed changes while playing
  useEffect(() => {
    if (playing) {
      // Stop old interval, start new one with current speed
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }

      const seq = ++sequenceRef.current
      lastDispatchedFhrRef.current = currentFhrRef.current

      intervalRef.current = setInterval(() => {
        if (sequenceRef.current !== seq) return

        const hours = forecastHoursRef.current
        if (hours.length === 0) {
          stopPlayback()
          return
        }

        const curFhr = currentFhrRef.current
        const curIdx = hours.indexOf(curFhr)

        let nextIdx: number
        if (curIdx < 0 || curIdx >= hours.length - 1) {
          nextIdx = 0
        } else {
          nextIdx = curIdx + 1
        }

        const nextFhr = hours[nextIdx]
        lastDispatchedFhrRef.current = nextFhr
        dispatch({ type: 'SET_FORECAST_HOUR', payload: nextFhr })
      }, speed)
    }

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speed, playing])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  // Pause if forecastHours becomes empty
  useEffect(() => {
    if (playing && forecastHours.length === 0) {
      stopPlayback()
    }
  }, [playing, forecastHours.length, stopPlayback])

  return { playing, play, pause, toggle, speed, setSpeed }
}
