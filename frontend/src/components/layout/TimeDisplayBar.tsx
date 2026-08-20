import { useMemo } from 'react'
import { useViewer } from '../../context/ViewerContext'
import { useTimes } from '../../hooks/useMetadata'

/**
 * Format a YYYYMMDD date + run string into a display label.
 * e.g. date="20240815", run="00" → "Aug 15, 2024 00Z"
 */
function formatInitTime(date: string, run: string): string {
  const year = date.slice(0, 4)
  const month = date.slice(4, 6)
  const day = date.slice(6, 8)
  const d = new Date(Number(year), Number(month) - 1, Number(day))
  const label = d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
  return `${label} ${run.padStart(2, '0')}Z`
}

/**
 * Format a forecast hour number as a zero-padded 3-digit string.
 * e.g. 6 → "006", 24 → "024"
 */
function formatForecastHour(fhr: number): string {
  return String(fhr).padStart(3, '0')
}

/**
 * Compute the valid time string from init date, run, and forecast hour.
 * Returns a label like "Aug 16, 2024 00Z".
 */
function computeValidTime(date: string, run: string, forecastHour: number): string {
  const year = Number(date.slice(0, 4))
  const month = Number(date.slice(4, 6)) - 1
  const day = Number(date.slice(6, 8))
  const hour = Number(run)

  const initDate = new Date(Date.UTC(year, month, day, hour))
  const validDate = new Date(initDate.getTime() + forecastHour * 3600 * 1000)

  const label = validDate.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })
  const validHour = String(validDate.getUTCHours()).padStart(2, '0')
  return `${label} ${validHour}Z`
}

/**
 * TimeDisplayBar shows initialization time, current forecast hour,
 * and the computed valid time. Updates on any selection change via ViewerContext.
 */
function TimeDisplayBar() {
  const { state } = useViewer()
  const { product, date, run, forecastHour } = state

  // Fetch times data (provides initTime from the API as well)
  useTimes(product, date, run)

  const display = useMemo(() => {
    if (!date || !run) {
      return null
    }
    return {
      init: formatInitTime(date, run),
      fhr: formatForecastHour(forecastHour),
      valid: computeValidTime(date, run, forecastHour),
    }
  }, [date, run, forecastHour])

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '4px 12px',
        background: '#111',
        borderBottom: '1px solid #333',
        fontSize: '0.8rem',
        color: '#aaa',
        letterSpacing: '0.5px',
        gap: '16px',
      }}
    >
      {display ? (
        <>
          <span>
            <strong style={{ color: '#ccc' }}>Init:</strong> {display.init}
          </span>
          <span>|</span>
          <span>
            <strong style={{ color: '#ccc' }}>FHR:</strong> {display.fhr}
          </span>
          <span>|</span>
          <span>
            <strong style={{ color: '#ccc' }}>Valid:</strong> {display.valid}
          </span>
        </>
      ) : (
        <span>No forecast selected</span>
      )}
    </div>
  )
}

export default TimeDisplayBar
