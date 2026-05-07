"""
Servicio de screener / escáner de mercado.
Batch download para indicadores técnicos, luego ThreadPoolExecutor para fundamentals.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
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
    delta = close_df.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    init_gain = gain.iloc[1:period + 1].mean()
    init_loss = loss.iloc[1:period + 1].mean()
    rsi_df = pd.DataFrame(index=close_df.index, columns=close_df.columns, dtype=float)
    for col in close_df.columns:
        cg, cl = avg_gain[col].copy(), avg_loss[col].copy()
        if not pd.isna(init_gain[col]) and not pd.isna(init_loss[col]):
            cg.iloc[period] = init_gain[col]
            cl.iloc[period] = init_loss[col]
        rs = cg / cl.replace(0, np.nan)
        rsi_df[col] = 100.0 - (100.0 / (1.0 + rs))
    return rsi_df.round(1)


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _fetch_fundamentals_batch(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """ThreadPoolExecutor para descargar fundamentals de varios tickers en paralelo."""
    results: dict[str, dict[str, Any]] = {}

    def fetch_one(ticker: str):
        try:
            info = yf.Ticker(ticker).info
            return ticker, {
                "name": info.get("shortName") or info.get("longName", ""),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "market_cap": info.get("marketCap"),
                "avg_volume": info.get("averageVolume"),
                "trailing_pe": info.get("trailingPE"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "target_mean_price": info.get("targetMeanPrice"),
                "beta": info.get("beta"),
            }
        except Exception:
            return ticker, None

    with ThreadPoolExecutor(max_workers=8) as executor:
        for ticker, data in executor.map(fetch_one, tickers):
            if data is not None:
                results[ticker] = data

    return results


def scan_market(filters: dict[str, Any], offset: int = 0, limit: int = 30) -> dict[str, Any]:
    """
    Escanea el mercado con filtros técnicos + fundamentals.
    Usa chunks de 30 tickers con ThreadPoolExecutor para fundamentals.
    """
    universe = filters.get("specific_ticker")
    if universe and isinstance(universe, str) and universe.strip():
        tickers = [universe.strip().upper()]
    else:
        start = offset
        end = min(offset + limit, len(DEFAULT_UNIVERSE))
        tickers = DEFAULT_UNIVERSE[start:end]

    if not tickers:
        return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}

    # Batch download técnico
    try:
        raw = yf.download(tickers=" ".join(tickers), period=_LOOKBACK, progress=False, auto_adjust=True)
    except Exception:
        return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}

    if not isinstance(raw.columns, pd.MultiIndex) or raw.empty:
        return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}

    close_df = raw["Close"].copy()
    vol_df = raw["Volume"].copy() if "Volume" in raw.columns else None
    close_df.dropna(axis=1, thresh=50, inplace=True)
    if close_df.empty:
        return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}

    active_tickers = list(close_df.columns)
    ema_200_df = close_df.apply(lambda col: _ema(col, 200))
    rsi_df = _vectorized_rsi(close_df, 14)
    ema12 = close_df.apply(lambda col: _ema(col, 12))
    ema26 = close_df.apply(lambda col: _ema(col, 26))
    macd_df = ema12 - ema26
    signal_df = macd_df.apply(lambda col: _ema(col.fillna(0), 9))
    last_row = close_df.iloc[-1]
    prev_row = close_df.iloc[-2]
    pct_series = ((last_row - prev_row) / prev_row.replace(0, float("nan"))) * 100

    results: list[dict[str, Any]] = []
    for ticker in active_tickers:
        try:
            closes = close_df[ticker].dropna()
            if len(closes) < 50: continue
            current_price = round(float(closes.iloc[-1]), 2)
            rsi_val = rsi_df[ticker].dropna().iloc[-1] if ticker in rsi_df.columns else None
            rsi = round(float(rsi_val), 1) if rsi_val is not None and not pd.isna(rsi_val) else None

            macd_v = float(macd_df[ticker].iloc[-1]) if ticker in macd_df.columns else 0
            sig_v = float(signal_df[ticker].iloc[-1]) if ticker in signal_df.columns else 0
            macd_signal = "Bullish" if (not pd.isna(macd_v) and not pd.isna(sig_v) and macd_v > sig_v) else "Bearish"

            ema_v = ema_200_df[ticker].iloc[-1] if ticker in ema_200_df.columns else None
            ema_diff = round(((current_price - float(ema_v)) / float(ema_v)) * 100, 2) if ema_v is not None and not pd.isna(ema_v) and ema_v > 0 else None

            daily_pct = pct_series.get(ticker)
            daily_change = round(float(daily_pct), 2) if daily_pct is not None and not pd.isna(daily_pct) else None

            # RVOL: volumen actual vs promedio de los últimos 20 días
            rvol: float | None = None
            if vol_df is not None and ticker in vol_df.columns:
                vol_series = vol_df[ticker].dropna()
                if len(vol_series) >= 21:
                    avg_vol_20 = float(vol_series.iloc[-21:-1].mean())
                    curr_vol = float(vol_series.iloc[-1])
                    if avg_vol_20 > 0:
                        rvol = round(curr_vol / avg_vol_20, 2)

            # Aplicar filtros técnicos (solo si no es búsqueda específica)
            if not filters.get("specific_ticker"):
                # RSI con operador libre
                rsi_op = filters.get("rsi_operator")
                rsi_val = filters.get("rsi_value")
                if rsi_op and rsi_val is not None:
                    if rsi_op == "<=" and (rsi is None or rsi > rsi_val): continue
                    if rsi_op == ">=" and (rsi is None or rsi < rsi_val): continue

                macd_filter = filters.get("macd_signal")
                if macd_filter == "Alcista" and macd_signal != "Bullish": continue
                if macd_filter == "Bajista" and macd_signal != "Bearish": continue

                ema_filter = filters.get("ema_200")
                if ema_filter == "Sobre" and (ema_diff is None or ema_diff <= 0): continue
                if ema_filter == "Bajo" and (ema_diff is None or ema_diff >= 0): continue

                daily_filter = filters.get("daily_change")
                if daily_filter == "Positiva" and (daily_change is None or daily_change <= 0): continue
                if daily_filter == "Negativa" and (daily_change is None or daily_change >= 0): continue

                # Filtro de volumen relativo (RVOL)
                volume_range = filters.get("volume_range")
                if volume_range == "= 1" and (rvol is None or not (0.95 <= rvol <= 1.05)): continue
                if volume_range == "< 1" and (rvol is None or rvol >= 1.0): continue
                if volume_range == "< 1.5" and (rvol is None or rvol >= 1.5): continue
                if volume_range == "> 1.5" and (rvol is None or rvol <= 1.5): continue
                if volume_range == "> 1" and (rvol is None or rvol <= 1.0): continue

            results.append({
                "ticker": ticker, "current_price": current_price, "rsi": rsi,
                "macd_signal": macd_signal, "macd_value": round(macd_v, 4) if not pd.isna(macd_v) else 0,
                "ema_200_diff_pct": ema_diff, "daily_change_pct": daily_change,
                "rvol": rvol,
                "name": "", "sector": "", "industry": "", "market_cap": None,
                "avg_volume": None, "trailing_pe": None, "price_to_sales": None,
                "target_mean_price": None, "beta": None,
            })
        except Exception as exc:
            logger.debug("Skip %s: %s", ticker, exc)

    # Fetch fundamentals in parallel
    surviving_tickers = [r["ticker"] for r in results]
    if surviving_tickers:
        fund_data = _fetch_fundamentals_batch(surviving_tickers)
        for r in results:
            fd = fund_data.get(r["ticker"])
            if fd:
                for k in ("name", "sector", "industry", "market_cap", "avg_volume",
                          "trailing_pe", "price_to_sales", "target_mean_price", "beta"):
                    r[k] = fd.get(k)

    # Aplicar filtros fundamentales (post-fetch)
    filtered = results
    if not filters.get("specific_ticker"):
        pe_range = filters.get("pe_range")
        if pe_range == "< 15":
            filtered = [r for r in filtered if r["trailing_pe"] is not None and r["trailing_pe"] < 15]
        elif pe_range == "15-30":
            filtered = [r for r in filtered if r["trailing_pe"] is not None and 15 <= r["trailing_pe"] <= 30]
        elif pe_range == "> 30":
            filtered = [r for r in filtered if r["trailing_pe"] is not None and r["trailing_pe"] > 30]

        ps_range = filters.get("ps_range")
        if ps_range == "< 2":
            filtered = [r for r in filtered if r["price_to_sales"] is not None and r["price_to_sales"] < 2]
        elif ps_range == "2-5":
            filtered = [r for r in filtered if r["price_to_sales"] is not None and 2 <= r["price_to_sales"] <= 5]
        elif ps_range == "> 5":
            filtered = [r for r in filtered if r["price_to_sales"] is not None and r["price_to_sales"] > 5]

        mcap_range = filters.get("market_cap_range")
        if mcap_range == "> 200B":
            filtered = [r for r in filtered if r["market_cap"] is not None and r["market_cap"] > 200_000_000_000]
        elif mcap_range == "10B-200B":
            filtered = [r for r in filtered if r["market_cap"] is not None and 10_000_000_000 <= r["market_cap"] <= 200_000_000_000]
        elif mcap_range == "< 10B":
            filtered = [r for r in filtered if r["market_cap"] is not None and r["market_cap"] < 10_000_000_000]

        beta_range = filters.get("beta_range")
        if beta_range == "< 1":
            filtered = [r for r in filtered if r["beta"] is not None and r["beta"] < 1]
        elif beta_range == "> 1":
            filtered = [r for r in filtered if r["beta"] is not None and r["beta"] > 1]

        sector = filters.get("sector")
        if sector and sector not in ("Todos", "", None):
            filtered = [r for r in filtered if r.get("sector") == sector]

    result_sorted = sorted(filtered, key=lambda x: x["rsi"] if x["rsi"] is not None else 100)
    total = len(DEFAULT_UNIVERSE) if not filters.get("specific_ticker") else 1
    return {"count": len(result_sorted), "results": result_sorted, "total": total, "offset": offset}
