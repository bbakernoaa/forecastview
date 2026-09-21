import React from 'react'

export type MobileTab = 'search' | 'controls' | 'legend' | 'inspector' | null

interface MobileHeaderProps {
  activeTab: MobileTab
  onToggleTab: (tab: MobileTab) => void
  currentInfo?: {
    variableName?: string | null
    initLabel?: string | null
    fhrLabel?: string | null
  }
}

export default function MobileHeader({ activeTab, onToggleTab, currentInfo }: MobileHeaderProps) {
  return (
    <header style={headerStyle}>
      <div style={titleContainerStyle}>
        <span style={titleStyle}>ForecastView</span>
        {currentInfo?.variableName && (
          <span style={badgeStyle}>
            {currentInfo.variableName}
            {currentInfo.fhrLabel ? ` (${currentInfo.fhrLabel})` : ''}
          </span>
        )}
      </div>

      <nav style={navStyle}>
        <button
          type="button"
          onClick={() => onToggleTab(activeTab === 'search' ? null : 'search')}
          style={buttonStyle(activeTab === 'search')}
          title="Smart Search"
          aria-label="Smart Search"
        >
          🔍
        </button>
        <button
          type="button"
          onClick={() => onToggleTab(activeTab === 'controls' ? null : 'controls')}
          style={buttonStyle(activeTab === 'controls')}
          title="Map & Data Controls"
          aria-label="Map & Data Controls"
        >
          ⚙️
        </button>
        <button
          type="button"
          onClick={() => onToggleTab(activeTab === 'legend' ? null : 'legend')}
          style={buttonStyle(activeTab === 'legend')}
          title="Legend & Quick Views"
          aria-label="Legend & Quick Views"
        >
          📊
        </button>
        <button
          type="button"
          onClick={() => onToggleTab(activeTab === 'inspector' ? null : 'inspector')}
          style={buttonStyle(activeTab === 'inspector')}
          title="Point Inspector"
          aria-label="Point Inspector"
        >
          📍
        </button>
      </nav>
    </header>
  )
}

// --------------------------------------------------------------------------
// Styles
// --------------------------------------------------------------------------

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '8px 12px',
  background: '#181818',
  borderBottom: '1px solid #333',
  zIndex: 1000,
  minHeight: '48px',
}

const titleContainerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  overflow: 'hidden',
}

const titleStyle: React.CSSProperties = {
  fontSize: '0.95rem',
  fontWeight: 700,
  color: '#4f46e5',
  letterSpacing: '0.5px',
}

const badgeStyle: React.CSSProperties = {
  fontSize: '0.72rem',
  color: '#ccc',
  background: '#2a2a2a',
  padding: '2px 6px',
  borderRadius: '4px',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}

const navStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
}

function buttonStyle(active: boolean): React.CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '36px',
    height: '36px',
    borderRadius: '6px',
    border: active ? '1px solid #6366f1' : '1px solid #333',
    background: active ? '#312e81' : '#262626',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '1rem',
    touchAction: 'manipulation',
  }
}
