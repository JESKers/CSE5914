import { useEffect, useMemo, useState } from 'react'
import Navbar from './components/Navbar'
import SearchHero from './components/SearchHero'
import FilterPanel from './components/FilterPanel'
import ActiveFilters from './components/ActiveFilters'
import CarGrid from './components/CarGrid'
import Pagination from './components/Pagination'
import Roadmap from './components/Roadmap'
import { searchCars } from './api/client'
import './App.css'

const PAGE_SIZE = 9

const EMPTY_FILTERS = {
  model: '',
  makes: [],
  engineTypes: [],
  cylinders: [],
  transmissions: [],
  drivenWheels: [],
  minPrice: null,
  maxPrice: null,
  minHp: null,
  maxHp: null,
  minYear: null,
  maxYear: null,
}

function countActive(filters) {
  return Object.values(filters).reduce((acc, v) => {
    if (Array.isArray(v)) return acc + v.length
    if (typeof v === 'string') return acc + (v.trim() ? 1 : 0)
    return acc + (v != null ? 1 : 0)
  }, 0)
}

export default function App() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [sort, setSort] = useState('relevance')
  const [page, setPage] = useState(1)

  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const activeCount = useMemo(() => countActive(filters), [filters])

  // Any change to the search itself (not the page) returns to page 1.
  useEffect(() => {
    setPage(1)
  }, [query, filters, sort])

  // Debounced search. Re-runs on query / filters / sort / page changes.
  useEffect(() => {
    let alive = true
    setLoading(true)
    const t = setTimeout(async () => {
      try {
        const res = await searchCars({ query, filters, sort, page, size: PAGE_SIZE })
        if (!alive) return
        setResults(res.results)
        setTotal(res.total)
      } catch (err) {
        console.error('search failed', err)
        if (alive) {
          setResults([])
          setTotal(0)
        }
      } finally {
        if (alive) setLoading(false)
      }
    }, 250)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [query, filters, sort, page])

  const pageCount = Math.ceil(total / PAGE_SIZE)

  function goToPage(p) {
    setPage(p)
    document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div id="top">
      <Navbar />
      <main>
        <SearchHero query={query} onSearch={setQuery} loading={loading} />

        <section className="layout shell">
          <FilterPanel
            filters={filters}
            setFilters={setFilters}
            activeCount={activeCount}
            onClear={() => {
              setFilters(EMPTY_FILTERS)
              setQuery('')
            }}
          />
          <div>
            <ActiveFilters
              query={query}
              filters={filters}
              onRemove={setFilters}
              onClearQuery={() => setQuery('')}
            />
            <CarGrid
              cars={results}
              loading={loading}
              total={total}
              page={page}
              size={PAGE_SIZE}
              sort={sort}
              setSort={setSort}
            />
            <Pagination page={page} pageCount={pageCount} onPage={goToPage} />
          </div>
        </section>

        <Roadmap />
      </main>

      <footer className="footer">
        <div className="shell footer__inner">
          <span className="mono">JESKers · CSE 5914 Capstone</span>
          <span className="footer__names">
            Jerry Meng · Eric Li · Shangrui Gao · Kangjie Jiang
          </span>
          <span className="mono footer__tag">Timebox 2 — Car Search System</span>
        </div>
      </footer>
    </div>
  )
}
