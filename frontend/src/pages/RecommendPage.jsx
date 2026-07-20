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
          <p>{data.message}</p>
          {data.narrative && <p className="reco__narrative">{data.narrative}</p>}
          <p className="mono">Generated via {data.generation_mode}; sources: {data.sources?.join(" + ")}</p>
          {data.warnings?.map((warning) => (
            <p className="results__error" key={warning}>{warning}</p>
          ))}
          {data.comparison_points?.length > 0 && (
            <ul className="reco__comparisons">
              {data.comparison_points.map((point) => <li key={point}>{point}</li>)}
            </ul>
          )}
          <ResultsGrid
            results={data.results}
            total={data.total}
            size={data.total || data.results.length}
          />
          {data.alternatives?.length > 0 && (
            <div className="reco__alternatives">
              <h3>Near matches</h3>
              <p>These vehicles violate only the explicitly listed relaxed constraint.</p>
              <ResultsGrid
                results={data.alternatives}
                total={data.alternatives.length}
                size={data.alternatives.length}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
