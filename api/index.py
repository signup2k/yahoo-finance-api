"""
Yahoo Finance API — Vercel Serverless Functions

通过 yfinance 库获取 Yahoo Finance 数据，部署在 Vercel 上。
支持：股票、ETF、指数、基金、商品、外汇、加密货币。
"""

from __future__ import annotations

import os
import time
from collections import OrderedDict
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import yfinance as yf

# ─── App Setup ────────────────────────────────────────────────────────

app = FastAPI(
    title="Yahoo Finance API",
    description="A proxy API for Yahoo Finance data, deployed on Vercel.",
    version="1.0.0",
)

# CORS — allow all origins by default; restrict via env if needed
_allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key from environment variable
_API_KEY = os.environ.get("API_KEY", "")
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PUBLIC_DIR = os.path.join(_ROOT_DIR, "public")

if os.path.isdir(_PUBLIC_DIR):
    app.mount("/static", StaticFiles(directory=_PUBLIC_DIR), name="static")
    _ASSETS_DIR = os.path.join(_PUBLIC_DIR, "assets")
    if os.path.isdir(_ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")


# ─── Auth Middleware ──────────────────────────────────────────────────

@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    """Verify API key for all /api/* endpoints (skip docs & health)."""
    path = request.url.path

    # Skip auth for the dashboard, docs, openapi, and health.
    if path in ("/", "/docs", "/redoc", "/openapi.json", "/api/health") or path.startswith(("/static/", "/assets/")):
        return await call_next(request)

    # Only /api/* endpoints are protected.
    if not path.startswith("/api/"):
        return await call_next(request)

    # If no API_KEY configured, skip auth entirely.
    if not _API_KEY:
        return await call_next(request)

    # Check header
    key = request.headers.get("X-API-Key", "")
    if key != _API_KEY:
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or missing API key"},
        )

    return await call_next(request)


# ─── Helper Functions ─────────────────────────────────────────────────

MAX_SYMBOLS = 20
HISTORY_CACHE_TTL_SECONDS = int(os.environ.get("HISTORY_CACHE_TTL_SECONDS", "3600"))
HISTORY_CACHE_MAX_ITEMS = int(os.environ.get("HISTORY_CACHE_MAX_ITEMS", "512"))
_history_cache: OrderedDict[tuple[str, str, str, str], tuple[float, list[dict]]] = OrderedDict()


def _parse_symbols(symbols: str) -> list[str]:
    """Parse comma-separated symbols string into a list."""
    return [s.strip().upper() for s in symbols.split(",") if s.strip()]


