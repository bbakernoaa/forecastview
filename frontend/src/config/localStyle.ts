/**
 * Offline fallback style: a plain dark ocean background with no tile
 * sources. Used when remote basemap tiles are unreachable (air-gapped
 * RZDM deployments). Forecast overlays still render georeferenced on top.
 */
import type { StyleSpecification } from 'maplibre-gl'

export const localStyle: StyleSpecification = {
  version: 8,
  name: 'forecastview-local',
  sources: {},
  layers: [
    {
      id: 'ocean-background',
      type: 'background',
      paint: { 'background-color': '#0b1a2b' },
    },
  ],
}

export default localStyle
