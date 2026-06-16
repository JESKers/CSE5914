// Renders a removable chip for every applied search criterion, so users always
// see what's narrowing their results — a hallmark of a real search system.

const TRANS_LABEL = {
  AUTOMATIC: 'Automatic',
  MANUAL: 'Manual',
  AUTOMATED_MANUAL: 'Automated',
  DIRECT_DRIVE: 'Direct (EV)',
}
const fuelLabel = (v) => v.replace(' (required)', '').replace(' (recommended)', '')
const usd = (n) => '$' + Number(n).toLocaleString('en-US')

function buildChips(query, filters) {
  const chips = []
  if (query?.trim()) chips.push({ key: '__query', label: `“${query.trim()}”` })
  if (filters.model?.trim())
    chips.push({ key: 'model', label: `Model: ${filters.model.trim()}`, reset: '' })

  ;(filters.makes || []).forEach((v) =>
    chips.push({ key: 'makes', val: v, label: v }),
  )
  ;(filters.engineTypes || []).forEach((v) =>
    chips.push({ key: 'engineTypes', val: v, label: fuelLabel(v) }),
  )
  ;(filters.cylinders || []).forEach((v) =>
    chips.push({ key: 'cylinders', val: v, label: v === 0 ? 'EV / 0 cyl' : `${v} cyl` }),
  )
  ;(filters.transmissions || []).forEach((v) =>
    chips.push({ key: 'transmissions', val: v, label: TRANS_LABEL[v] || v }),
  )
  ;(filters.drivenWheels || []).forEach((v) =>
    chips.push({ key: 'drivenWheels', val: v, label: v.replace(' wheel drive', '').toUpperCase() }),
  )

  const rangeChip = (lo, hi, key, fmt, name) => {
    if (filters[lo] == null && filters[hi] == null) return
    const a = filters[lo] != null ? fmt(filters[lo]) : '…'
    const b = filters[hi] != null ? fmt(filters[hi]) : '…'
    chips.push({ key, range: [lo, hi], label: `${name} ${a}–${b}` })
  }
  rangeChip('minPrice', 'maxPrice', 'price', usd, 'Price')
  rangeChip('minHp', 'maxHp', 'hp', (n) => `${n}hp`, 'Power')
  rangeChip('minYear', 'maxYear', 'year', (n) => n, 'Year')

  return chips
}

export default function ActiveFilters({ query, filters, onRemove, onClearQuery }) {
  const chips = buildChips(query, filters)
  if (chips.length === 0) return null

  function remove(chip) {
    if (chip.key === '__query') return onClearQuery()
    if (chip.range) return onRemove((f) => ({ ...f, [chip.range[0]]: null, [chip.range[1]]: null }))
    if (chip.reset !== undefined) return onRemove((f) => ({ ...f, [chip.key]: chip.reset }))
    // array facet
    return onRemove((f) => ({
      ...f,
      [chip.key]: (f[chip.key] || []).filter((x) => x !== chip.val),
    }))
  }

  return (
    <div className="active">
      {chips.map((chip, i) => (
        <button
          key={chip.key + (chip.val ?? '') + i}
          className="active__chip"
          type="button"
          onClick={() => remove(chip)}
        >
          {chip.label}
          <span className="active__x" aria-hidden="true">×</span>
        </button>
      ))}
    </div>
  )
}
