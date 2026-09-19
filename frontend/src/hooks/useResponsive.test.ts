// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useResponsive } from './useResponsive'

describe('useResponsive', () => {
  const originalInnerWidth = window.innerWidth

  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1200,
    })
  })

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: originalInnerWidth,
    })
  })

  it('detects desktop size by default when innerWidth >= 1024', () => {
    const { result } = renderHook(() => useResponsive())
    expect(result.current.isDesktop).toBe(true)
    expect(result.current.isMobile).toBe(false)
    expect(result.current.isTablet).toBe(false)
  })

  it('detects mobile size when innerWidth < 768', () => {
    Object.defineProperty(window, 'innerWidth', { value: 400 })
    const { result } = renderHook(() => useResponsive())

    expect(result.current.isMobile).toBe(true)
    expect(result.current.isDesktop).toBe(false)
    expect(result.current.isTablet).toBe(false)
  })

  it('detects tablet size when 768 <= innerWidth < 1024', () => {
    Object.defineProperty(window, 'innerWidth', { value: 800 })
    const { result } = renderHook(() => useResponsive())

    expect(result.current.isTablet).toBe(true)
    expect(result.current.isMobile).toBe(false)
    expect(result.current.isDesktop).toBe(false)
  })

  it('updates responsively on window resize event', () => {
    const { result } = renderHook(() => useResponsive())
    expect(result.current.isDesktop).toBe(true)

    act(() => {
      Object.defineProperty(window, 'innerWidth', { value: 500 })
      window.dispatchEvent(new Event('resize'))
    })

    expect(result.current.isMobile).toBe(true)
    expect(result.current.isDesktop).toBe(false)
  })
})
