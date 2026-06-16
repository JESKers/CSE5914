export default function Pagination({ page, pageCount, onPage }) {
  if (pageCount <= 1) return null

  const pages = []
  for (let i = 1; i <= pageCount; i++) {
    if (i === 1 || i === pageCount || Math.abs(i - page) <= 1) pages.push(i)
    else if (pages[pages.length - 1] !== '…') pages.push('…')
  }

  return (
    <nav className="pager" aria-label="Pagination">
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
          p === '…' ? (
            <span key={`g${i}`} className="pager__gap">
              …
            </span>
          ) : (
            <button
              key={p}
              type="button"
              className={`pager__page ${p === page ? 'pager__page--on' : ''}`}
              onClick={() => onPage(p)}
            >
              {p}
            </button>
          ),
        )}
      </div>
      <button
        className="pager__nav"
        type="button"
        disabled={page === pageCount}
        onClick={() => onPage(page + 1)}
      >
        Next →
      </button>
    </nav>
  )
}
