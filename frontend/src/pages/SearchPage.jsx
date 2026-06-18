import { useEffect, useMemo, useState } from "react";
import Hero from "@/components/Hero";
import FilterPanel from "@/components/FilterPanel";
import ActiveFilters from "@/components/ActiveFilters";
import ResultsGrid from "@/components/ResultsGrid";
import Pagination from "@/components/Pagination";
import Roadmap from "@/components/Roadmap";
import { SORT_OPTIONS } from "@/components/Sort";
import { searchCars, getFacets } from "@/lib/api";
import { useDebounce } from "@/lib/useDebounce";

const PAGE_SIZE = 12;

// Drop blank values so we only send filters the user actually set.
function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== "" && v != null));
}

export default function SearchPage() {
  const [filters, setFilters] = useState({}); // live structured filters
  const [keyword, setKeyword] = useState("");
  const [sortId, setSortId] = useState("popularity");
  const [page, setPage] = useState(1);

  const [data, setData] = useState({ results: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [facets, setFacets] = useState(null);

  const debouncedKeyword = useDebounce(keyword, 350);
  const debouncedFilters = useDebounce(filters, 350); // ranges type quickly

  const { sort, order } = useMemo(
    () => SORT_OPTIONS.find((o) => o.id === sortId) ?? SORT_OPTIONS[0],
    [sortId]
  );

  const activeCount = Object.keys(clean(filters)).length + (debouncedKeyword ? 1 : 0);

  // Load dropdown values once.
  useEffect(() => {
    getFacets()
      .then(setFacets)
      .catch(() => setFacets(null)); // dropdowns fall back to static options
  }, []);

  // Any change to query/filters/sort resets to the first page.
  useEffect(() => {
    setPage(1);
  }, [debouncedFilters, debouncedKeyword, sortId]);

  // Fetch results whenever the query changes. Stale requests are aborted.
  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    searchCars(
      { ...clean(debouncedFilters), q: debouncedKeyword, sort, order, page, size: PAGE_SIZE },
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
  }, [debouncedFilters, debouncedKeyword, sort, order, page]);

  const clearKeys = (keys) =>
    setFilters((f) => {
      const next = { ...f };
      keys.forEach((k) => delete next[k]);
      return next;
    });

  return (
    <>
      <Hero value={keyword} onChange={setKeyword} onSearch={setKeyword} loading={loading} />

      <div className="shell layout">
        <FilterPanel
          facets={facets}
          filters={filters}
          setFilters={setFilters}
          activeCount={activeCount}
          onReset={() => {
            setFilters({});
            setKeyword("");
          }}
        />

        <div>
          <ActiveFilters
            keyword={debouncedKeyword}
            filters={filters}
            onClearKeyword={() => setKeyword("")}
            onClearKeys={clearKeys}
          />
          <ResultsGrid
            results={data.results}
            total={data.total}
            loading={loading}
            error={error}
            page={page}
            size={PAGE_SIZE}
            sort={sortId}
            onSort={setSortId}
          />
          {!loading && !error && (
            <Pagination page={page} size={PAGE_SIZE} total={data.total} onPage={setPage} />
          )}
        </div>
      </div>

      <Roadmap />
    </>
  );
}
