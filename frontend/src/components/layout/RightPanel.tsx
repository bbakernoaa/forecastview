import { useState } from 'react'
import MapInspector from '../MapInspector'

function RightPanel() {
  const [collapsed, setCollapsed] = useState(false)

  if (collapsed) {
    return (
      <div
        style={{
          width: '32px',
          minWidth: '32px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-start',
          background: '#1a1a1a',
          borderLeft: '1px solid #333',
          paddingTop: '8px',
        }}
      >
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          style={{
            background: 'none',
            border: 'none',
            color: '#ccc',
            cursor: 'pointer',
            fontSize: '1rem',
            padding: '4px',
            lineHeight: 1,
          }}
          title="Expand inspector panel"
        >
          ◀
        </button>
      </div>
    )
  }

  return (
    <div
      style={{
        width: '240px',
        minWidth: '240px',
        display: 'flex',
        flexDirection: 'column',
        background: '#1a1a1a',
        borderLeft: '1px solid #333',
        overflowY: 'auto',
        padding: '12px',
        color: '#ccc',
        fontSize: '0.85rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#999', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Inspector
        </span>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          style={{
            background: 'none',
            border: 'none',
            color: '#999',
            cursor: 'pointer',
            fontSize: '0.9rem',
            padding: '2px 4px',
            lineHeight: 1,
          }}
          title="Collapse inspector panel"
        >
          ▶
        </button>
      </div>
      <MapInspector />
    </div>
  )
}

export default RightPanel