def _safe_serialize(obj):
    """Convert non-serializable types for JSON output."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    return str(obj)


def _clean_json_value(value: object) -> object:
    """Convert pandas/numpy values and NaN-like values into JSON-safe values."""
    if value is None or str(value) in ("nan", "NaT", "<NA>"):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return _clean_json_value(value.item())
    if isinstance(value, dict):
        return {str(k): _clean_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_json_value(v) for v in value]
    return value


def _dataframe_to_records(df: object) -> list[dict[str, object]]:
    """Serialize a yfinance DataFrame with its period index restored as a column."""
    if df is None or getattr(df, "empty", True):
        return []

    records_df = df.reset_index()
    if "index" in records_df.columns and "period" not in records_df.columns:
        records_df = records_df.rename(columns={"index": "period"})

    records = []
    for row in records_df.to_dict(orient="records"):
        records.append({str(k): _clean_json_value(v) for k, v in row.items()})
    return records


def _get_history_cache(key: tuple[str, str, str, str]) -> Optional[list[dict]]:
    """Return cached history records when the in-memory entry is still fresh."""
    if HISTORY_CACHE_TTL_SECONDS <= 0:
        return None

    cached = _history_cache.get(key)
    if not cached:
        return None

    saved_at, records = cached
    if time.time() - saved_at > HISTORY_CACHE_TTL_SECONDS:
        _history_cache.pop(key, None)
        return None

    _history_cache.move_to_end(key)
    return records


def _set_history_cache(key: tuple[str, str, str, str], records: list[dict]) -> None:
    """Store a small in-memory cache for warm serverless/runtime instances."""
    if HISTORY_CACHE_TTL_SECONDS <= 0:
        return

    _history_cache[key] = (time.time(), records)
    _history_cache.move_to_end(key)
    while len(_history_cache) > HISTORY_CACHE_MAX_ITEMS:
        _history_cache.popitem(last=False)


# ─── Endpoints ────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Serve the dashboard when available; otherwise return service info."""
    index_path = os.path.join(_PUBLIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {
        "service": "Yahoo Finance API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/api/health",
            "/api/history",
            "/api/quote",
            "/api/info",
            "/api/search",
            "/api/dividends",
            "/api/splits",
            "/api/earnings-estimates",
        ],
    }


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/history")
def history(
    symbols: str = Query(..., description="Comma-separated ticker symbols, e.g. AAPL,MSFT,^GSPC"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD). Defaults to 1 year ago."),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD). Defaults to today."),
    interval: str = Query("1d", description="Data interval: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo"),
):
    """
    Get OHLCV historical price data.

    Supports all Yahoo Finance ticker formats:
    - Stocks: AAPL, 0700.HK
    - ETFs: SPY, QQQ
    - Indices: ^GSPC, ^IXIC, ^HSI
    - Commodities: GC=F (Gold), CL=F (Oil)
    - Forex: EURUSD=X, JPYUSD=X
    - Crypto: BTC-USD, ETH-USD
    """
    tickers = _parse_symbols(symbols)
    if not tickers:
        raise HTTPException(status_code=400, detail="No valid symbols provided")
    if len(tickers) > MAX_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_SYMBOLS} symbols per request")

    end_date = end or date.today().isoformat()
    start_date = start or (date.today() - timedelta(days=365)).isoformat()

    all_data = []

    for symbol in tickers:
        cache_key = (symbol, start_date, end_date, interval)
        cached_records = _get_history_cache(cache_key)
        if cached_records is not None:
            all_data.extend(cached_records)
            continue

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)

            if df.empty:
                records = [{"symbol": symbol, "error": "No data available for the given range"}]
                _set_history_cache(cache_key, records)
                all_data.extend(records)
                continue

            df = df.reset_index()
            date_col = "Date" if "Date" in df.columns else "Datetime"
            df = df.rename(columns={
                date_col: "trade_date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            df["symbol"] = symbol
            cols = ["symbol", "trade_date", "open", "high", "low", "close", "volume"]
            records = df[cols].to_dict(orient="records")
            for r in records:
                r["trade_date"] = _safe_serialize(r["trade_date"])
                for k in ("open", "high", "low", "close", "volume"):
                    if r[k] is not None:
                        r[k] = _safe_serialize(r[k])
            _set_history_cache(cache_key, records)
            all_data.extend(records)
        except Exception as e:
            all_data.append({"symbol": symbol, "error": str(e)})

    return {"count": len(all_data), "data": all_data}


@app.get("/api/quote")
def quote(
    symbols: str = Query(..., description="Comma-separated ticker symbols"),
):
    """
    Get real-time quote data (price, change, volume, market cap, etc.).
    """
    tickers = _parse_symbols(symbols)
    if not tickers:
        raise HTTPException(status_code=400, detail="No valid symbols provided")
    if len(tickers) > MAX_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_SYMBOLS} symbols per request")

    results = []
    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info

            result = {
                "symbol": symbol,
                "last_price": getattr(info, "last_price", None),
                "previous_close": getattr(info, "previous_close", None),
                "open": getattr(info, "open", None),
                "day_high": getattr(info, "day_high", None),
                "day_low": getattr(info, "day_low", None),
                "volume": getattr(info, "last_volume", None),
                "market_cap": getattr(info, "market_cap", None),
                "fifty_day_average": getattr(info, "fifty_day_average", None),
                "two_hundred_day_average": getattr(info, "two_hundred_day_average", None),
                "currency": getattr(info, "currency", None),
                "exchange": getattr(info, "exchange", None),
                "timezone": getattr(info, "timezone", None),
            }
            # Clean up numpy/NaN values
            result = {
                k: (_safe_serialize(v) if v is not None and str(v) != "nan" else None)
                for k, v in result.items()
            }
            results.append(result)
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})

    return {"count": len(results), "data": results}


