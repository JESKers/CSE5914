import { useEffect, useState } from "react";

// Returns `value` after it has stopped changing for `delay` ms. Used to throttle
// the keyword box so we don't hit the API on every keystroke.
export function useDebounce(value, delay = 350) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}
