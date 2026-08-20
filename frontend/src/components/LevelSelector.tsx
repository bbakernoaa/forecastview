import { useEffect } from 'react'
import { useLevels } from '../hooks/useMetadata'

interface LevelSelectorProps {
  /** Currently selected product */
  product: string | null
  /** Currently selected date in YYYYMMDD format */
  date: string | null
  /** Currently selected run (e.g. "00", "06", "12", "18") */
  run: string | null
  /** Currently selected variable name */
  variable: string | null
  /** Currently selected level value */
  selectedLevel: number | null
  /** Callback when the user selects a different level */
  onLevelChange: (level: number) => void
}

/**
 * Level selector dropdown showing available vertical levels for the selected variable.
 * Only renders when the variable has multiple levels — hidden for surface-only fields.
 */
function LevelSelector({
  product,
  date,
  run,
  variable,
  selectedLevel,
  onLevelChange,
}: LevelSelectorProps) {
  const { status, data: levels } = useLevels(product, date, run, variable)

  // Auto-select the first level when levels become available
  // and no level is currently selected
  useEffect(() => {
    if (selectedLevel == null && levels && levels.length > 0) {
      onLevelChange(levels[0].value)
    }
  }, [selectedLevel, levels, onLevelChange])

  // Conditional visibility: render nothing if only one or no levels
  if (!variable) return null
  if (status === 'loading') {
    return (
      <span
        style={{
          fontSize: '0.75rem',
          color: '#a3a3a3',
          whiteSpace: 'nowrap',
        }}
      >
        Loading levels…
      </span>
    )
  }
  if (!levels || levels.length <= 1) return null

  return (
    <fieldset
      className="level-selector"
      style={{
        border: 'none',
        padding: 0,
        display: 'flex',
        gap: '4px',
        alignItems: 'center',
      }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Level</legend>
      <select
        aria-label="Select vertical level"
        value={selectedLevel ?? ''}
        onChange={(e) => onLevelChange(Number(e.target.value))}
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
        {levels.map((lvl) => (
          <option key={lvl.value} value={lvl.value}>
            {lvl.label}
          </option>
        ))}
      </select>
    </fieldset>
  )
}

export default LevelSelector
