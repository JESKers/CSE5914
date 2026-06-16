import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

const EXAMPLES = ['Corvette', 'Toyota', 'GTI', 'Mustang', 'Telluride']

const fadeUp = {
  hidden: { opacity: 0, y: 18 },
  show: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, delay: 0.1 + i * 0.08, ease: [0.16, 1, 0.3, 1] },
  }),
}

export default function SearchHero({ query, onSearch, loading }) {
  const [value, setValue] = useState(query || '')

  // Keep the input in sync when the query is cleared elsewhere (chips / reset).
  useEffect(() => {
    setValue(query || '')
  }, [query])

  return (
    <section className="hero" id="search">
      <div className="shell">
        <motion.p className="eyebrow" variants={fadeUp} initial="hidden" animate="show">
          Car Search System · Timebox 2
        </motion.p>

        <motion.h1
          className="hero__title"
          variants={fadeUp}
          initial="hidden"
          animate="show"
          custom={1}
        >
          Find the car.
          <br />
          <span className="hero__title-accent">Search every spec.</span>
        </motion.h1>

        <motion.p
          className="hero__sub"
          variants={fadeUp}
          initial="hidden"
          animate="show"
          custom={2}
        >
          Search by brand, model, year, price, horsepower, engine type, transmission
          and keywords — powered by Elasticsearch over the full vehicle dataset.
        </motion.p>

        <motion.form
          className="searchbar"
          variants={fadeUp}
          initial="hidden"
          animate="show"
          custom={3}
          onSubmit={(e) => {
            e.preventDefault()
            onSearch(value.trim())
          }}
        >
          <span className="searchbar__icon" aria-hidden="true">
            ⌕
          </span>
          <input
            className="searchbar__input"
            type="text"
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              onSearch(e.target.value.trim())
            }}
            placeholder="Search make, model or keyword — e.g. Corvette, Civic, GTI…"
            aria-label="Search cars by keyword"
          />
          <button className="searchbar__btn" type="submit" disabled={loading}>
            {loading ? 'Searching…' : 'Search'}
            <span className="searchbar__btn-arrow" aria-hidden="true">
              →
            </span>
          </button>
        </motion.form>

        <motion.div
          className="hero__chips"
          variants={fadeUp}
          initial="hidden"
          animate="show"
          custom={4}
        >
          <span className="hero__chips-label mono">TRY</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              className="chip"
              type="button"
              onClick={() => onSearch(ex)}
            >
              {ex}
            </button>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
