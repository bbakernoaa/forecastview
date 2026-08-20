/**
 * Product selector for choosing which forecast product to display.
 *
 * Currently only "Air Composition" is available. "Meteorology" is shown
 * as a disabled placeholder for future expansion.
 */

interface ProductSelectorProps {
  /** Currently active product identifier */
  product: string
  /** Callback when the user selects a different product */
  onChange: (product: string) => void
}

interface ProductOption {
  key: string
  label: string
  disabled: boolean
}

const PRODUCT_OPTIONS: ProductOption[] = [
  { key: 'air', label: 'Air Composition', disabled: false },
  { key: 'met', label: 'Meteorology', disabled: true },
]

function ProductSelector({ product, onChange }: ProductSelectorProps) {
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
        {PRODUCT_OPTIONS.map(({ key, label, disabled }) => (
          <option key={key} value={key} disabled={disabled}>
            {label}{disabled ? ' (coming soon)' : ''}
          </option>
        ))}
      </select>
    </fieldset>
  )
}

export default ProductSelector
