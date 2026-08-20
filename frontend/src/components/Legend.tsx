import type { VariableInfo } from '../api/types'

interface LegendProps {
  variable: VariableInfo | null
}

/**
 * Fallback palette if the API doesn't provide colors.
 */
const FALLBACK_PALETTE = [
  '#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8',
  '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027',
  '#a50026', '#67001f',
]

function formatValue(value: number): string {
  if (value === 0) return '0'
  const abs = Math.abs(value)
  if (abs >= 100) return value.toFixed(0)
  if (abs >= 1) return value.toPrecision(3)
  if (abs >= 0.01) return value.toPrecision(2)
  return value.toExponential(1)
}

function Legend({ variable }: LegendProps) {
  if (!variable) return null

  const rendering = variable.rendering
  if (!rendering) return null

  const { fillLevels, contourInterval, colors } = rendering
  if (!fillLevels || fillLevels.length < 2) return null

  // Number of color bands = number of fill levels - 1
  const numBands = fillLevels.length - 1

  // Use API-provided colors or fallback
  const palette = colors && colors.length > 0 ? colors : FALLBACK_PALETTE

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {/* Variable name and units */}
      <div style={{ textAlign: 'center' }}>
        <div
          style={{
            fontWeight: 600,
            fontSize: '0.82rem',
            color: '#e0e0e0',
            lineHeight: 1.3,
          }}
        >
          {variable.fullName}
        </div>
        <div style={{ fontSize: '0.72rem', color: '#999', marginTop: '2px' }}>
          ({variable.units})
        </div>
      </div>

      {/* Color ramp with value labels */}
      <div style={{ display: 'flex', flexDirection: 'row', gap: '4px', alignItems: 'stretch' }}>
        {/* Color bar */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            width: '20px',
            minWidth: '20px',
            borderRadius: '3px',
            overflow: 'hidden',
            border: '1px solid #444',
          }}
        >
          {Array.from({ length: numBands }, (_, i) => {
            // Reverse so highest values at top
            const bandIdx = numBands - 1 - i
            const color = palette[bandIdx % palette.length]
            return (
              <div
                key={bandIdx}
                style={{
                  flex: 1,
                  backgroundColor: color,
                  minHeight: '16px',
                }}
              />
            )
          })}
        </div>

        {/* Value labels */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            fontSize: '0.68rem',
            color: '#bbb',
          }}
        >
          {[...fillLevels].reverse().map((value, i) => (
            <span key={i} style={{ lineHeight: 1, whiteSpace: 'nowrap' }}>
              {formatValue(value)}
            </span>
          ))}
        </div>
      </div>

      {/* Contour interval */}
      <div
        style={{
          fontSize: '0.7rem',
          color: '#888',
          textAlign: 'center',
          borderTop: '1px solid #333',
          paddingTop: '6px',
        }}
      >
        Contour interval: {formatValue(contourInterval)}
      </div>
    </div>
  )
}

export default Legend
