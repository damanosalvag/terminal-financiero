"""
Screener service — pipeline inteligente:
  · Sin filtros activos → paginación directa sobre universo, sin pre-procesamiento.
  · Con filtros fundamentales → prefiltrar por fundamentals antes de descargar OHLCV.
  · Con solo filtros técnicos → batch OHLCV → filtros → fundamentals de supervivientes.
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


def _has_fundamental_filters(f: dict) -> bool:
    return any(f.get(k) for k in ("pe_range", "ps_range", "market_cap_range", "beta_range", "sector"))


def _has_technical_filters(f: dict) -> bool:
    return any(f.get(k) for k in ("rsi_operator", "macd_signal", "ema_200", "daily_change", "volume_range"))


def _vectorized_rsi(close_df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = close_df.diff()
    gain, loss = delta.clip(lower=0), (-delta).clip(lower=0)
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
        rsi_df[col] = 100.0 - (100.0 / (1.0 + cg / cl.replace(0, np.nan)))
    return rsi_df.round(1)


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _fetch_fundamentals_batch(tickers: list[str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}

    def fetch_one(ticker: str):
        try:
            info = yf.Ticker(ticker).info
            return ticker, {
                "name": info.get("shortName") or info.get("longName", ""),
                "sector": info.get("sector") or "",
                "industry": info.get("industry") or "",
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


def _passes_fundamental_filters(fd: dict, f: dict) -> bool:
    """Evalúa si un diccionario de fundamentals pasa todos los filtros activos."""
    pe = fd.get("trailing_pe")
    ps = fd.get("price_to_sales")
    mc = fd.get("market_cap")
    beta = fd.get("beta")
    sector = fd.get("sector", "")

    pr = f.get("pe_range")
    if pr == "< 15" and (pe is None or pe >= 15): return False
    if pr == "15-30" and (pe is None or not (15 <= pe <= 30)): return False
    if pr == "> 30" and (pe is None or pe <= 30): return False

    psr = f.get("ps_range")
    if psr == "< 2" and (ps is None or ps >= 2): return False
    if psr == "2-5" and (ps is None or not (2 <= ps <= 5)): return False
    if psr == "> 5" and (ps is None or ps <= 5): return False

    mcr = f.get("market_cap_range")
    if mcr == "> 200B" and (mc is None or mc <= 200_000_000_000): return False
    if mcr == "10B-200B" and (mc is None or not (10_000_000_000 <= mc <= 200_000_000_000)): return False
    if mcr == "< 10B" and (mc is None or mc >= 10_000_000_000): return False

    br = f.get("beta_range")
    if br == "< 1" and (beta is None or beta >= 1): return False
    if br == "> 1" and (beta is None or beta <= 1): return False

    sec = f.get("sector")
    if sec and sec not in ("Todos", "", None) and sector != sec: return False

    return True


def _passes_technical_filters(
    rsi: float | None, macd_signal: str, ema_diff: float | None,
    daily_change: float | None, rvol: float | None, f: dict
) -> bool:
    rsi_op = f.get("rsi_operator")
    rsi_val = f.get("rsi_value")
    if rsi_op and rsi_val is not None:
        if rsi_op == "<=" and (rsi is None or rsi > rsi_val): return False
        if rsi_op == ">=" and (rsi is None or rsi < rsi_val): return False

    ms = f.get("macd_signal")
    if ms == "Alcista" and macd_signal != "Bullish": return False
    if ms == "Bajista" and macd_signal != "Bearish": return False

    ef = f.get("ema_200")
    if ef == "Sobre" and (ema_diff is None or ema_diff <= 0): return False
    if ef == "Bajo" and (ema_diff is None or ema_diff >= 0): return False

    dc = f.get("daily_change")
    if dc == "Positiva" and (daily_change is None or daily_change <= 0): return False
    if dc == "Negativa" and (daily_change is None or daily_change >= 0): return False

    vr = f.get("volume_range")
    if vr == "= 1" and (rvol is None or not (0.95 <= rvol <= 1.05)): return False
    if vr == "< 1" and (rvol is None or rvol >= 1.0): return False
    if vr == "< 1.5" and (rvol is None or rvol >= 1.5): return False
    if vr == "> 1.5" and (rvol is None or rvol <= 1.5): return False
    if vr == "> 1" and (rvol is None or rvol <= 1.0): return False

    return True


def _compute_technicals(close_df: pd.DataFrame, vol_df: pd.DataFrame | None) -> dict[str, dict]:
    """Calcula RSI, MACD, EMA200, daily change y RVOL para todas las columnas."""
    ema_200_df = close_df.apply(lambda col: _ema(col, 200))
    rsi_df = _vectorized_rsi(close_df, 14)
    macd_df = close_df.apply(lambda col: _ema(col, 12)) - close_df.apply(lambda col: _ema(col, 26))
    signal_df = macd_df.apply(lambda col: _ema(col.fillna(0), 9))
    last, prev = close_df.iloc[-1], close_df.iloc[-2]
    pct = ((last - prev) / prev.replace(0, float("nan"))) * 100

    out: dict[str, dict] = {}
    for ticker in close_df.columns:
        closes = close_df[ticker].dropna()
        if len(closes) < 50:
            continue
        price = round(float(closes.iloc[-1]), 2)
        rsi_v = rsi_df[ticker].dropna().iloc[-1] if ticker in rsi_df.columns else None
        rsi = round(float(rsi_v), 1) if rsi_v is not None and not pd.isna(rsi_v) else None
        mv = float(macd_df[ticker].iloc[-1]) if ticker in macd_df.columns else 0
        sv = float(signal_df[ticker].iloc[-1]) if ticker in signal_df.columns else 0
        macd_sig = "Bullish" if (not pd.isna(mv) and not pd.isna(sv) and mv > sv) else "Bearish"
        ev = ema_200_df[ticker].iloc[-1] if ticker in ema_200_df.columns else None
        ema_diff = round(((price - float(ev)) / float(ev)) * 100, 2) if ev is not None and not pd.isna(ev) and ev > 0 else None
        dp = pct.get(ticker)
        daily = round(float(dp), 2) if dp is not None and not pd.isna(dp) else None
        rvol = None
        if vol_df is not None and ticker in vol_df.columns:
            vs = vol_df[ticker].dropna()
            if len(vs) >= 21:
                avg20 = float(vs.iloc[-21:-1].mean())
                if avg20 > 0:
                    rvol = round(float(vs.iloc[-1]) / avg20, 2)
        out[ticker] = {
            "current_price": price, "rsi": rsi, "macd_signal": macd_sig,
            "macd_value": round(mv, 4), "ema_200_diff_pct": ema_diff,
            "daily_change_pct": daily, "rvol": rvol,
        }
    return out


def scan_market(filters: dict[str, Any], offset: int = 0, limit: int = 30) -> dict[str, Any]:
    """Pipeline inteligente: si no hay filtros, devuelve el chunk sin pre-procesamiento."""

    # ── Búsqueda directa por ticker ───────────────────────────────────────────
    specific = filters.get("specific_ticker")
    if specific and isinstance(specific, str) and specific.strip():
        ticker = specific.strip().upper()
        try:
            raw = yf.download(tickers=ticker, period=_LOOKBACK, progress=False, auto_adjust=True)
        except Exception:
            return {"count": 0, "results": [], "total": 1, "offset": 0}
        if raw.empty:
            return {"count": 0, "results": [], "total": 1, "offset": 0}

        # yfinance siempre devuelve MultiIndex ahora, incluso con 1 ticker
        if isinstance(raw.columns, pd.MultiIndex):
            if "Close" not in raw.columns.get_level_values(0):
                return {"count": 0, "results": [], "total": 1, "offset": 0}
            close_df = raw["Close"].copy()
            vol_df = raw["Volume"].copy() if "Volume" in raw.columns.get_level_values(0) else None
        else:
            # Fallback: columnas planas
            if "Close" not in raw.columns:
                return {"count": 0, "results": [], "total": 1, "offset": 0}
            close_df = raw[["Close"]].rename(columns={"Close": ticker})
            vol_df = raw[["Volume"]].rename(columns={"Volume": ticker}) if "Volume" in raw.columns else None

        if close_df.empty:
            return {"count": 0, "results": [], "total": 1, "offset": 0}
        tech = _compute_technicals(close_df, vol_df)
        if ticker not in tech:
            return {"count": 0, "results": [], "total": 1, "offset": 0}
        fund = _fetch_fundamentals_batch([ticker])
        fd = fund.get(ticker, {})
        t = tech[ticker]
        result = {**t, "ticker": ticker, "name": fd.get("name", ""), "sector": fd.get("sector", ""),
                  "industry": fd.get("industry", ""), "market_cap": fd.get("market_cap"),
                  "avg_volume": fd.get("avg_volume"), "trailing_pe": fd.get("trailing_pe"),
                  "price_to_sales": fd.get("price_to_sales"),
                  "target_mean_price": fd.get("target_mean_price"), "beta": fd.get("beta")}
        return {"count": 1, "results": [result], "total": 1, "offset": 0}

    # ── Chunk del universo ────────────────────────────────────────────────────
    chunk = DEFAULT_UNIVERSE[offset: offset + limit]
    if not chunk:
        return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}

    has_fund = _has_fundamental_filters(filters)
    has_tech = _has_technical_filters(filters)

    # Sin ningún filtro → devolver datos técnicos + fundamentals sin prefiltrar
    if not has_fund and not has_tech:
        try:
            raw = yf.download(tickers=" ".join(chunk), period=_LOOKBACK, progress=False, auto_adjust=True)
        except Exception:
            return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}
        if not isinstance(raw.columns, pd.MultiIndex) or raw.empty:
            return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}
        close_df = raw["Close"].copy()
        vol_df = raw["Volume"].copy() if "Volume" in raw.columns else None
        close_df.dropna(axis=1, thresh=50, inplace=True)
        tech = _compute_technicals(close_df, vol_df)
        fund = _fetch_fundamentals_batch(list(tech.keys()))
        results = []
        for t_ticker, t_data in tech.items():
            fd = fund.get(t_ticker, {})
            results.append({**t_data, "ticker": t_ticker, "name": fd.get("name", ""),
                             "sector": fd.get("sector", ""), "industry": fd.get("industry", ""),
                             "market_cap": fd.get("market_cap"), "avg_volume": fd.get("avg_volume"),
                             "trailing_pe": fd.get("trailing_pe"), "price_to_sales": fd.get("price_to_sales"),
                             "target_mean_price": fd.get("target_mean_price"), "beta": fd.get("beta")})
        results.sort(key=lambda x: x["rsi"] if x["rsi"] is not None else 100)
        return {"count": len(results), "results": results, "total": len(DEFAULT_UNIVERSE), "offset": offset}

    # ── Con filtros fundamentales → prefiltrar antes de descargar OHLCV ───────
    if has_fund:
        fund_all = _fetch_fundamentals_batch(chunk)
        pre_filtered = [t for t in chunk if t in fund_all and _passes_fundamental_filters(fund_all[t], filters)]
        if not pre_filtered:
            return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}
        try:
            raw = yf.download(tickers=" ".join(pre_filtered), period=_LOOKBACK, progress=False, auto_adjust=True)
        except Exception:
            return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}
        if raw.empty:
            return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}
        if isinstance(raw.columns, pd.MultiIndex):
            close_df = raw["Close"].copy()
            vol_df = raw["Volume"].copy() if "Volume" in raw.columns else None
        else:
            # Un solo ticker descargado
            t_name = pre_filtered[0]
            close_df = raw[["Close"]].rename(columns={"Close": t_name})
            vol_df = raw[["Volume"]].rename(columns={"Volume": t_name}) if "Volume" in raw.columns else None
        close_df.dropna(axis=1, thresh=50, inplace=True)
        tech = _compute_technicals(close_df, vol_df)
        results = []
        for t_ticker, t_data in tech.items():
            if has_tech and not _passes_technical_filters(
                t_data["rsi"], t_data["macd_signal"], t_data["ema_200_diff_pct"],
                t_data["daily_change_pct"], t_data["rvol"], filters
            ):
                continue
            fd = fund_all.get(t_ticker, {})
            results.append({**t_data, "ticker": t_ticker, "name": fd.get("name", ""),
                             "sector": fd.get("sector", ""), "industry": fd.get("industry", ""),
                             "market_cap": fd.get("market_cap"), "avg_volume": fd.get("avg_volume"),
                             "trailing_pe": fd.get("trailing_pe"), "price_to_sales": fd.get("price_to_sales"),
                             "target_mean_price": fd.get("target_mean_price"), "beta": fd.get("beta")})
        results.sort(key=lambda x: x["rsi"] if x["rsi"] is not None else 100)
        return {"count": len(results), "results": results, "total": len(DEFAULT_UNIVERSE), "offset": offset}

    # ── Solo filtros técnicos → batch OHLCV → filtros → fundamentals de supervivientes ──
    try:
        raw = yf.download(tickers=" ".join(chunk), period=_LOOKBACK, progress=False, auto_adjust=True)
    except Exception:
        return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}
    if not isinstance(raw.columns, pd.MultiIndex) or raw.empty:
        return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}
    close_df = raw["Close"].copy()
    vol_df = raw["Volume"].copy() if "Volume" in raw.columns else None
    close_df.dropna(axis=1, thresh=50, inplace=True)
    tech = _compute_technicals(close_df, vol_df)
    survivors = [t for t, d in tech.items() if _passes_technical_filters(
        d["rsi"], d["macd_signal"], d["ema_200_diff_pct"], d["daily_change_pct"], d["rvol"], filters)]
    if not survivors:
        return {"count": 0, "results": [], "total": len(DEFAULT_UNIVERSE), "offset": offset}
    fund = _fetch_fundamentals_batch(survivors)
    results = []
    for t_ticker in survivors:
        fd = fund.get(t_ticker, {})
        t_data = tech[t_ticker]
        results.append({**t_data, "ticker": t_ticker, "name": fd.get("name", ""),
                         "sector": fd.get("sector", ""), "industry": fd.get("industry", ""),
                         "market_cap": fd.get("market_cap"), "avg_volume": fd.get("avg_volume"),
                         "trailing_pe": fd.get("trailing_pe"), "price_to_sales": fd.get("price_to_sales"),
                         "target_mean_price": fd.get("target_mean_price"), "beta": fd.get("beta")})
    results.sort(key=lambda x: x["rsi"] if x["rsi"] is not None else 100)
    return {"count": len(results), "results": results, "total": len(DEFAULT_UNIVERSE), "offset": offset}
