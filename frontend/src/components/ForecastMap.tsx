import { useEffect, useRef } from 'react'
import { Map as MaplibreMap } from 'maplibre-gl'
import type { MapStyleKey } from '../config/mapStyles'
import {
  MAP_STYLES,
  isRemoteStyle,
  styleFor,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  MIN_ZOOM,
  MAX_ZOOM,
} from '../config/mapStyles'
import { STATIC_MODE } from '../api/staticMode'

interface ForecastMapProps {
  styleKey: MapStyleKey
  onMapReady?: (map: MaplibreMap | null) => void
}

/**
 * Set once per page load after a remote basemap style fails to fetch.
 * Subsequent map creations start with the offline local style directly,
 * avoiding a failed-load flicker; a page reload retries the remote style.
 */
let offlineBasemap = false

function createMap(
  container: HTMLElement,
  styleKey: MapStyleKey,
  view?: { center: [number, number]; zoom: number; bearing: number; pitch: number },
): MaplibreMap {
  // Static builds (air-gapped) never attempt remote styles; a remote choice
  // renders the bundled offline basemap instead.
  const startLocal =
    (STATIC_MODE || offlineBasemap) && isRemoteStyle(styleKey)
  const map = new MaplibreMap({
    preserveDrawingBuffer: true,
    container,
    style: startLocal ? MAP_STYLES.local : styleFor(styleKey),
    center: view?.center ?? DEFAULT_CENTER,
    zoom: view?.zoom ?? DEFAULT_ZOOM,
    ...(view ? { bearing: view.bearing, pitch: view.pitch } : {}),
    minZoom: MIN_ZOOM,
    maxZoom: MAX_ZOOM,
  })

  // Fall back to the tile-free local style when the remote style itself
  // fails to load (before 'load' fires). Tile errors afterwards are ignored
  // so a mid-session network blip doesn't swap the basemap under the user.
  if (isRemoteStyle(styleKey)) {
    let styleLoaded = false
    let fellBack = false
    map.on('load', () => {
      styleLoaded = true
    })
    map.on('error', () => {
      if (styleLoaded || fellBack) return
      fellBack = true
      offlineBasemap = true
      map.setStyle(MAP_STYLES.local)
    })
  }
  return map
}

function ForecastMap({ styleKey, onMapReady }: ForecastMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MaplibreMap | null>(null)
  const initializedRef = useRef(false)
  const styleKeyRef = useRef(styleKey)

  useEffect(() => {
    if (!containerRef.current || initializedRef.current) return
    initializedRef.current = true

    const map = createMap(containerRef.current, styleKey)

    mapRef.current = map
    ;(window as unknown as Record<string, unknown>).__map = map

    map.on('load', () => {
      onMapReady?.(map)
    })

    return () => {
      onMapReady?.(null)
      mapRef.current = null
      map.remove()
      initializedRef.current = false
    }
  }, [])

  // Handle style changes by destroying and recreating the map
  useEffect(() => {
    // Skip the initial render (handled above)
    if (styleKeyRef.current === styleKey) return
    styleKeyRef.current = styleKey

    if (!containerRef.current || !mapRef.current) return

    const oldMap = mapRef.current

    // Get current view state before destroying
    const center = oldMap.getCenter()
    const zoom = oldMap.getZoom()
    const bearing = oldMap.getBearing()
    const pitch = oldMap.getPitch()

    // Signal layers to clean up
    onMapReady?.(null)
    oldMap.remove()
    mapRef.current = null

    // Create a new map with the new style
    const newMap = createMap(containerRef.current, styleKey, {
      center: [center.lng, center.lat],
      zoom,
      bearing,
      pitch,
    })

    mapRef.current = newMap
    ;(window as unknown as Record<string, unknown>).__map = newMap

    newMap.on('load', () => {
      onMapReady?.(newMap)
    })
  }, [styleKey])

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
      }}
    />
  )
}

export default ForecastMap
