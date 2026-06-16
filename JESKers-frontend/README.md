# JESKers — Smart Car Recommendation System (Frontend)

CSE 5914 Capstone · Team JESKers · Timebox 2 · Frontend by Shangrui Gao

## Run

> Requires [Node.js](https://nodejs.org) (LTS). Cannot be opened by double-clicking `index.html`.

```bash
npm install     # first time only
npm run dev
```

Opens at `http://localhost:5173`. Runs on mock data by default — no backend needed.

## Connect to backend

Create a `.env` file:

```env
VITE_API_BASE=/api
VITE_PROXY_TARGET=http://localhost:8000
```

Restart `npm run dev`. Frontend auto-switches to live Elasticsearch data.

## Search fields

Brand · Model · Year · Price · Horsepower · Engine type · Transmission · Keywords

## Stack

React 18 · Vite 5 · Framer Motion
