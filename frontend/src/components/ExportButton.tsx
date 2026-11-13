import { useCallback, useEffect, useState } from 'react'
import { apiGetStatic } from '../api/client'
import { buildFillImageUrl } from '../api/staticMode'
import { useViewer } from '../context/ViewerContext'
import { useLevels, useVariables } from '../hooks/useMetadata'
import { encodeStateToUrl } from '../hooks/useUrlState'
import {
  CAPTURE_SIZES, canvasBlob, captureMapRect, downloadCapture, embedForecastState,
} from '../export/imageCapture'
import type { CaptureLayout, CaptureSize } from '../export/imageCapture'
import { useCaptureVideo } from '../export/useCaptureVideo'
import './ExportButton.css'

const buttonStyle: React.CSSProperties = {
  padding: '4px 10px',
  fontSize: '0.8rem',
  cursor: 'pointer',
  border: '1px solid #555',
  borderRadius: '3px',
  background: '#2a2a2a',
  color: '#ccc',
}

const activeStyle: React.CSSProperties = {
  ...buttonStyle,
  background: '#4a9eff',
  color: '#fff',
  cursor: 'wait',
}

/**
 * Draw a colorbar + labels onto a canvas context at the specified position.
 */
function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = text.split(' ')
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    const test = current ? `${current} ${word}` : word
    if (ctx.measureText(test).width <= maxWidth) {
      current = test
    } else {
      if (current) lines.push(current)
      current = word
    }
  }
  if (current) lines.push(current)
  return lines
}

function drawColorbar(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  barHeight: number,
  colors: string[],
  fillLevels: number[],
  title: string,
) {
  const numBands = colors.length
  const barWidth = 20
  const bandHeight = barHeight / numBands
  const padding = 10
  const lineHeight = 14

  // Measure title to wrap it
  ctx.font = 'bold 11px sans-serif'
  const maxTitleWidth = width - 4
  const titleLines = wrapText(ctx, title, maxTitleWidth)
  const titleBlockHeight = titleLines.length * lineHeight + 20

  // Total box height: title + gap + color bar
  const totalHeight = titleBlockHeight + barHeight + padding
  const bgWidth = width + padding * 2

  // Draw background
  ctx.fillStyle = 'rgba(0, 0, 0, 0.75)'
  ctx.beginPath()
  ctx.roundRect(x - padding, y, bgWidth, totalHeight, 4)
  ctx.fill()

  // Draw title (wrapped)
  ctx.fillStyle = '#ffffff'
  ctx.font = 'bold 11px sans-serif'
  let textY = y + padding
  for (let i = 0; i < titleLines.length; i++) {
    ctx.fillText(titleLines[i], x, textY + (i + 1) * lineHeight - 2)
  }

  // Color bar starts below title
  const barTop = y + titleBlockHeight

  // Color bands (top = highest value)
  for (let i = 0; i < numBands; i++) {
    const bandIdx = numBands - 1 - i
    ctx.fillStyle = colors[bandIdx]
    ctx.fillRect(x, barTop + i * bandHeight, barWidth, bandHeight + 0.5)
  }

  // Border around color bar
  ctx.strokeStyle = '#666'
  ctx.lineWidth = 1
  ctx.strokeRect(x, barTop, barWidth, barHeight)

  // Labels beside color bar
  ctx.fillStyle = '#ffffff'
  ctx.font = '10px sans-serif'
  const labelX = x + barWidth + 5

  // Show labels for each fill level (top to bottom = high to low)
  const maxLabels = 10
  const step = Math.max(1, Math.ceil(fillLevels.length / maxLabels))
  for (let i = 0; i < fillLevels.length; i += step) {
    // Position: level index 0 = bottom of bar, last = top
    const frac = i / (fillLevels.length - 1)
    const labelY = barTop + (1 - frac) * barHeight + 4
    const val = fillLevels[i]
    const label = val >= 0.01 ? val.toPrecision(2) : val.toExponential(0)
    ctx.fillText(label, labelX, labelY)
  }
}

