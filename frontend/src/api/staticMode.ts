/**
 * Static mode configuration.
 *
 * When VITE_STATIC_MODE is set, the frontend fetches pre-generated
 * JSON files and PNGs from relative paths instead of calling /api/ endpoints.
 */

export const STATIC_MODE = import.meta.env.VITE_STATIC_MODE === 'true'

/**
 * Build the correct URL for an API-like request in both modes.
 *
 * Dynamic mode: /api/dates?product=air
 * Static mode:  ./data/air/dates.json
 */
export function buildUrl(endpoint: string, params: Record<string, string>): string {
  if (!STATIC_MODE) {
    const qs = new URLSearchParams(params).toString()
    return `/api/${endpoint}?${qs}`
  }

  // Static mode: map endpoints to file paths
  const { product, date, run, variable, fhr } = params

  switch (endpoint) {
    case 'catalog':
      return `./data/catalog.json`
    case 'dates':
      return `./data/${product}/dates.json`
    case 'runs':
      // In static mode, runs are implicit from directory structure
      // We embed them in dates.json or derive from variables.json existence
      return `./data/${product}/${date}/runs.json`
    case 'variables':
      return `./data/${product}/${date}/${run}/variables.json`
    case 'times':
      return `./data/${product}/${date}/${run}/times.json`
    case 'fill-image':
      return `./data/${product}/${date}/${run}/fill/${variable}/f${fhr.padStart(3, '0')}.png`
    default:
      // Fallback to API style
      const qs = new URLSearchParams(params).toString()
      return `/api/${endpoint}?${qs}`
  }
}

/**
 * Build fill image URL (used by FillImageLayer).
 */
export function buildFillImageUrl(
  product: string,
  date: string,
  run: string,
  variable: string,
  fhr: number,
  level: number | null,
): string {
  if (!STATIC_MODE) {
    const params = new URLSearchParams({ product, date, run, variable, fhr: String(fhr) })
    if (level != null) params.set('level', String(level))
    return `/api/fill-image?${params.toString()}`
  }
  return `./data/${product}/${date}/${run}/fill/${variable}/f${String(fhr).padStart(3, '0')}.png`
}
