import { useEffect, useRef } from 'react'
import { apiGet } from '../api/client'
import type { ContourFeatureCollection } from '../api/types'
import { buildCacheKey } from './useGeoJsonCache'

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

export interface UsePrefetchParams {
  /** Current forecast hour displayed */
  currentFhr: number
  /** Ordered list of available forecast hours */
  forecastHours: number[]
  /** Required request parameters (null = disabled) */
  product: string | null
  date: string | null
  run: string | null
  variable: string | null
  level: number | null
  /** Optional contour interval override */
  interval?: number | null
  /** Whether animation is currently playing */
  playing?: boolean
}

// --------------------------------------------------------------------------
// Internal prefetch cache for contour GeoJSON
// --------------------------------------------------------------------------

const prefetchCache = new Map<string, ContourFeatureCollection>()

/** How many fhr positions away before evicting cached frames */
const EVICTION_DISTANCE = 5

/** How many neighboring frames (each direction) to prefetch when idle */
const PREFETCH_WINDOW = 1

// --------------------------------------------------------------------------
// Fill image preload tracking
// --------------------------------------------------------------------------

/** Set of fill-image URLs that have been preloaded into browser cache */
const preloadedImages = new Set<string>()

function buildFillImageUrl(
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
 * Preload a fill image URL into the browser cache via an Image() element.
 * The browser will cache it due to Cache-Control: immutable.
 */
function preloadImage(url: string): void {
  if (preloadedImages.has(url)) return
  preloadedImages.add(url)
  const img = new Image()
  img.src = url
}

// --------------------------------------------------------------------------
// usePrefetch
// --------------------------------------------------------------------------

/**
 * Prefetch hook that:
 * 1. When idle: prefetches contours + fill images for ±1 neighboring frames
 * 2. When playing: bulk-preloads ALL fill images for smooth animation
 *
 * Fill images are preloaded via Image() elements which populate the browser
 * HTTP cache. Since the backend returns Cache-Control: immutable, MapLibre
 * will get instant cache hits when it loads the image source URL.
 */
export function usePrefetch(params: UsePrefetchParams): void {
  const {
    currentFhr,
    forecastHours,
    product,
    date,
    run,
    variable,
    level,
    interval,
    playing = false,
  } = params

  const controllersRef = useRef<AbortController[]>([])

  // Bulk preload all fill images when playback starts
  useEffect(() => {
    if (!playing || !product || !date || !run || !variable || forecastHours.length === 0) {
      return
    }

    // Preload all fill images for the entire forecast sequence
    console.log(`[Prefetch] Preloading ${forecastHours.length} fill images for animation`)
    for (const fhr of forecastHours) {
      const url = buildFillImageUrl(product, date, run, variable, fhr, level)
      preloadImage(url)
    }
  }, [playing, product, date, run, variable, level, forecastHours])

  // Neighborhood prefetch (contours + fill images for ±1 frame)
  useEffect(() => {
    if (!product || !date || !run || !variable || forecastHours.length === 0) {
      return
    }

    const currentIdx = forecastHours.indexOf(currentFhr)
    if (currentIdx < 0) return

    // Determine target fhrs
    const targetFhrs: number[] = []
    for (let offset = -PREFETCH_WINDOW; offset <= PREFETCH_WINDOW; offset++) {
      if (offset === 0) continue
      const idx = currentIdx + offset
      if (idx >= 0 && idx < forecastHours.length) {
        targetFhrs.push(forecastHours[idx])
      }
    }

    // Evict distant contour frames
    const evictionSet = new Set<string>()
    for (const [key] of prefetchCache) {
      const parts = key.split('|')
      const cachedFhr = Number(parts[6])
      if (!Number.isNaN(cachedFhr)) {
        const cachedIdx = forecastHours.indexOf(cachedFhr)
        if (cachedIdx < 0 || Math.abs(cachedIdx - currentIdx) > EVICTION_DISTANCE) {
          evictionSet.add(key)
        }
      }
    }
    for (const key of evictionSet) {
      prefetchCache.delete(key)
    }

    // Abort previous requests
    for (const controller of controllersRef.current) {
      controller.abort()
    }
    controllersRef.current = []

    for (const fhr of targetFhrs) {
      // Prefetch contours GeoJSON
      const contourKey = buildCacheKey({
        product,
        date,
        run,
        variable,
        level,
        fhr,
        type: 'contours',
        interval,
      })

      if (!prefetchCache.has(contourKey)) {
        const controller = new AbortController()
        controllersRef.current.push(controller)

        const queryParams: Record<string, string> = {
          product,
          date,
          run,
          variable,
          fhr: String(fhr),
        }
        if (level != null) queryParams.level = String(level)
        if (interval != null) queryParams.interval = String(interval)

        apiGet<ContourFeatureCollection>('/api/contours', queryParams, controller.signal)
          .then((data) => {
            prefetchCache.set(contourKey, data)
          })
          .catch(() => {})
      }

      // Prefetch fill image (browser cache)
      const url = buildFillImageUrl(product, date, run, variable, fhr, level)
      preloadImage(url)
    }

    return () => {
      for (const controller of controllersRef.current) {
        controller.abort()
      }
      controllersRef.current = []
    }
  }, [currentFhr, forecastHours, product, date, run, variable, level, interval])
}

// --------------------------------------------------------------------------
// Public cache access
// --------------------------------------------------------------------------

export function getPrefetchedData(key: string): ContourFeatureCollection | null {
  return prefetchCache.get(key) ?? null
}

export function clearPrefetchCache(): void {
  prefetchCache.clear()
  preloadedImages.clear()
}
