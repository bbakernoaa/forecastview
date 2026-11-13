import { useEffect, useRef, useState } from 'react'
import type { Map as ForecastMap } from 'maplibre-gl'
import { downloadCapture, preferredVideoType } from './imageCapture'

const MAX_RECORDING_MS = 120_000

export function useCaptureVideo(
  map: ForecastMap | null,
  draw: (canvas: HTMLCanvasElement) => void,
  report: (message: string) => void,
) {
  const [recording, setRecording] = useState(false)
  const session = useRef<{ stop: () => void; cancel: () => void } | null>(null)
  const latestDraw = useRef(draw)
  useEffect(() => { latestDraw.current = draw }, [draw])
  useEffect(() => () => session.current?.cancel(), [map])

  const videoType = typeof MediaRecorder !== 'undefined'
    && typeof HTMLCanvasElement.prototype.captureStream === 'function'
    ? preferredVideoType(type => MediaRecorder.isTypeSupported(type))
    : undefined

  function start(canvas: HTMLCanvasElement, filename: string) {
    if (!map || !videoType || session.current) return

    const chunks: Blob[] = []
    const stream = canvas.captureStream(12)
    let recorder: MediaRecorder
    try {
      recorder = new MediaRecorder(stream, { mimeType: videoType, videoBitsPerSecond: 1_500_000 })
    } catch (error) {
      stream.getTracks().forEach(track => track.stop())
      throw error
    }

    let timeout: ReturnType<typeof setTimeout>
    let cancelled = false
    function renderFrame() {
      try {
        latestDraw.current(canvas)
      } catch (error) {
        cancel()
        report(error instanceof Error ? error.message : 'The map frame could not be recorded.')
      }
    }
    function cleanup() {
      clearTimeout(timeout)
      map?.off('render', renderFrame)
      stream.getTracks().forEach(track => track.stop())
      session.current = null
      setRecording(false)
    }
    function stop() {
      if (recorder.state !== 'inactive') recorder.stop()
    }
    function cancel() {
      cancelled = true
      stop()
      cleanup()
    }

    recorder.ondataavailable = ({ data }) => {
      if (data.size) chunks.push(data)
    }
    recorder.onerror = () => {
      cancel()
      report('Video recording failed.')
    }
    recorder.onstop = () => {
      if (cancelled) return
      cleanup()
      if (!chunks.length) {
        report('No video frames were recorded.')
        return
      }
      const extension = recorder.mimeType.startsWith('video/mp4') ? 'mp4' : 'webm'
      downloadCapture(new Blob(chunks, { type: recorder.mimeType }), `${filename}.${extension}`)
      report('Video downloaded.')
    }

    try {
      recorder.start(1000)
    } catch (error) {
      cleanup()
      throw error
    }
    session.current = { stop, cancel }
    map.on('render', renderFrame)
    map.triggerRepaint()
    timeout = setTimeout(stop, MAX_RECORDING_MS)
    setRecording(true)
  }

  return { videoType, recording, start, stop: () => session.current?.stop() }
}
