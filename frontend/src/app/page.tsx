"use client";

import { useCallback, useEffect, useState } from "react";
import ClosePositionModal from "@/components/ClosePositionModal";
import NewPositionModal from "@/components/NewPositionModal";
import {
  type PortfolioSummary,
  type PositionAnalysis,
  type PositionHistoryItem,
  type PositionHistoryResponse,
  type WatchlistTicker,
  addWatchlistTicker,
  getPortfolioHistory,
  getPortfolioSummary,
  getWatchlist,
  removeWatchlistTicker,
} from "./api";

type ViewState = "loading" | "error" | "success" | "idle";
type Tab = "active" | "history" | "radar";

export default function Dashboard() {
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
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

  const handleTabChange = (newTab: Tab) => {
    setTab(newTab);
    if (newTab === "history" && history === null && historyView === "idle") {
      fetchHistory();
    }
    if (newTab === "radar" && watchlist === null && watchlistView === "idle") {
      fetchWatchlist();
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

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

          <section>
            <h2 className="mb-4 text-lg font-semibold text-foreground/80 font-mono">
              Posiciones Activas
            </h2>

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
                            {p.ticker}
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
              <div className="mb-4 rounded-xl border border-border bg-surface px-5 py-3 flex items-center justify-between">
                <span className="text-sm font-mono text-foreground/50">
                  {history.total_closed_positions} operaciones cerradas
                </span>
                <span
                  className={`text-lg font-bold font-mono ${history.total_realized_profit >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}
                >
                  {formatMoney(history.total_realized_profit)}
                </span>
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
                            {w.ticker}
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
