import { useEffect, useRef } from 'react'
import { apiGet } from '../api/client'
import type { ContourFeatureCollection, FilledFeatureCollection } from '../api/types'
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
}

type CachedData = ContourFeatureCollection | FilledFeatureCollection

// --------------------------------------------------------------------------
// Internal prefetch cache (module-level singleton)
// --------------------------------------------------------------------------

/**
 * Module-level cache shared across component re-renders.
 * Stores fetched GeoJSON keyed by the cache key string.
 * Evicts frames that are more than EVICTION_DISTANCE away from
 * the current forecast hour.
 */
const prefetchCache = new Map<string, CachedData>()

/** How many fhr positions away before evicting cached frames */
const EVICTION_DISTANCE = 3

/** How many neighboring frames (each direction) to prefetch */
const PREFETCH_WINDOW = 1

// --------------------------------------------------------------------------
// usePrefetch
// --------------------------------------------------------------------------

/**
 * Background prefetch hook for neighboring forecast hours.
 *
 * Pre-fetches contour and filled GeoJSON for fhr-1 and fhr+1
 * (the immediate neighbors of the current frame). Results are stored
 * in an in-memory Map cache keyed by the full request parameters.
 *
 * Frames more than ±3 positions from the current forecast hour are
 * evicted from the cache to manage memory.
 *
 * This hook does NOT render anything — it's a pure side-effect hook.
 * The fetched data is available to other hooks/components via the
 * exported `getPrefetchedData` function.
 */
export function usePrefetch(params: UsePrefetchParams): void {
  const { currentFhr, forecastHours, product, date, run, variable, level, interval } = params

  // Keep track of in-flight requests so we can abort them on cleanup
  const controllersRef = useRef<AbortController[]>([])

  useEffect(() => {
    // All required params must be present
    if (!product || !date || !run || !variable || forecastHours.length === 0) {
      return
    }

    const currentIdx = forecastHours.indexOf(currentFhr)
    if (currentIdx < 0) return

    // Determine which fhr values to prefetch (±PREFETCH_WINDOW)
    const targetFhrs: number[] = []
    for (let offset = -PREFETCH_WINDOW; offset <= PREFETCH_WINDOW; offset++) {
      if (offset === 0) continue // skip current frame
      const idx = currentIdx + offset
      if (idx >= 0 && idx < forecastHours.length) {
        targetFhrs.push(forecastHours[idx])
      }
    }

    // Evict distant frames from cache
    const evictionSet = new Set<string>()
    for (const [key] of prefetchCache) {
      // Parse the fhr from the cache key to check distance
      // Key format: type|product|date|run|variable|level|fhr[|interval]
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

    // Abort any previous in-flight prefetch requests
    for (const controller of controllersRef.current) {
      controller.abort()
    }
    controllersRef.current = []

    // Fire prefetch requests for each target fhr
    for (const fhr of targetFhrs) {
      // Prefetch contours
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
          .catch(() => {
            // Silently ignore prefetch failures — they are non-critical
          })
      }

      // Prefetch filled
      const filledKey = buildCacheKey({
        product,
        date,
        run,
        variable,
        level,
        fhr,
        type: 'filled',
      })

      if (!prefetchCache.has(filledKey)) {
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

        apiGet<FilledFeatureCollection>('/api/filled', queryParams, controller.signal)
          .then((data) => {
            prefetchCache.set(filledKey, data)
          })
          .catch(() => {
            // Silently ignore prefetch failures
          })
      }
    }

    // Cleanup: abort in-flight requests on unmount or dependency change
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

/**
 * Retrieve prefetched GeoJSON data from the cache.
 *
 * Returns the cached data if available, or null if the frame
 * hasn't been prefetched yet.
 */
export function getPrefetchedData(key: string): CachedData | null {
  return prefetchCache.get(key) ?? null
}

/**
 * Clear the entire prefetch cache.
 * Useful when switching products/variables/runs where old data is irrelevant.
 */
export function clearPrefetchCache(): void {
  prefetchCache.clear()
}
