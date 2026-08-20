/**
 * Map style configuration for the forecast viewer.
 *
 * OpenFreeMap: free vector tiles, no API key, strong coastlines/borders.
 * CARTO: free, no labels variant for cleaner overlay.
 */

export const MAP_STYLES = {
  /** OpenFreeMap Liberty — clear boundaries and coastlines under overlays */
  liberty: 'https://tiles.openfreemap.org/styles/liberty',
  /** CARTO Dark Matter (no labels) — dark background for data overlays */
  dark: 'https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json',
  /** CARTO Positron (no labels) — light minimal background */
  light: 'https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json',
} as const

export type MapStyleKey = keyof typeof MAP_STYLES

export const DEFAULT_MAP_STYLE: MapStyleKey = 'liberty'

export const DEFAULT_CENTER: [number, number] = [-98.5, 39.8]
export const DEFAULT_ZOOM = 2
export const MIN_ZOOM = 0
export const MAX_ZOOM = 10
