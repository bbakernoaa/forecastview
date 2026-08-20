import { createContext, useContext, useCallback, useState, useMemo } from 'react'
import type { ReactNode } from 'react'

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

export type NotificationLevel = 'info' | 'warning' | 'error'

export interface Notification {
  id: string
  message: string
  level: NotificationLevel
  /** Timestamp when the notification was created */
  createdAt: number
}

interface NotificationContextValue {
  notifications: Notification[]
  /** Push a new notification. Auto-dismisses after 5 seconds. */
  notify: (message: string, level?: NotificationLevel) => void
  /** Manually dismiss a notification */
  dismiss: (id: string) => void
}

// --------------------------------------------------------------------------
// Context
// --------------------------------------------------------------------------

const NotificationContext = createContext<NotificationContextValue | null>(null)

let nextId = 0

// --------------------------------------------------------------------------
// Provider
// --------------------------------------------------------------------------

interface NotificationProviderProps {
  children: ReactNode
}

export function NotificationProvider({ children }: NotificationProviderProps) {
  const [notifications, setNotifications] = useState<Notification[]>([])

  const dismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
  }, [])

  const notify = useCallback(
    (message: string, level: NotificationLevel = 'error') => {
      const id = `notif-${++nextId}`
      const notification: Notification = {
        id,
        message,
        level,
        createdAt: Date.now(),
      }

      setNotifications((prev) => [...prev, notification])

      // Auto-dismiss after 5 seconds
      setTimeout(() => {
        dismiss(id)
      }, 5000)
    },
    [dismiss],
  )

  const value = useMemo(
    () => ({ notifications, notify, dismiss }),
    [notifications, notify, dismiss],
  )

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  )
}

// --------------------------------------------------------------------------
// Hook
// --------------------------------------------------------------------------

export function useNotifications(): NotificationContextValue {
  const ctx = useContext(NotificationContext)
  if (!ctx) {
    throw new Error('useNotifications must be used within a NotificationProvider')
  }
  return ctx
}
