import { Button } from "@/components/ui/button";

// Prev/Next pagination bound to the API's page/size params.
export default function Pagination({ page, size, total, onPage }) {
  const totalPages = Math.max(1, Math.ceil((total ?? 0) / size));
  if (total === 0) return null;
  return (
    <div className="flex items-center justify-center gap-3 pt-4">
      <Button variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ← Prev
      </Button>
      <span className="text-sm text-slate-500">
        Page {page} of {totalPages}
      </span>
      <Button variant="outline" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
        Next →
      </Button>
    </div>
  );
}
