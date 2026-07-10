# File Map

> Per-file index for AI agents. Read the relevant entry BEFORE opening a file;
> read only the line ranges the entry points to. Update entries after structural
> changes (see the repo-map skill).
> Last full audit: 2026-07-10 | Files mapped: 6

## API

### api/index.py (~765 lines, py, map-updated 2026-07-10)

Purpose: FastAPI application that serves the dashboard and all Yahoo Finance-backed API endpoints on Vercel.
Structure:

- middleware and service setup (L20): CORS, API-key validation, static assets.
- request-budget, history-window, serialization, and cache helpers (L90).
- `/api/history` (L422): validates and downloads OHLCV data with a 200-symbol safety cap and row budgets.
- quote, earnings, info, search, dividends, and splits endpoints (L524).
Depends on: `fastapi`, `yfinance`; deployed through `vercel.json`.
Gotchas: history row estimates use full calendar duration, so intraday budgets are deliberately conservative for mixed asset classes.

## Tests

### tests/test_api_limits.py (~70 lines, py, map-updated 2026-07-10)

Purpose: verifies symbol-count and history data-point request limits without calling Yahoo Finance.
Structure: boundary tests cover 200/201 symbols, a short 21-symbol history request, `max_points=0`, and the default history row budget.
Depends on: `pytest`, FastAPI `TestClient`, and `api/index.py`.

## Deployment and dependencies

### vercel.json (~15 lines, json, map-updated 2026-07-10)

Configures `api/index.py` as the Vercel Python build and routes every path to it.

### requirements.txt (~2 lines, text, map-updated 2026-07-10)

Declares broad FastAPI and yfinance version ranges for the Vercel Python runtime.

### package.json (~20 lines, json, map-updated 2026-07-10)

Declares the React/Vite/ECharts frontend build, development, and type-check commands.

## Documentation

### README.md (~143 lines, md, map-updated 2026-07-10)

Documents endpoints, local development, Vercel deployment, the 200-symbol safety cap, and data-point budgets.

## Unmapped

- `.gitignore`
- `index.html`
- `public/index.html`
- `src/main.tsx`
- `src/styles.css`
- `tsconfig.json`
- `vite.config.ts`
- generated `package-lock.json` and `public/assets/`
