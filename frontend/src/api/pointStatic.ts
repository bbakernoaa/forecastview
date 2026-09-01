/**
 * Client-side point query for static mode.
 *
 * The dynamic backend answers /api/point by opening the kerchunk store; a
 * static deployment has no backend, so the exporter ships the raw analysis
 * grid (grid.json + field/<var>/f<NNN>.bin) and we do the nearest-gridpoint
 * lookup here. Results mirror the PointQueryResponse shape from /api/point.
 */

import type { PointQueryResponse } from './types'

export interface GridMeta {
  ny: number
  nx: number
  lon_min: number
  lon_max: number
  lat_min: number
  lat_max: number
}

/**
 * Nearest (row, col) for a (lon, lat) on a regular row-major grid.
 *
 * Row 0 is the northernmost latitude (grid.json lat_max), matching the
 * exporter's field orientation after the -180 longitude shift.
 */
export function nearestIndex(g: GridMeta, lon: number, lat: number): [number, number] {
  const dx = (g.lon_max - g.lon_min) / (g.nx - 1)
  const dy = (g.lat_max - g.lat_min) / (g.ny - 1)
  let j = Math.round((lon - g.lon_min) / dx)
  let i = Math.round((g.lat_max - lat) / dy) // row 0 = north
  j = Math.max(0, Math.min(g.nx - 1, j))
  i = Math.max(0, Math.min(g.ny - 1, i))
  return [i, j]
}

/** Value at (i, j) or null when the cell is NaN (no data). */
export function valueFromGrid(data: Float32Array, i: number, j: number, nx: number): number | null {
  const v = data[i * nx + j]
  return Number.isFinite(v) ? v : null
}

const gridCache = new Map<string, Promise<GridMeta>>()
const binCache = new Map<string, Promise<Float32Array>>()
const unitsCache = new Map<string, Promise<string>>()
const validTimeCache = new Map<string, Promise<string>>()

function cached<T>(map: Map<string, Promise<T>>, key: string, loader: () => Promise<T>): Promise<T> {
  let p = map.get(key)
  if (!p) {
    p = loader()
    map.set(key, p)
    // Drop failed lookups so a later retry isn't poisoned by the rejection.
    p.catch(() => map.delete(key))
  }
  return p
}

function loadGrid(path: string): Promise<GridMeta> {
  return cached(gridCache, path, async () => {
    const res = await fetch(path)
    if (!res.ok) throw new Error(`grid metadata unavailable (${res.status})`)
    return (await res.json()) as GridMeta
  })
}

function loadBin(path: string): Promise<Float32Array> {
  return cached(binCache, path, async () => {
    const res = await fetch(path)
    if (!res.ok) throw new Error(`field data unavailable (${res.status})`)
    return new Float32Array(await res.arrayBuffer())
  })
}

/** Units for a variable, read from the run's variables.json (404 → ''). */
function loadUnits(path: string, variable: string): Promise<string> {
  return cached(unitsCache, `${path}#${variable}`, async () => {
    try {
      const res = await fetch(path)
      if (!res.ok) return ''
      const data = await res.json()
      const vars: { name: string; units?: string }[] = data?.variables ?? []
      return vars.find((v) => v.name === variable)?.units ?? ''
    } catch {
      return ''
    }
  })
}

/** Valid time for a forecast hour, read from the run's times.json. */
function loadValidTime(path: string, fhr: number): Promise<string> {
  return cached(validTimeCache, `${path}#${fhr}`, async () => {
    try {
      const res = await fetch(path)
      if (!res.ok) return ''
      const data = await res.json()
      const entries: { fhr: number; valid_time?: string }[] = data?.forecast_hours ?? []
      return entries.find((e) => e.fhr === fhr)?.valid_time ?? ''
    } catch {
      return ''
    }
  })
}

/**
 * Query the value of `variable` at (lat, lon) for a static export frame.
 *
 * `level` is accepted for signature parity with /api/point; the air product
 * is surface-only, so the static grid has no level dimension and the field is
 * reported as null.
 */
export async function queryPointStatic(
  product: string,
  date: string,
  run: string,
  variable: string,
  fhr: number,
  lat: number,
  lon: number,
  level: number | null = null,
): Promise<PointQueryResponse> {
  const base = `./data/${product}/${date}/${run}`
  const f = String(fhr).padStart(3, '0')

  const [grid, data, units, validTime] = await Promise.all([
    loadGrid(`${base}/grid.json`),
    loadBin(`${base}/field/${variable}/f${f}.bin`),
    loadUnits(`${base}/variables.json`, variable),
    loadValidTime(`${base}/times.json`, fhr),
  ])

  const [i, j] = nearestIndex(grid, lon, lat)
  const dx = (grid.lon_max - grid.lon_min) / (grid.nx - 1)
  const dy = (grid.lat_max - grid.lat_min) / (grid.ny - 1)

  return {
    lat,
    lon,
    variable,
    value: valueFromGrid(data, i, j, grid.nx),
    units,
    level,
    fhr,
    valid_time: validTime,
    grid_lat: grid.lat_max - i * dy,
    grid_lon: grid.lon_min + j * dx,
  }
}
