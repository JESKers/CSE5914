import { useEffect, useState } from "react";
import { getModels } from "@/lib/api";
import { formatPrice, TRANSMISSION_LABEL } from "@/lib/utils";

const FALLBACK_TRANSMISSIONS = ["AUTOMATIC", "MANUAL", "AUTOMATED_MANUAL", "DIRECT_DRIVE"];
const FALLBACK_FUEL = ["regular unleaded", "premium unleaded (required)", "diesel", "electric"];

// Preset price thresholds (USD) — the rounded steps used by mainstream car
// sites (Cars.com / Autotrader / CarGurus).
const PRICE_STEPS = [
  5000, 7500, 10000, 12500, 15000, 17500, 20000, 25000, 30000, 35000, 40000, 45000, 50000,
  60000, 70000, 80000, 90000, 100000, 125000, 150000, 200000,
];

// Year choices when /facets hasn't loaded yet: current year back to 1990.
const CURRENT_YEAR = new Date().getFullYear();
const FALLBACK_YEARS = Array.from({ length: CURRENT_YEAR - 1989 }, (_, i) => CURRENT_YEAR - i);

// Pretty fuel label — strip the "(required)/(recommended)" noise.
const fuelLabel = (f) => f.replace(" (required)", "").replace(" (recommended)", "");

// A labelled group in the sidebar.
function Group({ title, children }) {
  return (
    <div className="filter__group">
      <h4 className="filter__title">{title}</h4>
      {children}
    </div>
  );
}

// A wrap of single-select toggle pills bound to one filter key.
function Pills({ options, value, onToggle, labelFor = (x) => x }) {
  return (
    <div className="filter__opts">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          className={`pill ${value === opt ? "pill--on" : ""}`}
          onClick={() => onToggle(value === opt ? "" : opt)}
        >
          {labelFor(opt)}
        </button>
      ))}
    </div>
  );
}

// A two-input min/max range bound to two filter keys.
function Range({ unit, minKey, maxKey, filters, set, placeholderMin, placeholderMax }) {
  return (
    <div className="range">
      <div className="range__field">
        {unit && <span className="range__unit">{unit}</span>}
        <input
          className="range__input"
          type="number"
          inputMode="numeric"
          placeholder={placeholderMin}
          value={filters[minKey] ?? ""}
          onChange={(e) => set(minKey, e.target.value)}
        />
      </div>
      <span className="range__sep">–</span>
      <div className="range__field">
        {unit && <span className="range__unit">{unit}</span>}
        <input
          className="range__input"
          type="number"
          inputMode="numeric"
          placeholder={placeholderMax}
          value={filters[maxKey] ?? ""}
          onChange={(e) => set(maxKey, e.target.value)}
        />
      </div>
    </div>
  );
}

// A min/max pair of dropdowns bound to two filter keys, with a shared list of
// preset option values. Each side hides options that would invert the range.
function RangeSelect({ options, minKey, maxKey, filters, set, labelFor = (x) => x, anyLabel }) {
  const min = filters[minKey];
  const max = filters[maxKey];
  const minOpts = options.filter((o) => !max || o <= Number(max));
  const maxOpts = options.filter((o) => !min || o >= Number(min));
  return (
    <div className="range">
      <select
        className="filter__select"
        value={min ?? ""}
        onChange={(e) => set(minKey, e.target.value)}
      >
        <option value="">{anyLabel?.min ?? "Min"}</option>
        {minOpts.map((o) => (
          <option key={o} value={o}>
            {labelFor(o)}
          </option>
        ))}
      </select>
      <span className="range__sep">–</span>
      <select
        className="filter__select"
        value={max ?? ""}
        onChange={(e) => set(maxKey, e.target.value)}
      >
        <option value="">{anyLabel?.max ?? "Max"}</option>
        {maxOpts.map((o) => (
          <option key={o} value={o}>
            {labelFor(o)}
          </option>
        ))}
      </select>
    </div>
  );
}

// Sidebar filters — controlled by the parent. Every change applies live; the
// parent debounces the fetch. Dropdown values come from /facets and /models.
export default function FilterPanel({ facets, filters, setFilters, activeCount, onReset }) {
  const [models, setModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  const set = (key, value) => setFilters((f) => ({ ...f, [key]: value }));
  // Changing make clears the model (its options no longer apply).
  const setMake = (value) => setFilters((f) => ({ ...f, make: value, model: "" }));

  // Load the model list whenever the selected make changes.
  useEffect(() => {
    if (!filters.make) {
      setModels([]);
      return;
    }
    const ctrl = new AbortController();
    setModelsLoading(true);
    getModels(filters.make, { signal: ctrl.signal })
      .then((r) => setModels(r.models))
      .catch(() => setModels([]))
      .finally(() => setModelsLoading(false));
    return () => ctrl.abort();
  }, [filters.make]);

  const makes = facets?.makes?.map((b) => b.key) ?? [];
  const transmissions = facets?.transmissions?.map((b) => b.key) ?? FALLBACK_TRANSMISSIONS;
  const fuels = facets?.fuel_types?.map((b) => b.key) ?? FALLBACK_FUEL;
  const years = facets?.years?.length ? facets.years : FALLBACK_YEARS;

  return (
    <aside className="filters">
      <div className="filters__head">
        <h3 className="filters__heading">
          Refine
          {activeCount > 0 && <span className="filters__count mono">{activeCount}</span>}
        </h3>
        <button type="button" className="filters__clear" onClick={onReset}>
          Reset
        </button>
      </div>

      <Group title="Make">
        <select
          className="filter__select"
          value={filters.make ?? ""}
          onChange={(e) => setMake(e.target.value)}
        >
          <option value="">Any make</option>
          {makes.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </Group>

      <Group title="Model">
        <select
          className="filter__select"
          value={filters.model ?? ""}
          onChange={(e) => set("model", e.target.value)}
          disabled={!filters.make || modelsLoading}
        >
          <option value="">
            {!filters.make ? "Select a make first" : modelsLoading ? "Loading…" : "Any model"}
          </option>
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </Group>

      <Group title="Price">
        <RangeSelect
          options={PRICE_STEPS}
          minKey="price_min"
          maxKey="price_max"
          filters={filters}
          set={set}
          labelFor={(v) => formatPrice(v)}
          anyLabel={{ min: "No min", max: "No max" }}
        />
      </Group>

      <Group title="Power">
        <Range
          minKey="hp_min"
          maxKey="hp_max"
          filters={filters}
          set={set}
          placeholderMin="hp min"
          placeholderMax="hp max"
        />
      </Group>

      <Group title="Year">
        <RangeSelect
          options={years}
          minKey="year_min"
          maxKey="year_max"
          filters={filters}
          set={set}
          anyLabel={{ min: "From", max: "To" }}
        />
      </Group>

      <Group title="Transmission">
        <Pills
          options={transmissions}
          value={filters.transmission_type ?? ""}
          onToggle={(v) => set("transmission_type", v)}
          labelFor={(t) => TRANSMISSION_LABEL[t] || t}
        />
      </Group>

      <Group title="Fuel type">
        <Pills
          options={fuels}
          value={filters.engine_fuel_type ?? ""}
          onToggle={(v) => set("engine_fuel_type", v)}
          labelFor={fuelLabel}
        />
      </Group>
    </aside>
  );
}
