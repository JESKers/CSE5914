import { useState } from "react";
import RecommendBox from "@/components/RecommendBox";
import ResultsGrid from "@/components/ResultsGrid";

export default function RecommendPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(query) {
    setError(null);
    setLoading(true);

    try {
      const res = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || res.statusText || "Recommendation request failed");
      }

      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shell reco">
      <RecommendBox onSubmit={handleSubmit} parsedFilters={data?.query_echo} />

      {loading && <p>Loading recommendations…</p>}
      {error && <p className="error">{error}</p>}

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
