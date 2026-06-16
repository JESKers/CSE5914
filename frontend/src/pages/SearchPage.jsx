import { useEffect, useState } from "react";
import SearchBar from "@/components/SearchBar";
import FilterPanel from "@/components/FilterPanel";
import ResultsGrid from "@/components/ResultsGrid";

// Renders against the static mock so the UI works before the backend exists.
// Swap loadMock() for `fetch("/api/search?...")` once the backend is live.
async function loadMock() {
  const res = await fetch("/mock_response.json");
  return res.json();
}

export default function SearchPage() {
  const [keyword, setKeyword] = useState("");
  const [data, setData] = useState({ results: [], total: 0 });

  useEffect(() => {
    loadMock().then(setData);
  }, []);

  return (
    <div className="space-y-4">
      <SearchBar value={keyword} onChange={setKeyword} onSearch={() => {}} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
        <aside>
          <FilterPanel />
        </aside>
        <section>
          <ResultsGrid results={data.results} total={data.total} />
        </section>
      </div>
    </div>
  );
}
