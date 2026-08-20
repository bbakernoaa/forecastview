import { useEffect, useRef } from 'react'
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

  useEffect(() => {
    if (!containerRef.current || initializedRef.current) return
    initializedRef.current = true

    const map = new MaplibreMap({
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

  useEffect(() => {
    if (!mapRef.current) return
    mapRef.current.setStyle(MAP_STYLES[styleKey])
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
