import { useRef, useCallback } from 'react'

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

interface CacheEntry<T> {
  key: string
  data: T
  timestamp: number
}

export interface GeoJsonCache<T> {
  /** Retrieve a cached entry by key, or null if not present */
  get: (key: string) => T | null
  /** Store a value in the cache, evicting the oldest entry if at capacity */
  set: (key: string, data: T) => void
  /** Check whether a key is in the cache */
  has: (key: string) => boolean
  /** Remove all entries from the cache */
  clear: () => void
  /** Current number of entries */
  size: () => number
}

// --------------------------------------------------------------------------
// useGeoJsonCache
// --------------------------------------------------------------------------

/**
 * A simple LRU-like in-memory cache for GeoJSON responses.
 *
 * Stores up to `maxEntries` recent frames. When capacity is exceeded,
 * the oldest (least-recently-inserted) entry is evicted.
 *
 * The cache is keyed by a string (typically built from
 * product/date/run/variable/level/fhr). The data type is generic
 * so it works for both ContourFeatureCollection and FilledFeatureCollection.
 *
 * The cache lives for the lifetime of the component that calls this hook.
 * It is NOT shared across components — use a shared ref or context if needed.
 */
export function useGeoJsonCache<T>(maxEntries = 10): GeoJsonCache<T> {
  const entriesRef = useRef<CacheEntry<T>[]>([])

  const get = useCallback((key: string): T | null => {
    const entry = entriesRef.current.find((e) => e.key === key)
    if (entry) {
      // Move to end (most-recently-used)
      entriesRef.current = [
        ...entriesRef.current.filter((e) => e.key !== key),
        entry,
      ]
      return entry.data
    }
    return null
  }, [])

  const set = useCallback(
    (key: string, data: T) => {
      // Remove existing entry with the same key (if any)
      entriesRef.current = entriesRef.current.filter((e) => e.key !== key)

      // Evict oldest entries if at capacity
      while (entriesRef.current.length >= maxEntries) {
        entriesRef.current.shift()
      }

      // Add new entry at end (most-recently-used position)
      entriesRef.current.push({ key, data, timestamp: Date.now() })
    },
    [maxEntries],
  )

  const has = useCallback((key: string): boolean => {
    return entriesRef.current.some((e) => e.key === key)
  }, [])

  const clear = useCallback(() => {
    entriesRef.current = []
  }, [])

  const size = useCallback(() => {
    return entriesRef.current.length
  }, [])

  return { get, set, has, clear, size }
}

// --------------------------------------------------------------------------
// Utility: build cache key from request parameters
// --------------------------------------------------------------------------

/**
 * Build a deterministic cache key string from fetch parameters.
 */
export function buildCacheKey(params: {
  product: string
  date: string
  run: string
  variable: string
  level: number | null
  fhr: number
  type: 'contours' | 'filled'
  interval?: number | null
}): string {
  const parts = [
    params.type,
    params.product,
    params.date,
    params.run,
    params.variable,
    String(params.level ?? 'null'),
    String(params.fhr),
  ]
  if (params.type === 'contours' && params.interval != null) {
    parts.push(String(params.interval))
  }
  return parts.join('|')
}
