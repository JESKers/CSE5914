import { useState } from "react";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

// Filter panel — controlled inputs mapping to GET /search query params. Holds a
// local draft and only lifts it up on "Apply" (the keyword box, handled in
// SearchPage, searches live). Dropdown options come from GET /facets, with a
// small static fallback used before facets load.
const FALLBACK_TRANSMISSIONS = ["MANUAL", "AUTOMATIC", "AUTOMATED_MANUAL"];
const FALLBACK_FUEL = ["regular unleaded", "premium unleaded (required)", "diesel", "electric"];

const EMPTY = {
  make: "", model: "", year_min: "", year_max: "",
  price_min: "", price_max: "", hp_min: "",
  transmission_type: "", engine_fuel_type: "",
};

function Field({ label, children }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-slate-500">{label}</span>
      {children}
    </label>
  );
}

export default function FilterPanel({ facets, onApply, onReset }) {
  const [draft, setDraft] = useState(EMPTY);
  const set = (key) => (e) => setDraft((d) => ({ ...d, [key]: e.target.value }));

  const makes = facets?.makes?.map((b) => b.key) ?? [];
  const transmissions = facets?.transmissions?.map((b) => b.key) ?? FALLBACK_TRANSMISSIONS;
  const fuels = facets?.fuel_types?.map((b) => b.key) ?? FALLBACK_FUEL;

  const apply = () => onApply?.(draft);
  const reset = () => {
    setDraft(EMPTY);
    onReset?.();
  };

  return (
    <Card>
      <CardHeader className="font-semibold">Filters</CardHeader>
      <CardBody className="space-y-3">
        <Field label="Make">
          <Select value={draft.make} onChange={set("make")}>
            <option value="">Any make</option>
            {makes.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </Select>
        </Field>
        <Field label="Model">
          <Input placeholder="e.g. M4" value={draft.model} onChange={set("model")} />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Year min">
            <Input type="number" placeholder="2010" value={draft.year_min} onChange={set("year_min")} />
          </Field>
          <Field label="Year max">
            <Input type="number" placeholder="2017" value={draft.year_max} onChange={set("year_max")} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Price min">
            <Input type="number" placeholder="0" value={draft.price_min} onChange={set("price_min")} />
          </Field>
          <Field label="Price max">
            <Input type="number" placeholder="50000" value={draft.price_max} onChange={set("price_max")} />
          </Field>
        </div>
        <Field label="Min horsepower">
          <Input type="number" placeholder="300" value={draft.hp_min} onChange={set("hp_min")} />
        </Field>
        <Field label="Transmission">
          <Select value={draft.transmission_type} onChange={set("transmission_type")}>
            <option value="">Any transmission</option>
            {transmissions.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </Select>
        </Field>
        <Field label="Engine fuel type">
          <Select value={draft.engine_fuel_type} onChange={set("engine_fuel_type")}>
            <option value="">Any fuel</option>
            {fuels.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </Select>
        </Field>
        <div className="flex gap-2 pt-1">
          <Button className="flex-1" onClick={apply}>Apply</Button>
          <Button variant="outline" onClick={reset}>Reset</Button>
        </div>
      </CardBody>
    </Card>
  );
}
