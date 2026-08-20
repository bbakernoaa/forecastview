import { useEffect, useRef } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'
import { useContours } from '../hooks/useContours'

interface IsolineLayerProps {
  map: MaplibreMap | null
  product: string
  date: string | null
  run: string | null
  variable: string | null
  level: number | null
  fhr: number | null
  interval?: number | null
  visible?: boolean
}

const SOURCE_ID = 'isoline-source'
const MINOR_LAYER_ID = 'isoline-minor-layer'
const MAJOR_LAYER_ID = 'isoline-major-layer'
const LABEL_LAYER_ID = 'contour-label-layer'

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
  const visibleRef = useRef(visible)
  visibleRef.current = visible

  const { status, data } = useContours({
    product,
    date,
    run,
    variable,
    level,
    fhr,
    interval,
  })

  useEffect(() => {
    if (!map) return

    if (status !== 'success' || !data) {
      if (addedRef.current) {
        removeLayers(map)
        addedRef.current = false
      }
      return
    }

    addOrUpdateLayers(map, data, visibleRef.current)
    addedRef.current = true

    return () => {
      if (map && addedRef.current) {
        removeLayers(map)
        addedRef.current = false
      }
    }
  }, [map, status, data])

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

  return null
}

function addOrUpdateLayers(
  map: MaplibreMap,
  collection: { type: string; features: GeoJSON.Feature[] },
  visible: boolean,
): void {
  const geojsonData: GeoJSON.FeatureCollection = {
    type: 'FeatureCollection',
    features: collection.features as GeoJSON.Feature[],
  }

  const visibility = visible ? 'visible' : 'none'

  if (map.getSource(SOURCE_ID)) {
    const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource
    source.setData(geojsonData)
  } else {
    map.addSource(SOURCE_ID, {
      type: 'geojson',
      data: geojsonData,
    })

    map.addLayer({
      id: MINOR_LAYER_ID,
      type: 'line',
      source: SOURCE_ID,
      filter: ['==', ['get', 'major'], false],
      layout: { visibility },
      paint: {
        'line-color': '#333333',
        'line-width': 1,
        'line-opacity': 0.5,
      },
    })

    map.addLayer({
      id: MAJOR_LAYER_ID,
      type: 'line',
      source: SOURCE_ID,
      filter: ['==', ['get', 'major'], true],
      layout: { visibility },
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
    if (map.getLayer(LABEL_LAYER_ID)) {
      map.removeLayer(LABEL_LAYER_ID)
    }
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
