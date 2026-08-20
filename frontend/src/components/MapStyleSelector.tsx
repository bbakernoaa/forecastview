import type { MapStyleKey } from '../config/mapStyles'

interface MapStyleSelectorProps {
  styleKey: MapStyleKey
  onChange: (style: MapStyleKey) => void
}

const STYLE_OPTIONS: { key: MapStyleKey; label: string }[] = [
  { key: 'liberty', label: 'Liberty' },
  { key: 'dark', label: 'Dark' },
  { key: 'light', label: 'Light' },
]

function MapStyleSelector({ styleKey, onChange }: MapStyleSelectorProps) {
  return (
    <fieldset
      className="map-style-selector"
      style={{ border: 'none', padding: 0, display: 'flex', gap: '4px', alignItems: 'center' }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Map Style</legend>
      {STYLE_OPTIONS.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          aria-pressed={styleKey === key}
          onClick={() => onChange(key)}
          style={{
            padding: '4px 10px',
            fontSize: '0.8rem',
            cursor: 'pointer',
            border: '1px solid #555',
            borderRadius: '3px',
            background: styleKey === key ? '#4a9eff' : '#2a2a2a',
            color: styleKey === key ? '#fff' : '#ccc',
          }}
        >
          {label}
        </button>
      ))}
    </fieldset>
  )
}

export default MapStyleSelector
