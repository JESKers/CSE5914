// Sort control — pill toggles mapping to the API's sort + order params.
// Each option carries the (sort, order) pair the backend expects.
export const SORT_OPTIONS = [
  { id: "popularity", label: "Popular", sort: "popularity", order: "desc" },
  { id: "price-asc", label: "Price ↑", sort: "price", order: "asc" },
  { id: "price-desc", label: "Price ↓", sort: "price", order: "desc" },
  { id: "hp-desc", label: "Power ↓", sort: "hp", order: "desc" },
  { id: "year-desc", label: "Newest", sort: "year", order: "desc" },
];

export default function Sort({ value, onChange }) {
  return (
    <div className="sort">
      <span className="sort__label mono">SORT</span>
      {SORT_OPTIONS.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className={`sort__opt ${value === opt.id ? "sort__opt--on" : ""}`}
          onClick={() => onChange(opt.id)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
