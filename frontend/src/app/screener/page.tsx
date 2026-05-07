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
  };
  return maps[key]?.[display] ?? display;
}

const selectClass = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-xs font-mono text-foreground focus:outline-none focus:ring-2 focus:ring-accent/40 transition-colors appearance-none cursor-pointer";

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
      "market_cap_range", "beta_range", "daily_change", "sector", "volume_range",
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
      const res = await fetch(`/api/screener/scan?offset=${off}&limit=30`, {
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
    <div className="min-h-screen bg-background px-4 py-6 md:px-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">Screener</h1>
        <p className="mt-1 text-sm text-foreground/50 font-mono">Escáner de Mercado Institucional</p>
      </header>

      {/* Filter Panel */}
      <section className="mb-6 rounded-xl border border-border bg-surface p-5">
        {/* Single Ticker Search */}
        <div className="mb-5 flex items-end gap-3">
          <div className="flex-1 max-w-xs">
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">
              Buscar Ticker
            </label>
            <input
              type="text" value={filters.specific_ticker}
              onChange={e => setFilter("specific_ticker", e.target.value.toUpperCase())}
              onKeyDown={e => e.key === "Enter" && doScan(0)}
              placeholder="AAPL, TSLA, NVDA..."
              maxLength={10}
              className="w-full rounded-lg border border-accent/30 bg-background px-3 py-2 text-sm font-bold font-mono text-foreground placeholder:text-foreground/20 focus:outline-none focus:ring-2 focus:ring-accent/50"
            />
          </div>
          <button onClick={() => doScan(0)} disabled={scanning}
            className="rounded-lg bg-accent px-6 py-2 text-sm font-bold text-accent-foreground hover:bg-accent/90 disabled:opacity-50 font-mono h-[38px]">
            {scanning ? "Escaneando..." : "Escanear"}
          </button>
          <button onClick={resetFilters}
            className="rounded-lg border border-border px-4 py-2 text-xs font-mono text-foreground/50 hover:text-foreground hover:border-foreground/20 transition-colors h-[38px]">
            Reset
          </button>
        </div>

        {/* Filter Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {/* RSI — operador libre + valor */}
          <div className="lg:col-span-2">
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">
              RSI (14)
            </label>
            <div className="flex gap-1.5">
              <select
                value={filters.rsi_operator}
                onChange={e => setFilter("rsi_operator", e.target.value)}
                className={`w-28 ${selectClass}`}
                title="Seleccionar operador: ≤ (menor o igual) o ≥ (mayor o igual)"
              >
                <option value="">Todos</option>
                <option value="<=">≤ (Sobrv.)</option>
                <option value=">=">≥ (Sobrcp.)</option>
              </select>
              <input
                type="number"
                value={filters.rsi_value}
                onChange={e => setFilter("rsi_value", e.target.value)}
                placeholder="0-100"
                min="0" max="100" step="1"
                disabled={!filters.rsi_operator}
                className={`flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs font-mono text-foreground placeholder:text-foreground/20 focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-30`}
              />
            </div>
          </div>

          {/* MACD */}
          <div>
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">MACD</label>
            <select value={filters.macd_signal} onChange={e => setFilter("macd_signal", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.macd_signal.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* EMA 200 */}
          <div>
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">EMA 200</label>
            <select value={filters.ema_200} onChange={e => setFilter("ema_200", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.ema_200.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Volumen Relativo (RVOL) */}
          <div>
            <label
              className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5"
              title="RVOL = Volumen actual ÷ Promedio 20 días. 1 = promedio ±5%. <1 = menor que promedio. >1.5 = pico de actividad."
            >
              Volumen (RVOL)
            </label>
            <select value={filters.volume_range} onChange={e => setFilter("volume_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.volume_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* P/E */}
          <div>
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">P/E Ratio</label>
            <select value={filters.pe_range} onChange={e => setFilter("pe_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.pe_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* P/S */}
          <div>
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">P/S Ratio</label>
            <select value={filters.ps_range} onChange={e => setFilter("ps_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.ps_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Market Cap */}
          <div>
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">Cap. Mercado</label>
            <select value={filters.market_cap_range} onChange={e => setFilter("market_cap_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.market_cap_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Beta */}
          <div>
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">Volatilidad (Beta)</label>
            <select value={filters.beta_range} onChange={e => setFilter("beta_range", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.beta_range.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Daily Change */}
          <div>
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">Variación Diaria</label>
            <select value={filters.daily_change} onChange={e => setFilter("daily_change", e.target.value)} className={selectClass}>
              <option value="">Todos</option>
              {SELECT_OPTIONS.daily_change.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Sector */}
          <div className="lg:col-span-2">
            <label className="block text-[10px] font-bold text-foreground/40 uppercase tracking-wider font-mono mb-1.5">Sector</label>
            <select value={filters.sector} onChange={e => setFilter("sector", e.target.value)} className={selectClass}>
              <option value="">Todos los sectores</option>
              {SELECT_OPTIONS.sector.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
        </div>

        {error && <p className="mt-3 text-xs font-mono text-[var(--negative)]">{error}</p>}
      </section>

      {/* Loading */}
      {scanning && (
        <div className="rounded-xl border border-border bg-surface px-6 py-16 text-center animate-pulse">
          <p className="text-sm font-bold text-foreground/40 uppercase tracking-widest font-mono">
            Descargando y calculando indicadores...
          </p>
          <p className="mt-2 text-xs text-foreground/20 font-mono">~15 segundos por chunk de 30 tickers</p>
        </div>
      )}

      {/* Results Table */}
      {!scanning && results && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-mono text-foreground/50">{results.count} resultado{results.count !== 1 ? "s" : ""}</span>
          </div>

          {results.count === 0 ? (
            <div className="rounded-xl border border-border bg-surface px-6 py-16 text-center">
              <p className="text-sm font-mono text-foreground/30">Ningún ticker cumple los filtros seleccionados</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-border bg-surface">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-border text-foreground/40 text-[10px] uppercase tracking-wider">
                    <th className="px-3 py-2.5 sticky left-0 bg-surface z-10">Ticker / Nombre</th>
                    <th className="px-3 py-2.5 whitespace-nowrap">Sector / Industria</th>
                    <th className="px-3 py-2.5 text-right whitespace-nowrap">Precio</th>
                    <th className="px-3 py-2.5 text-right whitespace-nowrap">Cambio</th>
                    <th className="px-3 py-2.5 text-center">RSI</th>
                    <th className="px-3 py-2.5 text-center">MACD</th>
                    <th className="px-3 py-2.5 text-center whitespace-nowrap">vs EMA200</th>
                    <th className="px-3 py-2.5 text-center" title="Volumen Relativo: volumen actual ÷ promedio 20 días. 1 = promedio.">RVOL</th>
                    <th className="px-3 py-2.5 text-right">P/E</th>
                    <th className="px-3 py-2.5 text-right">P/S</th>
                    <th className="px-3 py-2.5 text-right whitespace-nowrap">Cap. M.</th>
                    <th className="px-3 py-2.5 text-right">Beta</th>
                    <th className="px-3 py-2.5 text-right whitespace-nowrap">Analistas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {results.results.map(r => {
                    const rsiC = r.rsi == null ? "text-foreground/20" : r.rsi < 30 ? "text-[var(--positive)] font-bold" : r.rsi > 70 ? "text-[var(--negative)] font-bold" : r.rsi < 40 ? "text-[var(--positive)]" : r.rsi > 60 ? "text-[var(--negative)]" : "text-foreground/60";
                    const chg = r.daily_change_pct;
                    const chgC = chg == null ? "text-foreground/20" : chg >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
                    const emaC = r.ema_200_diff_pct == null ? "text-foreground/20" : r.ema_200_diff_pct > 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";
                    const betaC = r.beta ? (r.beta > 1.5 ? "text-[var(--negative)]" : r.beta < 0.8 ? "text-[var(--positive)]" : "text-foreground/60") : "text-foreground/20";
                    return (
                      <tr key={r.ticker} className="hover:bg-foreground/[0.02] transition-colors">
                        <td className="px-3 py-2.5 sticky left-0 bg-surface">
                          <Link href={`/asset/${r.ticker}`} className="text-foreground font-bold hover:text-accent transition-colors text-xs">{r.ticker}</Link>
                          {r.name && <div className="text-[10px] text-foreground/30 truncate max-w-[130px] mt-0.5">{r.name}</div>}
                        </td>
                        <td className="px-3 py-2.5">
                          {r.sector && r.sector !== "Unknown" ? (
                            <div>
                              <div className="text-foreground/60 truncate max-w-[130px]">{r.sector}</div>
                              {r.industry && r.industry !== "Unknown" && <div className="text-[10px] text-foreground/30 truncate max-w-[130px] mt-0.5">{r.industry}</div>}
                            </div>
                          ) : <span className="text-foreground/20">—</span>}
                        </td>
                        <td className="px-3 py-2.5 text-right text-foreground">{fmtMoney(r.current_price)}</td>
                        <td className={`px-3 py-2.5 text-right font-bold ${chgC}`}>
                          {chg != null ? `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%` : "—"}
                        </td>
                        <td className={`px-3 py-2.5 text-center ${rsiC}`}>{r.rsi?.toFixed(1) ?? "—"}</td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={`rounded-md border px-1.5 py-0.5 text-[10px] font-bold leading-none ${r.macd_signal === "Bullish" ? "text-[var(--positive)] border-[var(--positive)]/30 bg-[var(--positive)]/10" : "text-[var(--negative)] border-[var(--negative)]/30 bg-[var(--negative)]/10"}`}>
                            {r.macd_signal === "Bullish" ? "↑ ALC" : "↓ BAJ"}
                          </span>
                        </td>
                        <td className={`px-3 py-2.5 text-center font-bold ${emaC}`}>
                          {r.ema_200_diff_pct != null ? `${r.ema_200_diff_pct >= 0 ? "+" : ""}${r.ema_200_diff_pct.toFixed(1)}%` : "—"}
                        </td>
                        <td className={`px-3 py-2.5 text-center font-bold ${
                          r.rvol == null ? "text-foreground/20"
                          : r.rvol > 1.5 ? "text-[var(--positive)]"
                          : r.rvol > 1.05 ? "text-[var(--positive)]/60"
                          : r.rvol < 0.95 ? "text-foreground/40"
                          : "text-foreground/60"
                        }`} title={r.rvol != null ? `RVOL ${r.rvol.toFixed(2)}x — ${r.rvol >= 0.95 && r.rvol <= 1.05 ? "volumen en promedio" : r.rvol > 1.5 ? "volumen muy alto" : r.rvol > 1 ? "sobre promedio" : "bajo promedio"}` : "Sin datos de volumen"}>
                          {r.rvol != null ? `${r.rvol.toFixed(2)}×` : "—"}
                        </td>
                        <td className="px-3 py-2.5 text-right text-foreground/60">{r.trailing_pe?.toFixed(1) ?? "—"}</td>
                        <td className="px-3 py-2.5 text-right text-foreground/60">{r.price_to_sales?.toFixed(2) ?? "—"}</td>
                        <td className="px-3 py-2.5 text-right text-foreground/50">{fmtCap(r.market_cap)}</td>
                        <td className={`px-3 py-2.5 text-right ${betaC}`}>{r.beta?.toFixed(2) ?? "—"}</td>
                        <td className="px-3 py-2.5 text-right text-foreground/60">
                          {r.target_mean_price ? `$${r.target_mean_price.toFixed(2)}` : "—"}
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
                className="rounded-lg border border-border bg-surface px-6 py-2.5 text-sm font-bold font-mono text-foreground/70 hover:text-foreground hover:border-accent/50 transition-colors disabled:opacity-50">
                {loadingMore ? "Cargando..." : `Cargar 30 más (${results.total - results.offset - 30} restantes)`}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
