import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { HeatmapChart, LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { getInstanceByDom, init, use } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";
import "./styles.css";

use([LineChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, VisualMapComponent, SVGRenderer]);

const API_KEY = "this_is_awesome_yfinance";
const CLIENT_CACHE_TTL_MS = 6 * 60 * 60 * 1000;
const COLORS = ["#0f766e", "#b44c2f", "#2454a6", "#8b6f22", "#7d3f98", "#34495e", "#b0175b", "#2f7d32", "#d17a00", "#51606f"];

type RangeKey = "3m" | "6m" | "1y" | "3y" | "5y" | "ytd";
type HistoryRow = { symbol: string; trade_date: string; close: string | number; error?: string };
type PricePoint = { date: string; close: number };
type SeriesMap = Map<string, PricePoint[]>;
type NormalizedSeries = { symbol: string; rows: Array<{ date: string; value: number; close: number }> };
type ReturnRow = { date: string; [symbol: string]: number | string };
type Pair = { a: string; b: string; key: string };
type RollingMap = Map<string, Array<{ date: string; value: number }>>;

function dateOnly(value: string | Date) {
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value).slice(0, 10);
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function startForRange(range: RangeKey) {
  const now = new Date();
  const start = new Date(now);
  if (range === "3m") start.setMonth(start.getMonth() - 3);
  if (range === "6m") start.setMonth(start.getMonth() - 6);
  if (range === "1y") start.setFullYear(start.getFullYear() - 1);
  if (range === "3y") start.setFullYear(start.getFullYear() - 3);
  if (range === "5y") start.setFullYear(start.getFullYear() - 5);
  if (range === "ytd") return `${now.getFullYear()}-01-01`;
  return dateOnly(start);
}

function fetchStartFor(range: RangeKey, corrWindow: number) {
  return dateOnly(addDays(new Date(startForRange(range)), -Math.max(corrWindow * 3, 120)));
}

function parseSymbols(value: string) {
  return value.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean).slice(0, 20);
}

function readClientCache(key: string): SeriesMap | null {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as { savedAt: number; data: Array<[string, PricePoint[]]> };
    if (Date.now() - parsed.savedAt > CLIENT_CACHE_TTL_MS) {
      localStorage.removeItem(key);
      return null;
    }
    return new Map(parsed.data);
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}

function writeClientCache(key: string, data: SeriesMap) {
  const payload = { savedAt: Date.now(), data: [...data.entries()] };
  try {
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    localStorage.clear();
  }
}

async function fetchHistory(symbols: string[], range: RangeKey, corrWindow: number): Promise<{ series: SeriesMap; fromCache: boolean }> {
  const start = fetchStartFor(range, corrWindow);
  const end = dateOnly(addDays(new Date(), 1));
  const cacheKey = `yf-history:${symbols.join(",")}:${start}:${end}:1d`;
  const cached = readClientCache(cacheKey);
  if (cached) return { series: cached, fromCache: true };

  const params = new URLSearchParams({ symbols: symbols.join(","), start, end, interval: "1d" });
  const response = await fetch(`/api/history?${params}`, { headers: { "X-API-Key": API_KEY } });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  const payload = (await response.json()) as { data: HistoryRow[] };
  const grouped: SeriesMap = new Map(symbols.map((symbol) => [symbol, []]));

  for (const row of payload.data || []) {
    if (row.error || !grouped.has(row.symbol)) continue;
    const close = Number(row.close);
    if (Number.isFinite(close)) grouped.get(row.symbol)?.push({ date: dateOnly(row.trade_date), close });
  }

  for (const [symbol, rows] of grouped.entries()) {
    rows.sort((a, b) => a.date.localeCompare(b.date));
    if (!rows.length) grouped.delete(symbol);
  }

  writeClientCache(cacheKey, grouped);
  return { series: grouped, fromCache: false };
}

function buildNormalized(series: SeriesMap, range: RangeKey, base: number): NormalizedSeries[] {
  const start = startForRange(range);
  return [...series.entries()].map(([symbol, rows]) => {
    const visible = rows.filter((row) => row.date >= start);
    const first = visible.find((row) => row.close > 0);
    return {
      symbol,
      rows: first ? visible.map((row) => ({ date: row.date, value: (row.close / first.close) * base, close: row.close })) : []
    };
  }).filter((item) => item.rows.length > 1);
}

function buildReturns(series: SeriesMap): ReturnRow[] {
  const allDates = [...new Set([...series.values()].flatMap((rows) => rows.map((row) => row.date)))].sort();
  const indexed = new Map([...series.entries()].map(([symbol, rows]) => [symbol, new Map(rows.map((row, index) => [row.date, { row, index }]))]));
  return allDates.map((date) => {
    const record: ReturnRow = { date };
    for (const [symbol, rows] of series.entries()) {
      const hit = indexed.get(symbol)?.get(date);
      if (hit && hit.index > 0 && rows[hit.index - 1].close > 0) {
        record[symbol] = hit.row.close / rows[hit.index - 1].close - 1;
      }
    }
    return record;
  });
}

