"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ClosePositionModal from "@/components/ClosePositionModal";
import NewPositionModal from "@/components/NewPositionModal";
import {
  type MarketHeatmapResponse,
  type MarketHeatmapSector,
  type PortfolioNewsResponse,
  type PortfolioSummary,
  type PositionAnalysis,
  type PositionHistoryItem,
  type PositionHistoryResponse,
  type WatchlistTicker,
  addWatchlistTicker,
  getMarketHeatmap,
  getPortfolioHistory,
  getPortfolioNewsIntel,
  getPortfolioSummary,
  getWatchlist,
  removeWatchlistTicker,
} from "./api";

type ViewState = "loading" | "error" | "success" | "idle";
type Tab = "active" | "history" | "radar" | "heatmap";

export default function Dashboard() {
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [closeTarget, setCloseTarget] = useState<PositionAnalysis | null>(null);

  const [tab, setTab] = useState<Tab>("active");
  const [historyView, setHistoryView] = useState<ViewState>("idle");
  const [historyError, setHistoryError] = useState("");
  const [history, setHistory] = useState<PositionHistoryResponse | null>(null);

  const [watchlistView, setWatchlistView] = useState<ViewState>("idle");
  const [watchlistError, setWatchlistError] = useState("");
  const [watchlist, setWatchlist] = useState<WatchlistTicker[] | null>(null);
  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);

  const [heatmapData, setHeatmapData] = useState<MarketHeatmapResponse | null>(null);
  const [heatmapView, setHeatmapView] = useState<ViewState>("idle");
  const [heatmapError, setHeatmapError] = useState("");
  const [heatmapMarket, setHeatmapMarket] = useState("sp500");
  const [heatmapLoadingMore, setHeatmapLoadingMore] = useState(false);

  const [newsIntel, setNewsIntel] = useState<PortfolioNewsResponse | null>(null);
  const [newsIntelLoading, setNewsIntelLoading] = useState(false);

  const fetchSummary = useCallback(async () => {
    setViewState("loading");
    try {
      const data = await getPortfolioSummary();
      setSummary(data);
      setViewState("success");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Error desconocido");
      setViewState("error");
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    setHistoryView("loading");
    setHistoryError("");
    try {
      const data = await getPortfolioHistory();
      setHistory(data);
      setHistoryView("success");
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Error al cargar historial");
      setHistoryView("error");
    }
  }, []);

  const fetchWatchlist = useCallback(async () => {
    setWatchlistView("loading");
    setWatchlistError("");
    try {
      const data = await getWatchlist();
      setWatchlist(data);
      setWatchlistView("success");
    } catch (err) {
      setWatchlistError(err instanceof Error ? err.message : "Error al cargar radar");
      setWatchlistView("error");
    }
  }, []);

  const handleAddTicker = async () => {
    const ticker = newTicker.trim().toUpperCase();
    if (!ticker) return;
    setAdding(true);
    try {
      await addWatchlistTicker(ticker);
      setNewTicker("");
      await fetchWatchlist();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Error al agregar ticker");
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveTicker = async (id: string) => {
    try {
      await removeWatchlistTicker(id);
      await fetchWatchlist();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Error al eliminar ticker");
    }
  };

  const fetchHeatmap = useCallback(async (mkt: string, off: number = 0, append: boolean = false) => {
    if (off === 0) setHeatmapView("loading");
    else setHeatmapLoadingMore(true);
    setHeatmapError("");
    try {
      const data = await getMarketHeatmap(mkt, off, 100);
      if (append && heatmapData) {
        // Merge existing sectors with new data
        const existingSectors = [...heatmapData.sectors];
        data.sectors.forEach((newSec: MarketHeatmapSector) => {
          const existing = existingSectors.find(s => s.sector === newSec.sector);
          if (existing) {
            const existingTickers = new Set(existing.assets.map(a => a.ticker));
            existing.assets.push(...newSec.assets.filter(a => !existingTickers.has(a.ticker)));
            existing.assets.sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
          } else {
            existingSectors.push(newSec);
          }
        });
        setHeatmapData({ ...data, sectors: existingSectors });
      } else {
        setHeatmapData(data);
      }
      setHeatmapView("success");
    } catch (err) {
      setHeatmapError(err instanceof Error ? err.message : "Error al cargar heatmap");
      setHeatmapView("error");
    } finally {
      setHeatmapLoadingMore(false);
    }
  }, [heatmapData]);

  const handleTabChange = (newTab: Tab) => {
    setTab(newTab);
    if (newTab === "history" && history === null && historyView === "idle") {
      fetchHistory();
    }
    if (newTab === "radar" && watchlist === null && watchlistView === "idle") {
      fetchWatchlist();
    }
    if (newTab === "heatmap" && heatmapData === null && heatmapView === "idle") {
      fetchHeatmap(heatmapMarket, 0);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  // News Intel: se carga en segundo plano después del summary
  useEffect(() => {
    if (viewState !== "success" || !summary || summary.positions.length === 0) return;
    if (newsIntel !== null || newsIntelLoading) return;
    setNewsIntelLoading(true);
    getPortfolioNewsIntel()
      .then(setNewsIntel)
      .catch(() => {})
      .finally(() => setNewsIntelLoading(false));
  }, [viewState, summary, newsIntel, newsIntelLoading]);

  if (viewState === "loading") {
    return <Skeleton />;
  }

  if (viewState === "error") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="text-center space-y-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-negative/15">
            <AlertIcon />
          </div>
          <p className="text-negative font-mono text-sm">{errorMessage}</p>
          <button
            onClick={fetchSummary}
            className="rounded-lg bg-surface px-5 py-2 text-sm font-medium text-foreground border border-border hover:bg-border/50 transition-colors"
          >
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  const s = summary!;

  const formatMoney = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

  const formatPercent = (v: number) =>
    `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    const months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
    return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
  };

  const utilityColor = s.global_utility_percentage >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]";

  return (
    <div className="min-h-screen bg-background px-4 py-6 md:px-8">
      {/* Header */}
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
            Terminal Financiero
          </h1>
          <p className="mt-1 text-sm text-foreground/50 font-mono">
            Dashboard de Portafolio &middot; {s.positions.length} posiciones activas
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="shrink-0 rounded-lg bg-accent px-5 py-2.5 text-sm font-bold text-accent-foreground hover:bg-accent/90 transition-colors font-mono"
        >
          + Nueva Posición
        </button>
      </header>

      {/* Tabs */}
      <nav className="mb-6 flex gap-1 rounded-xl border border-border bg-surface p-1 w-fit">
        <TabButton
          active={tab === "active"}
          onClick={() => handleTabChange("active")}
        >
          Posiciones Activas
        </TabButton>
        <TabButton
          active={tab === "history"}
          onClick={() => handleTabChange("history")}
        >
          Historial
        </TabButton>
        <TabButton
          active={tab === "radar"}
          onClick={() => handleTabChange("radar")}
        >
          Radar (Watchlist)
        </TabButton>
        <TabButton
          active={tab === "heatmap"}
          onClick={() => handleTabChange("heatmap")}
        >
          Market Heatmap
        </TabButton>
      </nav>

      {/* Active Positions View */}
      {tab === "active" && (
        <>
          <section className="mb-8 grid gap-4 sm:grid-cols-3">
            <Card label="Capital Invertido" value={formatMoney(s.total_invested_capital)} />
            <Card label="Valor Actual" value={formatMoney(s.total_current_value)} />
            <Card
              label="Utilidad Global"
              value={formatPercent(s.global_utility_percentage)}
              valueClassName={utilityColor}
            />
          </section>

          {/* Heatmap Sectorial */}
          {s.positions.length > 0 && (() => {
            const grouped: Record<string, typeof s.positions> = {};
            s.positions.forEach(p => {
              const sec = p.sector || "Unknown";
              if (!grouped[sec]) grouped[sec] = [];
              grouped[sec].push(p);
            });
            return (
              <section className="mb-6">
                <h2 className="mb-3 text-xs font-bold text-foreground/50 uppercase tracking-widest font-mono">
                  Heatmap Sectorial
                </h2>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(grouped).map(([sector, positions]) => (
                    <div key={sector} className="rounded-xl border border-border bg-surface p-3 min-w-[180px]">
                      <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-2">
                        {sector}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {positions.map((p) => {
                          const pct = p.daily_change_pct;
                          const bg =
                            pct == null ? "bg-foreground/10"
                              : pct > 1 ? "bg-[var(--positive)]/80"
                              : pct > 0 ? "bg-[var(--positive)]/40"
                              : pct < -1 ? "bg-[var(--negative)]/80"
                              : "bg-[var(--negative)]/40";
                          const textColor = pct == null ? "text-foreground/60"
                            : Math.abs(pct) > 1 ? "text-white"
                            : "text-foreground/80";
                          return (
                            <Link
                              key={p.id}
                              href={`/asset/${p.ticker}`}
                              className={`rounded-md px-2 py-1 text-[10px] font-bold font-mono ${bg} ${textColor} hover:ring-1 hover:ring-accent/50 transition-all cursor-pointer`}
                              title={`${p.ticker}\nCambio diario: ${pct != null ? (pct >= 0 ? "+" : "") + pct.toFixed(2) + "%" : "N/D"}\nUtilidad: ${p.current_utility_percentage >= 0 ? "+" : ""}${p.current_utility_percentage.toFixed(2)}%\nPrecio: $${p.current_price.toFixed(2)}`}
                            >
                              {p.ticker}
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })()}

          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground/80 font-mono">
                Posiciones Activas
              </h2>
              <button
                onClick={async () => {
                  setRefreshing(true);
                  await fetchSummary();
                  setRefreshing(false);
                }}
                disabled={refreshing}
                className="rounded-md border border-border/50 px-3 py-1 text-[11px] font-mono text-foreground/40 hover:text-foreground/70 hover:border-accent/40 transition-colors disabled:opacity-30"
              >
                {refreshing ? "↻ Actualizando..." : "↻ Actualizar"}
              </button>
            </div>

            {s.positions.length === 0 ? (
              <div className="rounded-xl border border-border bg-surface px-6 py-12 text-center">
                <p className="text-foreground/40 font-mono text-sm">Sin posiciones activas</p>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-border bg-surface">
                <table className="w-full text-left text-sm font-mono">
                  <thead>
                    <tr className="border-b border-border text-foreground/50 text-xs uppercase tracking-wider">
                      <th className="px-4 py-3">Ticker</th>
                      <th className="px-4 py-3 text-right">Cantidad</th>
                      <th className="px-4 py-3 text-right">P. Compra</th>
                      <th className="px-4 py-3 text-right">P. Actual</th>
                      <th className="px-4 py-3 text-right">Días</th>
                      <th className="px-4 py-3 text-right">Salida Obj.</th>
                      <th className="px-4 py-3 text-right">Utilidad</th>
                      <th className="px-4 py-3 text-center">RSI (14d)</th>
                      <th className="px-4 py-3 text-center" title="Probabilidad de alcanzar el precio objetivo vs consenso de analistas">Prob.</th>
                      <th className="px-4 py-3 text-center" title="Latido: intervalo promedio entre eventos anómalos de volatilidad. Horizonte: ventana usada para calcular sigma (riesgo actual).">Ritmo</th>
                      <th className="px-4 py-3 text-center">Acción</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {s.positions.map((p) => {
                      const utilityClass =
                        p.current_utility_percentage >= 0
                          ? "text-[var(--positive)]"
                          : "text-[var(--negative)]";

                      return (
                        <tr
                          key={p.id}
                          className="hover:bg-foreground/[0.02] transition-colors"
                        >
                          <td className="px-4 py-3 font-semibold text-foreground">
                            <Link href={`/asset/${p.ticker}`} className="hover:text-accent transition-colors">
                              {p.ticker}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-right text-foreground/70">
                            {p.quantity}
                          </td>
                          <td className="px-4 py-3 text-right text-foreground/70">
                            ${p.buy_price.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-right text-foreground">
                            ${p.current_price.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-right text-foreground/50">
                            {p.days_held}
                          </td>
                          <td className="px-4 py-3 text-right text-accent">
                            ${p.target_exit_price.toFixed(2)}
                          </td>
                          <td className={`px-4 py-3 text-right font-medium ${utilityClass}`}>
                            {formatPercent(p.current_utility_percentage)}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <RSIBadge rsi={p.current_rsi} />
                          </td>
                          <td className="px-4 py-3 text-center">
                            <ProbabilityBadge prob={p.target_probability} />
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="text-[10px] font-mono text-foreground/40 leading-tight"
                              title={`Latido: ${p.heartbeat_days ? p.heartbeat_days.toFixed(0) + 'd' : 'N/D'} · Horizonte: ${p.volatility_window}d · La sigma se calcula con los últimos ${p.volatility_window} días.`}>
                              {p.heartbeat_days ? p.heartbeat_days.toFixed(0) + 'd' : '—'} · {p.volatility_window}d
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <button
                              onClick={() => setCloseTarget(p)}
                              className="rounded-md border border-negative/30 px-3 py-1 text-xs text-negative/80 hover:bg-negative/10 transition-colors"
                            >
                              Cerrar
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* News Intel Panel — IA-powered news analysis */}
          {newsIntel && newsIntel.results.length > 0 && (
            <section className="mb-8">
              <h2 className="mb-3 text-xs font-bold text-foreground/50 uppercase tracking-widest font-mono flex items-center gap-2">
                Inteligencia de Noticias
                <span className="text-[9px] text-accent/60 normal-case tracking-normal">DeepSeek AI</span>
              </h2>
              <div className="flex flex-wrap gap-3">
                {newsIntel.results.filter(n => n.llm_analysis).map((item) => {
                  const analysis = item.llm_analysis!;
                  const borderColor =
                    analysis.sentiment === "Bullish" ? "border-[var(--positive)]/40 bg-[var(--positive)]/5"
                    : analysis.sentiment === "Bearish" ? "border-[var(--negative)]/40 bg-[var(--negative)]/5"
                    : "border-border";
                  const glowColor =
                    analysis.sentiment === "Bullish" ? "#25c26e"
                    : analysis.sentiment === "Bearish" ? "#ff554a"
                    : "#6b7280";
                  return (
                    <div
                      key={item.ticker}
                      className={`rounded-xl border p-4 min-w-[260px] max-w-sm flex flex-col gap-2 ${borderColor}`}
                      style={{ boxShadow: `0 0 0 1px ${glowColor}20` }}
                    >
                      <div className="flex items-center justify-between">
                        <Link href={`/asset/${item.ticker}`} className="text-sm font-bold font-mono text-foreground hover:text-accent transition-colors">
                          {item.ticker}
                        </Link>
                        <span className={`text-[10px] font-bold font-mono uppercase px-2 py-0.5 rounded-md border ${
                          analysis.sentiment === "Bullish" ? "text-[var(--positive)] border-[var(--positive)]/30 bg-[var(--positive)]/10"
                          : analysis.sentiment === "Bearish" ? "text-[var(--negative)] border-[var(--negative)]/30 bg-[var(--negative)]/10"
                          : "text-foreground/50 border-border"
                        }`}>
                          {analysis.sentiment}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="rounded-md border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[10px] font-bold font-mono text-accent">
                          {analysis.macro_driver}
                        </span>
                      </div>
                      <p className="text-xs text-foreground/70 leading-relaxed font-mono">
                        {analysis.impact_summary}
                      </p>
                      {item.news.length > 0 && (
                        <div className="flex gap-2 mt-1">
                          {item.news.slice(0, 2).map((n, i) => (
                            n.link ? (
                              <a key={i} href={n.link} target="_blank" rel="noopener noreferrer"
                                className="text-[9px] text-foreground/30 hover:text-accent/60 transition-colors font-mono truncate max-w-[120px]"
                                title={n.title ?? ""}>
                                Fuente {i + 1}
                              </a>
                            ) : null
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </>
      )}

      {/* History View */}
      {tab === "history" && (
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground/80 font-mono">
            Historial de Operaciones
          </h2>

          {(historyView === "loading" || historyView === "idle") && (
            <div className="rounded-xl border border-border bg-surface px-6 py-12">
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-6 animate-pulse rounded bg-background" />
                ))}
              </div>
            </div>
          )}

          {historyView === "error" && (
            <div className="rounded-xl border border-border bg-surface px-6 py-8 text-center space-y-3">
              <p className="text-negative font-mono text-sm">{historyError}</p>
              <button
                onClick={fetchHistory}
                className="rounded-lg bg-surface px-4 py-1.5 text-xs font-medium text-foreground border border-border hover:bg-border/50 transition-colors"
              >
                Reintentar
              </button>
            </div>
          )}

          {historyView === "success" && history && (
            <>
              {/* Advanced Metrics Grid */}
              <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Card
                  label="Joya de la Corona"
                  value={
                    history.best_trade_ticker
                      ? `${history.best_trade_ticker}  ${formatMoney(history.best_trade_profit ?? 0)}`
                      : "—"
                  }
                  valueClassName="text-[var(--positive)]"
                />
                <Card
                  label="Agujero Negro"
                  value={
                    history.worst_trade_ticker
                      ? `${history.worst_trade_ticker}  ${formatMoney(history.worst_trade_loss ?? 0)}`
                      : "—"
                  }
                  valueClassName="text-[var(--negative)]"
                />
                <Card
                  label="Win Rate"
                  value={`${history.win_rate_percentage.toFixed(1)}%`}
                  valueClassName={
                    history.win_rate_percentage >= 50
                      ? "text-[var(--positive)]"
                      : "text-[var(--negative)]"
                  }
                />
                <Card
                  label="Total Comisiones"
                  value={formatMoney(history.total_commissions_paid)}
                  valueClassName="text-foreground/50"
                />
              </div>

              {history.positions.length === 0 ? (
                <div className="rounded-xl border border-border bg-surface px-6 py-12 text-center">
                  <p className="text-foreground/40 font-mono text-sm">Sin operaciones cerradas</p>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-border bg-surface">
                  <table className="w-full text-left text-sm font-mono">
                    <thead>
                      <tr className="border-b border-border text-foreground/50 text-xs uppercase tracking-wider">
                        <th className="px-4 py-3">Ticker</th>
                        <th className="px-4 py-3 text-right">F. Compra</th>
                        <th className="px-4 py-3 text-right">F. Salida</th>
                        <th className="px-4 py-3 text-right">P. Compra</th>
                        <th className="px-4 py-3 text-right">P. Salida</th>
                        <th className="px-4 py-3 text-right">Días</th>
                        <th className="px-4 py-3 text-right">Utilidad Realizada</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {history.positions.map((h: PositionHistoryItem) => {
                        const utilityClass =
                          h.realized_utility_percentage >= 0
                            ? "text-[var(--positive)]"
                            : "text-[var(--negative)]";

                        return (
                          <tr
                            key={h.id}
                            className="hover:bg-foreground/[0.02] transition-colors"
                          >
                            <td className="px-4 py-3 font-semibold text-foreground">
                              {h.ticker}
                            </td>
                            <td className="px-4 py-3 text-right text-foreground/50">
                              {formatDate(h.buy_date)}
                            </td>
                            <td className="px-4 py-3 text-right text-foreground/50">
                              {formatDate(h.exit_date)}
                            </td>
                            <td className="px-4 py-3 text-right text-foreground/70">
                              ${h.buy_price.toFixed(2)}
                            </td>
                            <td className="px-4 py-3 text-right text-foreground">
                              ${h.exit_price.toFixed(2)}
                            </td>
                            <td className="px-4 py-3 text-right text-foreground/50">
                              {h.actual_days_held}
                            </td>
                            <td className={`px-4 py-3 text-right font-medium ${utilityClass}`}>
                              {formatPercent(h.realized_utility_percentage)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {/* Watchlist / Radar View */}
      {tab === "radar" && (
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground/80 font-mono">
            Radar (Watchlist)
          </h2>

          {/* Add Ticker */}
          <div className="mb-4 flex gap-2">
            <input
              type="text"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddTicker()}
              placeholder="AAPL"
              maxLength={10}
              className="w-40 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-mono text-foreground placeholder:text-foreground/20 focus:outline-none focus:ring-2 focus:ring-accent/50 transition-colors"
            />
            <button
              onClick={handleAddTicker}
              disabled={adding || !newTicker.trim()}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-bold text-accent-foreground hover:bg-accent/90 transition-colors disabled:opacity-50 font-mono"
            >
              {adding ? "Agregando..." : "Agregar"}
            </button>
          </div>

          {(watchlistView === "loading" || watchlistView === "idle") && (
            <div className="rounded-xl border border-border bg-surface px-6 py-12">
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-6 animate-pulse rounded bg-background" />
                ))}
              </div>
            </div>
          )}

          {watchlistView === "error" && (
            <div className="rounded-xl border border-border bg-surface px-6 py-8 text-center space-y-3">
              <p className="text-negative font-mono text-sm">{watchlistError}</p>
              <button
                onClick={fetchWatchlist}
                className="rounded-lg bg-surface px-4 py-1.5 text-xs font-medium text-foreground border border-border hover:bg-border/50 transition-colors"
              >
                Reintentar
              </button>
            </div>
          )}

          {watchlistView === "success" && watchlist && (
            <>
              {watchlist.length === 0 ? (
                <div className="rounded-xl border border-border bg-surface px-6 py-12 text-center">
                  <p className="text-foreground/40 font-mono text-sm">Sin tickers en el radar</p>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-border bg-surface">
                  <table className="w-full text-left text-sm font-mono">
                    <thead>
                      <tr className="border-b border-border text-foreground/50 text-xs uppercase tracking-wider">
                        <th className="px-4 py-3">Ticker</th>
                        <th className="px-4 py-3 text-right">Precio Actual</th>
                        <th className="px-4 py-3 text-right">P. Objetivo</th>
                        <th className="px-4 py-3 text-center">Margen Seg.</th>
                        <th className="px-4 py-3 text-center">RSI (14d)</th>
                        <th className="px-4 py-3 text-center">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {watchlist.map((w: WatchlistTicker) => (
                        <tr
                          key={w.id}
                          className="hover:bg-foreground/[0.02] transition-colors"
                        >
                          <td className="px-4 py-3 font-semibold text-foreground">
                            <div className="flex items-center gap-1.5" title={w.reason_note ?? ""}>
                              <Link href={`/asset/${w.ticker}`} className="hover:text-accent transition-colors">
                                {w.ticker}
                              </Link>
                              <span className="text-[10px] text-accent/60">
                                {"★".repeat(w.importance_score ?? 1)}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right text-foreground">
                            {w.current_price !== null
                              ? `$${w.current_price.toFixed(2)}`
                              : <span className="text-foreground/20">—</span>}
                          </td>
                          <td className="px-4 py-3 text-right text-foreground/70">
                            {w.target_price !== null
                              ? `$${w.target_price.toFixed(2)}`
                              : <span className="text-foreground/20">—</span>}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <MarginBadge margin={w.margin_of_safety} />
                          </td>
                          <td className="px-4 py-3 text-center">
                            <RSIBadge rsi={w.current_rsi} />
                          </td>
                          <td className="px-4 py-3 text-center">
                            <button
                              onClick={() => handleRemoveTicker(w.id)}
                              className="rounded-md border border-negative/30 px-3 py-1 text-xs text-negative/80 hover:bg-negative/10 transition-colors"
                            >
                              Eliminar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {/* Market Heatmap View */}
      {tab === "heatmap" && (
        <section>
          {/* Market Selector */}
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground/80 font-mono">
              Market Heatmap — {heatmapMarket === "sp500" ? "S&P 500" : heatmapMarket === "dow" ? "Dow 30" : heatmapMarket === "nasdaq" ? "Nasdaq 100" : "Russell 2000"}
            </h2>
            <div className="flex gap-1 rounded-lg border border-border bg-surface p-1">
              {(["sp500", "dow", "nasdaq", "russell"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => { setHeatmapMarket(m); setHeatmapData(null); setHeatmapView("idle"); fetchHeatmap(m, 0); }}
                  className={`rounded-md px-3 py-1 text-[10px] font-bold font-mono uppercase transition-colors ${
                    heatmapMarket === m
                      ? "bg-accent text-accent-foreground"
                      : "text-foreground/50 hover:text-foreground/80"
                  }`}
                >
                  {m === "sp500" ? "S&P 500" : m === "dow" ? "Dow" : m === "nasdaq" ? "Nasdaq" : "Russell"}
                </button>
              ))}
            </div>
          </div>

          {(heatmapView === "loading" || heatmapView === "idle") && (
            <div className="rounded-xl border border-border bg-surface px-6 py-16 text-center animate-pulse">
              <p className="text-sm font-bold text-foreground/40 uppercase tracking-widest font-mono">
                Cargando heatmap del mercado...
              </p>
              <p className="mt-2 text-xs text-foreground/20 font-mono">
                Descargando datos de ~100 tickers
              </p>
            </div>
          )}

          {heatmapView === "error" && (
            <div className="rounded-xl border border-border bg-surface px-6 py-8 text-center space-y-3">
              <p className="text-negative font-mono text-sm">{heatmapError}</p>
              <button
                onClick={() => fetchHeatmap(heatmapMarket, 0)}
                className="rounded-lg bg-surface px-4 py-1.5 text-xs font-medium text-foreground border border-border hover:bg-border/50 transition-colors"
              >
                Reintentar
              </button>
            </div>
          )}

          {heatmapView === "success" && heatmapData && (
            <div className="flex flex-col gap-3">
              {heatmapData.sectors.map((sector: MarketHeatmapSector) => (
                <div key={sector.sector} className="rounded-xl border border-border bg-surface overflow-hidden">
                  <div className="px-3 py-2 border-b border-border">
                    <p className="text-[10px] font-bold text-foreground/50 uppercase tracking-widest font-mono">
                      {sector.sector}
                    </p>
                  </div>
                  <div className="flex flex-wrap p-1.5 gap-1">
                    {sector.assets.map((asset) => {
                      const pct = asset.change_pct;
                      const bg =
                        pct > 1.5 ? "#25c26e"
                        : pct > 0 ? "#1b5e20"
                        : pct < -1.5 ? "#ff554a"
                        : pct < 0 ? "#b71c1c"
                        : "#3a3f4a";
                      const sign = pct >= 0 ? "+" : "";
                      return (
                        <Link
                          key={asset.ticker}
                          href={`/asset/${asset.ticker}`}
                          className="flex flex-col items-center justify-center rounded-md px-2 py-1.5 min-w-[70px] flex-grow hover:ring-1 hover:ring-white/20 transition-all cursor-pointer"
                          style={{ backgroundColor: bg }}
                          title={`${asset.ticker}\nCambio diario: ${sign}${pct.toFixed(2)}%`}
                        >
                          <span className="text-[11px] font-bold font-mono text-white leading-tight">
                            {asset.ticker}
                          </span>
                          <span className="text-[10px] font-mono text-white/80 leading-tight">
                            {sign}{pct.toFixed(2)}%
                          </span>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ))}

              {/* Pagination: Load More */}
              {heatmapData.current_offset + 100 < heatmapData.total_assets && (
                <div className="flex justify-center">
                  <button
                    onClick={() => fetchHeatmap(heatmapMarket, heatmapData.current_offset + 100, true)}
                    disabled={heatmapLoadingMore}
                    className="rounded-lg border border-border bg-surface px-6 py-2.5 text-sm font-bold font-mono text-foreground/70 hover:text-foreground hover:border-accent/50 transition-colors disabled:opacity-50"
                  >
                    {heatmapLoadingMore
                      ? "Cargando..."
                      : `Cargar siguientes 100 activos (${heatmapData.total_assets - heatmapData.current_offset - 100} restantes)`}
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      <NewPositionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onPositionCreated={fetchSummary}
      />

      <ClosePositionModal
        open={closeTarget !== null}
        position={closeTarget}
        onClose={() => setCloseTarget(null)}
        onClosed={() => {
          fetchSummary();
          // También invalidar historial para que recargue al cambiar de tab
          setHistory(null);
        }}
      />
    </div>
  );
}

/* ── Subcomponents ─────────────────────────────────────────────── */

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg px-4 py-2 text-sm font-mono font-medium transition-colors ${
        active
          ? "bg-accent text-accent-foreground"
          : "text-foreground/50 hover:text-foreground/80"
      }`}
    >
      {children}
    </button>
  );
}

function ProbabilityBadge({ prob }: { prob: number | null }) {
  if (prob === null || prob === undefined) {
    return <span className="text-xs text-foreground/20 font-mono">—</span>;
  }
  const colorClass =
    prob >= 70 ? "text-[var(--positive)] bg-[var(--positive)]/10 border-[var(--positive)]/30"
    : prob >= 40 ? "text-accent bg-accent/10 border-accent/30"
    : "text-[var(--negative)] bg-[var(--negative)]/10 border-[var(--negative)]/30";
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-bold font-mono ${colorClass}`}
      title={`${prob.toFixed(1)}% de probabilidad de alcanzar el precio objetivo vs consenso de analistas Wall St.`}
    >
      {prob.toFixed(0)}%
    </span>
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
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold font-mono ${colorClass}`}
    >
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          rsi < 30
            ? "bg-[var(--positive)]"
            : rsi > 70
              ? "bg-[var(--negative)]"
              : "bg-foreground/30"
        }`}
      />
      {rsi.toFixed(1)}
    </span>
  );
}

function MarginBadge({ margin }: { margin: number | null }) {
  if (margin === null) {
    return <span className="text-xs text-foreground/20 font-mono">—</span>;
  }

  const colorClass =
    margin > 15
      ? "text-[var(--positive)] bg-[var(--positive)]/10 border-[var(--positive)]/30"
      : margin < 0
        ? "text-[var(--negative)] bg-[var(--negative)]/10 border-[var(--negative)]/30"
        : "text-foreground/50 bg-foreground/5 border-border";

  const sign = margin >= 0 ? "+" : "";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold font-mono ${colorClass}`}
    >
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          margin > 15
            ? "bg-[var(--positive)]"
            : margin < 0
              ? "bg-[var(--negative)]"
              : "bg-foreground/30"
        }`}
      />
      {sign}{margin.toFixed(1)}%
    </span>
  );
}

function Card({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface px-5 py-4">
      <p className="mb-1 text-xs font-medium uppercase tracking-wider text-foreground/40">
        {label}
      </p>
      <p className={`text-xl font-bold font-mono ${valueClassName ?? "text-foreground"}`}>
        {value}
      </p>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="min-h-screen bg-background px-4 py-6 md:px-8">
      <header className="mb-8 animate-pulse space-y-2">
        <div className="h-7 w-48 rounded bg-surface" />
        <div className="h-4 w-64 rounded bg-surface" />
      </header>

      <div className="mb-6 h-10 w-72 animate-pulse rounded-xl bg-surface" />

      <section className="mb-8 grid gap-4 sm:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse rounded-xl border border-border bg-surface px-5 py-4 space-y-2">
            <div className="h-3 w-24 rounded bg-background" />
            <div className="h-6 w-32 rounded bg-background" />
          </div>
        ))}
      </section>

      <section>
        <div className="mb-4 h-5 w-40 animate-pulse rounded bg-surface" />
        <div className="rounded-xl border border-border bg-surface px-6 py-12">
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-6 animate-pulse rounded bg-background" />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function AlertIcon() {
  return (
    <svg
      className="h-6 w-6 text-negative"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
      />
    </svg>
  );
}
