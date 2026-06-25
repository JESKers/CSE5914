// Numbered pager with prev/next, bound to the API's page/size params.
// Collapses long ranges with "…" gaps around the current page.
function pageList(current, count) {
  if (count <= 7) return Array.from({ length: count }, (_, i) => i + 1);
  const pages = new Set([1, count, current, current - 1, current + 1]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= count).sort((a, b) => a - b);
  const out = [];
  let prev = 0;
  for (const p of sorted) {
    if (p - prev > 1) out.push("…");
    out.push(p);
    prev = p;
  }
  return out;
}

export default function Pagination({ page, size, total, onPage }) {
  const count = Math.max(1, Math.ceil((total ?? 0) / size));
  if (count <= 1) return null;
  const pages = pageList(page, count);

  return (
    <div className="pager">
      <button
        className="pager__nav"
        type="button"
        disabled={page === 1}
        onClick={() => onPage(page - 1)}
      >
        ← Prev
      </button>
      <div className="pager__pages">
        {pages.map((p, i) =>
          p === "…" ? (
            <span className="pager__gap" key={`gap-${i}`}>
              …
            </span>
          ) : (
            <button
              key={p}
              type="button"
              className={`pager__page ${p === page ? "pager__page--on" : ""}`}
              onClick={() => onPage(p)}
            >
              {p}
            </button>
          )
        )}
      </div>
      <button
        className="pager__nav"
        type="button"
        disabled={page === count}
        onClick={() => onPage(page + 1)}
      >
        Next →
      </button>
    </div>
  );
}
