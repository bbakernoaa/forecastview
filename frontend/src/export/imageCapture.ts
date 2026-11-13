export const CAPTURE_SIZES = {
  native: null,
  hd: [1920, 1080],
  large: [1600, 900],
  standard: [1200, 675],
  square: [1080, 1080],
} as const

export type CaptureSize = keyof typeof CAPTURE_SIZES
export type CaptureLayout = 'map' | 'legend' | 'full'

export function captureMapRect(sourceWidth: number, sourceHeight: number, width: number, height: number) {
  const scale = Math.min(width / sourceWidth, height / sourceHeight)
  const fittedWidth = Math.round(sourceWidth * scale)
  const fittedHeight = Math.round(sourceHeight * scale)
  return {
    x: Math.floor((width - fittedWidth) / 2),
    y: Math.floor((height - fittedHeight) / 2),
    width: fittedWidth,
    height: fittedHeight,
  }
}

export function canvasBlob(canvas: HTMLCanvasElement, type: string): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Image encoding failed.')), type, 0.92)
  })
}

export async function embedForecastState(png: Blob, state: string): Promise<Blob> {
  // The canvas produces a PNG with a 13-byte IHDR. Insert tEXt immediately after it.
  const headerEnd = 33
  const data = new TextEncoder().encode(`tEXtForecastView\0${state}`)
  const chunk = new Uint8Array(data.length + 8)
  const view = new DataView(chunk.buffer)
  view.setUint32(0, data.length - 4)
  chunk.set(data, 4)

  let crc = 0xffffffff
  for (const byte of data) {
    crc ^= byte
    for (let bit = 0; bit < 8; bit++) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0)
    }
  }
  view.setUint32(chunk.length - 4, crc ^ 0xffffffff)
  return new Blob([png.slice(0, headerEnd), chunk, png.slice(headerEnd)], { type: 'image/png' })
}

export function downloadCapture(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function preferredVideoType(supports: (type: string) => boolean) {
  return ['video/mp4', 'video/webm'].find(supports)
}
