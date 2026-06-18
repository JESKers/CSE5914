import { useState } from "react";

const EXAMPLES = ["fast sports car under $50,000", "fuel-efficient SUV", "manual V8 coupe"];

// Natural-language recommendation input — maps to POST /recommend (RAG).
// Shows the parsed filters echoed back from the API for transparency.
export default function RecommendBox({ onSubmit, parsedFilters }) {
  const [query, setQuery] = useState("");

  return (
    <div className="reco__panel">
      <p className="eyebrow">Smart Recommendation Preview</p>
      <h2 className="reco__heading">Describe what you&apos;re looking for</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit?.(query);
        }}
      >
        <textarea
          className="reco__textarea"
          rows={3}
          placeholder="e.g. a reliable family SUV under $35k with good gas mileage"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="reco__actions">
          <button type="submit" className="reco__submit">
            Recommend
            <span aria-hidden="true">→</span>
          </button>
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" className="chip" onClick={() => setQuery(ex)}>
              {ex}
            </button>
          ))}
        </div>
      </form>

      {parsedFilters && (
        <div className="reco__echo">
          <span className="reco__echo-label">Parsed filters (query_echo)</span>
          <pre>{JSON.stringify(parsedFilters, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
