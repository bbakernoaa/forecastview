import { describe, it, expect, vi, afterEach } from 'vitest'
import { apiGetStatic } from './client'

describe('apiGetStatic', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('fetches relative path in static mode', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ dates: ['20260821'] }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const res = await apiGetStatic('dates', { product: 'air' }, undefined, {
      static: true,
    })
    expect(fetchMock.mock.calls[0][0]).toContain('./data/air/dates.json')
    expect(res).toEqual({ dates: ['20260821'] })
  })

  it('fetches /api path in dynamic mode', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ dates: ['20260821'] }),
    })
    vi.stubGlobal('fetch', fetchMock)
    await apiGetStatic('dates', { product: 'air' }, undefined, { static: false })
    expect(fetchMock.mock.calls[0][0]).toContain('/api/dates?product=air')
  })

  it('returns null on 404 when allowMissing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, statusText: 'NF' }))
    const res = await apiGetStatic(
      'levels',
      { product: 'air', date: 'd', run: 'r' },
      undefined,
      { static: true, allowMissing: true },
    )
    expect(res).toBeNull()
  })

  it('throws ApiError on non-404 failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'ISE',
        json: async () => {
          throw new Error('not json');
        },
        text: async () => 'internal error',
      }),
    )
    await expect(apiGetStatic('dates', { product: 'air' }, undefined, { static: true })).rejects.toThrow(
      /500/,
    )
  })
})
