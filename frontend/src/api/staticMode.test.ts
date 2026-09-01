import { describe, it, expect } from 'vitest'
import { buildUrl, buildFillImageUrl } from './staticMode'

describe('buildUrl dynamic mapping', () => {
  it('builds /api URLs with query string in dynamic mode', () => {
    const url = buildUrl('dates', { product: 'air' }, false)
    expect(url).toBe('/api/dates?product=air')
  })
})

describe('buildUrl static mapping', () => {
  const base = { product: 'air', date: '20260821', run: '00' }

  it('maps catalog', () => {
    expect(buildUrl('catalog', {}, true)).toBe('./data/catalog.json')
  })
  it('maps dates', () => {
    expect(buildUrl('dates', base, true)).toBe('./data/air/dates.json')
  })
  it('maps bounds', () => {
    expect(buildUrl('bounds', base, true)).toBe('./data/air/bounds.json')
  })
  it('maps runs', () => {
    expect(buildUrl('runs', base, true)).toBe('./data/air/20260821/runs.json')
  })
  it('maps variables', () => {
    expect(buildUrl('variables', base, true)).toBe(
      './data/air/20260821/00/variables.json',
    )
  })
  it('maps levels', () => {
    expect(buildUrl('levels', base, true)).toBe('./data/air/20260821/00/levels.json')
  })
  it('maps times', () => {
    expect(buildUrl('times', base, true)).toBe('./data/air/20260821/00/times.json')
  })
  it('maps contours with zero-padded fhr', () => {
    expect(
      buildUrl('contours', { ...base, variable: 'totAOD550', fhr: '3' }, true),
    ).toBe('./data/air/20260821/00/contours/totAOD550/f003.json')
  })
  it('maps fill-image with zero-padded fhr', () => {
    expect(
      buildUrl('fill-image', { ...base, variable: 'totAOD550', fhr: '120' }, true),
    ).toBe('./data/air/20260821/00/fill/totAOD550/f120.png')
  })
  it('falls back to /api for unknown endpoints', () => {
    expect(buildUrl('health', {}, true)).toBe('/api/health?')
  })
})

describe('buildFillImageUrl static mapping', () => {
  it('returns relative png path in static mode', () => {
    expect(
      buildFillImageUrl('air', '20260821', '00', 'totAOD550', 3, null, true),
    ).toBe('./data/air/20260821/00/fill/totAOD550/f003.png')
  })
  it('returns /api URL in dynamic mode', () => {
    const url = buildFillImageUrl('air', '20260821', '00', 'totAOD550', 3, 850, false)
    expect(url).toContain('/api/fill-image?')
    expect(url).toContain('level=850')
  })
})
