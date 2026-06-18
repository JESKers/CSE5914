import { formatPrice, TRANSMISSION_LABEL } from "@/lib/utils";

// Build the list of removable chips from the applied keyword + filters.
function buildChips(keyword, filters, { clearKeyword, clearKeys }) {
  const chips = [];

  if (keyword) {
    chips.push({ label: `"${keyword}"`, onRemove: clearKeyword });
  }
  if (filters.make) {
    chips.push({ label: filters.make, onRemove: () => clearKeys(["make", "model"]) });
  }
  if (filters.model) {
    chips.push({ label: filters.model, onRemove: () => clearKeys(["model"]) });
  }

  const range = (minKey, maxKey, title, fmt) => {
    const min = filters[minKey];
    const max = filters[maxKey];
    if (!min && !max) return;
    const lo = min ? fmt(min) : "Any";
    const hi = max ? fmt(max) : "Any";
    chips.push({ label: `${title} ${lo}–${hi}`, onRemove: () => clearKeys([minKey, maxKey]) });
  };
  range("price_min", "price_max", "Price", (v) => formatPrice(v));
  range("hp_min", "hp_max", "Power", (v) => `${v}hp`);
  range("year_min", "year_max", "Year", (v) => v);

  if (filters.transmission_type) {
    chips.push({
      label: TRANSMISSION_LABEL[filters.transmission_type] || filters.transmission_type,
      onRemove: () => clearKeys(["transmission_type"]),
    });
  }
  if (filters.engine_fuel_type) {
    chips.push({
      label: filters.engine_fuel_type.replace(" (required)", "").replace(" (recommended)", ""),
      onRemove: () => clearKeys(["engine_fuel_type"]),
    });
  }
  return chips;
}

export default function ActiveFilters({ keyword, filters, onClearKeyword, onClearKeys }) {
  const chips = buildChips(keyword, filters, {
    clearKeyword: onClearKeyword,
    clearKeys: onClearKeys,
  });
  if (chips.length === 0) return null;

  return (
    <div className="active">
      {chips.map((chip, i) => (
        <button key={i} type="button" className="active__chip" onClick={chip.onRemove}>
          {chip.label}
          <span className="active__x" aria-hidden="true">
            ×
          </span>
        </button>
      ))}
    </div>
  );
}
