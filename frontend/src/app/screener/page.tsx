"use client";

import { useState } from "react";
import Link from "next/link";

interface ScreenerResult {
  ticker: string;
  current_price: number;
  rsi: number | null;
  macd_signal: string;
  macd_value: number;
  ema_200_diff_pct: number | null;
  daily_change_pct: number | null;
  name: string;
  sector: string;
  industry: string;
  market_cap: number | null;
  avg_volume: number | null;
  trailing_pe: number | null;
  price_to_sales: number | null;
  target_mean_price: number | null;
  beta: number | null;
  rvol: number | null;
  debt_to_equity: number | null;
}
interface ScanResponse {
  count: number;
  results: ScreenerResult[];
  total: number;
  offset: number;
}

interface Filters {
  specific_ticker: string;
  rsi_operator: string;
  rsi_value: string;
  macd_signal: string;
  ema_200: string;
  pe_range: string;
  ps_range: string;
  market_cap_range: string;
  beta_range: string;
  daily_change: string;
  sector: string;
  volume_range: string;
  debt_to_equity_range: string;
}

const INITIAL_FILTERS: Filters = {
  specific_ticker: "",
  rsi_operator: "",
  rsi_value: "",
  macd_signal: "",
  ema_200: "",
  pe_range: "",
  ps_range: "",
  market_cap_range: "",
  beta_range: "",
  daily_change: "",
  sector: "",
  volume_range: "",
  debt_to_equity_range: "",
};

const SELECT_OPTIONS = {
  macd_signal: ["Alcista", "Bajista"],
  ema_200: ["Sobre EMA 200", "Bajo EMA 200"],
  pe_range: ["< 15 (Valor)", "15-30 (Crecimiento)", "> 30 (Alto)"],
  ps_range: ["< 2", "2-5", "> 5"],
  market_cap_range: ["> 200B (Mega)", "10B-200B (Large)", "< 10B (Mid/Small)"],
  beta_range: ["< 1 (Baja)", "> 1 (Alta)"],
  daily_change: ["Positiva", "Negativa"],
  volume_range: [
    "= 1 (Promedio ±5%)",
    "< 1 (Bajo Promedio)",
    "< 1.5 (Moderado)",
    "> 1.5 (Alto)",
    "> 1 (Sobre Promedio)",
  ],
  sector: [
    "Technology", "Healthcare", "Financial Services", "Consumer Cyclical",
    "Consumer Defensive", "Energy", "Industrials", "Basic Materials",
    "Communication Services", "Real Estate", "Utilities",
  ],
  debt_to_equity_range: ["< 100% (Baja)", "100%-200% (Moderada)", "> 200% (Alta)"],
};

// Map display labels to backend values
function toBackendValue(key: string, display: string): string {
  const maps: Record<string, Record<string, string>> = {
    ema_200: { "Sobre EMA 200": "Sobre", "Bajo EMA 200": "Bajo" },
    pe_range: { "< 15 (Valor)": "< 15", "15-30 (Crecimiento)": "15-30", "> 30 (Alto)": "> 30" },
    market_cap_range: { "> 200B (Mega)": "> 200B", "10B-200B (Large)": "10B-200B", "< 10B (Mid/Small)": "< 10B" },
    beta_range: { "< 1 (Baja)": "< 1", "> 1 (Alta)": "> 1" },
    volume_range: {
      "= 1 (Promedio ±5%)": "= 1",
      "< 1 (Bajo Promedio)": "< 1",
      "< 1.5 (Moderado)": "< 1.5",
      "> 1.5 (Alto)": "> 1.5",
      "> 1 (Sobre Promedio)": "> 1",
    },
    debt_to_equity_range: {
      "< 100% (Baja)": "< 100",
      "100%-200% (Moderada)": "100-200",
      "> 200% (Alta)": "> 200",
    },
  };
  return maps[key]?.[display] ?? display;
}

const selectClass = "w-full rounded-md border border-border/70 bg-surface px-2.5 py-1.5 text-[11px] font-mono text-foreground/80 focus:outline-none focus:border-accent/50 transition-colors appearance-none cursor-pointer";

function screenerFetch(path: string, options?: RequestInit): Promise<Response> {
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const match = typeof document !== "undefined" ? document.cookie.match(/(?:^|;\s*)token=([^;]*)/) : null;
  const headers: Record<string, string> = { ...(options?.headers as Record<string, string> || {}) };
  if (match) headers["Authorization"] = `Bearer ${match[1]}`;
  return fetch(`${base}${path}`, { ...options, headers });
}

