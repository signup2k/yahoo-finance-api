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

## Quick Examples

### Get Historical Prices
```bash
curl "https://your-app.vercel.app/api/history?symbols=AAPL,MSFT&start=2025-01-01&end=2025-12-31" \
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

## Local Development

```bash
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000
```

Then visit `http://localhost:8000/docs` for interactive API documentation.

## Tech Stack

- **Runtime**: Python 3.12+ on Vercel Serverless Functions
- **Framework**: FastAPI
- **Data Source**: yfinance (Yahoo Finance)
