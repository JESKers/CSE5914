# Frontend - JESKers Car Search

React and Vite frontend for catalog search, grounded recommendations, the
buy/rent store, and the AI assistant. All data comes from the FastAPI backend
through Vite's `/api` development proxy.

## Run

Start the backend from the repository root, then run:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open http://localhost:5173.

## Quality checks

```powershell
npm.cmd run lint
npm.cmd run build
```

## Routes

- `/` - catalog search with filters, sorting, and pagination
- `/recommend` - grounded natural-language recommendations
- `/store` - vehicle purchase and rental listings
- `/assistant` - conversational search, financing, rentals, and test drives

API response shapes are documented in
[../docs/API_CONTRACT.md](../docs/API_CONTRACT.md).
