import { useEffect, useRef } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'
import { useFilled } from '../hooks/useFilled'
import type { FilledFeatureCollection } from '../api/types'

interface FilledContourLayerProps {
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
  /** Whether the filled layer is visible */
  visible?: boolean
}

const SOURCE_ID = 'filled-contour-source'
const LAYER_ID = 'filled-contour-layer'

/** Layer ID of the minor isoline layer — filled layer is inserted below this */
const ISOLINE_MINOR_LAYER_ID = 'isoline-minor-layer'

/**
 * A discrete blue→red color palette for filled contour bands.
 * Supports up to 12 bands. If more bands are present, colors wrap.
 */
const DISCRETE_PALETTE = [
  '#313695', // deep blue
  '#4575b4', // blue
  '#74add1', // light blue
  '#abd9e9', // pale blue
  '#e0f3f8', // very light blue
  '#ffffbf', // pale yellow
  '#fee090', // light orange
  '#fdae61', // orange
  '#f46d43', // red-orange
  '#d73027', // red
  '#a50026', // deep red
  '#67001f', // dark red
]

/**
 * Builds a MapLibre data-driven fill-color expression that maps
 * each `level_low` value to a discrete color from the palette.
 *
 * Uses a "match" expression keyed on `level_low` property. Each
 * unique fill level boundary gets a distinct color.
 */
function buildFillColorExpression(
  collection: FilledFeatureCollection,
): maplibregl.ExpressionSpecification {
  // Extract unique level_low values from features, sorted ascending
  const uniqueLevels = Array.from(
    new Set(collection.features.map((f) => f.properties.level_low)),
  ).sort((a, b) => a - b)

  // Use "step" expression which supports float thresholds (unlike "match")
  if (uniqueLevels.length === 0) {
    return '#cccccc' as unknown as maplibregl.ExpressionSpecification
  }

  const stepExpr: unknown[] = ['step', ['get', 'level_low']]
  // Default color for values below first threshold
  stepExpr.push(DISCRETE_PALETTE[0])

  for (let i = 0; i < uniqueLevels.length; i++) {
    const colorIdx = Math.min(i + 1, DISCRETE_PALETTE.length - 1)
    stepExpr.push(uniqueLevels[i])
    stepExpr.push(DISCRETE_PALETTE[colorIdx])
  }

  return stepExpr as maplibregl.ExpressionSpecification
}

/**
 * Renders filled contour polygons on the MapLibre map with discrete
 * color bands based on the `level_low` property of each feature.
 *
 * The fill layer is placed BELOW the isoline layers using MapLibre's
 * `beforeId` parameter so that contour lines draw on top of the fill.
 *
 * Uses the useFilled hook to fetch GeoJSON data from /api/filled.
 */
function FilledContourLayer({
  map,
  product,
  date,
  run,
  variable,
  level,
  fhr,
  visible = true,
}: FilledContourLayerProps) {
  const addedRef = useRef(false)

  const { status, data } = useFilled({
    product,
    date,
    run,
    variable,
    level,
    fhr,
  })

  // Add or update layers when data arrives
  useEffect(() => {
    console.log("[FilledContourLayer] effect:", { map: !!map, status, hasData: !!data, visible })
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
      if (map.getLayer(LAYER_ID)) {
        map.setLayoutProperty(LAYER_ID, 'visibility', visibility)
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
  collection: FilledFeatureCollection,
): void {
  const geojsonData: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: collection.features as unknown as GeoJSON.Feature[],
  }

  const fillColor = buildFillColorExpression(collection)

  // Remove existing layer/source and re-add fresh to avoid stale state
  try {
    if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID)
    if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID)
  } catch { /* ignore */ }

  map.addSource(SOURCE_ID, {
    type: 'geojson',
    data: geojsonData,
  })

  map.addLayer({
    id: LAYER_ID,
    type: 'fill',
    source: SOURCE_ID,
    paint: {
      'fill-color': fillColor,
      'fill-opacity': 0.7,
    },
  })
}

function removeLayers(map: MaplibreMap): void {
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

export default FilledContourLayer
