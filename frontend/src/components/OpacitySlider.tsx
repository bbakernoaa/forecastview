import { useCallback } from 'react'

interface OpacitySliderProps {
  value: number
  onChange: (opacity: number) => void
}

/**
 * Simple opacity slider for the fill layer (0.0 to 1.0).
 */
function OpacitySlider({ value, onChange }: OpacitySliderProps) {
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onChange(Number(e.target.value) / 100)
    },
    [onChange],
  )

  return (
    <fieldset
      style={{
        border: 'none',
        padding: 0,
        display: 'flex',
        gap: '4px',
        alignItems: 'center',
      }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Opacity</legend>
      <input
        type="range"
        min={10}
        max={100}
        step={5}
        value={Math.round(value * 100)}
        onChange={handleChange}
        style={{ width: '60px', accentColor: '#4dabf7' }}
        title={`Fill opacity: ${Math.round(value * 100)}%`}
      />
      <span style={{ fontSize: '0.7rem', color: '#aaa', minWidth: '28px' }}>
        {Math.round(value * 100)}%
      </span>
    </fieldset>
  )
}

export default OpacitySlider
