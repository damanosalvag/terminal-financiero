"use client";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { addWatchlistTicker, checkWatchlistTicker } from "@/app/api";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import HealthRadarChart from "@/components/HealthRadarChart";

/* ── Interfaces ────────────────────────────────────────────────── */

interface OHLCV {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface TechnicalChecklist {
  above_ema50: boolean | null;
  above_ema200: boolean | null;
  rsi_in_range: boolean | null;
  rvol_strong: boolean | null;
  atr_ok: boolean | null;
}

interface MACDData {
  macd: number;
  signal: number;
  histogram: number;
  signal_cross: string;
}

interface StochasticData {
  percent_k: number | null;
  percent_d: number | null;
}

interface OBVData {
  value: number;
  trend: string;
}

interface TechnicalInsights {
  support: number | null;
  resistance: number | null;
  trend: string;
  wyckoff_phase: string;
  sma_20: number | null;
  sma_50: number | null;
  ema_50: number | null;
  ema_200: number | null;
  current_close: number | null;
  atr: number | null;
  rvol: number | null;
  current_rsi: number | null;
  checklist: TechnicalChecklist;
  high_52w: number | null;
  low_52w: number | null;
  pct_52w: number | null;
  macd: MACDData | null;
  stochastic: StochasticData | null;
  adx: number | null;
  obv: OBVData | null;
  mfi: number | null;
  vwap: number | null;
}

interface FundamentalChecklist {
  eps_growing_10pct: boolean | null;
  fcf_positive: boolean | null;
  debt_ok: boolean | null;
  no_earnings_soon: boolean | null;
  earnings_days_away: number | null;
  earnings_growth_pct: number | null;
  debt_to_equity_pct: number | null;
}

interface FundamentalRatios {
  trailing_pe: number | null;
  price_to_sales: number | null;
  dividend_yield: number | null;
  debt_to_equity: number | null;
  free_cashflow: number | null;
  trailing_eps: number | null;
  forward_eps: number | null;
  book_value: number | null;
  shares_outstanding: number | null;
  fcf_per_share: number | null;
  earnings_growth: number | null;
  sector: string;
  dividend_info?: {
    next_ex_date: number | null;
    history: { date: string; amount: number }[];
    payments_per_year: number;
  };
}

interface IntrinsicValues {
  graham_number: number | null;
  simple_dcf: number | null;
  historical_multiple_value: number | null;
}

interface FundamentalsResponse {
  ratios: FundamentalRatios;
  intrinsic_values: IntrinsicValues;
  fundamental_checklist: FundamentalChecklist;
  applicable_models: string[];
  sector: string;
  analyst_consensus: AnalystConsensus;
}

interface AnalystConsensus {
  target_mean_price: number | null;
  target_median_price: number | null;
  analyst_opinions: number | null;
  recommendation: string | null;
}

interface NarrativeData {
  business_summary: string;
  competitors: string[];
  supply_chain: {
    upstream_suppliers: string[];
    downstream_clients: string[];
  };
  macro_accelerators: string[];
  news_analysis: string[];
}

interface ChartResponse {
  chart_data: OHLCV[];
  technical_insights: TechnicalInsights;
}

type ViewState = "loading" | "error" | "success";

/* ── Main Component ────────────────────────────────────────────── */

export default function AssetCockpit() {
  const params = useParams<{ ticker: string }>();
  const router = useRouter();
  const ticker = (params?.ticker ?? "").toUpperCase();

  const [viewState, setViewState] = useState<ViewState>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [chartData, setChartData] = useState<OHLCV[] | null>(null);
  const [insights, setInsights] = useState<TechnicalInsights | null>(null);
  const [fundamentals, setFundamentals] = useState<FundamentalsResponse | null>(null);
  const [narrative, setNarrative] = useState<NarrativeData | null>(null);
  const [isNarrativeLoading, setIsNarrativeLoading] = useState(true);
  const [watchlistAdded, setWatchlistAdded] = useState(false);
  const [watchlistAdding, setWatchlistAdding] = useState(false);

  // Check if already in watchlist on mount
  useEffect(() => {
    checkWatchlistTicker(ticker).then(r => {
      if (r.is_in_watchlist) setWatchlistAdded(true);
    }).catch(() => {});
  }, [ticker]);

  const chartRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<ReturnType<typeof createChart> | null>(null);
  const candleSeriesRef = useRef<ReturnType<ReturnType<typeof createChart>["addSeries"]> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setViewState("loading");
      try {
        const [chartRes, fundRes] = await Promise.all([
          fetch(`/${API_BASE}/analysis/${ticker}/chart`),
          fetch(`/${API_BASE}/analysis/${ticker}/fundamentals`),
        ]);
        if (!chartRes.ok) {
          const detail = await chartRes.text().catch(() => "");
          throw new Error(`Error ${chartRes.status} en chart. ${detail}`);
        }
        const chartJson: ChartResponse = await chartRes.json();
        let fundJson: FundamentalsResponse | null = null;
        if (fundRes.ok) fundJson = await fundRes.json();
        if (!cancelled) {
          setChartData(chartJson.chart_data);
          setInsights(chartJson.technical_insights);
          setFundamentals(fundJson);
          setViewState("success");
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMessage(err instanceof Error ? err.message : "Error al cargar datos");
          setViewState("error");
        }
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, [ticker]);

  // Narrative: se carga en paralelo sin bloquear el gráfico
  useEffect(() => {
    let cancelled = false;
    setIsNarrativeLoading(true);
    const fetchNarrative = async () => {
      try {
        const res = await fetch(`/api/analysis/${ticker}/narrative`);
        if (res.ok && !cancelled) {
          const json: NarrativeData = await res.json();
          setNarrative(json);
        }
      } catch {
        // Silencioso: si DeepSeek no está configurado, el panel simplemente no aparece
      } finally {
        if (!cancelled) setIsNarrativeLoading(false);
      }
    };
    fetchNarrative();
    return () => { cancelled = true; };
  }, [ticker]);

  useEffect(() => {
    if (!chartData || viewState !== "success" || !chartRef.current) return;
    const container = chartRef.current;
    const chart = createChart(container, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8b8fa3" },
      grid: { vertLines: { color: "#1e2128" }, horzLines: { color: "#1e2128" } },
      crosshair: {
        vertLine: { color: "#2d7aff", width: 1, style: 2 },
        horzLine: { color: "#2d7aff", width: 1, style: 2 },
      },
      timeScale: { borderColor: "#232833", timeVisible: true },
      rightPriceScale: { borderColor: "#232833" },
      width: container.clientWidth,
      height: container.clientHeight,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#25c26e", downColor: "#ff554a",
      borderUpColor: "#25c26e", borderDownColor: "#ff554a",
      wickUpColor: "#25c26e", wickDownColor: "#ff554a",
    });
    const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "" });
    chart.priceScale("").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    candleSeries.setData(chartData.map((d) => ({
      time: (new Date(d.date).getTime() / 1000) as Time,
      open: d.open, high: d.high, low: d.low, close: d.close,
    })));
    volumeSeries.setData(chartData.map((d) => ({
      time: (new Date(d.date).getTime() / 1000) as Time,
      value: d.volume,
      color: d.close >= d.open ? "rgba(37,194,110,0.3)" : "rgba(255,85,74,0.3)",
    })));
    chart.timeScale().fitContent();

