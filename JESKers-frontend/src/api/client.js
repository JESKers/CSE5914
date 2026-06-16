// ---------------------------------------------------------------------------
// API client — the single integration seam between the frontend and backend.
//
// >>> HOW TO GO LIVE (no code edits needed) <<<
// Configure via .env (see .env.example):
//   • Leave VITE_API_BASE empty  -> runs on local mock data (default).
//   • Set VITE_API_BASE=<url>     -> calls the live Elasticsearch-backed API.
//   • VITE_USE_MOCK=true|false    -> force either mode regardless of API base.
//
// `buildEsQuery()` produces a ready-to-run Elasticsearch query body, so the
// backend can forward it straight to ES `_search`. Hits must match the
// CarRecord schema (see ../types.js) — then NOTHING in the components changes.
//
// Search fields covered (Timebox 2 spec):
//   brand, model, year, price, horsepower, engine type, transmission, keywords
// ---------------------------------------------------------------------------

import { mockCars } from '../data/cars'

const API_BASE = import.meta.env.VITE_API_BASE || ''
const USE_MOCK =
  import.meta.env.VITE_USE_MOCK != null
    ? import.meta.env.VITE_USE_MOCK === 'true'
    : !API_BASE // no backend configured -> mock
const INDEX = 'cars'

const SORT_MAP = {
  relevance: ['_score'],
  'price-asc': [{ msrp: 'asc' }],
  'price-desc': [{ msrp: 'desc' }],
  'hp-desc': [{ 'engine.hp': 'desc' }],
}

/**
 * Translate a SearchRequest into an Elasticsearch query body.
 * This is the contract Kangjie's index must satisfy.
 * @param {import('../types').SearchRequest} req
 */
export function buildEsQuery({ query = '', filters = {}, sort = 'relevance', page = 1, size = 9 }) {
  const must = []
  const filter = []

  // keywords -> full-text across the descriptive fields
  if (query.trim()) {
    must.push({
      multi_match: {
        query: query.trim(),
        fields: ['make^2', 'model^3', 'market_category', 'augmented_nhtsa.trim_level'],
        fuzziness: 'AUTO',
      },
    })
  }
  // model -> dedicated text match
  if (filters.model?.trim()) {
    filter.push({ match_phrase_prefix: { model: filters.model.trim() } })
  }
  // brand / transmission / engine type / cylinders -> term filters
  if (filters.makes?.length) filter.push({ terms: { make: filters.makes } })
  if (filters.transmissions?.length)
    filter.push({ terms: { transmission_type: filters.transmissions } })
  if (filters.drivenWheels?.length)
    filter.push({ terms: { driven_wheels: filters.drivenWheels } })
  if (filters.engineTypes?.length)
    filter.push({ terms: { 'engine.fuel_type': filters.engineTypes } })
  if (filters.cylinders?.length)
    filter.push({ terms: { 'engine.cylinders': filters.cylinders } })

  // price / horsepower / year -> range filters
  const range = (field, gte, lte) => {
    const r = {}
    if (gte != null) r.gte = gte
    if (lte != null) r.lte = lte
    if (Object.keys(r).length) filter.push({ range: { [field]: r } })
  }
  range('msrp', filters.minPrice, filters.maxPrice)
  range('engine.hp', filters.minHp, filters.maxHp)
  range('year', filters.minYear, filters.maxYear)

  return {
    index: INDEX,
    from: (page - 1) * size,
    size,
    sort: SORT_MAP[sort] || SORT_MAP.relevance,
    query: { bool: { must: must.length ? must : [{ match_all: {} }], filter } },
  }
}

// ---------------------------------------------------------------------------
// Mock backend: a faithful, framework-free re-implementation of the query above
// so the demo behaves like the real thing until ES is connected.
// ---------------------------------------------------------------------------

const STOPWORDS = new Set([
  'car', 'cars', 'with', 'the', 'a', 'an', 'for', 'and', 'good', 'nice', 'want',
])

function matchesMock(car, { query, filters }) {
  const f = filters
  if (f.makes?.length && !f.makes.includes(car.make)) return false
  if (f.model?.trim() && !car.model.toLowerCase().includes(f.model.trim().toLowerCase()))
    return false
  if (f.transmissions?.length && !f.transmissions.includes(car.transmission_type))
    return false
  if (f.drivenWheels?.length && !f.drivenWheels.includes(car.driven_wheels)) return false
  if (f.engineTypes?.length && !f.engineTypes.includes(car.engine.fuel_type)) return false
  if (f.cylinders?.length && !f.cylinders.includes(car.engine.cylinders)) return false
  if (f.minPrice != null && car.msrp < f.minPrice) return false
  if (f.maxPrice != null && car.msrp > f.maxPrice) return false
  if (f.minHp != null && (car.engine.hp ?? 0) < f.minHp) return false
  if (f.maxHp != null && (car.engine.hp ?? 0) > f.maxHp) return false
  if (f.minYear != null && car.year < f.minYear) return false
  if (f.maxYear != null && car.year > f.maxYear) return false

  // keyword full-text (mirrors the multi_match above)
  const q = (query || '').trim().toLowerCase()
  if (q) {
    const haystack = [
      car.make,
      car.model,
      car.augmented_nhtsa.trim_level,
      ...(car.market_category || []),
    ]
      .join(' ')
      .toLowerCase()
    const hit = q
      .split(/\s+/)
      .some((t) => t.length > 2 && !STOPWORDS.has(t) && haystack.includes(t))
    if (!hit) return false
  }
  return true
}

function sortMock(cars, sort) {
  const arr = [...cars]
  switch (sort) {
    case 'price-asc':
      return arr.sort((a, b) => a.msrp - b.msrp)
    case 'price-desc':
      return arr.sort((a, b) => b.msrp - a.msrp)
    case 'hp-desc':
      return arr.sort((a, b) => (b.engine.hp ?? 0) - (a.engine.hp ?? 0))
    default:
      return arr
  }
}

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

/**
 * Run a search. Returns one page of results plus the total hit count.
 * @param {import('../types').SearchRequest} req
 * @returns {Promise<import('../types').SearchResponse>}
 */
export async function searchCars({
  query = '',
  filters = {},
  sort = 'relevance',
  page = 1,
  size = 9,
} = {}) {
  if (USE_MOCK) {
    await delay(260)
    const all = sortMock(
      mockCars.filter((c) => matchesMock(c, { query, filters })),
      sort,
    )
    const from = (page - 1) * size
    return { results: all.slice(from, from + size), total: all.length, page, size }
  }

  // --- LIVE PATH (Eric) ---
  const body = buildEsQuery({ query, filters, sort, page, size })
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}