@app.get("/api/earnings-estimates")
def earnings_estimates(
    symbols: str = Query(..., description="Comma-separated ticker symbols"),
):
    """
    Get earningsTrend-derived analyst estimate tables.

    Returns the four yfinance tables sourced from Yahoo Finance's
    earningsTrend module: earnings_estimate, revenue_estimate, eps_trend,
    and eps_revisions.
    """
    tickers = _parse_symbols(symbols)
    if not tickers:
        raise HTTPException(status_code=400, detail="No valid symbols provided")
    if len(tickers) > MAX_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_SYMBOLS} symbols per request")

    results = []
    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            results.append({
                "symbol": symbol,
                "earnings_estimate": _dataframe_to_records(ticker.earnings_estimate),
                "revenue_estimate": _dataframe_to_records(ticker.revenue_estimate),
                "eps_trend": _dataframe_to_records(ticker.eps_trend),
                "eps_revisions": _dataframe_to_records(ticker.eps_revisions),
            })
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})

    return {"count": len(results), "data": results}


@app.get("/api/info")
def info(
    symbol: str = Query(..., description="Single ticker symbol, e.g. AAPL"),
):
    """
    Get detailed asset information (name, sector, industry, description, etc.).
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    try:
        ticker = yf.Ticker(symbol)
        raw_info = ticker.info

        if not raw_info or len(raw_info) <= 1:
            raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")

        # Serialize all values
        cleaned = {}
        for k, v in raw_info.items():
            if v is None or (isinstance(v, float) and str(v) == "nan"):
                cleaned[k] = None
            elif hasattr(v, "isoformat"):
                cleaned[k] = v.isoformat()
            elif hasattr(v, "item"):
                cleaned[k] = v.item()
            else:
                cleaned[k] = v

        return {"symbol": symbol, "data": cleaned}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch info for {symbol}: {str(e)}")


@app.get("/api/search")
def search(
    query: str = Query(..., description="Search query, e.g. 'Apple' or 'AAPL'"),
    max_results: int = Query(10, description="Maximum number of results", ge=1, le=50),
):
    """
    Search for Yahoo Finance tickers by name or symbol.
    """
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    try:
        results = yf.Search(query)

        quotes = []
        if hasattr(results, "quotes") and results.quotes:
            for q in results.quotes[:max_results]:
                quotes.append({
                    "symbol": q.get("symbol", ""),
                    "name": q.get("shortname") or q.get("longname", ""),
                    "exchange": q.get("exchange", ""),
                    "type": q.get("quoteType", ""),
                    "score": q.get("score", 0),
                })

        news = []
        if hasattr(results, "news") and results.news:
            for n in results.news[:5]:
                news.append({
                    "title": n.get("title", ""),
                    "publisher": n.get("publisher", ""),
                    "link": n.get("link", ""),
                    "published": n.get("providerPublishTime", ""),
                })

        return {"query": query, "quotes": quotes, "news": news}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/api/dividends")
def dividends(
    symbol: str = Query(..., description="Single ticker symbol"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Get dividend history for a ticker.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    try:
        ticker = yf.Ticker(symbol)
        divs = ticker.dividends

        if divs.empty:
            return {"symbol": symbol, "count": 0, "data": []}

        # Filter by date range if provided
        if start:
            divs = divs[divs.index >= start]
        if end:
            divs = divs[divs.index <= end]

        data = [
            {"date": idx.isoformat(), "dividend": float(val)}
            for idx, val in divs.items()
        ]

        return {"symbol": symbol, "count": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dividends: {str(e)}")


@app.get("/api/splits")
def splits(
    symbol: str = Query(..., description="Single ticker symbol"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Get stock split history for a ticker.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    try:
        ticker = yf.Ticker(symbol)
        sp = ticker.splits

        if sp.empty:
            return {"symbol": symbol, "count": 0, "data": []}

        if start:
            sp = sp[sp.index >= start]
        if end:
            sp = sp[sp.index <= end]

        data = [
            {"date": idx.isoformat(), "ratio": float(val)}
            for idx, val in sp.items()
        ]

        return {"symbol": symbol, "count": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch splits: {str(e)}")
