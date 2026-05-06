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
}

interface ScanResponse {
  count: number;
  results: ScreenerResult[];
}

const FILTERS = [
  { key: "rsi_below_40", label: "RSI < 40 (Sobreventa)" },
  { key: "macd_bullish", label: "MACD Alcista" },
  { key: "above_ema_200", label: "Sobre EMA 200" },
  { key: "rsi_above_70", label: "RSI > 70 (Sobrecompra)" },
] as const;

export default function ScreenerPage() {
  const [filters, setFilters] = useState<Record<string, boolean>>({
    rsi_below_40: true,
    macd_bullish: false,
    above_ema_200: false,
    rsi_above_70: false,
  });
  const [results, setResults] = useState<ScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");

  const toggleFilter = (key: string) => {
    setFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleScan = async () => {
    setScanning(true);
    setError("");
    try {
      const res = await fetch("/api/screener/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(filters),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data: ScanResponse = await res.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al escanear");
    } finally {
      setScanning(false);
    }
  };

  const formatMoney = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

  return (
    <div className="min-h-screen bg-background px-4 py-6 md:px-8">
      {/* Header */}
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
            Screener
          </h1>
          <p className="mt-1 text-sm text-foreground/50 font-mono">
            Escáner de Mercado &middot; Universo: 50 tickers
          </p>
        </div>
        <Link
          href="/"
          className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-mono text-foreground/70 hover:text-foreground hover:border-foreground/20 transition-colors"
        >
          ← Dashboard
        </Link>
      </header>

      {/* Filter Toggles */}
      <section className="mb-6 rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-bold text-foreground/50 uppercase tracking-widest font-mono mb-4">
          Filtros Técnicos
        </h2>
        <div className="flex flex-wrap gap-2 mb-4">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => toggleFilter(f.key)}
              className={`rounded-lg border px-4 py-2 text-xs font-bold font-mono transition-colors ${
                filters[f.key]
                  ? "border-accent/50 bg-accent/15 text-accent"
                  : "border-border text-foreground/40 hover:text-foreground/60"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="rounded-lg bg-accent px-6 py-2.5 text-sm font-bold text-accent-foreground hover:bg-accent/90 transition-colors disabled:opacity-50 font-mono"
        >
          {scanning ? "Escaneando..." : "Escanear Mercado"}
        </button>
        {error && (
          <p className="mt-3 text-xs font-mono text-[var(--negative)]">{error}</p>
        )}
      </section>

      {/* Results */}
      {scanning && (
        <div className="rounded-xl border border-border bg-surface px-6 py-16 text-center animate-pulse">
          <p className="text-sm font-bold text-foreground/40 uppercase tracking-widest font-mono">
            Descargando y calculando indicadores...
          </p>
          <p className="mt-2 text-xs text-foreground/20 font-mono">
            Esto puede tomar ~15 segundos (batch download de 50 tickers)
          </p>
        </div>
      )}

      {!scanning && results && (
        <section>
          <div className="mb-3 flex items-center gap-3">
            <span className="text-xs font-mono text-foreground/50">
              {results.count} tickers encontrados
            </span>
          </div>

          {results.count === 0 ? (
            <div className="rounded-xl border border-border bg-surface px-6 py-16 text-center">
              <p className="text-sm font-mono text-foreground/30">
                Ningún ticker cumple los filtros seleccionados
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-border bg-surface">
              <table className="w-full text-left text-sm font-mono">
                <thead>
                  <tr className="border-b border-border text-foreground/50 text-xs uppercase tracking-wider">
                    <th className="px-4 py-3">Ticker</th>
                    <th className="px-4 py-3 text-right">Precio</th>
                    <th className="px-4 py-3 text-center">RSI (14)</th>
                    <th className="px-4 py-3 text-center">MACD</th>
                    <th className="px-4 py-3 text-center">vs EMA 200</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {results.results.map((r) => {
                    const rsiColor =
                      r.rsi == null ? "text-foreground/20"
                        : r.rsi < 30 ? "text-[var(--positive)]"
                        : r.rsi > 70 ? "text-[var(--negative)]"
                        : "text-foreground/60";

                    const emaColor =
                      r.ema_200_diff_pct == null ? "text-foreground/20"
                        : r.ema_200_diff_pct > 0 ? "text-[var(--positive)]"
                        : "text-[var(--negative)]";

                    return (
                      <tr key={r.ticker} className="hover:bg-foreground/[0.02] transition-colors">
                        <td className="px-4 py-3 font-semibold text-foreground">
                          <Link href={`/asset/${r.ticker}`} className="hover:text-accent transition-colors">
                            {r.ticker}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-right text-foreground">
                          {formatMoney(r.current_price)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <RSIBadge rsi={r.rsi} />
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold font-mono ${
                            r.macd_signal === "Bullish"
                              ? "text-[var(--positive)] bg-[var(--positive)]/10 border-[var(--positive)]/30"
                              : "text-[var(--negative)] bg-[var(--negative)]/10 border-[var(--negative)]/30"
                          }`}>
                            <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                              r.macd_signal === "Bullish" ? "bg-[var(--positive)]" : "bg-[var(--negative)]"
                            }`} />
                            {r.macd_signal === "Bullish" ? "Alcista" : "Bajista"}
                          </span>
                        </td>
                        <td className={`px-4 py-3 text-center text-xs font-bold font-mono ${emaColor}`}>
                          {r.ema_200_diff_pct != null
                            ? `${r.ema_200_diff_pct >= 0 ? "+" : ""}${r.ema_200_diff_pct.toFixed(1)}%`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function RSIBadge({ rsi }: { rsi: number | null }) {
  if (rsi === null) {
    return <span className="text-xs text-foreground/20 font-mono">—</span>;
  }

  const colorClass =
    rsi < 30
      ? "text-[var(--positive)] bg-[var(--positive)]/10 border-[var(--positive)]/30"
      : rsi > 70
        ? "text-[var(--negative)] bg-[var(--negative)]/10 border-[var(--negative)]/30"
        : "text-foreground/50 bg-foreground/5 border-border";

  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold font-mono ${colorClass}`}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${
        rsi < 30 ? "bg-[var(--positive)]" : rsi > 70 ? "bg-[var(--negative)]" : "bg-foreground/30"
      }`} />
      {rsi.toFixed(1)}
    </span>
  );
}
