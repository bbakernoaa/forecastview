import { useEffect, useRef, useState, useCallback } from 'react'
import { Marker } from 'maplibre-gl'
import type { MapMouseEvent } from 'maplibre-gl'
import { apiGet } from '../api/client'
import type { PointQueryResponse } from '../api/types'
import { useViewer } from '../context/ViewerContext'

type InspectorStatus = 'idle' | 'loading' | 'success' | 'error'

interface InspectorState {
  status: InspectorStatus
  data: PointQueryResponse | null
  error: string | null
  clickedLat: number | null
  clickedLon: number | null
}

const INITIAL_STATE: InspectorState = {
  status: 'idle',
  data: null,
  error: null,
  clickedLat: null,
  clickedLon: null,
}

/**
 * MapInspector — point-click value display panel.
 *
 * Registers a click handler on the MapLibre map. When the user clicks,
 * it queries GET /api/point with the current viewer state and clicked
 * coordinates, then displays the result.
 */
function MapInspector() {
  const { state, map } = useViewer()
  const { product, date, run, variable, level, forecastHour } = state

  const [inspector, setInspector] = useState<InspectorState>(INITIAL_STATE)
  const markerRef = useRef<Marker | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const handleMapClick = useCallback(
    (e: MapMouseEvent) => {
      const { lng, lat } = e.lngLat

      // Cancel any in-flight request
      abortRef.current?.abort()

      // Must have enough state to make a query
      if (!product || !date || !run || !variable) {
        setInspector({
          status: 'idle',
          data: null,
          error: null,
          clickedLat: lat,
          clickedLon: lng,
        })
        return
      }

      setInspector({
        status: 'loading',
        data: null,
        error: null,
        clickedLat: lat,
        clickedLon: lng,
      })

      const controller = new AbortController()
      abortRef.current = controller

      const params: Record<string, string> = {
        product,
        date,
        run,
        variable,
        fhr: String(forecastHour),
        lat: String(lat),
        lon: String(lng),
      }
      if (level != null) {
        params.level = String(level)
      }

      apiGet<PointQueryResponse>('/api/point', params, controller.signal)
        .then((data) => {
          if (controller.signal.aborted) return
          setInspector({
            status: 'success',
            data,
            error: null,
            clickedLat: lat,
            clickedLon: lng,
          })
        })
        .catch((err) => {
          if (err instanceof DOMException && err.name === 'AbortError') return
          setInspector({
            status: 'error',
            data: null,
            error: err instanceof Error ? err.message : String(err),
            clickedLat: lat,
            clickedLon: lng,
          })
        })
    },
    [product, date, run, variable, level, forecastHour],
  )

  // Register/unregister map click handler
  useEffect(() => {
    if (!map) return

    map.on('click', handleMapClick)
    return () => {
      map.off('click', handleMapClick)
    }
  }, [map, handleMapClick])

  // Manage marker on map
  useEffect(() => {
    if (!map) return

    if (inspector.clickedLat != null && inspector.clickedLon != null) {
      if (markerRef.current) {
        markerRef.current.setLngLat([inspector.clickedLon, inspector.clickedLat])
      } else {
        const el = document.createElement('div')
        el.style.width = '12px'
        el.style.height = '12px'
        el.style.borderRadius = '50%'
        el.style.background = '#ff4444'
        el.style.border = '2px solid #fff'
        el.style.boxShadow = '0 0 4px rgba(0,0,0,0.5)'

        const marker = new Marker({ element: el })
          .setLngLat([inspector.clickedLon, inspector.clickedLat])
          .addTo(map)
        markerRef.current = marker
      }
    }

    return () => {
      // Only remove marker if map is being unmounted
    }
  }, [map, inspector.clickedLat, inspector.clickedLon])

  // Clean up marker on unmount
  useEffect(() => {
    return () => {
      markerRef.current?.remove()
      markerRef.current = null
      abortRef.current?.abort()
    }
  }, [])

  // Render
  if (inspector.status === 'idle' && inspector.clickedLat == null) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>Point Inspector</div>
        <div style={placeholderStyle}>Click map to inspect</div>
      </div>
    )
  }

  if (inspector.status === 'loading') {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>Point Inspector</div>
        <div style={loadingStyle}>Loading...</div>
      </div>
    )
  }

  if (inspector.status === 'error') {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>Point Inspector</div>
        {inspector.clickedLat != null && (
          <div style={coordStyle}>
            {formatCoord(inspector.clickedLat, inspector.clickedLon!)}
          </div>
        )}
        <div style={errorStyle}>{inspector.error ?? 'Request failed'}</div>
      </div>
    )
  }

  if (inspector.status === 'idle' && inspector.clickedLat != null) {
    // Clicked but no variable selected
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>Point Inspector</div>
        <div style={coordStyle}>
          {formatCoord(inspector.clickedLat, inspector.clickedLon!)}
        </div>
        <div style={placeholderStyle}>Select a variable to query values</div>
      </div>
    )
  }

  // Success
  const data = inspector.data!
  return (
    <div style={containerStyle}>
      <div style={headerStyle}>Point Inspector</div>
      <div style={resultStyle}>
        <Row label="Lat" value={data.lat.toFixed(4)} />
        <Row label="Lon" value={data.lon.toFixed(4)} />
        <Row label="Variable" value={data.variable} />
        <Row
          label="Value"
          value={data.value != null ? `${data.value} ${data.units}` : 'N/A'}
        />
        <Row label="Units" value={data.units} />
        {data.level != null && <Row label="Level" value={String(data.level)} />}
        <Row label="Valid Time" value={data.valid_time} />
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={rowStyle}>
      <span style={labelStyle}>{label}</span>
      <span style={valueStyle}>{value}</span>
    </div>
  )
}

function formatCoord(lat: number, lon: number): string {
  return `${lat.toFixed(4)}, ${lon.toFixed(4)}`
}

// --------------------------------------------------------------------------
// Styles (dark theme, compact layout)
// --------------------------------------------------------------------------

const containerStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
}

const headerStyle: React.CSSProperties = {
  fontSize: '0.8rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  color: '#999',
  borderBottom: '1px solid #333',
  paddingBottom: '6px',
}

const placeholderStyle: React.CSSProperties = {
  color: '#666',
  fontStyle: 'italic',
  fontSize: '0.8rem',
}

const loadingStyle: React.CSSProperties = {
  color: '#88b',
  fontSize: '0.8rem',
}

const errorStyle: React.CSSProperties = {
  color: '#e55',
  fontSize: '0.8rem',
}

const coordStyle: React.CSSProperties = {
  color: '#aaa',
  fontSize: '0.75rem',
  fontFamily: 'monospace',
}

const resultStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
}

const rowStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'baseline',
  gap: '8px',
}

const labelStyle: React.CSSProperties = {
  color: '#888',
  fontSize: '0.75rem',
  flexShrink: 0,
}

const valueStyle: React.CSSProperties = {
  color: '#ddd',
  fontSize: '0.8rem',
  fontFamily: 'monospace',
  textAlign: 'right',
  wordBreak: 'break-all',
}

export default MapInspector
