import { useEffect, useMemo, useState } from "react";
import ListingCard from "@/components/ListingCard";
import Pagination from "@/components/Pagination";
import { getFacets, getListings, createOrder } from "@/lib/api";
import { useDebounce } from "@/lib/useDebounce";

const PAGE_SIZE = 12;

// Buy / Rent storefront. Filters the priced catalog (/store/listings) by brand,
// price, fuel + keyword, and lets the customer purchase or rent each vehicle.
export default function StorePage() {
  const [mode, setMode] = useState("buy");
  const [make, setMake] = useState("");
  const [fuel, setFuel] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("popularity");
  const [page, setPage] = useState(1);

  const [facets, setFacets] = useState(null);
  const [data, setData] = useState({ results: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const debouncedPrice = useDebounce(maxPrice, 350);
  const debouncedQ = useDebounce(q, 350);

  // sort here maps to the API's sort/order pair.
  const { apiSort, order } = useMemo(() => {
    switch (sort) {
      case "price_asc":
        return { apiSort: "price", order: "asc" };
      case "price_desc":
        return { apiSort: "price", order: "desc" };
      case "year":
        return { apiSort: "year", order: "desc" };
      case "hp":
        return { apiSort: "hp", order: "desc" };
      default:
        return { apiSort: "popularity", order: "desc" };
    }
  }, [sort]);

  useEffect(() => {
    getFacets().then(setFacets).catch(() => setFacets(null));
  }, []);

  useEffect(() => {
    setPage(1);
  }, [mode, make, fuel, debouncedPrice, debouncedQ, sort]);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    getListings(
      {
        mode,
        make,
        engine_fuel_type: fuel,
        price_max: debouncedPrice,
        q: debouncedQ,
        sort: apiSort,
        order,
        page,
        size: PAGE_SIZE,
      },
      { signal: ctrl.signal }
    )
      .then((res) => setData({ results: res.results, total: res.total }))
      .catch((err) => {
        if (err.name === "AbortError") return;
        setError(err.message);
        setData({ results: [], total: 0 });
      })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [mode, make, fuel, debouncedPrice, debouncedQ, apiSort, order, page]);

  async function handleOrder(listing, { rentDays }) {
    try {
      const res = await createOrder({
        vehicle_id: String(listing.id),
        mode,
        rent_days: mode === "rent" ? rentDays : undefined,
      });
      setToast({ kind: "ok", text: res.message });
      // refresh so purchased stock updates
      setPage((p) => p);
      setData((d) => ({ ...d }));
      const refreshed = await getListings({
        mode, make, engine_fuel_type: fuel, price_max: debouncedPrice,
        q: debouncedQ, sort: apiSort, order, page, size: PAGE_SIZE,
      });
      setData({ results: refreshed.results, total: refreshed.total });
    } catch (err) {
      setToast({ kind: "err", text: err.message });
    }
    setTimeout(() => setToast(null), 4000);
  }

  const priceLabel = mode === "rent" ? "Max $/day" : "Max price";

  return (
    <div className="shell store">
      <div className="store__head">
        <div>
          <p className="eyebrow">Buy &amp; Rent</p>
          <h2 className="store__title">Find your vehicle</h2>
        </div>
        <div className="store__modes" role="tablist" aria-label="Buy or rent">
          <button
            className={mode === "buy" ? "is-active" : ""}
            onClick={() => setMode("buy")}
            role="tab"
            aria-selected={mode === "buy"}
          >
            Buy
          </button>
          <button
            className={mode === "rent" ? "is-active" : ""}
            onClick={() => setMode("rent")}
            role="tab"
            aria-selected={mode === "rent"}
          >
            Rent
          </button>
        </div>
      </div>

      <div className="store__filters">
        <input
          className="store__input"
          placeholder="Search make or model…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select value={make} onChange={(e) => setMake(e.target.value)} className="store__input">
          <option value="">All brands</option>
          {(facets?.makes || []).map((m) => (
            <option key={m.key} value={m.key}>
              {m.key}
            </option>
          ))}
        </select>
        <select value={fuel} onChange={(e) => setFuel(e.target.value)} className="store__input">
          <option value="">Any fuel</option>
          {(facets?.fuel_types || []).map((f) => (
            <option key={f.key} value={f.key}>
              {f.key}
            </option>
          ))}
        </select>
        <input
          className="store__input"
          type="number"
          min={0}
          placeholder={priceLabel}
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
        />
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="store__input">
          <option value="popularity">Most popular</option>
          <option value="price_asc">Price: low → high</option>
          <option value="price_desc">Price: high → low</option>
          <option value="year">Newest</option>
          <option value="hp">Most powerful</option>
        </select>
      </div>

      <p className="results__count" style={{ margin: "8px 0 18px" }}>
        {error ? (
          <span className="results__error">{error} — is the backend running on :8000?</span>
        ) : (
          <>
            <span className="mono results__num">{String(data.total).padStart(2, "0")}</span>{" "}
            vehicles {mode === "rent" ? "for rent" : "for sale"}
          </>
        )}
      </p>

      {loading ? (
        <div className="grid" aria-busy="true">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card card--skeleton">
              <div className="card__visual skel" />
            </div>
          ))}
        </div>
      ) : data.results.length === 0 && !error ? (
        <div className="empty">
          <span className="empty__mark" aria-hidden="true">⌀</span>
          <h3>No vehicles match</h3>
          <p>Try a different brand, fuel, or price.</p>
        </div>
      ) : (
        <div className="grid">
          {data.results.map((listing) => (
            <ListingCard key={listing.id} listing={listing} mode={mode} onOrder={handleOrder} />
          ))}
        </div>
      )}

      {!loading && !error && (
        <Pagination page={page} size={PAGE_SIZE} total={data.total} onPage={setPage} />
      )}

      {toast && (
        <div className={`store__toast store__toast--${toast.kind}`} role="status">
          {toast.text}
        </div>
      )}
    </div>
  );
}