export default function ScreenerPage() {
  const [filters, setFilters] = useState<Filters>(INITIAL_FILTERS);
  const [results, setResults] = useState<ScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const setFilter = (key: keyof Filters, val: string) =>
    setFilters(prev => ({ ...prev, [key]: val }));

  const buildPayload = () => {
    const payload: Record<string, string | number | null> = {
      specific_ticker: filters.specific_ticker.trim().toUpperCase() || null,
    };
    // RSI: operador + valor numérico
    payload.rsi_operator = filters.rsi_operator || null;
    payload.rsi_value = filters.rsi_value ? parseFloat(filters.rsi_value) : null;

    const dropdownKeys: (keyof Omit<Filters, "specific_ticker" | "rsi_operator" | "rsi_value">)[] = [
      "macd_signal", "ema_200", "pe_range", "ps_range",
      "market_cap_range", "beta_range", "debt_to_equity_range", "daily_change", "sector", "volume_range",
    ];
    for (const k of dropdownKeys) {
      const val = filters[k];
      payload[k] = val ? toBackendValue(k, val) : null;
    }
    return payload;
  };

  const doScan = async (off = 0, append = false) => {
    off === 0 ? setScanning(true) : setLoadingMore(true);
    setError("");
    try {
      const res = await screenerFetch(`/screener/scan?offset=${off}&limit=30`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data: ScanResponse = await res.json();
      setResults(prev =>
        append && prev ? { ...data, results: [...prev.results, ...data.results] } : data
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al escanear");
    } finally {
      setScanning(false); setLoadingMore(false);
    }
  };

  const resetFilters = () => { setFilters(INITIAL_FILTERS); setResults(null); };

  const fmtMoney = (v: number) => v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
  const fmtCap = (v: number | null) => v ? `$${(v / 1e9).toFixed(1)}B` : "—";
  const fmtVol = (v: number | null) => v ? `${(v / 1e6).toFixed(1)}M` : "—";

  return (
    <div className="min-h-screen bg-background px-4 py-5 md:px-6 max-w-screen-2xl mx-auto">
      <div className="mb-5">
        <h1 className="text-sm font-semibold text-foreground/60 font-mono uppercase tracking-widest">Screener</h1>
      </div>

      {/* Filter Panel */}
      <section className="mb-4 rounded-lg border border-border/50 bg-surface/60 p-4">
        {/* Single Ticker Search */}
        <div className="mb-4 flex items-end gap-2">
          <div className="flex-1 max-w-[180px]">
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">
              Ticker
            </label>
            <input
              type="text" value={filters.specific_ticker}
              onChange={e => setFilter("specific_ticker", e.target.value.toUpperCase())}
              onKeyDown={e => e.key === "Enter" && doScan(0)}
              placeholder="AAPL..."
              maxLength={10}
              className="w-full rounded-md border border-accent/20 bg-background px-2.5 py-1.5 text-[11px] font-bold font-mono text-foreground placeholder:text-foreground/15 focus:outline-none focus:border-accent/60"
            />
          </div>
          <button onClick={() => doScan(0)} disabled={scanning}
            className="rounded-md bg-accent/90 px-4 py-1.5 text-[11px] font-bold text-white hover:bg-accent disabled:opacity-40 font-mono">
            {scanning ? "…" : "Scan"}
          </button>
          <button onClick={resetFilters}
            className="rounded-md border border-border/50 px-3 py-1.5 text-[10px] font-mono text-foreground/30 hover:text-foreground/60 transition-colors">
            ×
          </button>
        </div>

        {/* Filter Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
          {/* RSI */}
          <div className="col-span-2">
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">RSI (14)</label>
            <div className="flex gap-1">
              <select value={filters.rsi_operator} onChange={e => setFilter("rsi_operator", e.target.value)} className="w-28 rounded-md border border-border/70 bg-surface px-2 py-1.5 text-[11px] font-mono text-foreground/80 focus:outline-none focus:border-accent/50 appearance-none cursor-pointer">
                <option value="">Todos</option>
                <option value="<=">≤</option>
                <option value=">=">≥</option>
              </select>
              <input type="number" value={filters.rsi_value} onChange={e => setFilter("rsi_value", e.target.value)}
                placeholder="35" min="0" max="100" step="1" disabled={!filters.rsi_operator}
                className="flex-1 rounded-md border border-border/70 bg-surface px-2 py-1.5 text-[11px] font-mono text-foreground/80 placeholder:text-foreground/20 focus:outline-none focus:border-accent/50 disabled:opacity-30" />
            </div>
          </div>

          {/* MACD */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">MACD</label>
            <select value={filters.macd_signal} onChange={e => setFilter("macd_signal", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.macd_signal.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* EMA 200 */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">EMA 200</label>
            <select value={filters.ema_200} onChange={e => setFilter("ema_200", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.ema_200.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Volume */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1" title="Volumen relativo vs promedio 20d">RVOL</label>
            <select value={filters.volume_range} onChange={e => setFilter("volume_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.volume_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Daily Change */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">Variación</label>
            <select value={filters.daily_change} onChange={e => setFilter("daily_change", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.daily_change.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* P/E */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">P/E</label>
            <select value={filters.pe_range} onChange={e => setFilter("pe_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.pe_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* P/S */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">P/S</label>
            <select value={filters.ps_range} onChange={e => setFilter("ps_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.ps_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Market Cap */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">Cap.</label>
            <select value={filters.market_cap_range} onChange={e => setFilter("market_cap_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.market_cap_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Beta */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">Beta</label>
            <select value={filters.beta_range} onChange={e => setFilter("beta_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.beta_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* D/E (Debt to Equity) */}
          <div>
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1"
                   title="Deuda Total / Patrimonio Neto. <100% = conservador.">
              D/E
            </label>
            <select value={filters.debt_to_equity_range}
                    onChange={e => setFilter("debt_to_equity_range", e.target.value)}
                    className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.debt_to_equity_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Sector */}
          <div className="col-span-2">
            <label className="block text-[9px] font-medium text-foreground/30 uppercase tracking-widest font-mono mb-1">Sector</label>
            <select value={filters.sector} onChange={e => setFilter("sector", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.sector.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
        </div>

        {error && <p className="mt-3 text-[11px] font-mono text-[var(--negative)]">{error}</p>}
      </section>

      {/* Loading */}
      {scanning && (
        <div className="rounded-lg border border-border/40 bg-surface/40 px-6 py-12 text-center">
          <div className="inline-flex items-center gap-2 text-[11px] font-mono text-foreground/30 uppercase tracking-widest">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
            Calculando...
          </div>
        </div>
      )}

      {/* Results Table */}
      {!scanning && results && (
        <section>
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[10px] font-mono text-foreground/30">{results.count} resultado{results.count !== 1 ? "s" : ""}</span>
          </div>

          {results.count === 0 ? (
            <div className="rounded-lg border border-border/40 bg-surface/40 px-6 py-10 text-center">
              <p className="text-[11px] font-mono text-foreground/20">Sin resultados</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border/50">
              <table className="w-full text-left text-[11px] font-mono">
                <thead>
                  <tr className="border-b border-border/40 text-[9px] text-foreground/25 uppercase tracking-wider">
                    <th className="px-3 py-2 sticky left-0 bg-background">Ticker</th>
                    <th className="px-3 py-2">Sector / Industria</th>
                    <th className="px-3 py-2 text-right">Precio</th>
                    <th className="px-3 py-2 text-right">Δ día</th>
                    <th className="px-3 py-2 text-center">RSI</th>
                    <th className="px-3 py-2 text-center">MACD</th>
                    <th className="px-3 py-2 text-center">EMA200</th>
                    <th className="px-3 py-2 text-center">RVOL</th>
                    <th className="px-3 py-2 text-right">P/E</th>
                    <th className="px-3 py-2 text-right">P/S</th>
                    <th className="px-3 py-2 text-right">Cap.</th>
                    <th className="px-3 py-2 text-right">Beta</th>
                    <th className="px-3 py-2 text-right">D/E</th>
                    <th className="px-3 py-2 text-right">Target</th>
                  </tr>
                </thead>
                <tbody>
                  {results.results.map(r => {
                    const rsiC = r.rsi == null ? "text-foreground/20"
                      : r.rsi < 30 ? "text-[var(--positive)]"
                      : r.rsi > 70 ? "text-[var(--negative)]"
                      : r.rsi < 40 ? "text-[var(--positive)]/70"
                      : r.rsi > 60 ? "text-[var(--negative)]/70"
                      : "text-foreground/50";
                    const chg = r.daily_change_pct;
                    const chgC = chg == null ? "text-foreground/20" : chg >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
                    const emaC = r.ema_200_diff_pct == null ? "text-foreground/20" : r.ema_200_diff_pct > 0 ? "text-[var(--positive)]/70" : "text-[var(--negative)]/70";
                    const rvolC = r.rvol == null ? "text-foreground/20"
                      : r.rvol > 1.5 ? "text-[var(--positive)]"
                      : r.rvol > 1.05 ? "text-foreground/50"
                      : r.rvol < 0.95 ? "text-foreground/30"
                      : "text-foreground/50";
                    return (
                      <tr key={r.ticker} className="border-b border-border/20 hover:bg-white/[0.015] transition-colors">
                        <td className="px-3 py-2 sticky left-0 bg-background">
                          <Link href={`/asset/${r.ticker}`} className="font-semibold text-foreground hover:text-accent transition-colors">{r.ticker}</Link>
                          {r.name && <div className="text-[9px] text-foreground/25 truncate max-w-[110px]">{r.name}</div>}
                        </td>
                        <td className="px-3 py-2">
                          <div className="text-foreground/40 truncate max-w-[120px]">{r.sector || "—"}</div>
                          {r.industry && r.industry !== r.sector && <div className="text-[9px] text-foreground/20 truncate max-w-[120px]">{r.industry}</div>}
                        </td>
                        <td className="px-3 py-2 text-right text-foreground/70">{fmtMoney(r.current_price)}</td>
                        <td className={`px-3 py-2 text-right font-medium ${chgC}`}>
                          {chg != null ? `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%` : "—"}
                        </td>
                        <td className={`px-3 py-2 text-center font-medium ${rsiC}`}>{r.rsi?.toFixed(1) ?? "—"}</td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-[9px] font-bold ${r.macd_signal === "Bullish" ? "text-[var(--positive)]/70" : "text-[var(--negative)]/70"}`}>
                            {r.macd_signal === "Bullish" ? "▲" : "▼"}
                          </span>
                        </td>
                        <td className={`px-3 py-2 text-center text-[10px] ${emaC}`}>
                          {r.ema_200_diff_pct != null ? `${r.ema_200_diff_pct >= 0 ? "+" : ""}${r.ema_200_diff_pct.toFixed(1)}%` : "—"}
                        </td>
                        <td className={`px-3 py-2 text-center font-medium ${rvolC}`}
                          title={r.rvol != null ? `RVOL ${r.rvol.toFixed(2)}×` : ""}>
                          {r.rvol != null ? `${r.rvol.toFixed(2)}×` : "—"}
                        </td>
                        <td className="px-3 py-2 text-right text-foreground/40">{r.trailing_pe?.toFixed(1) ?? "—"}</td>
                        <td className="px-3 py-2 text-right text-foreground/40">{r.price_to_sales?.toFixed(1) ?? "—"}</td>
                        <td className="px-3 py-2 text-right text-foreground/30 text-[10px]">{fmtCap(r.market_cap)}</td>
                        <td className={`px-3 py-2 text-right text-[10px] ${r.beta ? (r.beta > 1.5 ? "text-[var(--negative)]/60" : "text-foreground/40") : "text-foreground/20"}`}>
                          {r.beta?.toFixed(2) ?? "—"}
                        </td>
                        <td className={`px-3 py-2 text-right text-[10px] ${r.debt_to_equity == null ? "text-foreground/20"
                          : r.debt_to_equity < 100 ? "text-[var(--positive)]/70"
                          : r.debt_to_equity <= 200 ? "text-foreground/50"
                          : "text-[var(--negative)]/70"}`}>
                          {r.debt_to_equity != null ? `${r.debt_to_equity.toFixed(1)}%` : "—"}
                        </td>
                        <td className="px-3 py-2 text-right text-foreground/40">
                          {r.target_mean_price ? `$${r.target_mean_price.toFixed(0)}` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {!filters.specific_ticker && results.offset + 30 < results.total && (
            <div className="mt-4 flex justify-center">
              <button onClick={() => doScan(results.offset + 30, true)} disabled={loadingMore}
                className="rounded-md border border-border px-4 py-1.5 text-xs font-mono text-foreground/50 hover:text-foreground hover:border-accent/40 transition-colors disabled:opacity-30">
                {loadingMore ? "..." : `+ Más`}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