function corr(xs: number[], ys: number[]) {
  const n = Math.min(xs.length, ys.length);
  if (n < 3) return null;
  const ax = xs.reduce((sum, v) => sum + v, 0) / n;
  const ay = ys.reduce((sum, v) => sum + v, 0) / n;
  let cov = 0;
  let vx = 0;
  let vy = 0;
  for (let i = 0; i < n; i += 1) {
    const dx = xs[i] - ax;
    const dy = ys[i] - ay;
    cov += dx * dy;
    vx += dx * dx;
    vy += dy * dy;
  }
  const denom = Math.sqrt(vx * vy);
  return denom ? cov / denom : null;
}

function buildPairs(symbols: string[], returns: ReturnRow[], window: number) {
  const pairs: Pair[] = [];
  const rolling: RollingMap = new Map();
  for (let i = 0; i < symbols.length; i += 1) {
    for (let j = i + 1; j < symbols.length; j += 1) {
      const a = symbols[i];
      const b = symbols[j];
      const key = `${a}|${b}`;
      pairs.push({ a, b, key });
      const values: Array<{ date: string; value: number }> = [];
      for (let r = 0; r < returns.length; r += 1) {
        const slice = returns.slice(Math.max(0, r - window + 1), r + 1).filter((row) => Number.isFinite(row[a]) && Number.isFinite(row[b]));
        if (slice.length >= Math.max(5, Math.floor(window * 0.65))) {
          const value = corr(slice.map((row) => Number(row[a])), slice.map((row) => Number(row[b])));
          if (Number.isFinite(value)) values.push({ date: String(returns[r].date), value: value as number });
        }
      }
      rolling.set(key, values);
    }
  }
  return { pairs, rolling };
}

function useChart(ref: React.RefObject<HTMLDivElement | null>, option: EChartsOption) {
  useEffect(() => {
    if (!ref.current) return;
    const chart = getInstanceByDom(ref.current) || init(ref.current, undefined, { renderer: "svg" });
    chart.setOption(option, true);
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
    };
  }, [ref, option]);
}

