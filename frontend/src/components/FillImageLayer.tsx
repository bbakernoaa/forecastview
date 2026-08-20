import { useEffect, useRef } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'

interface FillImageLayerProps {
  map: MaplibreMap | null
  product: string
  date: string | null
  run: string | null
  variable: string | null
  level: number | null
  fhr: number | null
  visible?: boolean
  opacity?: number
}

const SOURCE_ID = 'fill-image-source'
const LAYER_ID = 'fill-image-layer'

function buildImageUrl(
  product: string,
  date: string,
  run: string,
  variable: string,
  fhr: number,
  level: number | null,
): string {
  const params = new URLSearchParams({
    product,
    date,
    run,
    variable,
    fhr: String(fhr),
  })
  if (level != null) {
    params.set('level', String(level))
  }
  return `/api/fill-image?${params.toString()}`
}

/**
 * Renders a raster fill image overlay on the MapLibre map.
 * Uses updateImage() for seamless frame transitions (no flash).
 */
function FillImageLayer({
  map,
  product,
  date,
  run,
  variable,
  level,
  fhr,
  visible = true,
  opacity = 0.7,
}: FillImageLayerProps) {
  const addedRef = useRef(false)

  // Create the source+layer once, then update the image URL on subsequent changes
  useEffect(() => {
    if (!map) return

    if (!product || !date || !run || !variable || fhr == null) {
      if (addedRef.current) {
        removeLayers(map)
        addedRef.current = false
      }
      return
    }

    const imageUrl = buildImageUrl(product, date, run, variable, fhr, level)

    if (addedRef.current) {
      // Source already exists — just swap the image URL (no flash)
      const source = map.getSource(SOURCE_ID)
      if (source && 'updateImage' in source) {
        ;(source as any).updateImage({ url: imageUrl })
        return
      }
    }

    // First time: create source + layer
    removeLayers(map)

    try {
      map.addSource(SOURCE_ID, {
        type: 'image',
        url: imageUrl,
        coordinates: [
          [-180, 85.06],
          [180, 85.06],
          [180, -85.06],
          [-180, -85.06],
        ],
      })

      map.addLayer({
        id: LAYER_ID,
        type: 'raster',
        source: SOURCE_ID,
        paint: {
          'raster-opacity': opacity,
          'raster-fade-duration': 0,
        },
        layout: {
          visibility: visible ? 'visible' : 'none',
        },
      })

      addedRef.current = true
    } catch (err) {
      console.error('[FillImageLayer] Error:', err)
    }
  }, [map, product, date, run, variable, level, fhr])

  useEffect(() => {
    if (!map || !addedRef.current) return
    try {
      if (map.getLayer(LAYER_ID)) {
        map.setLayoutProperty(LAYER_ID, 'visibility', visible ? 'visible' : 'none')
      }
    } catch { /* ignore */ }
  }, [map, visible])

  useEffect(() => {
    if (!map || !addedRef.current) return
    try {
      if (map.getLayer(LAYER_ID)) {
        map.setPaintProperty(LAYER_ID, 'raster-opacity', opacity)
      }
    } catch { /* ignore */ }
  }, [map, opacity])

  // Cleanup on unmount only
  useEffect(() => {
    return () => {
      if (map) {
        removeLayers(map)
        addedRef.current = false
      }
    }
  }, [map])

  return null
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
    // ignore
  }
}

export default FillImageLayer
