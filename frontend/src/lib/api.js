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

// --------------------------------------------------------------------------- //
// Buy / Rent store (additive — see docs/STORE_VPIC.md)
// --------------------------------------------------------------------------- //

// GET /store/listings — same filters as /search plus `mode` (buy|rent). In rent
// mode, price_min/max are daily-rent. Returns { results, total, mode, page, size }.
export async function getListings(params, { signal } = {}) {
  const res = await fetch(`${BASE}/store/listings?${toQueryString(params)}`, { signal });
  if (!res.ok) {
    let detail = `Listings failed (${res.status})`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

// POST /store/orders — purchase or rent. body: { vehicle_id, mode, rent_days?, customer? }
export async function createOrder(body) {
  const res = await fetch(`${BASE}/store/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Order failed (${res.status})`);
  return data;
}

// GET /store/orders — order history.
export async function getOrders({ signal } = {}) {
  const res = await fetch(`${BASE}/store/orders`, { signal });
  if (!res.ok) throw new Error(`Failed to load orders (${res.status})`);
  return res.json();
}

// GET /vpic/decode/{vin} — live VIN decode via the NHTSA vPIC API.
export async function decodeVin(vin, { signal } = {}) {
  const res = await fetch(`${BASE}/vpic/decode/${encodeURIComponent(vin)}`, { signal });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `VIN decode failed (${res.status})`);
  return data;
}
