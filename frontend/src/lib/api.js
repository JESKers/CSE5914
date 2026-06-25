// API client for the FastAPI backend. Calls go through the `/api` proxy
// configured in vite.config.js (rewrites /api -> http://localhost:8000).

const BASE = "/api";

// Build a query string from a filter object, dropping empty/blank values.
export function toQueryString(params) {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    qs.set(key, value);
  }
  return qs.toString();
}

// GET /search — structured filters + keyword. `params` matches the API contract
// (make, model, year_min/max, price_min/max, hp_min/max, engine_fuel_type,
// transmission_type, q, sort, order, page, size). Returns the response envelope.
export async function searchCars(params, { signal } = {}) {
  const res = await fetch(`${BASE}/search?${toQueryString(params)}`, { signal });
  if (!res.ok) {
    let detail = `Search failed (${res.status})`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

// GET /facets — make / transmission / fuel-type buckets + available years.
export async function getFacets({ signal } = {}) {
  const res = await fetch(`${BASE}/facets`, { signal });
  if (!res.ok) throw new Error(`Failed to load facets (${res.status})`);
  return res.json();
}

// GET /models?make= — distinct models for a make (dependent Model dropdown).
export async function getModels(make, { signal } = {}) {
  const res = await fetch(`${BASE}/models?${toQueryString({ make })}`, { signal });
  if (!res.ok) throw new Error(`Failed to load models (${res.status})`);
  return res.json();
}
