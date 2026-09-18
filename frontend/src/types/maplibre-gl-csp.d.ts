/**
 * Ambient types for the CSP build subpath (no bundled .d.ts ships with it).
 * The runtime module is UMD, so it is consumed via a default import whose
 * shape matches the main package's named-export surface.
 */
declare module 'maplibre-gl/dist/maplibre-gl-csp' {
  const maplibregl: typeof import('maplibre-gl')
  export default maplibregl
}
