// @vitest-environment jsdom
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import type { Map as MapLibreMap } from 'maplibre-gl'

type FakeSource = {
  url: string
  updateImage: ReturnType<typeof vi.fn>
}

function makeMap() {
  let source: FakeSource | null = null
  const layers = new Set<string>()
  const listeners = new Map<string, (event: { error?: unknown }) => void>()

  return {
    on: vi.fn((event: string, listener: (event: { error?: unknown }) => void) => {
      listeners.set(event, listener)
    }),
    off: vi.fn((event: string) => listeners.delete(event)),
    addSource: vi.fn((_id: string, options: { url: string }) => {
      source = {
        url: options.url,
        updateImage: vi.fn(({ url }: { url: string }) => {
          if (source) source.url = url
        }),
      }
    }),
    getSource: vi.fn((_id: string) => source),
    removeSource: vi.fn(() => { source = null }),
    addLayer: vi.fn((layer: { id: string }) => layers.add(layer.id)),
    getLayer: vi.fn((id: string) => layers.has(id) ? { id } : undefined),
    removeLayer: vi.fn((id: string) => layers.delete(id)),
    setLayoutProperty: vi.fn(),
    setPaintProperty: vi.fn(),
    emit: (event: string, value: { error?: unknown }) => listeners.get(event)?.(value),
  }
}

describe('FillImageLayer', () => {
  let FillImageLayer: (typeof import('./FillImageLayer'))['default']

  beforeAll(async () => {
    vi.stubEnv('VITE_STATIC_MODE', 'true')
    vi.resetModules()
    ;({ default: FillImageLayer } = await import('./FillImageLayer'))
  })

  afterAll(() => vi.unstubAllEnvs())
  afterEach(cleanup)

  it('does not reload a static image when only its level changes', () => {
    const map = makeMap()
    const props = {
      map: map as unknown as MapLibreMap,
      product: 'AQMv8',
      date: '20250901',
      run: '00',
      variable: 'TMP',
      level: null as number | null,
      fhr: 0,
    }
    const view = render(<FillImageLayer {...props} />)
    const source = map.getSource('fill-image-source')

    view.rerender(<FillImageLayer {...props} level={2} />)

    expect(source?.updateImage).not.toHaveBeenCalled()
  })

  it('filters MapLibre AbortError events without hiding real source errors', () => {
    const map = makeMap()
    render(
      <FillImageLayer
        map={map as unknown as MapLibreMap}
        product="AQMv8"
        date="20250901"
        run="00"
        variable="TMP"
        level={null}
        fhr={0}
      />,
    )
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    map.emit('error', { error: new Error('AbortError') })
    expect(consoleError).not.toHaveBeenCalled()

    const failure = new Error('Could not load image')
    map.emit('error', { error: failure })
    expect(consoleError).toHaveBeenCalledWith('[MapLibre]', failure)
    consoleError.mockRestore()
  })
})
