import { useCallback, useMemo } from 'react'
import { useViewer } from '../context/ViewerContext'
import { useTimes } from '../hooks/useMetadata'

/**
 * ForecastSlider renders an HTML range input showing available forecast hours.
 * Uses useTimes to discover available hours and dispatches SET_FORECAST_HOUR on change.
 */
function ForecastSlider() {
  const { state, dispatch } = useViewer()
  const { product, date, run, forecastHour } = state

  const { data: timesData } = useTimes(product, date, run)

  const forecastHours = useMemo(() => {
    if (!timesData) return []
    return timesData.forecastHours.map((entry) => entry.fhr)
  }, [timesData])

  const currentIndex = useMemo(() => {
    const idx = forecastHours.indexOf(forecastHour)
    return idx >= 0 ? idx : 0
  }, [forecastHours, forecastHour])

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const idx = Number(e.target.value)
      if (idx >= 0 && idx < forecastHours.length) {
        dispatch({ type: 'SET_FORECAST_HOUR', payload: forecastHours[idx] })
      }
    },
    [dispatch, forecastHours],
  )

  if (forecastHours.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          color: '#666',
          fontSize: '0.8rem',
        }}
      >
        <span>No forecast hours</span>
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flex: 1,
        minWidth: 0,
      }}
    >
      <span
        style={{
          fontSize: '0.75rem',
          color: '#888',
          whiteSpace: 'nowrap',
        }}
      >
        F{String(forecastHours[0]).padStart(3, '0')}
      </span>
      <input
        type="range"
        aria-label="Forecast hour slider"
        min={0}
        max={forecastHours.length - 1}
        step={1}
        value={currentIndex}
        onChange={handleChange}
        style={{
          flex: 1,
          cursor: 'pointer',
          accentColor: '#4dabf7',
        }}
      />
      <span
        style={{
          fontSize: '0.75rem',
          color: '#888',
          whiteSpace: 'nowrap',
        }}
      >
        F{String(forecastHours[forecastHours.length - 1]).padStart(3, '0')}
      </span>
      <span
        style={{
          fontSize: '0.8rem',
          color: '#ccc',
          fontWeight: 'bold',
          minWidth: '50px',
          textAlign: 'center',
        }}
      >
        F{String(forecastHour).padStart(3, '0')}
      </span>
    </div>
  )
}

export default ForecastSlider
