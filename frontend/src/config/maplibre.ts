/**
 * CSP-safe MapLibre entry point.
 *
 * RZDM's Apache injects a Content-Security-Policy whose `script-src` omits
 * both `blob:` and a `worker-src` fallback. The default `maplibre-gl` bundle
 * spawns its GeoJSON/vectortile worker from a blob URL, so under that policy
 * the worker is blocked, source data never parses, and the map renders blank
 * (the offline basemap's Natural Earth GeoJSON sources made this path
 * mandatory, which is why the static build broke after the basemap landed).
 *
 * MapLibre ships a dedicated `maplibre-gl-csp` build for exactly this case:
 * it spawns a real same-origin worker from a standalone file whose URL is
 * supplied via `setWorkerUrl`. We re-export that build so the rest of the app
 * imports MapLibre values from here instead of the package root, and Vite
 * bundles the worker file as an asset so it stays same-origin in the static
 * export. Type-only imports elsewhere may keep pointing at 'maplibre-gl' —
 * same version, same API surface.
 */
import type { Map as MapType, Marker as MarkerType } from 'maplibre-gl'
import maplibregl from 'maplibre-gl/dist/maplibre-gl-csp'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-csp-worker.js?url'

// Resolve the emitted asset URL against the document base so it stays correct
// under both the app-root ('/') and relative ('./') deploy bases. (Resolving
// against import.meta.url would double-prefix './assets/...' in hashed chunks.)
maplibregl.setWorkerUrl(new URL(workerUrl, document.baseURI).href)

export const Map = maplibregl.Map
export type Map = MapType

export const Marker = maplibregl.Marker
export type Marker = MarkerType
