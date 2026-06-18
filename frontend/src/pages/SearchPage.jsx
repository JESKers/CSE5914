import { useEffect, useState } from "react";
import SearchBar from "@/components/SearchBar";
import FilterPanel from "@/components/FilterPanel";
import ResultsGrid from "@/components/ResultsGrid";
import Pagination from "@/components/Pagination";
import { Select } from "@/components/ui/input";
import { searchCars, getFacets } from "@/lib/api";
import { useDebounce } from "@/lib/useDebounce";

const SORT_OPTIONS = [
  { value: "popularity", label: "Popularity" },
  { value: "price", label: "Price" },
  { value: "hp", label: "Horsepower" },
  { value: "year", label: "Year" },
];

const PAGE_SIZE = 12;

// Drop blank values so we only send filters the user actually set.
function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== "" && v != null));
}

export default function SearchPage() {
  const [filters, setFilters] = useState({}); // applied structured filters
  const [keyword, setKeyword] = useState("");
  const [sort, setSort] = useState("popularity");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);

  const [data, setData] = useState({ results: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [facets, setFacets] = useState(null);

  const debouncedKeyword = useDebounce(keyword, 350);

  // Load dropdown values once.
  useEffect(() => {
    getFacets()
      .then(setFacets)
      .catch(() => setFacets(null)); // dropdowns fall back to static options
  }, []);

  // Any change to filters/keyword/sort/order resets to the first page.
  useEffect(() => {
    setPage(1);
  }, [filters, debouncedKeyword, sort, order]);

  // Fetch results whenever the query changes. Stale requests are aborted.
  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    searchCars(
      { ...clean(filters), q: debouncedKeyword, sort, order, page, size: PAGE_SIZE },
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
  }, [filters, debouncedKeyword, sort, order, page]);

  return (
    <div className="space-y-4">
      <SearchBar value={keyword} onChange={setKeyword} onSearch={() => setKeyword((k) => k)} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
        <aside>
          <FilterPanel
            facets={facets}
            onApply={(draft) => setFilters(clean(draft))}
            onReset={() => setFilters({})}
          />
        </aside>
        <section className="space-y-3">
          <div className="flex items-center justify-end gap-2">
            <span className="text-xs font-medium text-slate-500">Sort by</span>
            <Select className="w-40" value={sort} onChange={(e) => setSort(e.target.value)}>
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
            <Select className="w-28" value={order} onChange={(e) => setOrder(e.target.value)}>
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </Select>
          </div>
          <ResultsGrid
            results={data.results}
            total={data.total}
            loading={loading}
            error={error}
          />
          {!loading && !error && (
            <Pagination page={page} size={PAGE_SIZE} total={data.total} onPage={setPage} />
          )}
        </section>
      </div>
    </div>
  );
}
