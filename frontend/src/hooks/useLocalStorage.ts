import { useState, useEffect, useCallback } from 'react'

/**
 * A hook that syncs state to localStorage.
 *
 * Reads the stored value on mount (falling back to `defaultValue` if absent
 * or unparseable), and writes back on every state change.
 */
export function useLocalStorage<T>(
  key: string,
  defaultValue: T,
  validate?: (value: unknown) => value is T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key)
      if (stored === null) return defaultValue
      const parsed = JSON.parse(stored)
      if (validate && !validate(parsed)) return defaultValue
      return parsed as T
    } catch {
      return defaultValue
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(state))
    } catch {
      // Silently ignore write failures (e.g. quota exceeded, private browsing)
    }
  }, [key, state])

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      setState(value)
    },
    []
  )

  return [state, setValue]
}
