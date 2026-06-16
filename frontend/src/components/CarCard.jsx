import { Card, CardBody } from "@/components/ui/card";
import { formatPrice } from "@/lib/utils";

// (2) Car card — renders one CarResult (see docs/API_CONTRACT.md).
export default function CarCard({ car }) {
  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardBody className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-base font-semibold leading-tight">
            {car.year} {car.make} {car.model}
          </h3>
          <span className="whitespace-nowrap text-base font-bold text-blue-700">
            {formatPrice(car.msrp)}
          </span>
        </div>
        <p className="text-sm text-slate-500">
          {car.vehicle_style}
          {car.engine_hp ? ` · ${car.engine_hp} hp` : ""}
          {car.transmission_type ? ` · ${car.transmission_type}` : ""}
        </p>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {car.engine_fuel_type && <Tag>{car.engine_fuel_type}</Tag>}
          {car.highway_mpg != null && <Tag>{car.highway_mpg} hwy mpg</Tag>}
          {car.city_mpg != null && <Tag>{car.city_mpg} city mpg</Tag>}
        </div>
      </CardBody>
    </Card>
  );
}

function Tag({ children }) {
  return (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{children}</span>
  );
}
