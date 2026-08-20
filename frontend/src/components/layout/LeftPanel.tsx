import type { ReactNode } from 'react'
import Legend from '../Legend'
import type { VariableInfo } from '../../api/types'

interface LeftPanelProps {
  variable?: VariableInfo | null
  children?: ReactNode
}

const DISCLAIMER_TEXT = 'EXPERIMENTAL — Not for operational use. Data shown is from experimental GEFS-Aerosol model guidance and has not been officially validated.'

function LeftPanel({ variable = null, children }: LeftPanelProps) {
  return (
    <div
      style={{
        width: '220px',
        minWidth: '220px',
        display: 'flex',
        flexDirection: 'column',
        background: '#1a1a1a',
        borderRight: '1px solid #333',
        overflowY: 'auto',
        padding: '12px',
        color: '#ccc',
        fontSize: '0.85rem',
      }}
    >
      <Legend variable={variable} />
      {children}
      {/* Experimental disclaimer */}
      <div
        style={{
          marginTop: 'auto',
          paddingTop: '12px',
          borderTop: '1px solid #333',
          fontSize: '0.65rem',
          color: '#f5a623',
          lineHeight: 1.4,
        }}
      >
        ⚠️ {DISCLAIMER_TEXT}
      </div>
    </div>
  )
}

export default LeftPanel