function ExportButton({ allowVideo = true }: { allowVideo?: boolean }) {
  const { map, state } = useViewer()
  const { product, date, run, variable, forecastHour } = state
  const [exporting, setExporting] = useState(false)

  const { data: variablesList } = useVariables(product, date, run)

  const { data: levels } = useLevels(product, date, run, variable)
  const [layout, setLayout] = useState<CaptureLayout>('legend')
  const [size, setSize] = useState<CaptureSize>('native')
  const [message, setMessage] = useState('')
  const [logo, setLogo] = useState<HTMLImageElement | null>(null)

  useEffect(() => {
    const image = new Image()
    image.onload = () => setLogo(image)
    image.src = new URL('nws-logo.png', document.baseURI).href
    return () => { image.onload = null }
  }, [])

  const filename = `${variable ?? 'map'}_${date ?? ''}_${run ?? ''}Z_f${String(forecastHour).padStart(3, '0')}`

  function drawFrame(canvas: HTMLCanvasElement) {
    if (!map) throw new Error('The map is unavailable.')
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Image capture is unavailable.')
    const { width, height } = canvas
    const source = map.getCanvas()
    if (!source.width || !source.height) throw new Error('The map is unavailable.')

    const scale = Math.min(2, Math.max(0.65, Math.min(width / 700, height / 440)))
    const full = layout === 'full'
    const headerHeight = full ? Math.round(35 * scale) : 0
    const footerHeight = layout === 'map' ? 0 : Math.round(62 * scale)
    const mapHeight = height - headerHeight - footerHeight
    if (mapHeight <= 0) throw new Error('Choose a larger image size.')
    const rect = captureMapRect(source.width, source.height, width, mapHeight)

    ctx.fillStyle = '#171b23'
    ctx.fillRect(0, 0, width, height)
    ctx.drawImage(source, rect.x, rect.y + headerHeight, rect.width, rect.height)
    ctx.save()
    ctx.scale(scale, scale)
    const w = width / scale
    const h = height / scale
    const varInfo = variablesList?.find(v => v.name === variable)
    const rendering = varInfo?.rendering
    const level = levels?.find(item => item.value === state.level)?.label
      ?? (state.level == null ? levels?.[0]?.label : String(state.level))
    const title = [varInfo?.fullName ?? variable ?? 'Forecast map', level, varInfo?.units]
      .filter(Boolean).join(' · ')

    if (layout !== 'map') {
      const init = new Date(`${date?.slice(0, 4)}-${date?.slice(4, 6)}-${date?.slice(6, 8)}T${run?.padStart(2, '0')}:00:00Z`)
      const valid = new Date(init.getTime() + forecastHour * 3600_000)
      const formatUtc = (time: Date) => Number.isFinite(time.getTime())
        ? time.toISOString().slice(0, 16).replace('T', ' ') + 'Z'
        : 'Unavailable'
      const time = `Init ${formatUtc(init)}   |   F${String(forecastHour).padStart(3, '0')}   |   Valid ${formatUtc(valid)}`
      const barHeight = Math.min(rect.height / scale * 0.55, 270)
      if (rendering?.colors?.length && rendering.fillLevels.length > 1 && state.renderingMode !== 'contours') {
        drawColorbar(ctx, 16, (headerHeight + rect.y) / scale + 8, 96, barHeight,
          rendering.colors, rendering.fillLevels, varInfo?.units ?? '')
      } else if (rendering && state.renderingMode === 'contours') {
        ctx.fillStyle = '#171b23'
        ctx.fillRect(8, headerHeight / scale + 8, 144, 24)
        ctx.fillStyle = '#fff'
        ctx.font = '11px sans-serif'
        ctx.fillText(`Contour interval ${state.contourInterval ?? rendering.contourInterval}`,
          14, headerHeight / scale + 24, 132)
      }

      if (full) {
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 17px sans-serif'
        ctx.fillText(`ForecastView · ${product}`, 12, 23, w - 24)
        if (logo) ctx.drawImage(logo, w - 35, 4, 27, 27)
      }
      ctx.fillStyle = '#fff'
      ctx.font = 'bold 14px sans-serif'
      ctx.fillText(title, 12, h - 43, w - 24)
      ctx.font = '12px sans-serif'
      ctx.fillText(time, 12, h - 27, w - 24)
      ctx.fillStyle = '#f5a623'
      ctx.font = '10px sans-serif'
      ctx.fillText('EXPERIMENTAL · Forecast guidance is for research use.', 12, h - 12, w - 24)
    }

    // MapLibre renders source attribution as HTML outside its WebGL canvas.
    const attribution = map.getContainer().querySelector('.maplibregl-ctrl-attrib-inner')?.textContent?.trim()
    if (attribution) {
      const maxWidth = Math.max(1, w - 12)
      const baseline = (headerHeight + mapHeight) / scale - 4
      ctx.font = '10px sans-serif'
      const labelWidth = Math.min(maxWidth, ctx.measureText(attribution).width)
      ctx.fillStyle = '#171b23'
      ctx.fillRect(w - labelWidth - 10, baseline - 10, labelWidth + 10, 14)
      ctx.fillStyle = '#fff'
      ctx.fillText(attribution, w - labelWidth - 5, baseline, maxWidth)
    }
    ctx.restore()
  }

  function createCaptureCanvas(forVideo = false) {
    if (!map || !map.loaded()) throw new Error('Wait for the map to finish loading and try again.')
    const source = map.getCanvas()
    const [width, height] = CAPTURE_SIZES[size] ?? [source.width, source.height]
    const canvas = document.createElement('canvas')
    const factor = forVideo ? Math.min(1, 1280 / width, 720 / height) : 1
    canvas.width = forVideo ? Math.floor(width * factor / 2) * 2 : width
    canvas.height = forVideo ? Math.floor(height * factor / 2) * 2 : height
    drawFrame(canvas)
    return canvas
  }

  const video = useCaptureVideo(map, canvas => {
    if (map?.loaded()) drawFrame(canvas)
  }, setMessage)

  async function exportFrame(action: 'png' | 'jpeg' | 'copy') {
    setMessage('')
    try {
      const canvas = createCaptureCanvas()
      if (action === 'jpeg') {
        downloadCapture(await canvasBlob(canvas, 'image/jpeg'), `${filename}.jpeg`)
      } else {
        const encoded = encodeStateToUrl({ ...state, fhr: forecastHour, mode: state.renderingMode })
        const png = canvasBlob(canvas, 'image/png').then(blob => embedForecastState(blob, encoded))
        if (action === 'copy') {
          await navigator.clipboard.write([new ClipboardItem({ 'image/png': png })])
          setMessage('Image copied.')
        } else {
          downloadCapture(await png, `${filename}.png`)
        }
      }
    } catch (error) {
      setMessage(action === 'copy' ? 'Could not copy the image. Try downloading PNG.'
        : error instanceof Error ? error.message : 'Image capture failed.')
    }
  }

  function startVideo() {
    try {
      video.start(createCaptureCanvas(true), `${filename}_animation`)
      setMessage('Recording the map. Use the forecast timeline, then stop to download.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not start recording.')
    }
  }

  const exportGif = useCallback(async () => {
    if (!map) return
    const { product, date, run, variable, level } = state
    if (!product || !date || !run || !variable) return

    setExporting(true)

    try {
      // Get forecast hours
      const timesData = await apiGetStatic<{ forecast_hours: { fhr: number }[] }>('times', {
        product,
        date,
        run,
      })
      if (!timesData) { setExporting(false); return }
      const fhrs: number[] = timesData.forecast_hours.map((e: { fhr: number }) => e.fhr)
      if (fhrs.length === 0) { setExporting(false); return }

      const { encode } = await import('modern-gif')
      const mapCanvas = map.getCanvas()
      const w = mapCanvas.width
      const h = mapCanvas.height
      const originalFhr = forecastHour

      // Load logo
      const logo = new Image()
      logo.crossOrigin = 'anonymous'
      logo.src = new URL('nws-logo.png', document.baseURI).href
      await new Promise<void>(r => { logo.onload = () => r(); logo.onerror = () => r(); if (logo.complete) r() })

      const varInfo = variablesList?.find(v => v.name === variable)

      // Capture each frame
      const frames: { data: Uint8ClampedArray<ArrayBuffer>; delay: number }[] = []

      for (const fhr of fhrs) {
        // Update fill image source
        const imgSrc = map.getSource('fill-image-source') as any
        if (imgSrc && 'updateImage' in imgSrc) {
          imgSrc.updateImage({
            url: buildFillImageUrl(product, date, run, variable, fhr, level),
          })
        }

        // Wait for image load + render
        await new Promise(r => setTimeout(r, 500))
        map.triggerRepaint()
        await new Promise(r => requestAnimationFrame(r))
        await new Promise(r => setTimeout(r, 150))

        // Composite frame (same as PNG export)
        const fc = document.createElement('canvas')
        fc.width = w; fc.height = h
        const ctx = fc.getContext('2d')!
        ctx.drawImage(mapCanvas, 0, 0)

        // Colorbar
        if (varInfo?.rendering?.colors && varInfo.rendering.fillLevels) {
          const { colors, fillLevels } = varInfo.rendering
          const bh = Math.min(h * 0.6, 300)
          drawColorbar(ctx, 16, Math.round((h - bh) / 2) + 20, 100, bh, colors, fillLevels, varInfo.fullName)
        }

        // Disclaimer
        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
        ctx.fillRect(0, h - 60, w, 20)
        ctx.fillStyle = '#f5a623'
        ctx.font = '10px sans-serif'
        ctx.fillText('\u26a0 EXPERIMENTAL \u2014 Not for operational use.', 12, h - 46)

        // Metadata bar with valid time
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
        ctx.fillRect(0, h - 40, w, 40)
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 16px sans-serif'
        const initDate = new Date(`${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)}T${run.padStart(2,'0')}:00:00Z`)
        const validDate = new Date(initDate.getTime() + fhr * 3600 * 1000)
        const validStr = validDate.toISOString().replace('T', ' ').slice(0, 16) + 'Z'
        ctx.fillText(`${variable}  |  Init: ${date} ${run}Z  |  FHR: ${String(fhr).padStart(3, '0')}  |  Valid: ${validStr}`, 12, h - 14)

        // Logo
        if (logo.complete && logo.naturalWidth > 0) {
          ctx.drawImage(logo, w - 46, h - 38, 36, 36)
        }

        const imgData = ctx.getImageData(0, 0, w, h)
        frames.push({ data: imgData.data, delay: 200 })
      }

      // Restore original frame
      const imgSrc = map.getSource('fill-image-source') as any
      if (imgSrc && 'updateImage' in imgSrc) {
        imgSrc.updateImage({
          url: buildFillImageUrl(product, date, run, variable, originalFhr, level),
        })
      }

      // Resize and encode GIF (max 800px wide for reasonable size)
      const gifW = Math.min(w, 800)
      const gifH = Math.round(gifW * h / w)

      const resized = frames.map(f => {
        const s = document.createElement('canvas'); s.width = w; s.height = h
        const sc = s.getContext('2d')!
        sc.putImageData(new ImageData(f.data, w, h), 0, 0)
        const d = document.createElement('canvas'); d.width = gifW; d.height = gifH
        const dc = d.getContext('2d')!
        dc.drawImage(s, 0, 0, gifW, gifH)
        return { data: dc.getImageData(0, 0, gifW, gifH).data, delay: f.delay }
      })

      const output = await encode({
        width: gifW,
        height: gifH,
        frames: resized.map(f => ({ data: f.data, delay: f.delay })),
      })

      const blob = new Blob([output], { type: 'image/gif' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.download = `${variable}_${date}_animation.gif`
      link.href = url
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('GIF export error:', err)
    } finally {
      setExporting(false)
    }
  }, [map, state, forecastHour, variablesList])

  const unavailable = !map || !date || !run || !variable
  const clipboardAvailable = typeof ClipboardItem !== 'undefined' && Boolean(navigator.clipboard?.write)

  return (
    <details className="forecast-capture">
      <summary>Capture</summary>
      <div className="forecast-capture__panel">
        <label>
          Layout
          <select value={layout} disabled={video.recording} onChange={event => setLayout(event.target.value as CaptureLayout)}>
            <option value="map">Map only</option>
            <option value="legend">Map + legend + metadata</option>
            <option value="full">Full forecast graphic</option>
          </select>
        </label>
        <label>
          Image size
          <select value={size} disabled={video.recording} onChange={event => setSize(event.target.value as CaptureSize)}>
            <option value="native">Native viewport</option>
            {Object.entries(CAPTURE_SIZES).map(([key, dimensions]) =>
              dimensions && <option key={key} value={key}>{dimensions.join(' × ')}</option>
            )}
          </select>
        </label>
        <div className="forecast-capture__actions">
          <button type="button" style={buttonStyle} disabled={unavailable || video.recording || exporting}
            onClick={() => void exportFrame('png')}>Download PNG</button>
          <button type="button" style={buttonStyle} disabled={unavailable || video.recording || exporting || !clipboardAvailable}
            onClick={() => void exportFrame('copy')}>Copy image</button>
          <button type="button" style={buttonStyle} disabled={unavailable || video.recording || exporting}
            onClick={() => void exportFrame('jpeg')}>Download JPEG</button>
          {allowVideo && <button type="button" style={buttonStyle} disabled={!video.recording && (unavailable || !video.videoType || exporting)}
            onClick={video.recording ? video.stop : startVideo}>
            {video.recording ? 'Stop and download video' : `Record video${video.videoType ? ` (${video.videoType.split('/')[1].toUpperCase()})` : ''}`}
          </button>}
          <button type="button" onClick={exportGif} disabled={unavailable || exporting || video.recording}
            style={exporting ? activeStyle : buttonStyle}>
            {exporting ? 'Exporting GIF…' : 'Download GIF'}
          </button>
        </div>
        <div role="status" aria-live="polite">{message}</div>
      </div>
    </details>
  )
}

export default ExportButton
