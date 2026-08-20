import { useCallback, useMemo } from 'react'
import { useViewer } from '../context/ViewerContext'
import { useTimes } from '../hooks/useMetadata'
import { useAnimation, PLAYBACK_SPEEDS } from '../hooks/useAnimation'
import type { PlaybackSpeed } from '../hooks/useAnimation'

const buttonStyle: React.CSSProperties = {
  padding: '4px 8px',
  fontSize: '1rem',
  cursor: 'pointer',
  border: '1px solid #555',
  borderRadius: '3px',
  background: '#2a2a2a',
  color: '#ccc',
  lineHeight: 1,
  minWidth: '32px',
}

const disabledStyle: React.CSSProperties = {
  ...buttonStyle,
  cursor: 'default',
  color: '#555',
  opacity: 0.5,
}

const speedButtonStyle: React.CSSProperties = {
  padding: '2px 6px',
  fontSize: '0.7rem',
  cursor: 'pointer',
  border: '1px solid #555',
  borderRadius: '3px',
  background: '#2a2a2a',
  color: '#aaa',
  lineHeight: 1,
  whiteSpace: 'nowrap',
}

/** Format speed value for display */
function formatSpeed(speed: PlaybackSpeed): string {
  if (speed >= 1000) {
    return `${speed / 1000}s`
  }
  return `${speed}ms`
}

/**
 * PlaybackControls provides First, Previous, Play/Pause, Next, Last buttons
 * and a speed selector for stepping through and animating forecast hours.
 *
 * The Play/Pause button is wired to the useAnimation hook which manages
 * the interval timer, sequence tagging, and frame stepping.
 *
 * Manual navigation (First/Previous/Next/Last) automatically pauses any
 * active animation because the external forecastHour change is detected
 * by useAnimation's stale-navigation guard.
 */
function PlaybackControls() {
  const { state, dispatch } = useViewer()
  const { product, date, run, forecastHour } = state

  const { data: timesData } = useTimes(product, date, run)

  const forecastHours = useMemo(() => {
    if (!timesData) return []
    return timesData.forecastHours.map((entry) => entry.fhr)
  }, [timesData])

  const { playing, toggle, pause, speed, setSpeed } = useAnimation({
    forecastHours,
    currentFhr: forecastHour,
    dispatch,
  })

  const currentIndex = useMemo(() => {
    const idx = forecastHours.indexOf(forecastHour)
    return idx >= 0 ? idx : 0
  }, [forecastHours, forecastHour])

  const isFirst = currentIndex <= 0
  const isLast = currentIndex >= forecastHours.length - 1
  const hasHours = forecastHours.length > 0

  const goFirst = useCallback(() => {
    if (hasHours) {
      pause()
      dispatch({ type: 'SET_FORECAST_HOUR', payload: forecastHours[0] })
    }
  }, [dispatch, forecastHours, hasHours, pause])

  const goPrevious = useCallback(() => {
    if (hasHours && !isFirst) {
      pause()
      dispatch({ type: 'SET_FORECAST_HOUR', payload: forecastHours[currentIndex - 1] })
    }
  }, [dispatch, forecastHours, currentIndex, isFirst, hasHours, pause])

  const goNext = useCallback(() => {
    if (hasHours && !isLast) {
      pause()
      dispatch({ type: 'SET_FORECAST_HOUR', payload: forecastHours[currentIndex + 1] })
    }
  }, [dispatch, forecastHours, currentIndex, isLast, hasHours, pause])

  const goLast = useCallback(() => {
    if (hasHours) {
      pause()
      dispatch({
        type: 'SET_FORECAST_HOUR',
        payload: forecastHours[forecastHours.length - 1],
      })
    }
  }, [dispatch, forecastHours, hasHours, pause])

  const cycleSpeed = useCallback(() => {
    const currentIdx = PLAYBACK_SPEEDS.indexOf(speed)
    const nextIdx = (currentIdx + 1) % PLAYBACK_SPEEDS.length
    setSpeed(PLAYBACK_SPEEDS[nextIdx] as PlaybackSpeed)
  }, [speed, setSpeed])

  if (!hasHours) {
    return null
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
      }}
    >
      <button
        type="button"
        aria-label="First forecast hour"
        disabled={isFirst}
        onClick={goFirst}
        style={isFirst ? disabledStyle : buttonStyle}
      >
        ⏮
      </button>
      <button
        type="button"
        aria-label="Previous forecast hour"
        disabled={isFirst}
        onClick={goPrevious}
        style={isFirst ? disabledStyle : buttonStyle}
      >
        ◀
      </button>
      <button
        type="button"
        aria-label={playing ? 'Pause playback' : 'Play animation'}
        onClick={toggle}
        style={buttonStyle}
      >
        {playing ? '⏸' : '▶'}
      </button>
      <button
        type="button"
        aria-label="Next forecast hour"
        disabled={isLast}
        onClick={goNext}
        style={isLast ? disabledStyle : buttonStyle}
      >
        ▶
      </button>
      <button
        type="button"
        aria-label="Last forecast hour"
        disabled={isLast}
        onClick={goLast}
        style={isLast ? disabledStyle : buttonStyle}
      >
        ⏭
      </button>
      <button
        type="button"
        aria-label={`Playback speed: ${formatSpeed(speed)}. Click to cycle.`}
        onClick={cycleSpeed}
        style={speedButtonStyle}
        title="Click to cycle playback speed"
      >
        {formatSpeed(speed)}
      </button>
    </div>
  )
}

export default PlaybackControls
