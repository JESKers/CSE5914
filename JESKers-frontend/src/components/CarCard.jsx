import { motion } from 'framer-motion'

const TRANS_SHORT = {
  AUTOMATIC: 'AUTO',
  MANUAL: 'MANUAL',
  AUTOMATED_MANUAL: 'AUTO-M',
  DIRECT_DRIVE: 'DIRECT',
  UNKNOWN: '—',
}

// A deterministic gradient per car so the placeholder "photo" feels designed,
// not broken. Swap this header block for a real <img> once listings have images.
const GRADIENTS = {
  electric: 'linear-gradient(135deg, #0f3d2e 0%, #1d6f4f 50%, #c9f24a 140%)',
  performance: 'linear-gradient(135deg, #2a1208 0%, #6e2a12 55%, #ff8a5c 140%)',
  luxury: 'linear-gradient(135deg, #1a1830 0%, #36325e 55%, #b6a8ff 150%)',
  default: 'linear-gradient(135deg, #16191d 0%, #2a2f36 60%, #4a525c 150%)',
}

function pickGradient(car) {
  if (car.engine.fuel_type === 'electric') return GRADIENTS.electric
  if (car.market_category.includes('Performance')) return GRADIENTS.performance
  if (car.market_category.includes('Luxury')) return GRADIENTS.luxury
  return GRADIENTS.default
}

const usd = (n) =>
  n == null ? '—' : '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 })

const cardVariants = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
}

export default function CarCard({ car }) {
  const { engine, augmented_nhtsa: n } = car
  const bodyShort = n.body_class
    .replace('Sport Utility Vehicle (SUV)', 'SUV')
    .replace(' (SUV)', '')

  return (
    <motion.article className="card" variants={cardVariants}>
      <div className="card__visual" style={{ background: pickGradient(car) }}>
        <span className="card__year mono">'{String(car.year).slice(2)}</span>
        <span className="card__body mono">{bodyShort}</span>
        <span className="card__silhouette" aria-hidden="true">
          {engine.fuel_type === 'electric' ? '⚡' : '◈'}
        </span>
      </div>

      <div className="card__body-inner">
        <div className="card__headrow">
          <div>
            <p className="card__make mono">{car.make}</p>
            <h3 className="card__model">{car.model}</h3>
          </div>
          <div className="card__price">
            <span className="card__price-val">{usd(car.msrp)}</span>
            <span className="card__price-label mono">MSRP</span>
          </div>
        </div>

        <dl className="card__specs">
          <div className="spec">
            <dt className="mono">PWR</dt>
            <dd>{engine.hp != null ? `${engine.hp} hp` : '—'}</dd>
          </div>
          <div className="spec">
            <dt className="mono">CYL</dt>
            <dd>{engine.cylinders ? engine.cylinders : 'EV'}</dd>
          </div>
          <div className="spec">
            <dt className="mono">TRANS</dt>
            <dd>{TRANS_SHORT[car.transmission_type]}</dd>
          </div>
          <div className="spec">
            <dt className="mono">DRIVE</dt>
            <dd>{car.driven_wheels.replace(' wheel drive', '').toUpperCase()}</dd>
          </div>
          <div className="spec">
            <dt className="mono">SEATS</dt>
            <dd>{n.seat_count ?? '—'}</dd>
          </div>
          <div className="spec">
            <dt className="mono">DOORS</dt>
            <dd>{car.number_of_doors ?? '—'}</dd>
          </div>
        </dl>

        <div className="card__tags">
          {car.market_category.map((t) => (
            <span key={t} className="tag">
              {t}
            </span>
          ))}
        </div>

        {/* TODO (Final / web app): link to real nearby/used listings. */}
        <button className="card__cta" type="button" title="Coming in the final build">
          View listings
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </motion.article>
  )
}
