import { useEffect, useRef } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'
import { apiGet } from '../api/client'

/**
 * GeoJSON FeatureCollection response from GET /api/preview.
 */
interface PreviewFeatureCollection {
  type: 'FeatureCollection'
  features: GeoJSON.Feature[]
  properties: {
    variable: string
    min: number
    max: number
    units: string
    resolution: number
    point_count: number
    original_shape: number[]
  }
}

interface PreviewLayerProps {
  /** MapLibre map instance to add the layer to */
  map: MaplibreMap | null
  /** Product identifier */
  product: string
  /** Selected date in YYYYMMDD format */
  date: string | null
  /** Selected initialization run (e.g. "00") */
  run: string | null
  /** Selected variable name */
  variable: string | null
  /** Forecast hour (default 0) */
  fhr?: number
  /** Downsample resolution factor (default 4) */
  resolution?: number
  /** Whether to show the preview layer (dev feature toggle) */
  enabled?: boolean
}

const SOURCE_ID = 'preview-points-source'
const LAYER_ID = 'preview-points-layer'

/**
 * Development/verification component that renders a downsampled field
 * as colored circles on the MapLibre map.
 *
 * Uses a blue→red color ramp based on the field's value range to
 * provide a rough visual representation for orientation validation.
 */
function PreviewLayer({
  map,
  product,
  date,
  run,
  variable,
  fhr = 0,
  resolution = 4,
  enabled = true,
}: PreviewLayerProps) {
  const addedRef = useRef(false)

  useEffect(() => {
    if (!map || !date || !run || !variable || !enabled) {
      // Clean up if conditions no longer met
      if (map && addedRef.current) {
        removeLayer(map)
        addedRef.current = false
      }
      return
    }

    const controller = new AbortController()

    apiGet<PreviewFeatureCollection>(
      '/api/preview',
      {
        product,
        date,
        run,
        variable,
        fhr: String(fhr),
        resolution: String(resolution),
      },
      controller.signal,
    )
      .then((collection) => {
        if (controller.signal.aborted) return
        addOrUpdateLayer(map, collection)
        addedRef.current = true
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        console.warn('[PreviewLayer] Failed to fetch preview:', err)
      })

    return () => {
      controller.abort()
      if (map && addedRef.current) {
        removeLayer(map)
        addedRef.current = false
      }
    }
  }, [map, product, date, run, variable, fhr, resolution, enabled])

  // This component renders nothing itself — it only manipulates the map
  return null
}

function addOrUpdateLayer(
  map: MaplibreMap,
  collection: PreviewFeatureCollection,
): void {
  const { min, max } = collection.properties

  // Build the GeoJSON data (strip non-standard properties from top level)
  const geojsonData: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: collection.features,
  }

  if (map.getSource(SOURCE_ID)) {
    // Update existing source data
    const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource
    source.setData(geojsonData)

    // Update the color ramp stops on the existing layer
    map.setPaintProperty(LAYER_ID, 'circle-color', buildColorRamp(min, max))
  } else {
    // Add new source and layer
    map.addSource(SOURCE_ID, {
      type: 'geojson',
      data: geojsonData,
    })

    map.addLayer({
      id: LAYER_ID,
      type: 'circle',
      source: SOURCE_ID,
      paint: {
        'circle-radius': 4,
        'circle-color': buildColorRamp(min, max),
        'circle-opacity': 0.8,
      },
    })
  }
}

/**
 * Build a MapLibre interpolate expression for blue→red color ramp
 * based on the value property of each feature.
 */
function buildColorRamp(
  min: number,
  max: number,
): maplibregl.ExpressionSpecification {
  // Avoid division by zero if min == max
  const effectiveMax = max > min ? max : min + 1

  return [
    'interpolate',
    ['linear'],
    ['get', 'value'],
    min, '#0000ff',                         // blue (low)
    min + (effectiveMax - min) * 0.25, '#00ccff', // cyan
    min + (effectiveMax - min) * 0.5, '#00ff00',  // green (mid)
    min + (effectiveMax - min) * 0.75, '#ffcc00', // yellow
    effectiveMax, '#ff0000',                       // red (high)
  ]
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

export default PreviewLayer
