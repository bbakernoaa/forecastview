import { describe, it, expect } from 'vitest'
import { MAP_STYLES, isRemoteStyle } from './mapStyles'
import localStyle from './localStyle'

describe('mapStyles', () => {
  it('has an offline local style with bundled GeoJSON sources', () => {
    expect(MAP_STYLES.local).toBe(localStyle)
    expect(localStyle.version).toBe(8)
    const sources = Object.values(localStyle.sources)
    expect(sources.length).toBeGreaterThan(0)
    // Every source must be a local GeoJSON file, never a tile service.
    for (const src of sources) {
      expect(src.type).toBe('geojson')
    }
  })

  it('local style has no network URLs (fully offline)', () => {
    const json = JSON.stringify(localStyle)
    expect(json).not.toMatch(/https?:\/\//)
  })

  it('local style basemap paths are relative to the app root', () => {
    for (const src of Object.values(localStyle.sources)) {
      if (src.type !== 'geojson') continue
      expect(String(src.data)).toMatch(/^(\.\/|\/)basemap\/[\w-]+\.geojson$/)
    }
  })

  it('classifies remote vs local styles', () => {
    expect(isRemoteStyle('liberty')).toBe(true)
    expect(isRemoteStyle('dark')).toBe(true)
    expect(isRemoteStyle('local')).toBe(false)
  })
})
