import { useEffect } from 'react'
import { useRuns } from '../hooks/useMetadata'

interface RunSelectorProps {
  /** Currently selected product */
  product: string | null
  /** Currently selected date in YYYYMMDD format */
  date: string | null
  /** Currently selected run (e.g. "00", "06", "12", "18") */
  selectedRun: string | null
  /** Callback when the user selects a different run */
  onRunChange: (run: string) => void
}

/**
 * Format a run string into a human-readable UTC label.
 * e.g. "06" → "06Z"
 */
function formatRunLabel(run: string): string {
  return `${run}Z`
}

/**
 * Run selector dropdown showing available forecast initialization runs
 * for the selected product and date. Fetches runs via the useRuns hook.
 */
function RunSelector({ product, date, selectedRun, onRunChange }: RunSelectorProps) {
  const { status, data: runs } = useRuns(product, date)

  // Auto-select the latest run when runs become available
  // and no run is currently selected
  useEffect(() => {
    if (!selectedRun && runs && runs.length > 0) {
      onRunChange(runs[runs.length - 1])
    }
  }, [selectedRun, runs, onRunChange])

  if (!date) {
    return (
      <span
        style={{
          fontSize: '0.75rem',
          color: '#a3a3a3',
          whiteSpace: 'nowrap',
        }}
      >
        Select a date first
      </span>
    )
  }

  if (status === 'loading') {
    return (
      <span
        style={{
          fontSize: '0.75rem',
          color: '#a3a3a3',
          whiteSpace: 'nowrap',
        }}
      >
        Loading runs…
      </span>
    )
  }

  if (status === 'error' || (status === 'success' && (!runs || runs.length === 0))) {
    return (
      <span
        style={{
          fontSize: '0.75rem',
          color: '#a3a3a3',
          whiteSpace: 'nowrap',
        }}
      >
        No runs available
      </span>
    )
  }

  if (!runs) return null

  return (
    <fieldset
      className="run-selector"
      style={{
        border: 'none',
        padding: 0,
        display: 'flex',
        gap: '4px',
        alignItems: 'center',
      }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Run</legend>
      <select
        aria-label="Select forecast run"
        value={selectedRun ?? ''}
        onChange={(e) => onRunChange(e.target.value)}
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
        {runs.map((r) => (
          <option key={r} value={r}>
            {formatRunLabel(r)}
          </option>
        ))}
      </select>
    </fieldset>
  )
}

export default RunSelector
