// JESKers storefront — talks to the FastAPI backend (/api/*).
const state = { mode: "buy", page: 1, pageSize: 24, total: 0, filters: null };

const $ = (id) => document.getElementById(id);
const money = (n) => "$" + Number(n).toLocaleString();
const emojiFor = (style) => {
  const s = (style || "").toLowerCase();
  if (s.includes("suv")) return "🚙";
  if (s.includes("pickup")) return "🛻";
  if (s.includes("convertible") || s.includes("roadster")) return "🏎️";
  if (s.includes("coupe")) return "🚗";
  if (s.includes("van") || s.includes("passenger")) return "🚐";
  if (s.includes("wagon")) return "🚙";
  return "🚗";
};

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 3500);
}

// --------------------------------------------------------------------------- //
// Filters setup
// --------------------------------------------------------------------------- //
async function loadFilters() {
  const f = await getJSON("/api/filters");
  state.filters = f;
  fillSelect("make", f.makes, "All brands");
  fillSelect("body_style", f.body_styles, "Any");
  fillSelect("fuel_type", f.fuel_types, "Any");
  fillSelect("drive", f.drives, "Any");
  updatePriceSlider();
}

function fillSelect(id, values, allLabel) {
  const el = $(id);
  el.innerHTML = `<option value="">${allLabel}</option>` +
    values.map((v) => `<option value="${v}">${v}</option>`).join("");
}

function updatePriceSlider() {
  const range = state.mode === "rent" ? state.filters.rent_daily : state.filters.buy_price;
  const slider = $("max_price");
  slider.min = range.min;
  slider.max = range.max;
  slider.step = state.mode === "rent" ? 5 : 1000;
  slider.value = range.max;
  $("priceLabel").textContent = state.mode === "rent" ? "Max daily rent" : "Max price";
  showPriceVal();
}
function showPriceVal() {
  const v = $("max_price").value;
  $("priceVal").textContent = state.mode === "rent" ? money(v) + "/day" : money(v);
}

// --------------------------------------------------------------------------- //
// Catalog
// --------------------------------------------------------------------------- //
function buildQuery() {
  const p = new URLSearchParams({ mode: state.mode, page: state.page, page_size: state.pageSize });
  const fields = ["make", "body_style", "fuel_type", "drive", "q", "sort", "year_min", "min_seats"];
  for (const f of fields) {
    const val = $(f).value;
    if (val) p.set(f, val);
  }
  const range = state.mode === "rent" ? state.filters.rent_daily : state.filters.buy_price;
  if (Number($("max_price").value) < range.max) p.set("max_price", $("max_price").value);
  return p.toString();
}

async function loadVehicles() {
  $("resultCount").textContent = "Loading…";
  const data = await getJSON("/api/vehicles?" + buildQuery());
  state.total = data.total;
  renderGrid(data.results);
  $("resultCount").textContent = `${data.total.toLocaleString()} vehicles ${state.mode === "rent" ? "for rent" : "for sale"}`;
  const pages = Math.max(1, Math.ceil(data.total / state.pageSize));
  $("pageInfo").textContent = `Page ${state.page} of ${pages}`;
  $("prevPage").disabled = state.page <= 1;
  $("nextPage").disabled = state.page >= pages;
}

function priceTag(v) {
  return state.mode === "rent"
    ? `${money(v.rent_daily)} <small>/day</small>`
    : `${money(v.buy_price)}`;
}

function renderGrid(items) {
  const grid = $("grid");
  if (!items.length) { grid.innerHTML = `<p class="muted">No vehicles match these filters.</p>`; return; }
  grid.innerHTML = items.map((v) => `
    <div class="card" data-id="${v.id}">
      <div class="thumb">${emojiFor(v.body_style)}</div>
      <div class="title">${v.year} ${v.make} ${v.model}</div>
      <div class="sub">${v.body_style} · ${v.size}</div>
      <div class="price">${priceTag(v)}</div>
      <div class="specs">
        ${v.vpic_verified ? `<span class="chip verified">vPIC ✓</span>` : ""}
        ${v.match_score != null ? `<span class="chip score">${v.match_score}% match</span>` : ""}
        <span class="chip">${v.engine_hp || "—"} HP</span>
        <span class="chip">${v.mpg_hwy || "—"} hwy MPG</span>
        <span class="chip">${v.seats} seats</span>
      </div>
    </div>`).join("");
  grid.querySelectorAll(".card").forEach((c) =>
    c.addEventListener("click", () => openDetail(c.dataset.id)));
}

