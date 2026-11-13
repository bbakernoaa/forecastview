import type { ReactNode } from 'react'
import Legend from '../Legend'
import QuickViews from '../QuickViews'
import type { VariableInfo } from '../../api/types'

interface LeftPanelProps {
  variable?: VariableInfo | null
  children?: ReactNode
}

const DISCLAIMER_TEXT = 'EXPERIMENTAL — Not for operational use. Forecast guidance is for research use and has not been officially validated.'

function LeftPanel({ variable = null, children }: LeftPanelProps) {
  return (
    <aside className="desktop-panel left-panel" aria-label="Forecast and map controls">
      {children}
      <details className="legend-section" open>
        <summary>Legend and quick views</summary>
        <div className="legend-content">
          <Legend variable={variable} />
          <QuickViews />
        </div>
      </details>
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
    </aside>
  )
}

export default LeftPanel
