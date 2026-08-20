import { useCallback, useState } from 'react'
import { useViewer } from '../context/ViewerContext'
import { useVariables } from '../hooks/useMetadata'

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

function ExportButton() {
  const { map, state } = useViewer()
  const { product, date, run, variable, forecastHour } = state
  const [exporting, setExporting] = useState(false)

  const { data: variablesList } = useVariables(product, date, run)

  const exportFrame = useCallback((format: 'png' | 'jpeg') => {
    if (!map) return

    const mapCanvas = map.getCanvas()
    const w = mapCanvas.width
    const h = mapCanvas.height

    // Load logo then composite everything
    const logo = new Image()
    logo.crossOrigin = 'anonymous'
    logo.src = '/nws-logo.png'

    const doExport = () => {
      const canvas = document.createElement('canvas')
      canvas.width = w
      canvas.height = h
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      // Draw the map
      ctx.drawImage(mapCanvas, 0, 0)

      // Find variable info for colorbar
      const varInfo = variablesList?.find(v => v.name === variable)
      if (varInfo?.rendering?.colors && varInfo.rendering.fillLevels) {
        const { colors, fillLevels } = varInfo.rendering
        const barHeight = Math.min(h * 0.6, 300)
        const barX = 16
        const barY = Math.round((h - barHeight) / 2) + 20
        drawColorbar(ctx, barX, barY, 100, barHeight, colors, fillLevels, varInfo.fullName)
      }

      // Add timestamp/metadata at bottom
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
      ctx.fillRect(0, h - 40, w, 40)
      ctx.fillStyle = '#ffffff'
      ctx.font = 'bold 16px sans-serif'
      // Compute valid time from init + fhr
      let validTimeStr = ''
      if (date && run != null) {
        const initDate = new Date(`${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)}T${run.padStart(2,'0')}:00:00Z`)
        const validDate = new Date(initDate.getTime() + forecastHour * 3600 * 1000)
        validTimeStr = validDate.toISOString().replace('T', ' ').slice(0, 16) + 'Z'
      }
      const meta = `${variable ?? ''}  |  Init: ${date ?? ''} ${run ?? ''}Z  |  FHR: ${String(forecastHour).padStart(3, '0')}  |  Valid: ${validTimeStr}  |  ForecastView`
      ctx.fillText(meta, 12, h - 14)

      // Draw NWS logo in bottom-right corner
      const logoSize = 36
      if (logo.complete && logo.naturalWidth > 0) {
        ctx.drawImage(logo, w - logoSize - 10, h - logoSize - 2, logoSize, logoSize)
      }

      // Disclaimer text above the metadata bar
      ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
      ctx.fillRect(0, h - 60, w, 20)
      ctx.fillStyle = '#f5a623'
      ctx.font = '10px sans-serif'
      ctx.fillText('⚠ EXPERIMENTAL — Not for operational use. Data from experimental GEFS-Aerosol model guidance.', 12, h - 46)

      // Export
      const mimeType = format === 'jpeg' ? 'image/jpeg' : 'image/png'
      const dataUrl = canvas.toDataURL(mimeType, 0.92)
      const link = document.createElement('a')
      link.download = `${variable ?? 'map'}_${date ?? ''}_f${String(forecastHour).padStart(3, '0')}.${format}`
      link.href = dataUrl
      link.click()
    }

    // If logo already cached, export immediately; otherwise wait for load
    if (logo.complete) {
      doExport()
    } else {
      logo.onload = doExport
      logo.onerror = doExport  // export without logo if it fails
    }
  }, [map, state, variablesList, variable, date, run, forecastHour])

  const exportGif = useCallback(async () => {
    if (!map) return
    const { product, date, run, variable, level } = state
    if (!product || !date || !run || !variable) return

    setExporting(true)

    try {
      // Get forecast hours
      const timesResp = await fetch(`/api/times?product=${product}&date=${date}&run=${run}`)
      if (!timesResp.ok) { setExporting(false); return }
      const timesData = await timesResp.json()
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
      logo.src = '/nws-logo.png'
      await new Promise<void>(r => { logo.onload = () => r(); logo.onerror = () => r(); if (logo.complete) r() })

      const varInfo = variablesList?.find(v => v.name === variable)

      // Capture each frame
      const frames: { data: Uint8ClampedArray; delay: number }[] = []

      for (const fhr of fhrs) {
        // Update fill image source
        const imgSrc = map.getSource('fill-image-source') as any
        if (imgSrc && 'updateImage' in imgSrc) {
          const p = new URLSearchParams({ product, date, run, variable, fhr: String(fhr) })
          if (level != null) p.set('level', String(level))
          imgSrc.updateImage({ url: `/api/fill-image?${p.toString()}` })
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
        const p = new URLSearchParams({ product, date, run, variable, fhr: String(originalFhr) })
        if (level != null) p.set('level', String(level))
        imgSrc.updateImage({ url: `/api/fill-image?${p.toString()}` })
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

  return (
    <fieldset
      style={{ border: 'none', padding: 0, display: 'flex', gap: '4px', alignItems: 'center' }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Export</legend>
      <button
        type="button"
        onClick={() => exportFrame('png')}
        style={buttonStyle}
        title="Export current view as PNG with colorbar"
      >
        PNG
      </button>
      <button
        type="button"
        onClick={() => exportFrame('jpeg')}
        style={buttonStyle}
        title="Export current view as JPEG with colorbar"
      >
        JPG
      </button>
      <button
        type="button"
        onClick={exportGif}
        disabled={exporting}
        style={exporting ? activeStyle : buttonStyle}
        title="Export animated GIF of all forecast hours"
      >
        {exporting ? 'GIF...' : 'GIF'}
      </button>
    </fieldset>
  )
}

export default ExportButton
