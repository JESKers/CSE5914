import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

// (1) Filter panel — maps to GET /search query params. Mockup options are static;
// Shangrui will populate make/transmission/fuel from GET /facets once wired.
const MAKES = ["Any make", "BMW", "Toyota", "Ford", "Audi", "Honda", "Chevrolet"];
const TRANSMISSIONS = ["Any transmission", "MANUAL", "AUTOMATIC", "AUTOMATED_MANUAL"];
const FUEL_TYPES = ["Any fuel", "regular unleaded", "premium unleaded (required)", "diesel", "electric"];

function Field({ label, children }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-slate-500">{label}</span>
      {children}
    </label>
  );
}

export default function FilterPanel() {
  return (
    <Card>
      <CardHeader className="font-semibold">Filters</CardHeader>
      <CardBody className="space-y-3">
        <Field label="Make">
          <Select>
            {MAKES.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </Select>
        </Field>
        <Field label="Model">
          <Input placeholder="e.g. M4" />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Year min">
            <Input type="number" placeholder="2010" />
          </Field>
          <Field label="Year max">
            <Input type="number" placeholder="2017" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Price min">
            <Input type="number" placeholder="0" />
          </Field>
          <Field label="Price max">
            <Input type="number" placeholder="50000" />
          </Field>
        </div>
        <Field label="Min horsepower">
          <Input type="number" placeholder="300" />
        </Field>
        <Field label="Transmission">
          <Select>
            {TRANSMISSIONS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </Select>
        </Field>
        <Field label="Engine fuel type">
          <Select>
            {FUEL_TYPES.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </Select>
        </Field>
        <div className="flex gap-2 pt-1">
          <Button className="flex-1">Apply</Button>
          <Button variant="outline" type="reset">
            Reset
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
