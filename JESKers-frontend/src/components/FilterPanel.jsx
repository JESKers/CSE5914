import { FACETS, BOUNDS } from '../data/cars'

const TRANS_LABEL = {
  AUTOMATIC: 'Automatic',
  MANUAL: 'Manual',
  AUTOMATED_MANUAL: 'Automated',
  DIRECT_DRIVE: 'Direct (EV)',
}

function PillGroup({ title, options, selected, labelFor, onToggle }) {
  return (
    <div className="filter__group">
      <h4 className="filter__title">{title}</h4>
      <div className="filter__opts">
        {options.map((opt) => {
          const active = selected.includes(opt)
          return (
            <button
              key={String(opt)}
              type="button"
              className={`pill ${active ? 'pill--on' : ''}`}
              aria-pressed={active}
              onClick={() => onToggle(opt)}
            >
              {labelFor ? labelFor(opt) : opt}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function RangeGroup({ title, unit, bounds, minVal, maxVal, onMin, onMax }) {
  const parse = (v) => (v === '' ? null : Number(v))
  return (
    <div className="filter__group">
      <h4 className="filter__title">{title}</h4>
      <div className="range">
        <div className="range__field">
          {unit && <span className="range__unit">{unit}</span>}
          <input
            type="number"
            className="range__input"
            placeholder={`Min ${bounds.min}`}
            value={minVal ?? ''}
            min={bounds.min}
            max={bounds.max}
            onChange={(e) => onMin(parse(e.target.value))}
            aria-label={`${title} minimum`}
          />
        </div>
        <span className="range__sep">–</span>
        <div className="range__field">
          {unit && <span className="range__unit">{unit}</span>}
          <input
            type="number"
            className="range__input"
            placeholder={`Max ${bounds.max}`}
            value={maxVal ?? ''}
            min={bounds.min}
            max={bounds.max}
            onChange={(e) => onMax(parse(e.target.value))}
            aria-label={`${title} maximum`}
          />
        </div>
      </div>
    </div>
  )
}

export default function FilterPanel({ filters, setFilters, onClear, activeCount }) {
  const toggleArray = (key, val) =>
    setFilters((f) => {
      const cur = f[key] || []
      const next = cur.includes(val) ? cur.filter((x) => x !== val) : [...cur, val]
      return { ...f, [key]: next }
    })
  const setScalar = (key, val) => setFilters((f) => ({ ...f, [key]: val }))

  return (
    <aside className="filters" aria-label="Search filters">
      <div className="filters__head">
        <h3 className="filters__heading">
          Refine
          {activeCount > 0 && <span className="filters__count mono">{activeCount}</span>}
        </h3>
        <button className="filters__clear" type="button" onClick={onClear}>
          Reset
        </button>
      </div>

      {/* model — text search */}
      <div className="filter__group">
        <h4 className="filter__title">Model</h4>
        <input
          type="text"
          className="filter__text"
          placeholder="e.g. Corvette, Civic…"
          value={filters.model || ''}
          onChange={(e) => setScalar('model', e.target.value)}
        />
      </div>

      <RangeGroup
        title="Price (MSRP)"
        unit="$"
        bounds={BOUNDS.price}
        minVal={filters.minPrice}
        maxVal={filters.maxPrice}
        onMin={(v) => setScalar('minPrice', v)}
        onMax={(v) => setScalar('maxPrice', v)}
      />
      <RangeGroup
        title="Horsepower"
        bounds={BOUNDS.hp}
        minVal={filters.minHp}
        maxVal={filters.maxHp}
        onMin={(v) => setScalar('minHp', v)}
        onMax={(v) => setScalar('maxHp', v)}
      />
      <RangeGroup
        title="Year"
        bounds={BOUNDS.year}
        minVal={filters.minYear}
        maxVal={filters.maxYear}
        onMin={(v) => setScalar('minYear', v)}
        onMax={(v) => setScalar('maxYear', v)}
      />

      <PillGroup
        title="Brand"
        options={FACETS.makes}
        selected={filters.makes || []}
        onToggle={(v) => toggleArray('makes', v)}
      />
      <PillGroup
        title="Engine type (fuel)"
        options={FACETS.engineTypes}
        selected={filters.engineTypes || []}
        labelFor={(v) => v.replace(' (required)', '').replace(' (recommended)', '')}
        onToggle={(v) => toggleArray('engineTypes', v)}
      />
      <PillGroup
        title="Cylinders"
        options={FACETS.cylinders}
        selected={filters.cylinders || []}
        labelFor={(v) => (v === 0 ? 'EV / 0' : v)}
        onToggle={(v) => toggleArray('cylinders', v)}
      />
      <PillGroup
        title="Transmission"
        options={FACETS.transmissions}
        selected={filters.transmissions || []}
        labelFor={(v) => TRANS_LABEL[v] || v}
        onToggle={(v) => toggleArray('transmissions', v)}
      />
      <PillGroup
        title="Drivetrain"
        options={FACETS.drivenWheels}
        selected={filters.drivenWheels || []}
        labelFor={(v) => v.replace(' wheel drive', '').toUpperCase()}
        onToggle={(v) => toggleArray('drivenWheels', v)}
      />
    </aside>
  )
}
