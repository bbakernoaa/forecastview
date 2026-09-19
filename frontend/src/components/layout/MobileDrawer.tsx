import React from 'react'
import type { ReactNode } from 'react'
import type { MobileTab } from './MobileHeader'

interface MobileDrawerProps {
  activeTab: MobileTab
  onClose: () => void
  children: ReactNode
  title?: string
}

export default function MobileDrawer({ activeTab, onClose, children, title }: MobileDrawerProps) {
  if (!activeTab) return null

  return (
    <div style={backdropStyle} onClick={onClose}>
      <div style={drawerStyle} onClick={(e) => e.stopPropagation()}>
        <div style={headerStyle}>
          <span style={titleStyle}>{title || formatTabTitle(activeTab)}</span>
          <button type="button" onClick={onClose} style={closeButtonStyle} aria-label="Close drawer">
            ✕
          </button>
        </div>
        <div style={contentStyle}>{children}</div>
      </div>
    </div>
  )
}

function formatTabTitle(tab: MobileTab): string {
  switch (tab) {
    case 'search':
      return 'Smart Search'
    case 'controls':
      return 'Forecast Controls & Layers'
    case 'legend':
      return 'Legend & Quick Views'
    case 'inspector':
      return 'Point Inspector'
    default:
      return 'Controls'
  }
}

// --------------------------------------------------------------------------
// Styles
// --------------------------------------------------------------------------

const backdropStyle: React.CSSProperties = {
  position: 'fixed',
  top: '48px',
  left: 0,
  right: 0,
  bottom: 0,
  background: 'rgba(0,0,0,0.4)',
  zIndex: 1100,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'flex-end',
}

const drawerStyle: React.CSSProperties = {
  background: '#1a1a1a',
  borderTopLeftRadius: '12px',
  borderTopRightRadius: '12px',
  borderTop: '1px solid #444',
  maxHeight: '75vh',
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '0 -4px 20px rgba(0,0,0,0.7)',
  overflow: 'hidden',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px 16px',
  borderBottom: '1px solid #333',
  background: '#222',
}

const titleStyle: React.CSSProperties = {
  fontSize: '0.9rem',
  fontWeight: 600,
  color: '#eee',
}

const closeButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#aaa',
  fontSize: '1rem',
  cursor: 'pointer',
  padding: '4px 8px',
  borderRadius: '4px',
  touchAction: 'manipulation',
}

const contentStyle: React.CSSProperties = {
  padding: '16px',
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
}
