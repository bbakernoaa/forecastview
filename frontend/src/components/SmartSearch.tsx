import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useViewer } from '../context/ViewerContext'
import { useVariables } from '../hooks/useMetadata'
import type { VariableInfo } from '../api/types'

interface LocationPreset {
  label: string
  center: [number, number] // [lng, lat]
  zoom: number
  category: string
}

const LOCATION_PRESETS: LocationPreset[] = [
  { label: 'Global View', center: [0, 20], zoom: 1.5, category: 'Region' },
  { label: 'CONUS (United States)', center: [-98.5, 39.8], zoom: 4, category: 'Region' },
  { label: 'East Coast US', center: [-78, 37], zoom: 5, category: 'Region' },
  { label: 'West Coast US', center: [-121, 38], zoom: 5, category: 'Region' },
  { label: 'New York / Tri-State', center: [-74.0, 40.7], zoom: 7, category: 'City' },
  { label: 'Los Angeles / SoCal', center: [-118.2, 34.0], zoom: 7, category: 'City' },
  { label: 'Chicago / Great Lakes', center: [-87.6, 41.8], zoom: 7, category: 'City' },
  { label: 'Houston / Texas Coast', center: [-95.3, 29.7], zoom: 7, category: 'City' },
  { label: 'Seattle / Pacific NW', center: [-122.3, 47.6], zoom: 7, category: 'City' },
  { label: 'Miami / South Florida', center: [-80.2, 25.7], zoom: 7, category: 'City' },
  { label: 'Alaska', center: [-153, 64], zoom: 4, category: 'Region' },
  { label: 'Hawaii', center: [-157, 20], zoom: 6, category: 'Region' },
  { label: 'Central America / Caribbean', center: [-87, 15], zoom: 4, category: 'Region' },
  { label: 'Europe', center: [15, 50], zoom: 4, category: 'Region' },
  { label: 'Sahara / North Africa', center: [10, 20], zoom: 3.5, category: 'Region' },
  { label: 'East Asia', center: [115, 35], zoom: 3.5, category: 'Region' },
  { label: 'India / South Asia', center: [78, 22], zoom: 4, category: 'Region' },
  { label: 'South America', center: [-60, -15], zoom: 3, category: 'Region' },
  { label: 'Australia', center: [135, -25], zoom: 3.5, category: 'Region' },
]

export interface SmartSearchResult {
  id: string
  type: 'variable' | 'location' | 'coordinates'
  title: string
  subtitle: string
  category?: string
  variableName?: string
  center?: [number, number]
  zoom?: number
}

interface SmartSearchProps {
  onSelectResult?: () => void
  placeholder?: string
}

