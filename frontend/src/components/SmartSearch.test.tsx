// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import SmartSearch from './SmartSearch'

vi.mock('../context/ViewerContext', () => ({
  useViewer: () => ({
    state: { product: 'air', date: '20260821', run: '00' },
    dispatch: vi.fn(),
    map: { flyTo: vi.fn() },
  }),
}))

vi.mock('../hooks/useMetadata', () => ({
  useVariables: () => ({
    data: [
      {
        name: 'totAOD550',
        shortName: 'Total AOD',
        fullName: 'Total Aerosol Optical Depth at 550nm',
        units: 'dimensionless',
        category: 'Optical Depth',
        rendering: null,
      },
      {
        name: 'pm25',
        shortName: 'PM2.5',
        fullName: 'Particulate Matter < 2.5um',
        units: 'ug m-3',
        category: 'Particulate Matter',
        rendering: null,
      },
    ],
  }),
}))

describe('SmartSearch Component', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders input field with placeholder', () => {
    render(<SmartSearch placeholder="Search test..." />)
    expect(screen.getByPlaceholderText('Search test...')).toBeDefined()
  })

  it('filters and displays variables when searching', () => {
    render(<SmartSearch />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'pm25' } })

    expect(screen.getByText('Particulate Matter < 2.5um')).toBeDefined()
  })

  it('filters and displays region location presets when searching', () => {
    render(<SmartSearch />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'Europe' } })

    expect(screen.getByText('Europe')).toBeDefined()
  })

  it('parses valid coordinate inputs', () => {
    render(<SmartSearch />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '39.9, -83.0' } })

    expect(screen.getByText(/Coordinates: 39\.9000°N, -83\.0000°E/)).toBeDefined()
  })
})
