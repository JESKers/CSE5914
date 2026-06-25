import CarCard from "@/components/CarCard";
import Sort from "@/components/Sort";

// Skeleton card shown while results load.
function SkeletonCard() {
  return (
    <div className="card card--skeleton">
      <div className="card__visual skel" />
      <div className="card__body-inner">
        <div className="skel skel--line" style={{ width: "60%" }} />
        <div className="skel skel--line" style={{ width: "40%" }} />
        <div className="skel skel--block" />
      </div>
    </div>
  );
}

// Results region — count + sort bar, then the card grid with loading / error /
// empty states. `page`/`size` drive the "showing X–Y" range readout.
export default function ResultsGrid({
  results = [],
  total = 0,
  loading,
  error,
  page = 1,
  size = 12,
  sort,
  onSort,
}) {
  const from = total === 0 ? 0 : (page - 1) * size + 1;
  const to = Math.min(page * size, total);

  return (
    <section className="results" id="results">
      <div className="results__bar">
        <p className="results__count">
          {error ? (
            <span className="results__error">{error} — is the backend running on :8000?</span>
          ) : (
            <>
              <span className="mono results__num">{String(total).padStart(2, "0")}</span>{" "}
              {total === 1 ? "car found" : "cars found"}
              {total > 0 && (
                <span className="results__range mono">
                  · showing {from}–{to}
                </span>
              )}
            </>
          )}
        </p>
        {onSort && <Sort value={sort} onChange={onSort} />}
      </div>

      {loading ? (
        <div className="grid" aria-busy="true">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : !error && results.length === 0 ? (
        <div className="empty">
          <span className="empty__mark" aria-hidden="true">
            ⌀
          </span>
          <h3>No cars match your search</h3>
          <p>Try removing a filter or broadening your keywords.</p>
        </div>
      ) : (
        <div className="grid">
          {results.map((car) => (
            <CarCard key={car.id} car={car} />
          ))}
        </div>
      )}
    </section>
  );
}
