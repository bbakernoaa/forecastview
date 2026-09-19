import { useState, useEffect } from 'react'

export interface ResponsiveInfo {
  isMobile: boolean
  isTablet: boolean
  isDesktop: boolean
  width: number
}

export function useResponsive(mobileBreakpoint = 768, tabletBreakpoint = 1024): ResponsiveInfo {
  const [width, setWidth] = useState<number>(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth
    }
    return 1200
  })

  useEffect(() => {
    function handleResize() {
      setWidth(window.innerWidth)
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const isMobile = width < mobileBreakpoint
  const isTablet = width >= mobileBreakpoint && width < tabletBreakpoint
  const isDesktop = width >= tabletBreakpoint

  return {
    isMobile,
    isTablet,
    isDesktop,
    width,
  }
}
