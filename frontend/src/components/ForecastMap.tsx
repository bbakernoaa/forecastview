import { useEffect, useRef, useState } from 'react'
import { Map as MaplibreMap } from 'maplibre-gl'
import type { MapStyleKey } from '../config/mapStyles'
import {
  MAP_STYLES,
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  MIN_ZOOM,
  MAX_ZOOM,
} from '../config/mapStyles'

interface ForecastMapProps {
  styleKey: MapStyleKey
  onMapReady?: (map: MaplibreMap | null) => void
}

function ForecastMap({ styleKey, onMapReady }: ForecastMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MaplibreMap | null>(null)
  const initializedRef = useRef(false)
  const styleKeyRef = useRef(styleKey)

  useEffect(() => {
    if (!containerRef.current || initializedRef.current) return
    initializedRef.current = true

    const map = new MaplibreMap({
      preserveDrawingBuffer: true,
      container: containerRef.current,
      style: MAP_STYLES[styleKey],
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      minZoom: MIN_ZOOM,
      maxZoom: MAX_ZOOM,
    })

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
    const newMap = new MaplibreMap({
      preserveDrawingBuffer: true,
      container: containerRef.current,
      style: MAP_STYLES[styleKey],
      center,
      zoom,
      bearing,
      pitch,
      minZoom: MIN_ZOOM,
      maxZoom: MAX_ZOOM,
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
