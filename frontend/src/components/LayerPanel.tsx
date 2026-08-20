import { useState, useEffect, useCallback } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'

/**
 * Geographic layer toggle definitions.
 * The `layerIds` are typical MapLibre basemap layer IDs that may or may not
 * exist depending on the chosen basemap style.
 */
interface LayerToggle {
  key: string
  label: string
  /** Possible MapLibre layer ID prefixes/patterns to toggle */
  layerIds: string[]
}

const LAYER_TOGGLES: LayerToggle[] = [
  { key: 'states', label: 'State Borders', layerIds: ['admin-1', 'boundary-land-level-4', 'boundary_state', 'admin_level_4'] },
  { key: 'countries', label: 'Country Borders', layerIds: ['admin-0', 'boundary-land-level-2', 'boundary_country', 'admin_level_2'] },
  { key: 'cities', label: 'Cities', layerIds: ['place-city', 'place_city', 'place-town', 'place_label'] },
  { key: 'roads', label: 'Roads', layerIds: ['road', 'highway', 'tunnel', 'bridge'] },
  { key: 'terrain', label: 'Terrain', layerIds: ['hillshade', 'terrain', 'landcover', 'landuse'] },
]

type LayerVisibility = Record<string, boolean>

const DEFAULT_VISIBILITY: LayerVisibility = {
  states: true,
  countries: true,
  cities: true,
  roads: true,
  terrain: true,
}

interface LayerPanelProps {
  /** MapLibre map instance */
  map: MaplibreMap | null
}

/**
 * LayerPanel provides checkboxes to toggle geographic overlay layers
 * on the basemap. Placed in the left panel below the legend.
 *
 * Note: Toggles only work if the active basemap style contains layers
 * whose IDs match the patterns defined here. If a layer ID doesn't exist
 * in the current style, the toggle is a no-op.
 */
function LayerPanel({ map }: LayerPanelProps) {
  const [visibility, setVisibility] = useState<LayerVisibility>(DEFAULT_VISIBILITY)
  const [collapsed, setCollapsed] = useState(false)

  const applyVisibility = useCallback(
    (key: string, visible: boolean) => {
      if (!map) return

      const toggle = LAYER_TOGGLES.find((t) => t.key === key)
      if (!toggle) return

      const targetVisibility = visible ? 'visible' : 'none'

      try {
        const style = map.getStyle()
        if (!style?.layers) return

        for (const layer of style.layers) {
          const matches = toggle.layerIds.some(
            (pattern) => layer.id.includes(pattern),
          )
          if (matches) {
            map.setLayoutProperty(layer.id, 'visibility', targetVisibility)
          }
        }
      } catch {
        // Style may not be loaded yet or layers may not exist
      }
    },
    [map],
  )

  // Re-apply visibility when map becomes available or style changes
  useEffect(() => {
    if (!map) return

    const applyAll = () => {
      for (const key of Object.keys(visibility)) {
        applyVisibility(key, visibility[key])
      }
    }

    // Apply on style load events (e.g., when user switches map style)
    map.on('styledata', applyAll)
    applyAll()

    return () => {
      map.off('styledata', applyAll)
    }
  }, [map, visibility, applyVisibility])

  const handleToggle = (key: string) => {
    setVisibility((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      applyVisibility(key, next[key])
      return next
    })
  }

  return (
    <div
      style={{
        marginTop: '16px',
        borderTop: '1px solid #333',
        paddingTop: '12px',
      }}
    >
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        style={{
          background: 'none',
          border: 'none',
          color: '#ccc',
          cursor: 'pointer',
          fontSize: '0.78rem',
          fontWeight: 600,
          padding: '0 0 8px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          width: '100%',
        }}
      >
        <span style={{ transform: collapsed ? 'rotate(-90deg)' : 'rotate(0)', transition: 'transform 0.15s' }}>
          ▼
        </span>
        Layers
      </button>

      {!collapsed && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {LAYER_TOGGLES.map(({ key, label }) => (
            <label
              key={key}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.75rem',
                color: '#bbb',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={visibility[key]}
                onChange={() => handleToggle(key)}
                style={{ accentColor: '#4a9eff' }}
              />
              {label}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

export default LayerPanel
