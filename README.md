# Yahoo Finance API

A lightweight API proxy for Yahoo Finance data, deployed on **Vercel** as Python Serverless Functions.

Supports: **Stocks, ETFs, Indices, Mutual Funds, Commodities, Forex, and Crypto**.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info & endpoint list |
| `/api/health` | GET | Health check |
| `/api/history` | GET | OHLCV historical price data |
| `/api/quote` | GET | Real-time quotes |
| `/api/info` | GET | Detailed asset information |
| `/api/search` | GET | Search tickers by name/symbol |
| `/api/dividends` | GET | Dividend history |
| `/api/splits` | GET | Stock split history |
| `/api/earnings-estimates` | GET | EarningsTrend-derived analyst estimate tables |

## Quick Examples

### Get Historical Prices
```bash
curl "https://your-app.vercel.app/api/history?symbols=AAPL,MSFT&start=2025-01-01&end=2025-12-31" \
  -H "X-API-Key: your-api-key"
```

`/api/history` batches symbols through `yfinance.download`. Multi-symbol endpoints accept at most 200 unique symbols per request, while history requests are additionally limited by estimated/returned data rows. Use `max_points` to lower the per-request row budget when needed:

```bash
curl "https://your-app.vercel.app/api/history?symbols=AAPL,MSFT,NVDA&interval=1d&max_points=5000" \
  -H "X-API-Key: your-api-key"
```

### Get Real-time Quote
```bash
curl "https://your-app.vercel.app/api/quote?symbols=AAPL,^GSPC,GC=F,EURUSD=X" \
  -H "X-API-Key: your-api-key"
```

### Get Asset Info
```bash
curl "https://your-app.vercel.app/api/info?symbol=AAPL" \
  -H "X-API-Key: your-api-key"
```

### Search Tickers
```bash
curl "https://your-app.vercel.app/api/search?query=Apple" \
  -H "X-API-Key: your-api-key"
```

### Get Earnings Estimates
```bash
curl "https://your-app.vercel.app/api/earnings-estimates?symbols=AAPL,MSFT" \
  -H "X-API-Key: your-api-key"
```

### Supported Ticker Formats
| Type | Examples |
|------|----------|
| US Stocks | `AAPL`, `MSFT`, `GOOGL` |
| HK Stocks | `0700.HK`, `9988.HK` |
| ETFs | `SPY`, `QQQ`, `VTI` |
| Indices | `^GSPC`, `^IXIC`, `^HSI` |
| Commodities | `GC=F` (Gold), `CL=F` (Oil), `SI=F` (Silver) |
| Forex | `EURUSD=X`, `JPYUSD=X`, `GBPUSD=X` |
| Crypto | `BTC-USD`, `ETH-USD` |

## Deployment

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USER/yahoo-finance-api.git
git push -u origin main
```

### 2. Deploy on Vercel
1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repository
3. Vercel auto-detects the Python project
4. Click **Deploy**

### 3. Set Environment Variables
In Vercel Dashboard → Project Settings → Environment Variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `API_KEY` | API authentication key | Optional (if empty, auth is disabled) |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | Optional (defaults to `*`) |
| `MAX_SYMBOLS_PER_REQUEST` | Maximum unique symbols accepted by a multi-symbol endpoint | Optional (defaults to `200`) |
| `MAX_HISTORY_DATA_POINTS` | Maximum estimated/returned `/api/history` OHLCV rows per request | Optional (defaults to `20000`) |
| `MAX_QUOTE_ROWS` | Maximum `/api/quote` result rows per request | Optional (defaults to `500`) |
| `MAX_EARNINGS_ESTIMATE_ROWS` | Maximum earnings-estimate table rows per request; each symbol is budgeted as 16 rows | Optional (defaults to `2000`) |
| `HISTORY_CACHE_TTL_SECONDS` | In-memory `/api/history` cache TTL | Optional (defaults to `3600`) |
| `HISTORY_CACHE_MAX_ITEMS` | Maximum history cache entries per warm runtime | Optional (defaults to `512`) |

## Upstream Limits

This API uses yfinance on top of Yahoo Finance's public endpoints. yfinance supports batch historical downloads with `tickers` as a string or list and threaded downloading. The practical limits are mainly request volume, Yahoo rate limiting, and interval/date availability:

- Intraday history is limited by Yahoo/yfinance lookback windows.
- `1m` history is constrained to roughly the last 8 days.
- `2m`, `5m`, `15m`, `30m`, and `90m` history are constrained to roughly the last 60 days.
- `60m`/`1h` history is constrained to roughly the last 730 days.
- Daily and coarser intervals can request longer history, subject to the row budget and Yahoo availability.

## Local Development

```bash
pip install -r requirements.txt
npm install
npm run build
API_KEY=this_is_awesome_yfinance uvicorn api.index:app --reload --port 8000
```

Then visit:

- `http://localhost:8000/` for the multi-asset dashboard
- `http://localhost:8000/docs` for interactive API documentation

## Dashboard

The root page serves a React + Vite + ECharts research-style web app:

- Normalized multi-asset price chart. Changing the time window automatically rebases each selected asset to `100` or `1` at the first available close inside that window.
- Rolling correlation view. Enter a window length in trading days to calculate pairwise return correlations, with a latest-correlation heatmap and a selectable asset-pair history chart.
- Interactive SVG charts with tooltips, legends, zoom controls, and hover emphasis.
- Client-side history cache in `localStorage` so browser refreshes do not immediately re-request the API for the same symbol/range/window.
- Server-side in-memory history cache so repeated API calls avoid reloading the same Yahoo Finance data during the cache TTL.
- Default assets: `SPY,QQQ,TLT,GLD,USO,BTC-USD`. Any Yahoo Finance symbols supported by `/api/history` can be used.

## Tech Stack

- **Runtime**: Python 3.12+ on Vercel Serverless Functions
- **Framework**: FastAPI
- **Frontend**: React, Vite, TypeScript
- **Charts**: ECharts with SVG rendering
- **Data Source**: yfinance (Yahoo Finance)
