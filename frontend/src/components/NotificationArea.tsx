import { useNotifications } from '../context/NotificationContext'
import type { NotificationLevel } from '../context/NotificationContext'

/**
 * Fixed-position notification area that displays non-blocking
 * error/warning/info messages. Auto-dismisses after 5s or
 * allows manual dismiss via close button.
 *
 * Positioned in the top-right corner to avoid interfering with
 * map controls or toolbars.
 */
function NotificationArea() {
  const { notifications, dismiss } = useNotifications()

  if (notifications.length === 0) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: '60px',
        right: '16px',
        zIndex: 10000,
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        maxWidth: '380px',
        pointerEvents: 'none',
      }}
    >
      {notifications.map((notification) => (
        <div
          key={notification.id}
          style={{
            ...getNotificationStyle(notification.level),
            pointerEvents: 'auto',
          }}
          role="alert"
        >
          <span style={{ flex: 1, fontSize: '0.82rem', lineHeight: 1.4 }}>
            {getIcon(notification.level)} {notification.message}
          </span>
          <button
            type="button"
            onClick={() => dismiss(notification.id)}
            style={{
              background: 'none',
              border: 'none',
              color: 'inherit',
              cursor: 'pointer',
              fontSize: '1rem',
              padding: '0 4px',
              opacity: 0.7,
            }}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}

function getNotificationStyle(level: NotificationLevel): React.CSSProperties {
  const base: React.CSSProperties = {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    padding: '10px 14px',
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
    backdropFilter: 'blur(8px)',
  }

  switch (level) {
    case 'error':
      return {
        ...base,
        background: 'rgba(153, 27, 27, 0.92)',
        color: '#fecaca',
        border: '1px solid rgba(239, 68, 68, 0.4)',
      }
    case 'warning':
      return {
        ...base,
        background: 'rgba(120, 53, 15, 0.92)',
        color: '#fde68a',
        border: '1px solid rgba(245, 158, 11, 0.4)',
      }
    case 'info':
      return {
        ...base,
        background: 'rgba(30, 58, 95, 0.92)',
        color: '#bfdbfe',
        border: '1px solid rgba(59, 130, 246, 0.4)',
      }
  }
}

function getIcon(level: NotificationLevel): string {
  switch (level) {
    case 'error':
      return '⚠'
    case 'warning':
      return '⚡'
    case 'info':
      return 'ℹ'
  }
}

export default NotificationArea
