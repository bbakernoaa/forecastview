import { useHealth } from '../hooks/useHealth'

/**
 * Small indicator showing backend connection status.
 * Displays in the toolbar area.
 */
function ConnectionStatus() {
  const { status, version } = useHealth()

  const label =
    status === 'loading'
      ? '⏳ Connecting…'
      : status === 'connected'
        ? `🟢 v${version}`
        : '🔴 Disconnected'

  return (
    <span
      style={{
        fontSize: '0.75rem',
        color: status === 'error' ? '#f87171' : '#a3a3a3',
        whiteSpace: 'nowrap',
      }}
      title={
        status === 'connected'
          ? `Backend connected — version ${version}`
          : status === 'error'
            ? 'Cannot reach backend'
            : 'Checking backend connection…'
      }
    >
      {label}
    </span>
  )
}

export default ConnectionStatus
