import type { VariableInfo } from '../api/types'

interface LegendProps {
  /** The currently selected variable's metadata, or null if none selected */
  variable: VariableInfo | null
}

/**
 * Discrete blue→red color palette matching the FilledContourLayer.
 * Each color corresponds to one fill band between adjacent fill levels.
 */
const DISCRETE_PALETTE = [
  '#313695',
  '#4575b4',
  '#74add1',
  '#abd9e9',
  '#e0f3f8',
  '#ffffbf',
  '#fee090',
  '#fdae61',
  '#f46d43',
  '#d73027',
  '#a50026',
  '#67001f',
]

/**
 * Formats a numeric value for display in the legend, keeping it compact.
 * Uses up to 4 significant digits to avoid overly wide labels.
 */
function formatValue(value: number): string {
  if (value === 0) return '0'
  const abs = Math.abs(value)
  if (abs >= 100) return value.toFixed(0)
  if (abs >= 1) return value.toPrecision(3)
  if (abs >= 0.01) return value.toPrecision(2)
  return value.toExponential(1)
}

/**
 * Legend component displaying the color ramp and value labels for the
 * currently selected variable. Renders in the left panel.
 *
 * Shows:
 * - Variable name and units at the top
 * - A vertical color bar with discrete bands matching the fill layer palette
 * - Value labels at each fill level boundary
 * - Contour interval at the bottom
 *
 * Returns null when no variable is selected.
 */
function Legend({ variable }: LegendProps) {
  if (!variable) return null

  const rendering = variable.rendering
  if (!rendering) return null

  const { fillLevels, contourInterval } = rendering
  if (!fillLevels || fillLevels.length < 2) return null

  // Number of bands = number of fill levels - 1
  // (each band spans from fillLevels[i] to fillLevels[i+1])
  const numBands = fillLevels.length - 1

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
        <div
          style={{
            fontSize: '0.72rem',
            color: '#999',
            marginTop: '2px',
          }}
        >
          ({variable.units})
        </div>
      </div>

      {/* Color ramp with value labels */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          gap: '4px',
          alignItems: 'stretch',
        }}
      >
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
            // Reverse order so highest values are at the top
            const bandIdx = numBands - 1 - i
            const colorIdx = bandIdx % DISCRETE_PALETTE.length
            return (
              <div
                key={bandIdx}
                style={{
                  flex: 1,
                  backgroundColor: DISCRETE_PALETTE[colorIdx],
                  minHeight: '16px',
                }}
              />
            )
          })}
        </div>

        {/* Value labels aligned to band boundaries */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            fontSize: '0.68rem',
            color: '#bbb',
            paddingTop: '0px',
            paddingBottom: '0px',
          }}
        >
          {/* Labels from top (highest) to bottom (lowest) */}
          {[...fillLevels].reverse().map((value, i) => (
            <span
              key={i}
              style={{
                lineHeight: 1,
                whiteSpace: 'nowrap',
              }}
            >
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
