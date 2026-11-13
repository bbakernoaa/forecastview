// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import ProductSelector from './ProductSelector'

vi.mock('../api/client', () => ({
  apiGetStatic: vi.fn().mockResolvedValue({
    products: [{ product: 'GCAVSv1', description: 'GCAVSv1 Forecast' }],
  }),
}))

describe('ProductSelector', () => {
  afterEach(cleanup)

  it('uses the published catalog and selects its first product when the old default is absent', async () => {
    const onChange = vi.fn()
    render(<ProductSelector product="air" onChange={onChange} />)

    expect(await screen.findByRole('option', { name: 'GCAVSv1 Forecast' })).toBeTruthy()
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('GCAVSv1'))
  })
})
