import { useEffect, useRef } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'

interface ContourLabelLayerProps {
  /** MapLibre map instance to add the label layer to */
  map: MaplibreMap | null
  /** Whether the label layer is visible */
  visible?: boolean
}

const SOURCE_ID = 'isoline-source'
const LABEL_LAYER_ID = 'contour-label-layer'

/**
 * Renders value labels along contour lines using a MapLibre symbol layer.
 *
 * Reuses the existing 'isoline-source' GeoJSON source created by IsolineLayer.
 * Labels are placed along lines with text halos for readability over shaded
 * backgrounds. Major contours are prioritized via `symbol-sort-key`, and
 * label density adjusts with zoom level through zoom-dependent `symbol-spacing`.
 */
function ContourLabelLayer({ map, visible = true }: ContourLabelLayerProps) {
  const addedRef = useRef(false)

  // Add the label layer when the isoline source becomes available
  useEffect(() => {
    if (!map) return

    const addLayer = () => {
      if (addedRef.current) return
      if (!map.getSource(SOURCE_ID)) return

      map.addLayer({
        id: LABEL_LAYER_ID,
        type: 'symbol',
        source: SOURCE_ID,
        layout: {
          // Place labels along the line geometry
          'symbol-placement': 'line',
          // Display the contour value, formatted to reasonable precision
          'text-field': ['to-string', ['get', 'value']],
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
          'text-size': 12,
          // Allow labels to be dropped when they collide, prioritizing major contours
          'text-optional': true,
          // Sort so major contours (priority 0) render labels before minor (priority 1)
          'symbol-sort-key': [
            'case',
            ['get', 'major'],
            0,
            1,
          ],
          // Adjust spacing based on zoom: tighter at high zoom, sparser at low zoom
          'symbol-spacing': [
            'interpolate',
            ['linear'],
            ['zoom'],
            3, 400,
            6, 300,
            10, 200,
            14, 150,
          ],
          // Keep labels upright for readability
          'text-rotation-alignment': 'map',
          'text-keep-upright': true,
          visibility: visible ? 'visible' : 'none',
        },
        paint: {
          'text-color': '#222222',
          // White halo for readability over shaded/dark backgrounds
          'text-halo-color': 'rgba(255, 255, 255, 0.9)',
          'text-halo-width': 1.5,
        },
      })

      addedRef.current = true
    }

    // The isoline source may not exist yet if IsolineLayer hasn't loaded data.
    // Listen for the 'sourcedata' event to detect when it becomes available.
    if (map.getSource(SOURCE_ID)) {
      addLayer()
    } else {
      const onSourceData = () => {
        if (map.getSource(SOURCE_ID) && !addedRef.current) {
          addLayer()
          map.off('sourcedata', onSourceData)
        }
      }
      map.on('sourcedata', onSourceData)

      return () => {
        map.off('sourcedata', onSourceData)
        if (addedRef.current) {
          removeLayer(map)
          addedRef.current = false
        }
      }
    }

    return () => {
      if (map && addedRef.current) {
        removeLayer(map)
        addedRef.current = false
      }
    }
  }, [map])

  // Handle visibility toggle
  useEffect(() => {
    if (!map || !addedRef.current) return

    try {
      if (map.getLayer(LABEL_LAYER_ID)) {
        map.setLayoutProperty(
          LABEL_LAYER_ID,
          'visibility',
          visible ? 'visible' : 'none',
        )
      }
    } catch {
      // Layer may not exist yet
    }
  }, [map, visible])

  // This component renders nothing — it only manipulates the map
  return null
}

function removeLayer(map: MaplibreMap): void {
  try {
    if (map.getLayer(LABEL_LAYER_ID)) {
      map.removeLayer(LABEL_LAYER_ID)
    }
  } catch {
    // Map may already be destroyed
  }
}

export default ContourLabelLayer
