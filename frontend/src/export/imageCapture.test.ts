import { describe, expect, it } from 'vitest'
import { captureMapRect, embedForecastState, preferredVideoType } from './imageCapture'

describe('forecast image capture', () => {
  it('fits the full map in a square without distortion or cropping', () => {
    expect(captureMapRect(1600, 900, 1080, 1080)).toEqual({
      x: 0, y: 236, width: 1080, height: 608,
    })
  })

  it('retains native map pixels at the native size', () => {
    expect(captureMapRect(1536, 960, 1536, 960)).toEqual({
      x: 0, y: 0, width: 1536, height: 960,
    })
  })

  it('writes forecast state to a PNG text chunk without modifying image chunks', async () => {
    const png = Uint8Array.from(atob(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2uoAAAAASUVORK5CYII=',
    ), char => char.charCodeAt(0))
    const blob = await embedForecastState(new Blob([png], { type: 'image/png' }), 'product=air&fhr=12')
    const result = new Uint8Array(await blob.arrayBuffer())
    const view = new DataView(result.buffer)
    const decoder = new TextDecoder()
    const chunkStart = 33 // PNG signature and IHDR
    const chunkEnd = chunkStart + 12 + view.getUint32(chunkStart)
    expect(blob.type).toBe('image/png')
    expect(decoder.decode(result.slice(chunkStart + 4, chunkEnd - 4))).toBe(
      'tEXtForecastView\0product=air&fhr=12',
    )
    expect(view.getUint32(chunkEnd - 4)).toBe(0x58373c4c)
    expect(result.slice(0, chunkStart)).toEqual(png.slice(0, chunkStart))
    expect(result.slice(chunkEnd)).toEqual(png.slice(chunkStart))
  })
})

describe('video format selection', () => {
  it('prefers MP4 when the browser can encode it', () => {
    expect(preferredVideoType(() => true)).toBe('video/mp4')
  })

  it('uses WebM when MP4 encoding is unavailable', () => {
    expect(preferredVideoType(type => type === 'video/webm')).toBe('video/webm')
  })

  it('reports unavailable when neither format can be encoded', () => {
    expect(preferredVideoType(() => false)).toBeUndefined()
  })
})
