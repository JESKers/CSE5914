import CarCard from "@/components/CarCard";

// (2) Results grid — lays out CarCards from a results array.
export default function ResultsGrid({ results = [], total }) {
  if (results.length === 0) {
    return <p className="py-12 text-center text-slate-400">No cars match your search yet.</p>;
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">{total ?? results.length} results</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {results.map((car) => (
          <CarCard key={car.id} car={car} />
        ))}
      </div>
    </div>
  );
}
