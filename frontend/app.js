// PLACEHOLDER frontend logic (Owner: Shangrui).
const API_BASE = "http://localhost:8000";

const form = document.getElementById("search-form");
const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");

async function loadFacets() {
  try {
    const res = await fetch(`${API_BASE}/facets`);
    if (!res.ok) return;
    const data = await res.json();
    fillSelect("make", data.makes);
    fillSelect("transmission", data.transmissions);
  } catch (_) {
    /* facets are best-effort; ES may not be seeded yet */
  }
}

function fillSelect(id, buckets) {
  const sel = document.getElementById(id);
  for (const b of buckets) {
    const opt = document.createElement("option");
    opt.value = b.key;
    opt.textContent = `${b.key} (${b.count})`;
    sel.appendChild(opt);
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const params = new URLSearchParams();
  for (const [k, v] of new FormData(form)) {
    if (v) params.append(k, v);
  }
  statusEl.textContent = "Searching…";
  resultsEl.innerHTML = "";
  try {
    const res = await fetch(`${API_BASE}/search?${params}`);
    const data = await res.json();
    statusEl.textContent = `${data.total} results`;
    for (const car of data.results) {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <h3>${car.year ?? ""} ${car.make} ${car.model}</h3>
        <p>$${car.msrp?.toLocaleString() ?? "—"} ·
           ${car.engine_hp ?? "—"} hp ·
           ${car.transmission_type ?? ""} ·
           ${car.vehicle_style ?? ""}</p>`;
      resultsEl.appendChild(card);
    }
  } catch (err) {
    statusEl.textContent = "Error — is the backend running?";
  }
});

loadFacets();