function PriceChart({ data, base }: { data: NormalizedSeries[]; base: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const option = useMemo<EChartsOption>(() => ({
    color: COLORS,
    animationDuration: 350,
    tooltip: { trigger: "axis", valueFormatter: (value) => Number(value).toFixed(2) },
    legend: { top: 0, right: 0, type: "scroll" },
    grid: { left: 52, right: 22, top: 56, bottom: 52 },
    dataZoom: [{ type: "inside" }, { type: "slider", height: 22, bottom: 10 }],
    xAxis: { type: "time" },
    yAxis: { type: "value", scale: true, name: `Base ${base}`, splitLine: { lineStyle: { color: "#e1e5df" } } },
    series: data.map((item) => ({
      name: item.symbol,
      type: "line",
      showSymbol: false,
      emphasis: { focus: "series" },
      data: item.rows.map((row) => [row.date, Number(row.value.toFixed(4))])
    }))
  }), [data, base]);
  useChart(ref, option);
  return <div className="chart tall" ref={ref} />;
}

function Heatmap({ symbols, rolling }: { symbols: string[]; rolling: RollingMap }) {
  const ref = useRef<HTMLDivElement>(null);
  const option = useMemo<EChartsOption>(() => {
    const data: Array<[number, number, number]> = [];
    symbols.forEach((rowSymbol, y) => {
      symbols.forEach((colSymbol, x) => {
        const key = x < y ? `${colSymbol}|${rowSymbol}` : `${rowSymbol}|${colSymbol}`;
        const values = rolling.get(key);
        const latest = x === y ? 1 : values?.[values.length - 1]?.value;
        data.push([x, y, Number.isFinite(latest) ? Number((latest as number).toFixed(3)) : 0]);
      });
    });
    return {
      tooltip: {
        position: "top",
        formatter: (param) => {
          const value = (Array.isArray(param) ? param[0].data : param.data) as number[];
          return `${symbols[value[1]]} / ${symbols[value[0]]}: ${value[2].toFixed(2)}`;
        }
      },
      grid: { left: 72, right: 12, top: 48, bottom: 36 },
      xAxis: { type: "category", data: symbols, splitArea: { show: true }, axisLabel: { rotate: 45 } },
      yAxis: { type: "category", data: symbols, splitArea: { show: true } },
      visualMap: { min: -1, max: 1, calculable: true, orient: "horizontal", left: "center", bottom: 0, inRange: { color: ["#b44c2f", "#f4f0e9", "#0f766e"] } },
      series: [{ type: "heatmap", data, label: { show: true, formatter: ({ value }) => Number((value as number[])[2]).toFixed(2) }, emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,.18)" } } }]
    };
  }, [symbols, rolling]);
  useChart(ref, option);
  return <div className="chart heat" ref={ref} />;
}

function CorrChart({ pairKey, rolling, range }: { pairKey: string; rolling: RollingMap; range: RangeKey }) {
  const ref = useRef<HTMLDivElement>(null);
  const rows = useMemo(() => (rolling.get(pairKey) || []).filter((row) => row.date >= startForRange(range)), [pairKey, range, rolling]);
  const option = useMemo<EChartsOption>(() => ({
    color: ["#0f766e"],
    tooltip: { trigger: "axis", valueFormatter: (value) => Number(value).toFixed(3) },
    grid: { left: 48, right: 16, top: 32, bottom: 52 },
    dataZoom: [{ type: "inside" }, { type: "slider", height: 22, bottom: 8 }],
    xAxis: { type: "time" },
    yAxis: { type: "value", min: -1, max: 1, splitLine: { lineStyle: { color: "#e1e5df" } } },
    series: [{ name: pairKey.replace("|", " / "), type: "line", showSymbol: false, areaStyle: { opacity: 0.08 }, data: rows.map((row) => [row.date, Number(row.value.toFixed(4))]) }]
  }), [pairKey, rows]);
  useChart(ref, option);
  return <div className="chart heat" ref={ref} />;
}

function App() {
  const [symbolsText, setSymbolsText] = useState("SPY,QQQ,TLT,GLD,USO,BTC-USD");
  const [range, setRange] = useState<RangeKey>("1y");
  const [base, setBase] = useState(100);
  const [corrWindow, setCorrWindow] = useState(60);
  const [series, setSeries] = useState<SeriesMap>(new Map());
  const [status, setStatus] = useState("Ready");
  const [pairKey, setPairKey] = useState("");

  const normalized = useMemo(() => buildNormalized(series, range, base), [series, range, base]);
  const returns = useMemo(() => buildReturns(series), [series]);
  const built = useMemo(() => buildPairs([...series.keys()], returns, corrWindow), [series, returns, corrWindow]);
  const pairs = built.pairs;
  const rolling = built.rolling;

  useEffect(() => {
    if (!pairKey && pairs[0]) setPairKey(pairs[0].key);
    if (pairKey && !rolling.has(pairKey) && pairs[0]) setPairKey(pairs[0].key);
  }, [pairKey, pairs, rolling]);

  async function load() {
    const symbols = parseSymbols(symbolsText);
    if (symbols.length < 2) {
      setStatus("Use at least two assets");
      return;
    }
    setStatus("Loading market data");
    try {
      const result = await fetchHistory(symbols, range, corrWindow);
      setSeries(result.series);
      setStatus(`${result.series.size}/${symbols.length} assets updated${result.fromCache ? " from cache" : ""}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load data");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const metrics = normalized.map((item) => {
    const first = item.rows[0];
    const last = item.rows[item.rows.length - 1];
    const change = first && last ? (last.close / first.close - 1) * 100 : 0;
    return { symbol: item.symbol, change, start: first?.date, end: last?.date };
  });

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Yahoo Finance API</p>
          <h1>Multi-Asset Research Dashboard</h1>
        </div>
        <div className="status">{status}</div>
      </header>

      <section className="controls">
        <label className="field wide">
          <span>Assets</span>
          <input value={symbolsText} onChange={(event) => setSymbolsText(event.target.value)} spellCheck={false} />
        </label>
        <label className="field">
          <span>Window</span>
          <select value={range} onChange={(event) => setRange(event.target.value as RangeKey)}>
            <option value="3m">3M</option>
            <option value="6m">6M</option>
            <option value="1y">1Y</option>
            <option value="3y">3Y</option>
            <option value="5y">5Y</option>
            <option value="ytd">YTD</option>
          </select>
        </label>
        <label className="field">
          <span>Base</span>
          <select value={base} onChange={(event) => setBase(Number(event.target.value))}>
            <option value={100}>100</option>
            <option value={1}>1</option>
          </select>
        </label>
        <label className="field">
          <span>Corr Days</span>
          <input type="number" min={5} max={756} value={corrWindow} onChange={(event) => setCorrWindow(Number(event.target.value))} />
        </label>
        <button className="primary" onClick={load}>Refresh</button>
      </section>

      <section className="metrics">
        {metrics.map((item) => (
          <div className="metric" key={item.symbol}>
            <div className="name">{item.symbol}</div>
            <div className="value">{item.change >= 0 ? "+" : ""}{item.change.toFixed(1)}%</div>
            <div className="detail">{item.start} to {item.end}</div>
          </div>
        ))}
      </section>

      <section className="grid">
        <article className="panel line-panel">
          <div className="panel-head">
            <div>
              <p className="chart-label">NDR-style normalized price path</p>
              <h2>Normalized Multi-Asset Trend</h2>
            </div>
          </div>
          <PriceChart data={normalized} base={base} />
        </article>

        <article className="panel corr-panel">
          <div className="panel-head">
            <div>
              <p className="chart-label">BCA-style cross-asset relationship map</p>
              <h2>Rolling Correlation</h2>
            </div>
            <label className="pair-select">
              <span>Pair</span>
              <select value={pairKey} onChange={(event) => setPairKey(event.target.value)}>
                {pairs.map((pair) => <option key={pair.key} value={pair.key}>{pair.a} / {pair.b}</option>)}
              </select>
            </label>
          </div>
          <div className="corr-layout">
            <Heatmap symbols={[...series.keys()]} rolling={rolling} />
            <CorrChart pairKey={pairKey || pairs[0]?.key || ""} rolling={rolling} range={range} />
          </div>
        </article>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
