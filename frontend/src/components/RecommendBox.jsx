import { useState } from "react";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const EXAMPLES = ["fast sports car under $50,000", "fuel-efficient SUV", "manual V8 coupe"];

// (3) Recommendation / chat input — maps to POST /recommend.
export default function RecommendBox({ onSubmit, parsedFilters }) {
  const [query, setQuery] = useState("");

  return (
    <Card>
      <CardBody className="space-y-3">
        <h2 className="text-base font-semibold">Describe what you&apos;re looking for</h2>
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit?.(query);
          }}
        >
          <textarea
            className="w-full resize-none rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            rows={3}
            placeholder="e.g. a reliable family SUV under $35k with good gas mileage"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit">Recommend</Button>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => setQuery(ex)}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 hover:bg-slate-200"
              >
                {ex}
              </button>
            ))}
          </div>
        </form>

        {parsedFilters && (
          <div className="rounded-md bg-slate-50 p-3 text-xs">
            <span className="font-medium text-slate-500">Parsed filters (query_echo):</span>
            <pre className="mt-1 overflow-x-auto text-slate-700">
              {JSON.stringify(parsedFilters, null, 2)}
            </pre>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
