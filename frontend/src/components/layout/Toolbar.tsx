import type { ReactNode } from 'react'

interface ToolbarProps {
  children: ReactNode
}

function Toolbar({ children }: ToolbarProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: '12px',
        padding: '6px 12px',
        background: '#151f29',
        borderBottom: '1px solid #2a3a48',
      }}
    >
      {children}
    </div>
  )
}

export default Toolbar
