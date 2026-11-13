import { useHealth } from '../hooks/useHealth'
import { STATIC_MODE } from '../api/staticMode'

/**
 * Small indicator showing backend connection status.
 * Displays in the toolbar area.
 */
function ConnectionStatus() {
  const { status, version, exportedAt } = useHealth()
  const exportDate = exportedAt ? new Date(exportedAt) : null

  const formattedExportTime = exportDate && Number.isFinite(exportDate.getTime())
    ? exportDate.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC'
    : null

  const label = STATIC_MODE
    ? formattedExportTime ? `Static · ${formattedExportTime}` : 'Static bundle'
    : status === 'loading'
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
        STATIC_MODE
          ? formattedExportTime
            ? `Static bundle exported ${formattedExportTime}`
            : 'Static bundle; export time is unavailable'
          : status === 'connected'
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
