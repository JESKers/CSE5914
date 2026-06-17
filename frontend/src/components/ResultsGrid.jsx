import CarCard from "@/components/CarCard";

// Results grid — renders CarCards plus loading / error / empty states.
export default function ResultsGrid({ results = [], total, loading, error }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-32 animate-pulse rounded-xl border border-slate-200 bg-slate-100" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <p className="py-12 text-center text-red-500">
        {error} — is the backend running on :8000?
      </p>
    );
  }

  if (results.length === 0) {
    return <p className="py-12 text-center text-slate-400">No cars match your search.</p>;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">{(total ?? results.length).toLocaleString()} results</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {results.map((car) => (
          <CarCard key={car.id} car={car} />
        ))}
      </div>
    </div>
  );
}
