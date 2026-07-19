import { carCategory, carGradient, formatPrice, TRANSMISSION_SHORT } from "@/lib/utils";

const CATEGORY_BADGE = {
  electric: "Electric",
  performance: "Performance",
  luxury: "Luxury",
  default: "Standard",
};

// One car result, styled to the team reference: a gradient "visual" header with
// the year + category badge, then make/model + MSRP, a spec grid, and tags.
// Specs are mapped to the fields the API actually returns (see API_CONTRACT.md).
export default function CarCard({ car }) {
  const category = carCategory(car);

  return (
    <article className="card">
      <div className="card__visual" style={{ background: carGradient(car) }}>
        <span className="card__year mono">{"'" + String(car.year).slice(2)}</span>
        <span className="card__badge">{CATEGORY_BADGE[category]}</span>
        <span className="card__silhouette" aria-hidden="true">
          {category === "electric" ? "⚡" : "◈"}
        </span>
      </div>

      <div className="card__body-inner">
        <div className="card__headrow">
          <div>
            <p className="card__make mono">{car.make}</p>
            <h3 className="card__model">{car.model}</h3>
          </div>
          <div className="card__price">
            <span className="card__price-val">{formatPrice(car.msrp)}</span>
            <span className="card__price-label mono">MSRP</span>
          </div>
        </div>

        <dl className="card__specs">
          <div className="spec">
            <dt className="mono">PWR</dt>
            <dd>{car.engine_hp != null ? `${car.engine_hp} hp` : "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">TRANS</dt>
            <dd>{TRANSMISSION_SHORT[car.transmission_type] || "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">STYLE</dt>
            <dd>{car.vehicle_style || "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">HWY</dt>
            <dd>{car.highway_mpg != null ? `${car.highway_mpg} mpg` : "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">CITY</dt>
            <dd>{car.city_mpg != null ? `${car.city_mpg} mpg` : "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">YEAR</dt>
            <dd>{car.year}</dd>
          </div>
        </dl>

        {car.engine_fuel_type && (
          <div className="card__tags">
            <span className="tag">{car.engine_fuel_type}</span>
          </div>
        )}

        {car.match_reasons?.length > 0 && (
          <div className="card__reasons">
            <p className="mono">WHY THIS MATCHES</p>
            <ul>
              {car.match_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
  );
}
