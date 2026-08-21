import { useCallback, useState } from 'react'

const buttonStyle: React.CSSProperties = {
  padding: '4px 10px',
  fontSize: '0.8rem',
  cursor: 'pointer',
  border: '1px solid #555',
  borderRadius: '3px',
  background: '#2a2a2a',
  color: '#ccc',
}

const activeStyle: React.CSSProperties = {
  ...buttonStyle,
  background: '#4a9eff',
  color: '#fff',
  cursor: 'wait',
}

/**
 * Button to trigger data ingest from the frontend.
 * Fetches latest data from S3 for all products.
 */
function IngestButton() {
  const [ingesting, setIngesting] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const handleIngest = useCallback(async () => {
    setIngesting(true)
    setResult(null)

    try {
      const resp = await fetch('/api/ingest?product=all&days=1', { method: 'POST' })
      if (resp.ok) {
        const data = await resp.json()
        const statuses = Object.entries(data.results)
          .map(([k, v]: [string, any]) => `${k}: ${v.status}`)
          .join(', ')
        setResult(`✓ ${statuses}`)
        // Reload the page after a brief delay to pick up new dates
        setTimeout(() => window.location.reload(), 2000)
      } else {
        setResult('✗ Failed')
      }
    } catch {
      setResult('✗ Error')
    } finally {
      setIngesting(false)
    }
  }, [])

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
      <button
        type="button"
        onClick={handleIngest}
        disabled={ingesting}
        style={ingesting ? activeStyle : buttonStyle}
        title="Fetch latest data from NOAA S3"
      >
        {ingesting ? '⟳ Ingesting...' : '⟳ Refresh Data'}
      </button>
      {result && (
        <span style={{ fontSize: '0.7rem', color: result.startsWith('✓') ? '#4caf50' : '#f44336' }}>
          {result}
        </span>
      )}
    </div>
  )
}

export default IngestButton
