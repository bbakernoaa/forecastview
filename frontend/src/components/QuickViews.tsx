import { useCallback } from 'react'
import { useViewer } from '../context/ViewerContext'

interface ViewPreset {
  label: string
  center: [number, number]  // [lng, lat]
  zoom: number
}

const PRESETS: ViewPreset[] = [
  { label: 'Global', center: [0, 20], zoom: 1 },
  { label: 'CONUS', center: [-98.5, 39.8], zoom: 4 },
  { label: 'East Coast', center: [-78, 37], zoom: 5 },
  { label: 'West Coast', center: [-121, 38], zoom: 5 },
  { label: 'Alaska', center: [-153, 64], zoom: 4 },
  { label: 'Hawaii', center: [-157, 20], zoom: 6 },
  { label: 'Central America', center: [-87, 15], zoom: 4 },
  { label: 'N. Atlantic', center: [-45, 35], zoom: 3 },
  { label: 'Sahara/Africa', center: [10, 20], zoom: 3 },
  { label: 'Central Africa', center: [22, 0], zoom: 3.5 },
  { label: 'Europe', center: [15, 50], zoom: 4 },
  { label: 'E. Asia', center: [115, 35], zoom: 3.5 },
  { label: 'India', center: [78, 22], zoom: 4 },
  { label: 'SE Asia', center: [105, 12], zoom: 4 },
  { label: 'Indonesia', center: [118, -2], zoom: 3.5 },
  { label: 'S. America', center: [-60, -15], zoom: 3 },
  { label: 'Australia', center: [135, -25], zoom: 3.5 },
  { label: 'Arctic', center: [0, 75], zoom: 3 },
]

const buttonStyle: React.CSSProperties = {
  padding: '3px 8px',
  fontSize: '0.72rem',
  cursor: 'pointer',
  border: '1px solid #444',
  borderRadius: '3px',
  background: '#2a2a2a',
  color: '#bbb',
  textAlign: 'left',
  width: '100%',
}

function QuickViews() {
  const { map } = useViewer()

  const flyTo = useCallback((preset: ViewPreset) => {
    if (!map) return
    map.flyTo({
      center: preset.center,
      zoom: preset.zoom,
      duration: 1000,
    })
  }, [map])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
      <div
        style={{
          fontSize: '0.75rem',
          fontWeight: 600,
          color: '#999',
          marginBottom: '2px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}
      >
        Quick Views
      </div>
      {PRESETS.map((preset) => (
        <button
          key={preset.label}
          type="button"
          onClick={() => flyTo(preset)}
          style={buttonStyle}
        >
          {preset.label}
        </button>
      ))}
    </div>
  )
}

export default QuickViews
