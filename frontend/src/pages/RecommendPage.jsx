import { useState } from "react";
import RecommendBox from "@/components/RecommendBox";
import ResultsGrid from "@/components/ResultsGrid";

// Mockup for POST /recommend. On submit, loads the static mock and shows the
// parsed filters from query_echo. Swap for a POST to /api/recommend when live.
export default function RecommendPage() {
  const [data, setData] = useState(null);

  async function handleSubmit(query) {
    const res = await fetch("/mock_response.json");
    const mock = await res.json();
    setData({ ...mock, query_echo: { query, parsed_filters: mock.query_echo } });
  }

  return (
    <div className="shell reco">
      <RecommendBox onSubmit={handleSubmit} parsedFilters={data?.query_echo} />
      {data && (
        <div style={{ marginTop: 32 }}>
          <ResultsGrid
            results={data.results}
            total={data.total}
            size={data.total || data.results.length}
          />
        </div>
      )}
    </div>
  );
}
