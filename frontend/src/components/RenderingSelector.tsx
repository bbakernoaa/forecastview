/**
 * Rendering mode selector for controlling contour/fill layer visibility.
 *
 * Three modes per FR-9:
 * - "contours" — IsolineLayer + ContourLabelLayer visible, FilledContourLayer hidden
 * - "filled" — FilledContourLayer visible, IsolineLayer + ContourLabelLayer hidden
 * - "filled+contours" — all layers visible (default for air composition)
 */

export type RenderingMode = 'contours' | 'filled' | 'filled+contours'

interface RenderingSelectorProps {
  /** Currently active rendering mode */
  mode: RenderingMode
  /** Callback when the user selects a different mode */
  onChange: (mode: RenderingMode) => void
}

const MODE_OPTIONS: { key: RenderingMode; label: string }[] = [
  { key: 'contours', label: 'Contours' },
  { key: 'filled', label: 'Filled' },
  { key: 'filled+contours', label: 'Filled + Contours' },
]

/**
 * Button group for switching between rendering modes.
 * Styled with dark-theme inline styles matching MapStyleSelector.
 */
function RenderingSelector({ mode, onChange }: RenderingSelectorProps) {
  return (
    <fieldset
      className="rendering-selector"
      style={{ border: 'none', padding: 0, display: 'flex', gap: '4px', alignItems: 'center' }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Rendering</legend>
      {MODE_OPTIONS.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          aria-pressed={mode === key}
          onClick={() => onChange(key)}
          style={{
            padding: '4px 10px',
            fontSize: '0.8rem',
            cursor: 'pointer',
            border: '1px solid #555',
            borderRadius: '3px',
            background: mode === key ? '#4a9eff' : '#2a2a2a',
            color: mode === key ? '#fff' : '#ccc',
          }}
        >
          {label}
        </button>
      ))}
    </fieldset>
  )
}

export default RenderingSelector