// --------------------------------------------------------------------------- //
// Detail + checkout
// --------------------------------------------------------------------------- //
async function openDetail(id) {
  const v = await getJSON("/api/vehicles/" + id);
  const isRent = state.mode === "rent";
  const available = isRent ? v.for_rent : (v.for_sale && v.stock > 0);
  $("modalBody").innerHTML = `
    <div class="thumb" style="font-size:54px;text-align:center">${emojiFor(v.body_style)}</div>
    <h2>${v.year} ${v.make} ${v.model}</h2>
    <div class="muted">${v.body_style} · ${v.size} · ${v.market_category || "Standard"}</div>
    ${v.vpic_verified ? `<div class="chip verified" style="display:inline-block;margin-top:8px">Brand verified in NHTSA vPIC (Make ID ${v.vpic_make_id})</div>` : ""}
    <div class="big-price">${isRent ? money(v.rent_daily) + " <small style='font-size:14px'>/day</small>" : money(v.buy_price)}</div>
    <div class="kv">
      <div><span>Engine</span><br>${v.engine_hp || "—"} HP · ${v.cylinders || "—"} cyl</div>
      <div><span>Fuel</span><br>${v.fuel_type || "—"}</div>
      <div><span>Transmission</span><br>${v.transmission || "—"}</div>
      <div><span>Drive</span><br>${v.drive || "—"}</div>
      <div><span>Efficiency</span><br>${v.mpg_city || "—"} city / ${v.mpg_hwy || "—"} hwy</div>
      <div><span>Seats / Doors</span><br>${v.seats} seats · ${v.doors} doors</div>
      <div><span>${isRent ? "Rental fleet" : "In stock"}</span><br>${isRent ? (v.for_rent ? "Available" : "Unavailable") : v.stock + " units"}</div>
      <div><span>MSRP</span><br>${money(v.msrp)}</div>
    </div>
    ${available ? checkoutBlock(v, isRent) : `<p style="color:var(--danger)">Not available for ${isRent ? "rent" : "purchase"} right now.</p>`}
    <div class="vpic-box" id="vpicBox"><h4>NHTSA vPIC live data</h4><span class="muted">Loading…</span></div>
  `;
  $("modal").classList.remove("hidden");

  if (available) {
    $("orderBtn").addEventListener("click", () => placeOrder(v, isRent));
    if (isRent) {
      const upd = () => { $("rentTotal").textContent = money(v.rent_daily * (Number($("rentDays").value) || 1)); };
      $("rentDays").addEventListener("input", upd); upd();
    }
  }
  loadVpic(id);
}

function checkoutBlock(v, isRent) {
  if (isRent) {
    return `<div class="buy-row">
      <label>Days</label>
      <input type="number" id="rentDays" value="3" min="1" max="365" />
      <strong>Total: <span id="rentTotal"></span></strong>
      <button class="primary" id="orderBtn" style="margin-left:auto">Rent now</button>
    </div>`;
  }
  return `<div class="buy-row">
    <strong>Total: ${money(v.buy_price)}</strong>
    <button class="primary" id="orderBtn" style="margin-left:auto">Buy now</button>
  </div>`;
}

async function loadVpic(id) {
  try {
    const d = await getJSON(`/api/vehicles/${id}/vpic`);
    $("vpicBox").innerHTML = `<h4>NHTSA vPIC live data</h4>
      <div>Vehicle types: ${(d.vpic_vehicle_types || []).join(", ") || "—"}</div>
      <div>vPIC lists <strong>${d.vpic_models_count}</strong> models for ${d.make} ${d.year}.</div>
      <div class="muted" style="margin-top:6px">${(d.vpic_models_sample || []).slice(0, 12).join(" · ")}</div>`;
  } catch {
    $("vpicBox").innerHTML = `<h4>NHTSA vPIC live data</h4><span class="muted">vPIC unavailable right now.</span>`;
  }
}

