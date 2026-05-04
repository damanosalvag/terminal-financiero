"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CandlestickSeries, ColorType, createChart, HistogramSeries, type Time } from "lightweight-charts";

interface OHLCV {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

type ViewState = "loading" | "error" | "success";

export default function AssetCockpit() {
  const params = useParams<{ ticker: string }>();
  const router = useRouter();
  const ticker = (params?.ticker ?? "").toUpperCase();

  const [viewState, setViewState] = useState<ViewState>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [data, setData] = useState<OHLCV[] | null>(null);

  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setViewState("loading");
      try {
        const res = await fetch(`/api/analysis/${ticker}/chart`);
        if (!res.ok) {
          const detail = await res.text().catch(() => "");
          throw new Error(`Error ${res.status}. ${detail}`);
        }
        const json: OHLCV[] = await res.json();
        if (!cancelled) {
          setData(json);
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

  // Renderizar gráfico cuando los datos están listos
  useEffect(() => {
    if (!data || viewState !== "success" || !chartRef.current) return;

    const container = chartRef.current;
    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b8fa3",
      },
      grid: {
        vertLines: { color: "#1e2128" },
        horzLines: { color: "#1e2128" },
      },
      crosshair: {
        vertLine: { color: "#2d7aff", width: 1, style: 2 },
        horzLine: { color: "#2d7aff", width: 1, style: 2 },
      },
      timeScale: {
        borderColor: "#232833",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "#232833",
      },
      width: container.clientWidth,
      height: container.clientHeight,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#25c26e",
      downColor: "#ff554a",
      borderUpColor: "#25c26e",
      borderDownColor: "#ff554a",
      wickUpColor: "#25c26e",
      wickDownColor: "#ff554a",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });

    chart.priceScale("").applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    const candleData = data.map((d) => ({
      time: (new Date(d.date).getTime() / 1000) as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    const volumeData = data.map((d) => ({
      time: (new Date(d.date).getTime() / 1000) as Time,
      value: d.volume,
      color: d.close >= d.open ? "rgba(37,194,110,0.3)" : "rgba(255,85,74,0.3)",
    }));

    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);

    chart.timeScale().fitContent();

    const handleResize = () => {
      chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight,
      });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, viewState]);

  const currentPrice = data?.length ? data[data.length - 1].close : null;
  const priceChange = data?.length
    ? currentPrice! - data[0].close
    : null;
  const priceChangePct = data?.length && data[0].close > 0
    ? ((priceChange!) / data[0].close) * 100
    : null;

  const formatMoney = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

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
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
            {ticker}
          </h1>
          {currentPrice !== null && (
            <p className={`text-sm font-mono font-medium ${priceChangePct !== null && priceChangePct >= 0 ? "text-[var(--positive)]" : "text-[var(--negative)]"}`}>
              {formatMoney(currentPrice)}
              {priceChangePct !== null && (
                <span className="ml-2 font-mono text-foreground/50 text-xs">
                  6M {priceChangePct >= 0 ? "+" : ""}{priceChangePct.toFixed(2)}%
                </span>
              )}
            </p>
          )}
        </div>
      </header>

      {/* Content */}
      {viewState === "loading" && (
        <div className="rounded-xl border border-border bg-surface px-6 py-24 text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <p className="mt-4 text-sm font-mono text-foreground/40">Cargando datos de {ticker}...</p>
        </div>
      )}

      {viewState === "error" && (
        <div className="rounded-xl border border-border bg-surface px-6 py-24 text-center space-y-3">
          <p className="text-negative font-mono text-sm">{errorMessage}</p>
        </div>
      )}

      {viewState === "success" && data && (
        <div className="rounded-xl border border-border bg-surface p-4">
          <div ref={chartRef} className="h-[500px] w-full" />
        </div>
      )}
    </div>
  );
}
