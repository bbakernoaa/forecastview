import { useEffect } from 'react'
import { useDates } from '../hooks/useMetadata'

interface DateSelectorProps {
  /** Currently selected product (drives date discovery) */
  product: string | null
  /** Currently selected date in YYYYMMDD format */
  selectedDate: string | null
  /** Callback when the user selects a different date */
  onDateChange: (date: string) => void
}

/**
 * Format a YYYYMMDD date string into a human-readable label.
 * e.g. "20240815" → "Aug 15, 2024"
 */
function formatDateLabel(dateStr: string): string {
  const year = dateStr.slice(0, 4)
  const month = dateStr.slice(4, 6)
  const day = dateStr.slice(6, 8)
  const date = new Date(Number(year), Number(month) - 1, Number(day))
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Date selector with a dropdown and Previous/Next navigation buttons.
 * Fetches available dates from the API via the useDates hook.
 */
function DateSelector({ product, selectedDate, onDateChange }: DateSelectorProps) {
  const { status, data: dates } = useDates(product)

  // Auto-select the most recent date when dates become available
  // and no date is currently selected
  useEffect(() => {
    if (!selectedDate && dates && dates.length > 0) {
      onDateChange(dates[dates.length - 1])
    }
  }, [selectedDate, dates, onDateChange])

  const currentIndex = dates && selectedDate ? dates.indexOf(selectedDate) : -1
  const hasPrevious = currentIndex > 0
  const hasNext = dates !== null && currentIndex >= 0 && currentIndex < dates.length - 1

  if (status === 'loading') {
    return (
      <span
        style={{
          fontSize: '0.75rem',
          color: '#a3a3a3',
          whiteSpace: 'nowrap',
        }}
      >
        Loading dates…
      </span>
    )
  }

  if (status === 'error' || (status === 'success' && (!dates || dates.length === 0))) {
    return (
      <span
        style={{
          fontSize: '0.75rem',
          color: '#a3a3a3',
          whiteSpace: 'nowrap',
        }}
      >
        No dates available
      </span>
    )
  }

  if (!dates) return null

  return (
    <fieldset
      className="date-selector"
      style={{
        border: 'none',
        padding: 0,
        display: 'flex',
        gap: '4px',
        alignItems: 'center',
      }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Date</legend>
      <button
        type="button"
        aria-label="Previous date"
        disabled={!hasPrevious}
        onClick={() => {
          if (hasPrevious) onDateChange(dates[currentIndex - 1])
        }}
        style={{
          padding: '4px 8px',
          fontSize: '0.8rem',
          cursor: hasPrevious ? 'pointer' : 'default',
          border: '1px solid #555',
          borderRadius: '3px',
          background: '#2a2a2a',
          color: hasPrevious ? '#ccc' : '#666',
          opacity: hasPrevious ? 1 : 0.5,
        }}
      >
        ←
      </button>
      <select
        aria-label="Select forecast date"
        value={selectedDate ?? ''}
        onChange={(e) => onDateChange(e.target.value)}
        style={{
          padding: '4px 8px',
          fontSize: '0.8rem',
          border: '1px solid #555',
          borderRadius: '3px',
          background: '#2a2a2a',
          color: '#ccc',
          cursor: 'pointer',
        }}
      >
        {dates.map((d) => (
          <option key={d} value={d}>
            {formatDateLabel(d)}
          </option>
        ))}
      </select>
      <button
        type="button"
        aria-label="Next date"
        disabled={!hasNext}
        onClick={() => {
          if (hasNext) onDateChange(dates[currentIndex + 1])
        }}
        style={{
          padding: '4px 8px',
          fontSize: '0.8rem',
          cursor: hasNext ? 'pointer' : 'default',
          border: '1px solid #555',
          borderRadius: '3px',
          background: '#2a2a2a',
          color: hasNext ? '#ccc' : '#666',
          opacity: hasNext ? 1 : 0.5,
        }}
      >
        →
      </button>
    </fieldset>
  )
}

export default DateSelector
