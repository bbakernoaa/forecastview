import type { ReactNode } from 'react'
import Legend from '../Legend'
import type { VariableInfo } from '../../api/types'

interface LeftPanelProps {
  /** The currently selected variable info for the legend */
  variable?: VariableInfo | null
  children?: ReactNode
}

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
    </div>
  )
}

export default LeftPanel
