# Frontend — JESKers Car Search (Owner: Shangrui)

React + Vite + Tailwind. Currently **static mockups** rendering against
`public/mock_response.json` — no backend required yet.

## Run

```bash
npm install
npm run dev        # http://localhost:5173
npm run lint       # ESLint (flat config)
npm run format     # Prettier
```

`vite.config.js` proxies `/api/*` → `http://localhost:8000`, so once the backend
is live, swap the mock `fetch("/mock_response.json")` calls for `fetch("/api/search?...")`
and `fetch("/api/recommend", { method: "POST", ... })`.

## Mockups (the three required views)

| # | View | Component(s) | Maps to |
|---|------|--------------|---------|
| 1 | Search bar + filter panel | `SearchBar`, `FilterPanel` | `GET /search`, `GET /facets` |
| 2 | Results grid with car cards | `ResultsGrid`, `CarCard` | response envelope `results[]` |
| 3 | Recommendation / chat input | `RecommendBox` | `POST /recommend` |

Routes: `/` (search) and `/recommend`.

## Structure

```
src/
  components/ui/   shadcn-style primitives (Button, Card, Input/Select)
  components/      SearchBar, FilterPanel, CarCard, ResultsGrid, RecommendBox
  pages/           SearchPage, RecommendPage
  lib/utils.js     cn() + formatPrice()
public/mock_response.json   sample data matching docs/API_CONTRACT.md
```

The UI primitives are hand-written in shadcn style (no generator) to stay
dependency-light. To adopt full shadcn/ui later: `npx shadcn@latest init`.

## Contract

All shapes follow [../docs/API_CONTRACT.md](../docs/API_CONTRACT.md):
envelope `{ results, total, query_echo }`, Car object fields, query params.
