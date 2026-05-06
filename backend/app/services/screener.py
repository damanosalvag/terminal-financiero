"""
Servicio de screener / escáner de mercado.
Usa yfinance.download() en batch + pandas vectorizado para calcular
indicadores de 50 tickers simultáneamente sin loops por ticker.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "AMD", "INTC",
    "JPM", "BAC", "WFC", "GS", "MS", "C",
    "XOM", "CVX", "COP", "EOG", "SLB",
    "PFE", "JNJ", "MRK", "ABBV", "UNH",
    "HD", "WMT", "COST", "TGT", "LOW",
    "NFLX", "DIS", "CMCSA", "T", "VZ",
    "BA", "CAT", "GE", "MMM", "HON",
    "CRM", "ADBE", "ORCL", "CSCO", "IBM",
    "TSM", "ASML", "QCOM", "AVGO", "TXN",
]

_LOOKBACK = "1y"


def _vectorized_rsi(close_df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calcula RSI 14 (Wilder smoothing) para TODAS las columnas a la vez."""
    delta = close_df.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    # Los primeros (period - 1) valores de ewm no son válidos; usamos SMA para el arranque
    init_gain = gain.iloc[1:period + 1].mean()
    init_loss = loss.iloc[1:period + 1].mean()

    # Construimos manualmente para combinar SMA inicial + ewm posterior
    rsi_df = pd.DataFrame(index=close_df.index, columns=close_df.columns, dtype=float)
    for col in close_df.columns:
        col_gain = avg_gain[col].copy()
        col_loss = avg_loss[col].copy()
        if not pd.isna(init_gain[col]) and not pd.isna(init_loss[col]):
            col_gain.iloc[period] = init_gain[col]
            col_loss.iloc[period] = init_loss[col]
        rs = col_gain / col_loss.replace(0, np.nan)
        rsi_df[col] = 100.0 - (100.0 / (1.0 + rs))

    return rsi_df.round(1)


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def scan_market(filters: dict[str, bool]) -> dict[str, Any]:
    """
    Escanea el universo de tickers usando cálculos vectorizados.

    Args:
        filters: Diccionario con claves booleanas:
            rsi_below_40, macd_bullish, above_ema_200, rsi_above_70

    Returns:
        {"count": int, "results": [{"ticker", "current_price", "rsi",
         "macd_signal", "macd_value", "ema_200_diff_pct"}, ...]}
    """
    universe = DEFAULT_UNIVERSE

    # ── Batch download ───────────────────────────────
    try:
        raw = yf.download(
            tickers=" ".join(universe),
            period=_LOOKBACK,
            progress=False,
            auto_adjust=True,
        )
        logger.info("Screener downloaded %d rows for %d tickers", len(raw), len(universe))
    except Exception as exc:
        logger.exception("Screener batch download failed: %s", exc)
        return {"count": 0, "results": []}

    if not isinstance(raw.columns, pd.MultiIndex) or raw.empty:
        return {"count": 0, "results": []}

    close_df = raw["Close"].copy()
    # Eliminar tickers que no tienen datos suficientes
    close_df = close_df.dropna(axis=1, thresh=50)
    if close_df.empty:
        return {"count": 0, "results": []}

    active_tickers = list(close_df.columns)
    logger.info("Screener processing %d tickers with >= 50 closing prices", len(active_tickers))

    # ── Vectorized indicators ────────────────────────
    # EMA 200
    ema_200_df = close_df.apply(lambda col: _ema(col, 200))
    latest_ema_200 = ema_200_df.iloc[-1]

    # RSI 14
    rsi_df = _vectorized_rsi(close_df, 14)
    latest_rsi = rsi_df.iloc[-1]

    # MACD (12, 26, 9) — vectorizado sobre todas las columnas
    ema12_df = close_df.apply(lambda col: _ema(col, 12))
    ema26_df = close_df.apply(lambda col: _ema(col, 26))
    macd_df = ema12_df - ema26_df
    signal_df = macd_df.apply(lambda col: _ema(col.fillna(0), 9))
    latest_macd = macd_df.iloc[-1]
    latest_signal = signal_df.iloc[-1]

    # ── Filter & collect results ─────────────────────
    results: list[dict[str, Any]] = []

    for ticker in active_tickers:
        try:
            close_series = close_df[ticker].dropna()
            if len(close_series) < 50:
                continue

            current_price = round(float(close_series.iloc[-1]), 2)

            rsi_val = latest_rsi.get(ticker)
            rsi = round(float(rsi_val), 1) if not pd.isna(rsi_val) else None

            macd_val = float(latest_macd.get(ticker, np.nan))
            sig_val = float(latest_signal.get(ticker, np.nan))
            macd_signal = "Bullish" if (not pd.isna(macd_val) and not pd.isna(sig_val) and macd_val > sig_val) else "Bearish"

            ema200_val = latest_ema_200.get(ticker)
            if not pd.isna(ema200_val) and ema200_val > 0:
                ema_diff_pct = round(((current_price - float(ema200_val)) / float(ema200_val)) * 100, 2)
            else:
                ema_diff_pct = None

            # Aplicar filtros
            if filters.get("rsi_below_40") and (rsi is None or rsi >= 40):
                continue
            if filters.get("rsi_above_70") and (rsi is None or rsi <= 70):
                continue
            if filters.get("macd_bullish") and macd_signal != "Bullish":
                continue
            if filters.get("above_ema_200") and (ema_diff_pct is None or ema_diff_pct <= 0):
                continue

            results.append({
                "ticker": ticker,
                "current_price": current_price,
                "rsi": rsi,
                "macd_signal": macd_signal,
                "macd_value": round(macd_val, 4) if not pd.isna(macd_val) else 0.0,
                "ema_200_diff_pct": ema_diff_pct,
            })

        except Exception as exc:
            logger.debug("Skipping %s: %s", ticker, exc)
            continue

    # Ordenar: RSI más bajo primero (sobreventa), salvo filtro activo de sobrecompra
    if filters.get("rsi_above_70"):
        results.sort(key=lambda x: x["rsi"] if x["rsi"] is not None else 0, reverse=True)
    else:
        results.sort(key=lambda x: x["rsi"] if x["rsi"] is not None else 100)

    return {"count": len(results), "results": results}
