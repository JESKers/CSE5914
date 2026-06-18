// Tiny className joiner (shadcn-style `cn`, dependency-free).
export function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}

// Format an MSRP number as USD.
export function formatPrice(value) {
  if (value == null) return "—";
  return "$" + Number(value).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

// Card visual gradients keyed by the car's derived category.
const GRADIENTS = {
  electric: "linear-gradient(135deg, #0f3d2e 0%, #1d6f4f 50%, #c9f24a 140%)",
  performance: "linear-gradient(135deg, #2a1208 0%, #6e2a12 55%, #ff8a5c 140%)",
  luxury: "linear-gradient(135deg, #1a1830 0%, #36325e 55%, #b6a8ff 150%)",
  default: "linear-gradient(135deg, #16191d 0%, #2a2f36 60%, #4a525c 150%)",
};

// Derive a loose category from the fields the API actually returns, used to pick
// the card's accent gradient and the small badge in the card header.
export function carCategory(car) {
  const fuel = (car.engine_fuel_type || "").toLowerCase();
  const style = (car.vehicle_style || "").toLowerCase();
  if (fuel.includes("electric")) return "electric";
  if ((car.engine_hp ?? 0) >= 400 || /coupe|convertible|spyder/.test(style)) return "performance";
  if (fuel.includes("premium")) return "luxury";
  return "default";
}

export function carGradient(car) {
  return GRADIENTS[carCategory(car)] || GRADIENTS.default;
}

// Short, human transmission labels (the API sends SCREAMING_CASE values).
export const TRANSMISSION_LABEL = {
  AUTOMATIC: "Automatic",
  MANUAL: "Manual",
  AUTOMATED_MANUAL: "Automated",
  DIRECT_DRIVE: "Direct",
  UNKNOWN: "—",
};

export const TRANSMISSION_SHORT = {
  AUTOMATIC: "AUTO",
  MANUAL: "MANUAL",
  AUTOMATED_MANUAL: "AUTO-M",
  DIRECT_DRIVE: "DIRECT",
  UNKNOWN: "—",
};
