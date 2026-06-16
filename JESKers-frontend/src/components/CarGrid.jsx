import { motion } from 'framer-motion'
import CarCard from './CarCard'

const gridVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
}

function SortControl({ sort, setSort }) {
  const opts = [
    { id: 'relevance', label: 'Relevance' },
    { id: 'price-asc', label: 'Price ↑' },
    { id: 'price-desc', label: 'Price ↓' },
    { id: 'hp-desc', label: 'Power ↓' },
  ]
  return (
    <div className="sort">
      <span className="sort__label mono">SORT</span>
      {opts.map((o) => (
        <button
          key={o.id}
          className={`sort__opt ${sort === o.id ? 'sort__opt--on' : ''}`}
          onClick={() => setSort(o.id)}
          type="button"
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export default function CarGrid({ cars, loading, total, page, size, sort, setSort }) {
  const from = total === 0 ? 0 : (page - 1) * size + 1
  const to = Math.min(page * size, total)

  return (
    <div className="results" id="results">
      <div className="results__bar">
        <p className="results__count">
          <span className="mono results__num">{String(total).padStart(2, '0')}</span>{' '}
          {total === 1 ? 'car found' : 'cars found'}
          {total > 0 && (
            <span className="results__range mono">
              · showing {from}–{to}
            </span>
          )}
        </p>
        <SortControl sort={sort} setSort={setSort} />
      </div>

      {loading ? (
        <div className="grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div className="card card--skeleton" key={i}>
              <div className="card__visual skel" />
              <div className="card__body-inner">
                <div className="skel skel--line" style={{ width: '40%' }} />
                <div className="skel skel--line" style={{ width: '70%', height: 22 }} />
                <div className="skel skel--block" />
              </div>
            </div>
          ))}
        </div>
      ) : cars.length === 0 ? (
        <div className="empty">
          <span className="empty__mark" aria-hidden="true">⌀</span>
          <h3>No cars match your search</h3>
          <p>Try removing a filter or broadening your keywords.</p>
        </div>
      ) : (
        <motion.div
          className="grid"
          variants={gridVariants}
          initial="hidden"
          animate="show"
          key={cars.map((c) => c.id).join('-')}
        >
          {cars.map((car) => (
            <CarCard car={car} key={car.id} />
          ))}
        </motion.div>
      )}
    </div>
  )
}
