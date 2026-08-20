/**
 * Map style configuration for the forecast viewer.
 */

export const MAP_STYLES = {
  dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
} as const

export type MapStyleKey = keyof typeof MAP_STYLES

export const DEFAULT_MAP_STYLE: MapStyleKey = 'dark'

export const DEFAULT_CENTER: [number, number] = [-98.5, 39.8]
export const DEFAULT_ZOOM = 4
export const MIN_ZOOM = 2
export const MAX_ZOOM = 10
