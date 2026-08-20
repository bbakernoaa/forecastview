import { useEffect } from 'react'
import { useVariables } from '../hooks/useMetadata'
import type { VariableInfo } from '../api/types'

interface VariableSelectorProps {
  /** Currently selected product */
  product: string | null
  /** Currently selected date in YYYYMMDD format */
  date: string | null
  /** Currently selected run (e.g. "00", "06", "12", "18") */
  run: string | null
  /** Currently selected variable name */
  selectedVariable: string | null
  /** Callback when the user selects a different variable */
  onVariableChange: (variable: string) => void
}

/**
 * Group variables by their category field, preserving the order from the backend.
 */
function groupByCategory(variables: VariableInfo[]): Map<string, VariableInfo[]> {
  const groups = new Map<string, VariableInfo[]>()
  for (const v of variables) {
    const existing = groups.get(v.category)
    if (existing) {
      existing.push(v)
    } else {
      groups.set(v.category, [v])
    }
  }
  return groups
}

/**
 * Variable selector dropdown showing available forecast variables grouped by category.
 * Fetches variables via the useVariables hook given the current product, date, and run.
 */
function VariableSelector({
  product,
  date,
  run,
  selectedVariable,
  onVariableChange,
}: VariableSelectorProps) {
  const { status, data: variables } = useVariables(product, date, run)

  // Auto-select the first variable when variables become available
  // and no variable is currently selected
  useEffect(() => {
    if (!selectedVariable && variables && variables.length > 0) {
      onVariableChange(variables[0].name)
    }
  }, [selectedVariable, variables, onVariableChange])

  if (!date || !run) {
    return (
      <span
        style={{
          fontSize: '0.75rem',
          color: '#a3a3a3',
          whiteSpace: 'nowrap',
        }}
      >
        Select a run first
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
        Loading variables…
      </span>
    )
  }

  if (status === 'error' || (status === 'success' && (!variables || variables.length === 0))) {
    return (
      <span
        style={{
          fontSize: '0.75rem',
          color: '#a3a3a3',
          whiteSpace: 'nowrap',
        }}
      >
        No variables
      </span>
    )
  }

  if (!variables) return null

  const grouped = groupByCategory(variables)

  return (
    <fieldset
      className="variable-selector"
      style={{
        border: 'none',
        padding: 0,
        display: 'flex',
        gap: '4px',
        alignItems: 'center',
      }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Variable</legend>
      <select
        aria-label="Select forecast variable"
        value={selectedVariable ?? ''}
        onChange={(e) => onVariableChange(e.target.value)}
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
        {Array.from(grouped.entries()).map(([category, vars]) => (
          <optgroup key={category} label={category}>
            {vars.map((v) => (
              <option key={v.name} value={v.name} title={v.fullName}>
                {v.shortName}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </fieldset>
  )
}

export default VariableSelector