export default function SmartSearch({ onSelectResult, placeholder = 'Search species, region, city, coordinates...' }: SmartSearchProps) {
  const { state, dispatch, map } = useViewer()
  const { product, date, run } = state
  const { data: variablesList } = useVariables(product, date, run)

  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Parse input for coordinate match (e.g. "39.9, -83.0" or "40.71 -74.00")
  const parsedCoords = useMemo<[number, number] | null>(() => {
    const trimmed = query.trim()
    const match = trimmed.match(/^(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$/)
    if (!match) return null
    const lat = parseFloat(match[1])
    const lng = parseFloat(match[2])
    if (isNaN(lat) || isNaN(lng)) return null
    if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
      return [lng, lat]
    }
    return null
  }, [query])

  const results = useMemo<SmartSearchResult[]>(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []

    const list: SmartSearchResult[] = []

    // 1. Direct coordinate match
    if (parsedCoords) {
      list.push({
        id: `coords-${parsedCoords[0]}-${parsedCoords[1]}`,
        type: 'coordinates',
        title: `Coordinates: ${parsedCoords[1].toFixed(4)}°N, ${parsedCoords[0].toFixed(4)}°E`,
        subtitle: 'Fly map center to location',
        center: parsedCoords,
        zoom: 7,
      })
    }

    // 2. Search variables / species
    if (variablesList) {
      variablesList.forEach((v: VariableInfo) => {
        const matchScore =
          (v.fullName && v.fullName.toLowerCase().includes(q)) ||
          (v.shortName && v.shortName.toLowerCase().includes(q)) ||
          (v.name && v.name.toLowerCase().includes(q)) ||
          (v.category && v.category.toLowerCase().includes(q))

        if (matchScore) {
          list.push({
            id: `var-${v.name}`,
            type: 'variable',
            title: v.fullName || v.shortName || v.name,
            subtitle: `${v.category || 'Species'} • Units: ${v.units || 'N/A'}`,
            category: v.category,
            variableName: v.name,
          })
        }
      })
    }

    // 3. Search location presets
    LOCATION_PRESETS.forEach((preset) => {
      if (preset.label.toLowerCase().includes(q) || preset.category.toLowerCase().includes(q)) {
        list.push({
          id: `loc-${preset.label}`,
          type: 'location',
          title: preset.label,
          subtitle: `${preset.category} View`,
          center: preset.center,
          zoom: preset.zoom,
        })
      }
    })

    return list.slice(0, 8)
  }, [query, parsedCoords, variablesList])

  const handleSelect = useCallback(
    (item: SmartSearchResult) => {
      if (item.type === 'variable' && item.variableName) {
        dispatch({ type: 'SET_VARIABLE', payload: item.variableName })
      } else if ((item.type === 'location' || item.type === 'coordinates') && item.center) {
        if (map) {
          map.flyTo({
            center: item.center,
            zoom: item.zoom ?? 5,
            duration: 1200,
          })
        }
      }

      setQuery('')
      setIsOpen(false)
      onSelectResult?.()
    },
    [dispatch, map, onSelectResult]
  )

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={containerRef} style={wrapperStyle}>
      <div style={inputContainerStyle}>
        <span style={iconStyle}>🔍</span>
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setIsOpen(true)
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setIsOpen(false)
            if (e.key === 'Enter' && results.length > 0) {
              handleSelect(results[0])
            }
          }}
          placeholder={placeholder}
          style={inputStyle}
        />
        {query && (
          <button
            type="button"
            onClick={() => {
              setQuery('')
              setIsOpen(false)
            }}
            style={clearButtonStyle}
            title="Clear search"
          >
            ✕
          </button>
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div style={dropdownStyle}>
          {results.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => handleSelect(item)}
              style={itemStyle}
            >
              <span style={typeBadgeStyle(item.type)}>
                {item.type === 'variable' ? '🧪' : item.type === 'location' ? '📍' : '🎯'}
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
                <span style={titleStyle}>{item.title}</span>
                <span style={subtitleStyle}>{item.subtitle}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------
// Inline Styles
// --------------------------------------------------------------------------

const wrapperStyle: React.CSSProperties = {
  position: 'relative',
  display: 'flex',
  flexDirection: 'column',
  width: '100%',
  maxWidth: '320px',
}

const inputContainerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  background: '#222',
  border: '1px solid #444',
  borderRadius: '4px',
  padding: '4px 8px',
  gap: '6px',
}

const iconStyle: React.CSSProperties = {
  fontSize: '0.85rem',
  color: '#888',
}

const inputStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  outline: 'none',
  color: '#eee',
  fontSize: '0.8rem',
  width: '100%',
}

const clearButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#888',
  cursor: 'pointer',
  fontSize: '0.75rem',
  padding: '2px',
}

const dropdownStyle: React.CSSProperties = {
  position: 'absolute',
  top: 'calc(100% + 4px)',
  left: 0,
  right: 0,
  background: '#1e1e1e',
  border: '1px solid #444',
  borderRadius: '4px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
  zIndex: 1000,
  maxHeight: '260px',
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
}

const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '8px 10px',
  background: 'transparent',
  border: 'none',
  borderBottom: '1px solid #2a2a2a',
  color: '#ccc',
  textAlign: 'left',
  cursor: 'pointer',
  width: '100%',
}

const titleStyle: React.CSSProperties = {
  fontSize: '0.8rem',
  fontWeight: 600,
  color: '#eee',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}

const subtitleStyle: React.CSSProperties = {
  fontSize: '0.7rem',
  color: '#888',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}

function typeBadgeStyle(_type: SmartSearchResult['type']): React.CSSProperties {
  return {
    fontSize: '0.9rem',
    flexShrink: 0,
  }
}
