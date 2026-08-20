import { useEffect, useRef } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'
import { useContours } from '../hooks/useContours'

interface IsolineLayerProps {
  /** MapLibre map instance to add layers to */
  map: MaplibreMap | null
  /** Product identifier */
  product: string
  /** Selected date in YYYYMMDD format */
  date: string | null
  /** Selected initialization run (e.g. "00") */
  run: string | null
  /** Selected variable name */
  variable: string | null
  /** Vertical level (null for surface-only fields) */
  level: number | null
  /** Forecast hour */
  fhr: number | null
  /** Contour interval override (null = backend default) */
  interval?: number | null
  /** Whether the isoline layers are visible */
  visible?: boolean
}

const SOURCE_ID = 'isoline-source'
const MINOR_LAYER_ID = 'isoline-minor-layer'
const MAJOR_LAYER_ID = 'isoline-major-layer'

/**
 * Renders contour isolines on the MapLibre map with distinct
 * styling for major and minor contours.
 *
 * Major contours: 2px opaque lines
 * Minor contours: 1px semi-transparent lines
 *
 * Uses the useContours hook to fetch GeoJSON data from /api/contours.
 */
function IsolineLayer({
  map,
  product,
  date,
  run,
  variable,
  level,
  fhr,
  interval = null,
  visible = true,
}: IsolineLayerProps) {
  const addedRef = useRef(false)

  const { status, data } = useContours({
    product,
    date,
    run,
    variable,
    level,
    fhr,
    interval,
  })

  // Add or update layers when data arrives
  useEffect(() => {
    if (!map) return

    if (status !== 'success' || !data) {
      // Clean up if no data
      if (addedRef.current) {
        removeLayers(map)
        addedRef.current = false
      }
      return
    }

    addOrUpdateLayers(map, data)
    addedRef.current = true

    return () => {
      if (map && addedRef.current) {
        removeLayers(map)
        addedRef.current = false
      }
    }
  }, [map, status, data])

  // Handle visibility toggle
  useEffect(() => {
    if (!map || !addedRef.current) return

    const visibility = visible ? 'visible' : 'none'

    try {
      if (map.getLayer(MINOR_LAYER_ID)) {
        map.setLayoutProperty(MINOR_LAYER_ID, 'visibility', visibility)
      }
      if (map.getLayer(MAJOR_LAYER_ID)) {
        map.setLayoutProperty(MAJOR_LAYER_ID, 'visibility', visibility)
      }
    } catch {
      // Layer may not exist yet
    }
  }, [map, visible])

  // This component renders nothing itself — it only manipulates the map
  return null
}

function addOrUpdateLayers(
  map: MaplibreMap,
  collection: { type: string; features: GeoJSON.Feature[] },
): void {
  const geojsonData: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: collection.features as GeoJSON.Feature[],
  }

  if (map.getSource(SOURCE_ID)) {
    // Update existing source data
    const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource
    source.setData(geojsonData)
  } else {
    // Add new source
    map.addSource(SOURCE_ID, {
      type: 'geojson',
      data: geojsonData,
    })

    // Minor contours: thin, semi-transparent
    map.addLayer({
      id: MINOR_LAYER_ID,
      type: 'line',
      source: SOURCE_ID,
      filter: ['==', ['get', 'major'], false],
      paint: {
        'line-color': '#333333',
        'line-width': 1,
        'line-opacity': 0.5,
      },
    })

    // Major contours: thicker, fully opaque
    map.addLayer({
      id: MAJOR_LAYER_ID,
      type: 'line',
      source: SOURCE_ID,
      filter: ['==', ['get', 'major'], true],
      paint: {
        'line-color': '#333333',
        'line-width': 2,
        'line-opacity': 1.0,
      },
    })
  }
}

function removeLayers(map: MaplibreMap): void {
  try {
    if (map.getLayer(MAJOR_LAYER_ID)) {
      map.removeLayer(MAJOR_LAYER_ID)
    }
    if (map.getLayer(MINOR_LAYER_ID)) {
      map.removeLayer(MINOR_LAYER_ID)
    }
    if (map.getSource(SOURCE_ID)) {
      map.removeSource(SOURCE_ID)
    }
  } catch {
    // Map may already be destroyed
  }
}

export default IsolineLayer
