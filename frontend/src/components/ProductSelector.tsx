/**
 * Product selector for choosing which forecast product to display.
 *
 * Product options come from the exported catalog so a new static dataset
 * appears without a frontend code change.
 */

import { useEffect, useState } from 'react'
import { apiGetStatic } from '../api/client'
import type { CatalogEntry, CatalogResponse } from '../api/types'

interface ProductSelectorProps {
  /** Currently active product identifier */
  product: string
  /** Callback when the user selects a different product */
  onChange: (product: string) => void
}

function ProductSelector({ product, onChange }: ProductSelectorProps) {
  const [products, setProducts] = useState<CatalogEntry[]>([])

  useEffect(() => {
    const controller = new AbortController()
    apiGetStatic<CatalogResponse>('catalog', undefined, controller.signal)
      .then((catalog) => setProducts(catalog?.products ?? []))
      .catch((error) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setProducts([])
        }
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (products.length > 0 && !products.some((item) => item.product === product)) {
      onChange(products[0].product)
    }
  }, [products, product, onChange])

  return (
    <fieldset
      className="product-selector"
      style={{
        border: 'none',
        padding: 0,
        display: 'flex',
        gap: '4px',
        alignItems: 'center',
      }}
    >
      <legend style={{ fontSize: '0.75rem', marginBottom: '2px' }}>Product</legend>
      <select
        aria-label="Select forecast product"
        value={product}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: '4px 8px',
          fontSize: '0.8rem',
          border: '1px solid #555',
          borderRadius: '3px',
          background: '#2a2a2a',
          color: '#ccc',
          cursor: 'pointer',
        }}
      >
        {products.map(({ product: key, description }) => (
          <option key={key} value={key}>
            {description || key}
          </option>
        ))}
      </select>
    </fieldset>
  )
}

export default ProductSelector
