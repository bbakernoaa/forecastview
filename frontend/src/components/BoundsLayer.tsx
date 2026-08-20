import { useEffect, useRef } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'
import { apiGet } from '../api/client'

/**
 * GeoJSON Feature response from GET /api/bounds.
 */
interface BoundsFeature {
  type: 'Feature'
  geometry: {
    type: 'Polygon'
    coordinates: number[][][]
  }
  properties: {
    grid_type: string
    shape: number[]
    lon_min: number
    lon_max: number
    lat_min: number
    lat_max: number
  }
}

interface BoundsLayerProps {
  /** MapLibre map instance to add the layer to */
  map: MaplibreMap | null
  /** Product identifier */
  product: string
  /** Selected date in YYYYMMDD format */
  date: string | null
  /** Selected initialization run (e.g. "00") */
  run: string | null
  /** Whether to show the bounds layer (dev feature toggle) */
  enabled?: boolean
}

const SOURCE_ID = 'bounds-polygon-source'
const LAYER_ID = 'bounds-polygon-layer'

/**
 * Development/verification component that renders the field's geographic
 * bounding polygon on the MapLibre map as a dashed orange line.
 *
 * Fetches the bounds polygon from GET /api/bounds when product, date,
 * and run are all available. Cleans up the source and layer on unmount
 * or when disabled.
 */
function BoundsLayer({ map, product, date, run, enabled = true }: BoundsLayerProps) {
  const addedRef = useRef(false)

  useEffect(() => {
    if (!map || !date || !run || !enabled) {
      // Clean up if conditions no longer met
      if (map && addedRef.current) {
        removeLayer(map)
        addedRef.current = false
      }
      return
    }

    const controller = new AbortController()

    apiGet<BoundsFeature>(
      '/api/bounds',
      { product, date, run },
      controller.signal,
    )
      .then((feature) => {
        if (controller.signal.aborted) return
        addOrUpdateLayer(map, feature)
        addedRef.current = true
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        // Silently fail for this dev feature — just log to console
        console.warn('[BoundsLayer] Failed to fetch bounds:', err)
      })

    return () => {
      controller.abort()
      if (map && addedRef.current) {
        removeLayer(map)
        addedRef.current = false
      }
    }
  }, [map, product, date, run, enabled])

  // This component renders nothing itself — it only manipulates the map
  return null
}

function addOrUpdateLayer(map: MaplibreMap, feature: BoundsFeature): void {
  const geojsonData: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: [feature as unknown as GeoJSON.Feature],
  }

  if (map.getSource(SOURCE_ID)) {
    // Update existing source data
    const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource
    source.setData(geojsonData)
  } else {
    // Add new source and layer
    map.addSource(SOURCE_ID, {
      type: 'geojson',
      data: geojsonData,
    })

    map.addLayer({
      id: LAYER_ID,
      type: 'line',
      source: SOURCE_ID,
      paint: {
        'line-color': '#ff8c00',
        'line-width': 2,
        'line-dasharray': [4, 3],
      },
    })
  }
}

function removeLayer(map: MaplibreMap): void {
  try {
    if (map.getLayer(LAYER_ID)) {
      map.removeLayer(LAYER_ID)
    }
    if (map.getSource(SOURCE_ID)) {
      map.removeSource(SOURCE_ID)
    }
  } catch {
    // Map may already be destroyed
  }
}

export default BoundsLayer
