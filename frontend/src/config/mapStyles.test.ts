import { describe, it, expect } from 'vitest'
import { MAP_STYLES, isRemoteStyle } from './mapStyles'
import localStyle from './localStyle'

describe('mapStyles', () => {
  it('has an offline local style with no tile sources', () => {
    expect(MAP_STYLES.local).toBe(localStyle)
    expect(localStyle.version).toBe(8)
    expect(Object.keys(localStyle.sources)).toHaveLength(0)
  })

  it('local style has no network URLs in layers', () => {
    const json = JSON.stringify(localStyle)
    expect(json).not.toMatch(/https?:\/\//)
  })

  it('classifies remote vs local styles', () => {
    expect(isRemoteStyle('liberty')).toBe(true)
    expect(isRemoteStyle('dark')).toBe(true)
    expect(isRemoteStyle('local')).toBe(false)
  })
})
