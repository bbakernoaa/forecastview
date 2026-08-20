import { useState, useEffect, useCallback } from 'react'

interface ContourIntervalSelectorProps {
  /** Default contour interval from the variable's rendering config (null if no variable selected) */
  defaultInterval: number | null
  /** Currently active interval override (null means "use default") */
  interval: number | null
  /** Called when the user changes the interval. Pass null to reset to default. */
  onChange: (interval: number | null) => void
}

/**
 * A compact numeric input for overriding the contour interval.
 * Displays the current default from the variable config. When the user
 * enters a custom value, it triggers a contour refetch via the parent.
 * A reset button returns to the variable's default interval.
 */
function ContourIntervalSelector({
  defaultInterval,
  interval,
  onChange,
}: ContourIntervalSelectorProps) {
  const [inputValue, setInputValue] = useState('')

  // Sync input display with the active interval
  useEffect(() => {
    if (interval != null) {
      setInputValue(String(interval))
    } else if (defaultInterval != null) {
      setInputValue(String(defaultInterval))
    } else {
      setInputValue('')
    }
  }, [interval, defaultInterval])

  const handleSubmit = useCallback(() => {
    const parsed = parseFloat(inputValue)
    if (!isFinite(parsed) || parsed <= 0) {
      // Invalid — reset to default
      onChange(null)
      return
    }
    // If user typed the same as default, treat as "no override"
    if (defaultInterval != null && parsed === defaultInterval) {
      onChange(null)
    } else {
      onChange(parsed)
    }
  }, [inputValue, defaultInterval, onChange])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit()
    }
  }

  const handleReset = () => {
    onChange(null)
  }

  // Don't render if no variable is selected (no default available)
  if (defaultInterval == null) return null

  const isOverridden = interval != null && interval !== defaultInterval

  return (
    <fieldset
      className="contour-interval-selector"
      style={{
        border: 'none',
        padding: 0,
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
      }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>
        Interval
      </legend>
      <input
        type="number"
        min="0.1"
        step="any"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onBlur={handleSubmit}
        onKeyDown={handleKeyDown}
        style={{
          width: '60px',
          padding: '3px 6px',
          fontSize: '0.8rem',
          background: '#2a2a2a',
          border: isOverridden ? '1px solid #4a9eff' : '1px solid #555',
          borderRadius: '3px',
          color: '#eee',
          textAlign: 'center',
        }}
        title={`Default: ${defaultInterval}. Enter a custom value to override.`}
      />
      {isOverridden && (
        <button
          type="button"
          onClick={handleReset}
          style={{
            padding: '2px 6px',
            fontSize: '0.7rem',
            cursor: 'pointer',
            border: '1px solid #555',
            borderRadius: '3px',
            background: '#2a2a2a',
            color: '#ccc',
          }}
          title="Reset to default interval"
        >
          Reset
        </button>
      )}
    </fieldset>
  )
}

export default ContourIntervalSelector
