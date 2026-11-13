import { describe, it, expect } from 'vitest'
import { nearestIndex, nearestCurvilinearIndex, valueFromGrid, type GridMeta } from './pointStatic'

describe('pointStatic math', () => {
  const grid: GridMeta = { ny: 3, nx: 3, lon_min: -2, lon_max: 2, lat_min: -2, lat_max: 2 }
  // row-major: row 0 = lat_max (north). values = index
  const data = new Float32Array([8, 9, 10, 5, 6, 7, 2, 3, 4])

  it('finds center cell', () => {
    const [i, j] = nearestIndex(grid, 0, 0)
    expect(data[i * grid.nx + j]).toBe(6)
  })

  it('finds north-east cell', () => {
    const [i, j] = nearestIndex(grid, 2, 2)
    expect(data[i * grid.nx + j]).toBe(10)
  })

  it('finds south-west cell', () => {
    const [i, j] = nearestIndex(grid, -2, -2)
    expect(data[i * grid.nx + j]).toBe(2)
  })

  it('clamps out-of-range coordinates', () => {
    const [i, j] = nearestIndex(grid, 99, -99)
    expect(data[i * grid.nx + j]).toBe(4) // south-east corner
  })

  it('returns null for NaN', () => {
    const d2 = new Float32Array([NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN])
    expect(valueFromGrid(d2, 1, 1, 3)).toBeNull()
  })

  it('returns finite value otherwise', () => {
    expect(valueFromGrid(data, 0, 0, 3)).toBe(8)
  })

  it('finds the nearest point in a curvilinear grid and wraps longitude', () => {
    const coords = new Float32Array([
      -100, 40, -98, 40, -96, 40,
      -101, 38, -99, 38, -97, 38,
    ])
    expect(nearestCurvilinearIndex(coords, 3, 262, 40.1)).toEqual([0, 1])
  })

  it('skips invalid geolocation cells', () => {
    const coords = new Float32Array([NaN, NaN, 10, 20, 30, 40, 50, 60])
    expect(nearestCurvilinearIndex(coords, 2, 11, 21)).toEqual([0, 1])
  })
})