    // Guardar referencias para usar en el segundo useEffect (marcadores de dividendos)
    chartInstanceRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const handleResize = () => chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); chart.remove(); };
  }, [chartData, viewState]);

  // 'D' Marker histórico de dividendos sobre las velas (v5: createSeriesMarkers)
  useEffect(() => {
    const divInfo = fundamentals?.ratios?.dividend_info;
    const chart = chartInstanceRef.current;
    const series = candleSeriesRef.current;
    if (!divInfo || !divInfo.history || !chartData?.length || !chart || !series) return;

    const markers: SeriesMarker<Time>[] = [];

    divInfo.history.forEach((div: { date: string; amount: number }) => {
      const matchingCandle = chartData.find((c: { date: string }) => c.date.startsWith(div.date));
      if (matchingCandle) {
        markers.push({
          time: (new Date(matchingCandle.date).getTime() / 1000) as Time,
          position: "belowBar",
          color: "#2d7aff",
          shape: "circle",
          text: "D",
          size: 1,
        });
      }
    });

    // lightweight-charts v5: los marcadores se gestionan con createSeriesMarkers()
    const markersPlugin = createSeriesMarkers(series, markers);
    markersPluginRef.current = markersPlugin;

    chart.subscribeCrosshairMove((param) => {
      if (!tooltipRef.current) return;
      if (!param.point || !param.time) {
        tooltipRef.current.style.display = "none";
        return;
      }

      const hoveredCandle = chartData.find((c: { date: string }) => (new Date(c.date).getTime() / 1000) === param.time);
      if (hoveredCandle) {
        const div = divInfo.history.find((d: { date: string }) => hoveredCandle.date.startsWith(d.date));
        if (div) {
          tooltipRef.current.style.display = "block";
          tooltipRef.current.style.left = param.point.x + 15 + "px";
          tooltipRef.current.style.top = param.point.y + 15 + "px";
          tooltipRef.current.innerHTML = [
            '<div class="text-[10px] text-foreground/40 uppercase tracking-widest mb-1">Dividendo Histórico</div>',
            `<div class="text-[#2d7aff] font-bold text-base mb-0.5">$${div.amount.toFixed(2)}</div>`,
            `<div class="text-foreground/80 text-xs">${div.date}</div>`,
          ].join("");
          return;
        }
      }
      tooltipRef.current.style.display = "none";
    });

    return () => {
      try { markersPluginRef.current?.detach(); } catch { /* noop */ }
    };
  }, [chartData, fundamentals]);

  const currentPrice = chartData?.length ? chartData[chartData.length - 1].close : null;
  const priceChangePct = chartData?.length && chartData[0].close > 0
    ? ((currentPrice! - chartData[0].close) / chartData[0].close) * 100
    : null;

  const formatMoney = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

  const ratios = fundamentals?.ratios;
  const fundChecklist = fundamentals?.fundamental_checklist;

  const radarAxes = ratios && currentPrice
    ? [
        {
          label: "Rentabilidad",
          tooltip: "FCF Yield: FCF por acción ÷ precio. 10% yield = 100pts. >5% = excelente.",
          value: Math.min(Math.max(0, ((ratios.fcf_per_share || 0) / currentPrice) * 1000), 100),
        },
        {
          label: "Valuación",
          tooltip: "Inverso del P/E. P/E 15 ≈ 70pts. P/E 50 = 0pts. Menor P/E = más barata.",
          value: ratios.trailing_pe ? Math.max(0, Math.min(100, 100 - ratios.trailing_pe * 2)) : 0,
        },
        {
          label: "Solidez",
          tooltip: "Inverso del D/E %. D/E 0% = 100pts. D/E 200% = 0pts.",
          value: ratios.debt_to_equity != null ? Math.max(0, Math.min(100, 100 - ratios.debt_to_equity / 2)) : 0,
        },
        {
          label: "Dividendos",
          tooltip: "Dividend Yield. 5% = 100pts.",
          value: Math.min(Math.max(0, ((ratios.dividend_yield || 0) / 5) * 100), 100),
        },
      ]
    : [];

  return (
    <div className="min-h-screen bg-background px-4 py-6 md:px-8">
      {/* Header */}
      <header className="mb-6 flex items-center justify-between">
        <button
          onClick={() => router.push("/")}
          className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-mono text-foreground/70 hover:text-foreground hover:border-foreground/20 transition-colors"
        >
          ← Dashboard
        </button>
        <div className="text-right">
          <div className="flex items-center gap-3 justify-end mb-1">
            <button
              onClick={async () => {
                if (watchlistAdding) return;
                const importanceStr = prompt("Nivel de importancia (1-5):", "3");
                if (!importanceStr) return;
                const importance = parseInt(importanceStr);
                if (isNaN(importance) || importance < 1 || importance > 5) { alert("Valor inválido (1-5)"); return; }
                const reason = prompt("Razón de seguimiento:", "") || "";
                setWatchlistAdding(true);
                try {
                  await addWatchlistTicker(ticker, importance, reason);
                  setWatchlistAdded(true);
                } catch { /* Silencioso */ }
                finally { setWatchlistAdding(false); }
              }}
              disabled={watchlistAdded || watchlistAdding}
              className={`rounded-lg border px-3 py-1 text-[10px] font-bold font-mono uppercase transition-colors ${
                watchlistAdded
                  ? "border-[var(--positive)]/30 bg-[var(--positive)]/10 text-[var(--positive)]"
                  : "border-accent/30 bg-accent/10 text-accent hover:bg-accent/20"
              } disabled:opacity-50`}
              title="Añadir al radar de watchlist"
            >
              {watchlistAdded ? "En Radar ✓" : watchlistAdding ? "..." : "+ Watchlist"}
            </button>
            <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">{ticker}</h1>
          </div>
          {currentPrice !== null && (
            <div className="flex items-end gap-4">
              <div>
                <p className="text-[10px] font-medium uppercase tracking-widest text-foreground/30 font-mono leading-none mb-1">Precio Actual</p>
                <p className="text-sm font-mono font-medium text-foreground leading-none">{formatMoney(currentPrice)}</p>
              </div>
              {priceChangePct !== null && (
                <div>
                  <p className="text-[10px] font-medium uppercase tracking-widest text-foreground/30 font-mono leading-none mb-1">Retorno (6M)</p>
                  <p className={`text-sm font-mono font-bold leading-none ${priceChangePct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>
                    {priceChangePct >= 0 ? "+" : ""}{priceChangePct.toFixed(2)}%
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </header>

      {viewState === "loading" && (
        <div className="rounded-xl border border-border bg-surface px-6 py-24 text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <p className="mt-4 text-sm font-mono text-foreground/40">Cargando datos de {ticker}...</p>
        </div>
      )}

      {viewState === "error" && (
        <div className="rounded-xl border border-border bg-surface px-6 py-24 text-center">
          <p className="text-negative font-mono text-sm">{errorMessage}</p>
        </div>
      )}

      {viewState === "success" && chartData && insights && (
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Left Column — 70%: Chart + Strategic + Fundamental */}
          <div className="lg:w-[70%] flex flex-col gap-4">
            {/* Chart */}
            <div className="rounded-xl border border-border bg-surface p-4">
              <div className="relative h-[500px] w-full">
                <div ref={chartRef} className="h-full w-full" />
                <div
                  ref={tooltipRef}
                  className="absolute hidden z-50 rounded-lg border border-border bg-background/95 backdrop-blur-sm p-3 text-sm font-mono shadow-2xl pointer-events-none"
                />
              </div>
            </div>

            {/* ── INTELIGENCIA ESTRATÉGICA & MACRO ──────────────── */}
            {isNarrativeLoading && !narrative && (
              <div className="rounded-xl border border-border bg-surface p-5 flex items-center justify-center min-h-[150px] animate-pulse">
                <p className="text-xs font-bold text-foreground/40 uppercase tracking-widest font-mono">
                  Generando Inteligencia Estratégica (IA)...
                </p>
              </div>
            )}
            {narrative && (
              <div className="rounded-xl border border-border bg-surface p-5">
                <h2 className="text-xs font-bold text-foreground/50 uppercase tracking-widest font-mono mb-4">
                  Inteligencia Estratégica & Macro
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Col 1: Business Summary + Supply Chain */}
                  <div className="flex flex-col gap-3">
                    <p
                      className="text-xs text-foreground/70 leading-relaxed font-mono border-l-2 border-accent/40 pl-3"
                      title={narrative.business_summary}
                    >
                      {narrative.business_summary}
                    </p>
                    {narrative.supply_chain && (
                      <div
                        className="flex items-center gap-1.5 text-[10px] font-mono flex-wrap"
                        title="Cadena de suministro: proveedores → empresa → clientes"
                      >
                        {narrative.supply_chain.upstream_suppliers.slice(0, 3).map((s, i) => (
                          <span key={i} className="rounded-md border border-border bg-background px-2 py-0.5 text-foreground/50">{s}</span>
                        ))}
                        <span className="text-accent/60 mx-0.5">→</span>
                        <span className="rounded-md border border-accent/30 bg-accent/10 px-2 py-0.5 text-accent font-bold">{ticker}</span>
                        <span className="text-accent/60 mx-0.5">→</span>
                        {narrative.supply_chain.downstream_clients.slice(0, 3).map((c, i) => (
                          <span key={i} className="rounded-md border border-border bg-background px-2 py-0.5 text-foreground/50">{c}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  {/* Col 2: Competitors + Macro + News */}
                  <div className="flex flex-col gap-3">
                    <div className="grid grid-cols-2 gap-2">
                      {narrative.competitors?.length > 0 && (
                        <div className="rounded-lg border border-border bg-background px-3 py-2">
                          <p className="text-[9px] text-foreground/40 uppercase tracking-wider font-mono mb-1">Competidores</p>
                          <div className="flex flex-wrap gap-1">
                            {narrative.competitors.map((c, i) => (
                              <Link key={i} href={`/asset/${c}`}
                                className="text-[10px] font-bold font-mono text-accent/80 hover:text-accent transition-colors"
                                title={`Competidor: ${c}`}>{c}</Link>
                            ))}
                          </div>
                        </div>
                      )}
                      {narrative.macro_accelerators?.length > 0 && (
                        <div className="rounded-lg border border-border bg-background px-3 py-2">
                          <p className="text-[9px] text-foreground/40 uppercase tracking-wider font-mono mb-1">Aceleradores Macro</p>
                          <div className="flex flex-wrap gap-1">
                            {narrative.macro_accelerators.map((m, i) => (
                              <span key={i} className="rounded-md border border-border px-1.5 py-0.5 text-[10px] font-mono text-foreground/60" title={m}>{m}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    {narrative.news_analysis?.length > 0 && (
                      <div className="rounded-lg border border-border bg-background px-3 py-2">
                        <p className="text-[9px] text-foreground/40 uppercase tracking-wider font-mono mb-1.5">Análisis de Noticias</p>
                        <div className="space-y-1">
                          {narrative.news_analysis.map((bullet, i) => (
                            <div key={i} className="flex items-start gap-1.5" title={bullet}>
                              <span className="text-accent/60 text-[10px] mt-0.5 shrink-0">•</span>
                              <p className="text-[10px] text-foreground/60 leading-snug font-mono">{bullet}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ── ANÁLISIS FUNDAMENTAL ────────────────────────── */}
            {fundamentals && (
              <div className="rounded-xl border border-border bg-surface p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xs font-bold text-foreground/50 uppercase tracking-widest font-mono">
                    Análisis Fundamental
                  </h2>
                  {fundChecklist && (
                    <ChecklistScore
                      items={[
                        fundChecklist.eps_growing_10pct,
                        fundChecklist.fcf_positive,
                        fundChecklist.debt_ok,
                        fundChecklist.no_earnings_soon,
                      ]}
                      minPass={3}
                    />
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Col 1: Checklist + Intrinsic Values */}
                  <div className="flex flex-col gap-3">
                    {fundChecklist && (
                      <div className="space-y-1">
                        <CheckItem pass={fundChecklist.eps_growing_10pct} label="EPS creciendo >10% YoY"
                          detail={fundChecklist.earnings_growth_pct != null ? `Crecimiento: ${fundChecklist.earnings_growth_pct > 0 ? "+" : ""}${fundChecklist.earnings_growth_pct.toFixed(1)}%` : undefined}
                          tooltip="Las ganancias por acción crecen más del 10% interanual. Empresas con EPS acelerado atraen capital institucional y sostienen el alza." />
                        <CheckItem pass={fundChecklist.fcf_positive} label="Flujo de Caja Libre (FCF) positivo"
                          detail={ratios?.free_cashflow != null ? `FCF: $${(ratios.free_cashflow / 1e9).toFixed(2)}B` : undefined}
                          tooltip="La empresa genera más efectivo del que gasta después de invertir en su infraestructura." />
                        <CheckItem pass={fundChecklist.debt_ok} label="Deuda controlada (D/E < 150%)"
                          detail={fundChecklist.debt_to_equity_pct != null ? `D/E: ${fundChecklist.debt_to_equity_pct.toFixed(1)}%` : undefined}
                          tooltip="La deuda total es menor al 150% del patrimonio neto. Empresas con D/E bajo son más resistentes." />
                        <CheckItem pass={fundChecklist.no_earnings_soon} label="Sin earnings en los próximos 7 días"
                          detail={fundChecklist.earnings_days_away != null ? (fundChecklist.earnings_days_away > 0 ? `Próximo earnings: ${fundChecklist.earnings_days_away}d` : "Earnings ya reportado") : undefined}
                          tooltip="No hay reporte de resultados en los próximos 7 días. Los earnings son eventos binarios de alto riesgo." />
                      </div>
                    )}
                    <div>
                      <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-2">
                        Valor Intrínseco vs Precio Actual
                        <span className="ml-2 text-foreground/25 font-normal normal-case tracking-normal">
                          Sector: {ratios?.sector ?? "—"}
                        </span>
                      </p>
                      <div className="space-y-2.5">
                        {fundamentals.applicable_models?.includes("graham_number") && (
                          <IntrinsicBar label="Núm. Graham" tooltip="√(22.5 × EPS × BVPS). Valor máximo según Benjamin Graham." intrinsicValue={fundamentals.intrinsic_values.graham_number} currentPrice={currentPrice} />
                        )}
                        {fundamentals.applicable_models?.includes("simple_dcf") && (
                          <IntrinsicBar label="DCF (FCF/Acción)" tooltip="FCF por acción proyectado a 10 años, 5% crecimiento, 9% descuento." intrinsicValue={fundamentals.intrinsic_values.simple_dcf} currentPrice={currentPrice} />
                        )}
                        {fundamentals.applicable_models?.includes("historical_multiple_value") && (
                          <IntrinsicBar label="P/E Histórico ×15" tooltip="EPS × 15x (P/E promedio histórico del S&P 500)." intrinsicValue={fundamentals.intrinsic_values.historical_multiple_value} currentPrice={currentPrice} />
                        )}
                        {/* Wall Street Consensus */}
                        {fundamentals.analyst_consensus?.target_median_price != null && fundamentals.analyst_consensus?.analyst_opinions != null && (
                          <>
                            <div className="border-t border-border pt-2.5 mt-2.5">
                              <IntrinsicBar
                                label="Consenso Wall St."
                                tooltip={`Basado en ${fundamentals.analyst_consensus.analyst_opinions} analistas. Recomendación general: ${fundamentals.analyst_consensus.recommendation ?? "—"}. Promedio: $${fundamentals.analyst_consensus.target_mean_price?.toFixed(2) ?? "—"}.`}
                                intrinsicValue={fundamentals.analyst_consensus.target_median_price}
                                currentPrice={currentPrice}
                              />
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  {/* Col 2: Health Radar + Mini Ratios */}
                  <div className="flex flex-col gap-3">
                    {radarAxes.length > 0 && (
                      <div>
                        <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-1"
                          title="Radar de salud: Rentabilidad, Valuación, Solidez, Dividendos. Mayor área = más saludable.">
                          Health Radar
                        </p>
                        <HealthRadarChart axes={radarAxes} />
                      </div>
                    )}
                    <div className="grid grid-cols-3 gap-1.5">
                      <MiniRatio label="P/E" value={ratios?.trailing_pe?.toFixed(1)} tooltip="Price-to-Earnings. Promedio histórico S&P 500: ~15–20×." />
                      <MiniRatio label="P/S" value={ratios?.price_to_sales?.toFixed(2)} tooltip="Price-to-Sales. <2 = razonable." />
                      <MiniRatio label="D/E" value={ratios?.debt_to_equity != null ? `${ratios.debt_to_equity.toFixed(0)}%` : undefined} tooltip="Deuda/Patrimonio. <100% = conservador." />
                      <MiniRatio label="Div. Yield" value={ratios?.dividend_yield != null ? `${ratios.dividend_yield.toFixed(2)}%` : undefined} tooltip="Rendimiento del dividendo anual." />
                      <MiniRatio label="FCF/Acc." value={ratios?.fcf_per_share != null ? `$${ratios.fcf_per_share.toFixed(2)}` : undefined} tooltip="Free Cash Flow por acción." />
                      <MiniRatio label="EPS" value={ratios?.trailing_eps != null ? `$${ratios.trailing_eps.toFixed(2)}` : undefined} tooltip="Earnings Per Share (últimos 12 meses)." />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column — 30%: Technical + Momentum */}
          <div className="lg:w-[30%] flex flex-col gap-4">

            {/* ── ANÁLISIS TÉCNICO ────────────────────────────── */}
            <div className="rounded-xl border border-border bg-surface p-5 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-bold text-foreground/50 uppercase tracking-widest font-mono">
                  Análisis Técnico
                </h2>
                <ChecklistScore
                  items={[
                    insights.checklist.above_ema50,
                    insights.checklist.above_ema200,
                    insights.checklist.rsi_in_range,
                    insights.checklist.rvol_strong,
                    insights.checklist.atr_ok,
                  ]}
                  minPass={4}
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <StatCard
                  label="Soporte (20d)"
                  value={insights.support != null ? `$${insights.support.toFixed(2)}` : "—"}
                  color="positive"
                  tooltip="Mínimo de cierre de los últimos 20 días. Zona donde el precio históricamente rebota al alza."
                />
                <StatCard
                  label="Resistencia (20d)"
                  value={insights.resistance != null ? `$${insights.resistance.toFixed(2)}` : "—"}
                  color="negative"
                  tooltip="Máximo de cierre de los últimos 20 días. Zona de presión vendedora."
                />
              </div>

              <div className="space-y-1">
                <CheckItem pass={insights.checklist.above_ema50} label="Precio sobre EMA 50"
                  detail={insights.ema_50 != null ? `EMA 50: $${insights.ema_50.toFixed(2)}` : undefined}
                  tooltip="El precio cierra por encima de la EMA de 50 días." />
                <CheckItem pass={insights.checklist.above_ema200} label="Precio sobre EMA 200"
                  detail={insights.ema_200 != null ? `EMA 200: $${insights.ema_200.toFixed(2)}` : "Sin datos (< 200 velas)"}
                  tooltip="El precio cierra por encima de la EMA de 200 días." />
                <CheckItem pass={insights.checklist.rsi_in_range} label="RSI en zona óptima (40–65)"
                  detail={insights.current_rsi != null ? `RSI: ${insights.current_rsi.toFixed(1)}` : undefined}
                  tooltip="RSI entre 40-65 = momentum sin sobrecompra." />
                <CheckItem pass={insights.checklist.rvol_strong} label="Volumen relativo > 1.3×"
                  detail={insights.rvol != null ? `RVOL: ${insights.rvol.toFixed(2)}×` : undefined}
                  tooltip="Volumen actual > 1.3× el promedio de 20 días." />
                <CheckItem pass={insights.checklist.atr_ok} label="ATR razonable (riesgo < 8%)"
                  detail={insights.atr != null ? `ATR: $${insights.atr.toFixed(2)}` : undefined}
                  tooltip="ATR < 8% del precio = risk/reward viable." />
              </div>

              <div className={`rounded-lg border px-3 py-2.5 ${
                insights.wyckoff_phase === "Accumulation" || insights.wyckoff_phase === "Markup"
                  ? "border-[var(--positive)]/30 bg-[var(--positive)]/5"
                  : "border-[var(--negative)]/30 bg-[var(--negative)]/5"
              }`}
                title="Fase de Wyckoff basada en posición del precio relativo a soporte/resistencia.">
                <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-0.5">Fase Wyckoff</p>
                <p className={`text-sm font-bold font-mono ${
                  insights.wyckoff_phase === "Accumulation" || insights.wyckoff_phase === "Markup"
                    ? "text-[var(--positive)]" : "text-[var(--negative)]"
                }`}>
                  {insights.wyckoff_phase}
                </p>
              </div>
            </div>

            {/* ── MOMENTUM & VOLUMEN ────────────────────────────── */}
            <div className="rounded-xl border border-border bg-surface p-5 flex flex-col gap-4">
              <h2 className="text-xs font-bold text-foreground/50 uppercase tracking-widest font-mono">
                Momentum & Volumen
              </h2>

              {/* 52-Week Range Bar */}
              <div>
                <div className="flex justify-between text-[10px] font-mono text-foreground/40 mb-1">
                  <span>52W LOW</span><span>52W HIGH</span>
                </div>
                <div className="relative h-1.5 rounded-full bg-background border border-border"
                  title={insights.high_52w != null && insights.low_52w != null
                    ? `Rango 52 semanas: $${insights.low_52w.toFixed(2)} – $${insights.high_52w.toFixed(2)}`
                    : "Datos insuficientes para rango 52 semanas."}>
                  {insights.high_52w != null && insights.low_52w != null && insights.pct_52w != null && (
                    <>
                      <div className="absolute top-0 left-0 h-full rounded-full bg-accent/30" style={{ width: `${insights.pct_52w}%` }} />
                      <div className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-accent border-2 border-background shadow-sm"
                        style={{ left: `calc(${insights.pct_52w}% - 5px)` }} />
                    </>
                  )}
                </div>
                <div className="flex justify-between text-[9px] font-mono text-foreground/25 mt-0.5">
                  <span>{insights.low_52w != null ? `$ ${insights.low_52w.toFixed(2)}` : "—"}</span>
                  <span>{insights.high_52w != null ? `$ ${insights.high_52w.toFixed(2)}` : "—"}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {insights.macd && (
                  <div className={`rounded-lg border px-3 py-2 ${insights.macd.signal_cross === "Bullish" ? "border-[var(--positive)]/30 bg-[var(--positive)]/5" : "border-[var(--negative)]/30 bg-[var(--negative)]/5"}`}
                    title={`MACD (12,26,9). ${insights.macd.signal_cross === "Bullish" ? "MACD > Signal = cruce alcista." : "MACD < Signal = cruce bajista."}`}>
                    <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-1">MACD</p>
                    <p className={`text-sm font-bold font-mono ${insights.macd.signal_cross === "Bullish" ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>{insights.macd.signal_cross}</p>
                    <p className="text-[9px] font-mono text-foreground/30 mt-0.5">{insights.macd.macd.toFixed(2)} / {insights.macd.signal.toFixed(2)}</p>
                  </div>
                )}
                {insights.adx != null && (
                  <div className="rounded-lg border border-border px-3 py-2"
                    title="ADX (14). <20 = débil, >25 = fuerte, >40 = muy fuerte.">
                    <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-1">ADX</p>
                    <p className={`text-sm font-bold font-mono ${insights.adx > 25 ? "text-accent" : "text-foreground/50"}`}>{insights.adx.toFixed(1)}</p>
                    <p className="text-[9px] font-mono text-foreground/30 mt-0.5">{insights.adx < 20 ? "Débil" : insights.adx > 40 ? "Muy fuerte" : "Fuerte"}</p>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                {insights.stochastic?.percent_k != null && (
                  <div className="rounded-lg border border-border px-3 py-2"
                    title={`Stochastic (14,3,3). >80 = sobrecompra, <20 = sobreventa.`}>
                    <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-1">Stochastic</p>
                    <p className={`text-sm font-bold font-mono ${insights.stochastic.percent_k > 80 ? "text-[var(--negative)]" : insights.stochastic.percent_k < 20 ? "text-[var(--positive)]" : "text-foreground/70"}`}>
                      {insights.stochastic.percent_k.toFixed(1)} / {insights.stochastic.percent_d?.toFixed(1)}</p>
                  </div>
                )}
                {insights.mfi != null && (
                  <div className="rounded-lg border border-border px-3 py-2"
                    title="MFI (14). RSI ponderado por volumen.">
                    <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-1">MFI</p>
                    <p className={`text-sm font-bold font-mono ${insights.mfi > 80 ? "text-[var(--negative)]" : insights.mfi < 20 ? "text-[var(--positive)]" : "text-foreground/70"}`}>{insights.mfi.toFixed(1)}</p>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                {insights.obv && (
                  <div className={`rounded-lg border px-3 py-2 ${insights.obv.trend === "Accumulating" ? "border-[var(--positive)]/30 bg-[var(--positive)]/5" : "border-[var(--negative)]/30 bg-[var(--negative)]/5"}`}
                    title="On-Balance Volume: presión compradora/vendedora institucional.">
                    <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-1">OBV</p>
                    <p className={`text-sm font-bold font-mono ${insights.obv.trend === "Accumulating" ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>
                      {insights.obv.trend === "Accumulating" ? "Acumulando" : "Distribuyendo"}</p>
                  </div>
                )}
                {insights.vwap != null && (
                  <div className="rounded-lg border border-border px-3 py-2"
                    title={`VWAP (20d): $${insights.vwap.toFixed(2)}. Precio > VWAP = momentum alcista.`}>
                    <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-1">VWAP (20d)</p>
                    <p className={`text-sm font-bold font-mono ${currentPrice != null && currentPrice > insights.vwap ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>
                      $ {insights.vwap.toFixed(2)}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Subcomponents ─────────────────────────────────────────────── */

function ChecklistScore({ items, minPass }: { items: (boolean | null)[]; minPass: number }) {
  const passed = items.filter((v) => v === true).length;
  const total = items.filter((v) => v !== null).length;
  const isOk = passed >= minPass;
  return (
    <span className={`text-xs font-bold font-mono px-2 py-0.5 rounded-md border ${
      isOk
        ? "text-[var(--positive)] border-[var(--positive)]/30 bg-[var(--positive)]/10"
        : "text-[var(--negative)] border-[var(--negative)]/30 bg-[var(--negative)]/10"
    }`}>
      {passed}/{total}
    </span>
  );
}

function CheckItem({
  pass,
  label,
  detail,
  tooltip,
}: {
  pass: boolean | null;
  label: string;
  detail?: string;
  tooltip: string;
}) {
  const icon = pass === null ? "○" : pass ? "✓" : "✗";
  const color =
    pass === null
      ? "text-foreground/25"
      : pass
        ? "text-[var(--positive)]"
        : "text-[var(--negative)]";
  const bgColor =
    pass === null
      ? ""
      : pass
        ? "bg-[var(--positive)]/5 border-[var(--positive)]/15"
        : "bg-[var(--negative)]/5 border-[var(--negative)]/15";

  return (
    <div
      className={`flex items-start gap-2.5 rounded-lg border px-3 py-2 ${bgColor || "border-border"}`}
      title={tooltip}
    >
      <span className={`text-sm font-bold font-mono mt-0.5 shrink-0 ${color}`}>{icon}</span>
      <div className="min-w-0">
        <p className="text-xs font-medium text-foreground/80 font-mono leading-tight">{label}</p>
        {detail && (
          <p className={`text-[10px] font-mono mt-0.5 ${color} opacity-80`}>{detail}</p>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
  tooltip,
}: {
  label: string;
  value: string;
  color: "positive" | "negative" | "neutral";
  tooltip: string;
}) {
  const textColor =
    color === "positive" ? "text-[var(--positive)]"
      : color === "negative" ? "text-[var(--negative)]"
        : "text-foreground/70";
  const borderColor =
    color === "positive" ? "border-[var(--positive)]/20 bg-[var(--positive)]/5"
      : color === "negative" ? "border-[var(--negative)]/20 bg-[var(--negative)]/5"
        : "border-border";

  return (
    <div className={`rounded-lg border px-3 py-2 ${borderColor}`} title={tooltip}>
      <p className="text-[10px] text-foreground/40 uppercase tracking-wider font-mono mb-0.5">{label}</p>
      <p className={`text-sm font-bold font-mono ${textColor}`}>{value}</p>
    </div>
  );
}

function IntrinsicBar({
  label,
  tooltip,
  intrinsicValue,
  currentPrice,
}: {
  label: string;
  tooltip: string;
  intrinsicValue: number | null;
  currentPrice: number | null;
}) {
  const formatMoney = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

  if (intrinsicValue === null || currentPrice === null) {
    return (
      <div title={tooltip}>
        <div className="flex justify-between text-[10px] font-mono mb-1">
          <span className="text-foreground/40">{label}</span>
          <span className="text-foreground/20">Sin datos</span>
        </div>
        <div className="h-2 rounded-full bg-background border border-border" />
      </div>
    );
  }

  const marginPct = ((intrinsicValue - currentPrice) / intrinsicValue) * 100;
  const isUndervalued = marginPct > 0;
  const fillPct = isUndervalued
    ? Math.min(100, (currentPrice / intrinsicValue) * 100)
    : Math.min(100, (intrinsicValue / currentPrice) * 100);

  return (
    <div title={tooltip} className="space-y-1">
      <div className="flex justify-between items-baseline">
        <span className="text-[10px] font-mono text-foreground/50">{label}</span>
        <span className={`text-[10px] font-bold font-mono ${isUndervalued ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>
          {isUndervalued ? "+" : ""}{marginPct.toFixed(1)}% {isUndervalued ? "descuento" : "sobrevalor"}
        </span>
      </div>
      <div className="flex justify-between text-[9px] font-mono text-foreground/25">
        <span>Actual: {formatMoney(currentPrice)}</span>
        <span>Intrínseco: {formatMoney(intrinsicValue)}</span>
      </div>
      <div className="h-2 rounded-full bg-background border border-border overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${fillPct}%`, backgroundColor: isUndervalued ? "var(--positive)" : "var(--negative)", opacity: 0.7 }}
        />
      </div>
    </div>
  );
}

function MiniRatio({ label, value, tooltip }: { label: string; value: string | undefined | null; tooltip: string }) {
  return (
    <div className="rounded-md border border-border bg-background px-2 py-1.5" title={tooltip}>
      <p className="text-[9px] text-foreground/35 uppercase tracking-wider font-mono leading-none">{label}</p>
      <p className="text-xs font-bold font-mono text-foreground/65 mt-0.5">{value ?? "—"}</p>
    </div>
  );
}
