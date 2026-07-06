import { useState } from "react";
import { carCategory, carGradient, formatPrice, TRANSMISSION_SHORT } from "@/lib/utils";

const CATEGORY_BADGE = {
  electric: "Electric",
  performance: "Performance",
  luxury: "Luxury",
  default: "Standard",
};

// A purchasable / rentable car. Mirrors CarCard's visual language but adds the
// buy/rent price, a vPIC-verified badge, availability, and an action control.
// `mode` is "buy" | "rent"; `onOrder(listing, { rentDays })` places the order.
export default function ListingCard({ listing, mode, onOrder }) {
  const category = carCategory(listing);
  const [days, setDays] = useState(3);
  const [busy, setBusy] = useState(false);

  const isRent = mode === "rent";
  const available = isRent ? listing.for_rent : listing.stock > 0;

  async function place() {
    setBusy(true);
    try {
      await onOrder(listing, { rentDays: days });
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="card">
      <div className="card__visual" style={{ background: carGradient(listing) }}>
        <span className="card__year mono">{"'" + String(listing.year).slice(2)}</span>
        <span className="card__badge">{CATEGORY_BADGE[category]}</span>
        {listing.vpic_verified && (
          <span className="card__vpic mono" title="Brand verified in the NHTSA vPIC directory">
            vPIC ✓
          </span>
        )}
        <span className="card__silhouette" aria-hidden="true">
          {category === "electric" ? "⚡" : "◈"}
        </span>
      </div>

      <div className="card__body-inner">
        <div className="card__headrow">
          <div>
            <p className="card__make mono">{listing.make}</p>
            <h3 className="card__model">{listing.model}</h3>
          </div>
          <div className="card__price">
            <span className="card__price-val">
              {isRent ? formatPrice(listing.rent_daily) : formatPrice(listing.buy_price)}
            </span>
            <span className="card__price-label mono">{isRent ? "PER DAY" : "PRICE"}</span>
          </div>
        </div>

        <dl className="card__specs">
          <div className="spec">
            <dt className="mono">PWR</dt>
            <dd>{listing.engine_hp != null ? `${listing.engine_hp} hp` : "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">SEATS</dt>
            <dd>{listing.seats ?? "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">TRANS</dt>
            <dd>{TRANSMISSION_SHORT[listing.transmission_type] || "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">STYLE</dt>
            <dd>{listing.vehicle_style || "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">HWY</dt>
            <dd>{listing.highway_mpg != null ? `${listing.highway_mpg} mpg` : "—"}</dd>
          </div>
          <div className="spec">
            <dt className="mono">{isRent ? "AVAIL" : "STOCK"}</dt>
            <dd>{isRent ? (listing.for_rent ? "Yes" : "No") : `${listing.stock}`}</dd>
          </div>
        </dl>

        <div className="store__action">
          {isRent && (
            <label className="store__days">
              <span className="mono">DAYS</span>
              <input
                type="number"
                min={1}
                max={365}
                value={days}
                onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
              />
            </label>
          )}
          {isRent && (
            <span className="store__total mono">
              {formatPrice(listing.rent_daily * days)}
            </span>
          )}
          <button
            type="button"
            className="store__btn"
            disabled={!available || busy}
            onClick={place}
          >
            {busy ? "…" : !available ? "Unavailable" : isRent ? "Rent" : "Buy now"}
          </button>
        </div>
      </div>
    </article>
  );
}
