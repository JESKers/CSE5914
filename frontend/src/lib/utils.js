// Tiny className joiner (shadcn-style `cn`, dependency-free).
export function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}

// Format an MSRP number as USD.
export function formatPrice(value) {
  if (value == null) return "—";
  return "$" + Number(value).toLocaleString("en-US", { maximumFractionDigits: 0 });
}