async function placeOrder(v, isRent) {
  const body = { vehicle_id: v.id, mode: isRent ? "rent" : "buy" };
  if (isRent) body.rent_days = Number($("rentDays").value) || 1;
  try {
    const r = await getJSON("/api/orders", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    $("modal").classList.add("hidden");
    toast("✅ " + r.message);
    loadVehicles();
  } catch (e) {
    toast("⚠️ " + e.message);
  }
}

// --------------------------------------------------------------------------- //
// Recommend
// --------------------------------------------------------------------------- //
async function recommend() {
  const body = {
    mode: state.mode,
    make: $("make").value || null,
    body_style: $("body_style").value || null,
    fuel_type: $("fuel_type").value || null,
    min_seats: $("min_seats").value ? Number($("min_seats").value) : null,
    budget_max: Number($("max_price").value) || null,
    priorities: [],
    limit: 12,
  };
  // infer priorities from sort choice
  const sort = $("sort").value;
  if (sort === "mpg") body.priorities.push("efficiency");
  if (sort.startsWith("price")) body.priorities.push("price");
  if (!body.priorities.length) body.priorities = ["efficiency", "price"];

  const data = await getJSON("/api/recommend", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  renderGrid(data.results);
  $("resultCount").textContent = `Top ${data.count} recommendations for you`;
  $("pageInfo").textContent = "";
}

// --------------------------------------------------------------------------- //
// Orders view
// --------------------------------------------------------------------------- //
async function showOrders() {
  const d = await getJSON("/api/orders");
  $("modalBody").innerHTML = `<h2>My Orders</h2>` + (
    d.orders.length
      ? d.orders.map((o) => `<div class="kv" style="grid-template-columns:1fr auto">
          <div>${o.year} ${o.make} ${o.model}<br><span class="muted">${o.mode === "rent" ? o.rent_days + " day rental" : "Purchase"} · ${o.created_at}</span></div>
          <div class="big-price" style="font-size:18px">${money(o.total)}</div></div>`).join("<hr>")
      : `<p class="muted">No orders yet.</p>`
  );
  $("modal").classList.remove("hidden");
}

// --------------------------------------------------------------------------- //
// Wiring
// --------------------------------------------------------------------------- //
function bind() {
  $("modeToggle").addEventListener("click", (e) => {
    const btn = e.target.closest("button"); if (!btn) return;
    state.mode = btn.dataset.mode; state.page = 1;
    document.querySelectorAll("#modeToggle button").forEach((b) => b.classList.toggle("active", b === btn));
    updatePriceSlider(); loadVehicles();
  });
  ["make", "body_style", "fuel_type", "drive", "sort", "year_min", "min_seats"].forEach((id) =>
    $(id).addEventListener("change", () => { state.page = 1; loadVehicles(); }));
  $("q").addEventListener("input", debounce(() => { state.page = 1; loadVehicles(); }, 350));
  $("max_price").addEventListener("input", showPriceVal);
  $("max_price").addEventListener("change", () => { state.page = 1; loadVehicles(); });
  $("resetBtn").addEventListener("click", () => {
    ["make", "body_style", "fuel_type", "drive", "q", "year_min", "min_seats"].forEach((id) => $(id).value = "");
    $("sort").value = "popularity"; updatePriceSlider(); state.page = 1; loadVehicles();
  });
  $("recommendBtn").addEventListener("click", recommend);
  $("prevPage").addEventListener("click", () => { if (state.page > 1) { state.page--; loadVehicles(); } });
  $("nextPage").addEventListener("click", () => { state.page++; loadVehicles(); });
  $("modalClose").addEventListener("click", () => $("modal").classList.add("hidden"));
  $("modal").addEventListener("click", (e) => { if (e.target.id === "modal") $("modal").classList.add("hidden"); });
  $("ordersBtn").addEventListener("click", showOrders);
}

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

(async function init() {
  bind();
  await loadFilters();
  await loadVehicles();
})();
